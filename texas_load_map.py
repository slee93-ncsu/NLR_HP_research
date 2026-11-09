"""
Draw the county end-use map from the OCHRE load breakdown, in a notebook.

Put this file and tx_counties.geojson next to your breakdown CSVs, then in a
notebook cell:

    from texas_load_map import Breakdown
    bd = Breakdown("county_load_breakdown*.csv")   # a glob, or a list of paths
    bd.map("Space cooling")                        # share of county energy
    bd.map("Space heating", metric="per")          # kWh per modeled building
    bd.map("Water heating", zone="3A", period="winter")
    bd.table()                                     # the zone summary table
    bd.county("Harris")                            # one county's breakdown

With ipywidgets installed, `bd.explore()` gives dropdowns instead.

Nothing leaves the machine: it reads the CSVs and the local GeoJSON and draws
with matplotlib.
"""

import glob as _glob
import json
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize

HERE = os.path.dirname(os.path.abspath(__file__))
GEOJSON = os.path.join(HERE, "tx_counties.geojson")

# the six reporting groups; every end use not named here falls into Other
GROUPS = {
    "Space cooling":     ["HVAC Cooling"],
    "Space heating":     ["HVAC Heating"],
    "Water heating":     ["Water Heating"],
    "Laundry & dishwasher":    ["Clothes Washer", "Clothes Dryer", "Dishwasher"],
    "Plug loads (MELs)": ["MELs"],
}
GROUP_ORDER = ["Space cooling", "Space heating", "Water heating",
               "Laundry & dishwasher", "Plug loads (MELs)", "Other"]

PERIOD_LABEL = {"annual": "Annual", "summer": "Summer (Jun–Sep)",
                "winter": "Winter (Dec–Feb)", "uri": "Uri (Feb 14–18)"}

# blue → teal → green → gold → rust, readable on a light background
RAMP = LinearSegmentedColormap.from_list(
    "load", ["#2f5d7c", "#3d918d", "#67a95b", "#c8a128", "#bd5029"])

# counties with no rows, and why (from the ResStock metadata for TX upgrade 0)
NO_RESULT = {
    "Loving":    "no models sampled",
    "Glasscock": "2 models, both vacant",
}


