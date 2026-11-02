# Texas residential load breakdown

텍사스 251개 카운티의 OCHRE 주거 부하를 용도별로 분해한 인터랙티브 지도와 집계 결과 (ResStock 2025, AMY 2021 기상)

**인터랙티브 지도:** https://slee93-ncsu.github.io/NLR_HP_research/

## 파일

| 파일 | 설명 |
|---|---|
| `index.html` | 인터랙티브 지도 (GitHub Pages로 게시되는 페이지) |
| `Texas_load_breakdown.html` | `index.html`의 원본 (내용 동일) |
| `texas_load_map.ipynb` | 같은 지도를 로컬에서 그리는 주피터 노트북 |
| `texas_load_map.py` | 노트북이 사용하는 지도·표 코드 |
| `tx_counties.geojson` | 텍사스 카운티 경계 (254개, 단순화) |
| `county_load_breakdown_*.csv` | 카운티 × 기간 × 용도별 집계 결과 데이터 |

## 노트북 실행법

```bash
pip install pandas matplotlib notebook
```

```bash
jupyter notebook
```

브라우저에서 `texas_load_map.ipynb`를 열고 위에서부터 실행합니다.
드롭다운(`bd.explore()`)을 쓰려면 `ipywidgets`도 필요합니다 — `pip install -r requirements.txt`로 한 번에 설치할 수 있습니다.