class Breakdown:
    def __init__(self, csvs, geojson=GEOJSON):
        if isinstance(csvs, str):
            paths = sorted(_glob.glob(csvs))
        else:
            paths = list(csvs)
        if not paths:
            raise FileNotFoundError(f"no CSV matched {csvs}")
        df = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
        df["county"] = df["county"].str.replace("_", " ", regex=False)
        df["group"] = df["end_use"].map(
            {u: g for g, us in GROUPS.items() for u in us}).fillna("Other")
        self.raw = df
        self.paths = paths

        # county × period × group energy, plus the county total
        g = (df.groupby(["zone", "county", "n_buildings", "period", "group"],
                        as_index=False)["energy_kWh"].sum())
        tot = (g.groupby(["zone", "county", "period"], as_index=False)["energy_kWh"]
                 .sum().rename(columns={"energy_kWh": "total_kWh"}))
        g = g.merge(tot, on=["zone", "county", "period"])
        g["share"] = g["energy_kWh"] / g["total_kWh"]
        g["per_building"] = g["energy_kWh"] / g["n_buildings"]
        self.groups = g

        self.shapes = self._load_shapes(geojson)
        self.zones = sorted(df["zone"].unique())
        self.end_uses = sorted(df["end_use"].unique())
        self.periods = [p for p in PERIOD_LABEL if p in set(df["period"])]
        n = df.drop_duplicates(["zone", "county"])["n_buildings"].sum()
        print(f"{df['county'].nunique()} counties, {n:,} models, "
              f"zones {', '.join(self.zones)}")

    # ---------- geometry ----------
    @staticmethod
    def _load_shapes(path):
        gj = json.load(open(path))
        lat0 = 31.0
        k = np.cos(np.radians(lat0))
        out = {}
        for f in gj["features"]:
            geom = f["geometry"]
            polys = ([geom["coordinates"]] if geom["type"] == "Polygon"
                     else geom["coordinates"])
            rings = []
            for p in polys:
                for ring in p:
                    a = np.asarray(ring, dtype=float)
                    rings.append(np.column_stack([a[:, 0] * k, a[:, 1]]))
            out[f["properties"]["name"]] = rings
        return out

    # ---------- values ----------
    def _slice(self, key, period, zone):
        g = self.groups
        g = g[g["period"] == period]
        if zone and zone != "all":
            g = g[g["zone"] == zone]
        if key in GROUP_ORDER:
            g = g[g["group"] == key]
            v = g.set_index("county")
        elif key == "Total":
            v = (g.groupby("county")
                   .agg(energy_kWh=("total_kWh", "first"),
                        n_buildings=("n_buildings", "first"),
                        total_kWh=("total_kWh", "first"),
                        zone=("zone", "first")))
            v["share"] = 1.0
            v["per_building"] = v["energy_kWh"] / v["n_buildings"]
        else:                                   # a single end use
            d = self.raw
            d = d[(d["period"] == period) & (d["end_use"] == key)]
            if zone and zone != "all":
                d = d[d["zone"] == zone]
            v = d.set_index("county")
            v = v.assign(share=v["energy_share"],
                         per_building=v["energy_kWh"] / v["n_buildings"])
        return v

    # ---------- the map ----------
    def map(self, key="Space cooling", period="annual", zone="all",
            metric="share", ax=None, min_models=0, save=None, dpi=140):
        """metric: 'share' of county energy, or 'per' for kWh per model."""
        v = self._slice(key, period, zone)
        if min_models:
            v = v[v["n_buildings"] >= min_models]
        col = "share" if metric == "share" else "per_building"
        vals = v[col].dropna()
        if vals.empty:
            raise ValueError(f"nothing to draw for {key} / {period} / {zone}")
        norm = Normalize(0, float(vals.max()))

        if ax is None:
            fig, ax = plt.subplots(figsize=(9.5, 9.0), dpi=dpi)
        else:
            fig = ax.figure

        faces, colors, edges = [], [], []
        for name, rings in self.shapes.items():
            for r in rings:
                faces.append(r)
                if name in vals.index:
                    colors.append(RAMP(norm(float(vals[name]))))
                    edges.append("#ffffff")
                elif name in NO_RESULT:
                    colors.append("#cfd6de")
                    edges.append("#9aa6b4")
                else:
                    colors.append("#e6eaef")
                    edges.append("#d3dae3")
        ax.add_collection(PolyCollection(faces, facecolors=colors,
                                         edgecolors=edges, linewidths=.45))
        ax.autoscale_view()
        ax.set_aspect(1.0)
        ax.axis("off")

        unit = "share of county energy" if metric == "share" else "kWh per model"
        ax.set_title(f"{key} — {PERIOD_LABEL.get(period, period)}"
                     + ("" if zone in (None, "all") else f", zone {zone}"),
                     fontsize=13, loc="left", pad=26)
        ax.text(0, 1.004, f"grey: no results ({', '.join(NO_RESULT)})",
                transform=ax.transAxes, ha="left", va="bottom",
                fontsize=8, color="#5d6b7a")
        sm = plt.cm.ScalarMappable(cmap=RAMP, norm=norm)
        cb = fig.colorbar(sm, ax=ax, fraction=.032, pad=.01, orientation="horizontal")
        cb.set_label(unit, fontsize=9)
        if metric == "share":
            cb.ax.xaxis.set_major_formatter(lambda x, p: f"{x*100:.0f}%")
        cb.ax.tick_params(labelsize=8)
        fig.tight_layout()
        if save:
            fig.savefig(save, dpi=dpi, bbox_inches="tight", facecolor="white")
            print("saved", save)
        return ax

    # ---------- tables ----------
    def table(self, period="annual", metric="share"):
        """Group shares (or kWh per model) by climate zone, plus ALL."""
        g = self.groups[self.groups["period"] == period]
        rows = []
        for z in ["ALL"] + self.zones:
            s = g if z == "ALL" else g[g["zone"] == z]
            nb = s.drop_duplicates(["zone", "county"])["n_buildings"].sum()
            e = s.groupby("group")["energy_kWh"].sum()
            tot = e.sum()
            r = {"zone": z, "models": int(nb)}
            for k in GROUP_ORDER:
                r[k] = (e.get(k, 0) / tot if metric == "share"
                        else e.get(k, 0) / nb)
            rows.append(r)
        out = pd.DataFrame(rows).set_index("zone")
        if metric == "share":
            return out.style.format({k: "{:.1%}" for k in GROUP_ORDER}) \
                            .format({"models": "{:,}"})
        return out.style.format({k: "{:,.0f}" for k in GROUP_ORDER}) \
                        .format({"models": "{:,}"})

    def county(self, name, period="annual"):
        """One county: group shares and the end uses inside each group."""
        name = name.replace("_", " ")
        d = self.raw[(self.raw["county"] == name) & (self.raw["period"] == period)]
        if d.empty:
            raise ValueError(f"no rows for {name} / {period}")
        nb = int(d["n_buildings"].iloc[0])
        tot = d["energy_kWh"].sum()
        print(f"{name} County — zone {d['zone'].iloc[0]}, {nb:,} models, "
              f"{tot:,.0f} kWh ({tot/nb:,.0f} per model)")
        out = (d.groupby(["group", "end_use"])["energy_kWh"].sum()
                 .reset_index())
        out["share"] = out["energy_kWh"] / tot
        out["kWh/model"] = out["energy_kWh"] / nb
        out = out.sort_values(["group", "energy_kWh"], ascending=[True, False])
        return out[["group", "end_use", "share", "kWh/model"]] \
            .style.format({"share": "{:.2%}", "kWh/model": "{:,.0f}"}).hide(axis="index")

    # ---------- widgets ----------
    def explore(self):
        """Dropdowns, if ipywidgets is installed."""
        try:
            from ipywidgets import interact, Dropdown
        except ImportError:
            print("ipywidgets is not installed — use bd.map(...) directly, or\n"
                  "    pip install ipywidgets")
            return
        keys = ["Total"] + GROUP_ORDER + ["— single end uses —"] + self.end_uses
        def show(key, period, zone, metric):
            if key.startswith("—"):
                return
            self.map(key, period=period, zone=zone, metric=metric)
            plt.show()
        return interact(show,
                        key=Dropdown(options=keys, value="Space cooling"),
                        period=Dropdown(options=self.periods, value="annual"),
                        zone=Dropdown(options=["all"] + self.zones, value="all"),
                        metric=Dropdown(options=[("share of energy", "share"),
                                                 ("kWh per model", "per")],
                                        value="share"))
