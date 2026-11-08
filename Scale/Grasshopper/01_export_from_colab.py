# 在现有 Colab 的末尾新增代码格并运行。
from pathlib import Path
from datetime import datetime
import json
import math
import shutil
import geopandas as gpd
import pandas as pd
from google.colab import drive
from IPython.display import display

if not Path("/content/drive/MyDrive").exists():
    drive.mount("/content/drive")

ROOT = Path("/content/drive/MyDrive/ARCH6131_Scale")
RAW, OUT = ROOT / "data/raw", ROOT / "outputs"
CRS = 2263  # NAD83 / New York Long Island (US survey feet)

def read_layer(path):
    layer = gpd.read_file(path)
    if layer.crs is None:
        raise ValueError(f"缺少坐标系：{path.name}")
    return layer.to_crs(CRS)

plots = read_layer(OUT / "all_enriched_plots.geojson")
boundary = read_layer(RAW / "boundary.geojson").geometry.union_all()
if plots.plot_id.isna().any() or plots.plot_id.astype(str).duplicated().any():
    raise ValueError("plot_id 必须非空且唯一")
plots["plot_id"] = plots.plot_id.astype(str)
fields = {
    "building": "building_coverage_pct",
    "food": "food_store_count_buffer",
    "crashes": "crash_count_buffer",
    "pedestrian": "ped_casualty_crash_count_buffer",
    "age": "age65_pct",
    "asthma": "adult_asthma_pct",
}
for field in fields.values():
    plots[field] = pd.to_numeric(plots[field], errors="coerce")

# 复现分步图纸的五层规则，阈值始终从完整的分析数据计算。
age_by_tract = plots[["age65_pct_GEOID", "age65_pct"]].dropna().drop_duplicates()
if not age_by_tract.age65_pct_GEOID.is_unique:
    raise ValueError("同一统计区存在不同的年龄比例")
thresholds = {
    "building": float(plots[fields["building"]].quantile(.25)),
    "age": float(age_by_tract.age65_pct.median()),
    "food": float(plots[fields["food"]].median()),
    "pedestrian": float(plots[fields["pedestrian"]].median()),
}
if not all(math.isfinite(value) for value in thresholds.values()):
    raise ValueError("筛选字段缺少有效数据")
vacant = pd.to_numeric(plots.LandUse, errors="coerce").eq(11)
parking = plots.BldgClass.astype("string").str.strip().str.upper().isin(["G6", "G7", "Z2", "RP"])
active = (
    plots[fields["building"]].le(thresholds["building"])
    & plots[fields["age"]].ge(thresholds["age"])
    & plots[fields["food"]].le(thresholds["food"])
    & plots[fields["pedestrian"]].ge(thresholds["pedestrian"])
    & (vacant | parking)
)
plots["space_type"] = ""
plots.loc[vacant, "space_type"] = "Vacant land"
plots.loc[parking & ~vacant, "space_type"] = "Surface parking"

# 裁切展示几何。分析值仍对应原始地块。
mapped = gpd.clip(plots, boundary, keep_geom_type=True)
mapped = mapped.loc[mapped.geom_type.isin(["Polygon", "MultiPolygon"]) & mapped.area.gt(0)].copy()
if mapped.empty:
    raise ValueError("研究边界内没有可导出的地块")
selected_ids = plots.loc[active.fillna(False), "plot_id"].sort_values()
item_ids = {plot_id: f"P{i:02d}" for i, plot_id in enumerate(selected_ids, 1)}
candidates = mapped.loc[mapped.plot_id.isin(item_ids)].sort_values("plot_id").copy()
if candidates.empty:
    raise ValueError("研究边界内没有通过五层筛选的候选地块")
candidates["item_id"] = candidates.plot_id.map(item_ids)

# 平移到 Rhino 局部原点，地块尺寸仍为英尺。
origin_x, origin_y, _, _ = boundary.bounds
def xy(x, y):
    return [round(x - origin_x, 4), round(y - origin_y, 4)]

def polygon_rings(geometry):
    if geometry.geom_type == "Polygon":
        return [[xy(p[0], p[1]) for p in ring.coords]
                for ring in [geometry.exterior, *geometry.interiors]]
    if geometry.geom_type in {"MultiPolygon", "GeometryCollection"}:
        return [ring for part in geometry.geoms for ring in polygon_rings(part)]
    return []

def number(value):
    return float(value) if pd.notna(value) and math.isfinite(float(value)) else None

records = []
for _, row in mapped.iterrows():
    anchor = row.geometry.representative_point()
    records.append({
        "plot_id": row.plot_id,
        "item_id": item_ids.get(row.plot_id),
        "type": row.space_type,
        "anchor": xy(anchor.x, anchor.y),
        "rings": polygon_rings(row.geometry),
        "values": {name: number(row[field]) for name, field in fields.items()},
    })

# 年龄、健康专题使用统计区轮廓。卡片仍显示各候选地块关联的统计区数值。
tracts = {}
for name, filename in [("age", "age_tracts.geojson"), ("asthma", "health_tracts.geojson")]:
    layer = gpd.clip(read_layer(RAW / filename), boundary, keep_geom_type=True)
    values = pd.to_numeric(layer[fields[name]], errors="coerce")
    tracts[name] = [
        {"rings": polygon_rings(shape), "value": number(value)}
        for shape, value in zip(layer.geometry, values)
    ]

traffic = []
traffic_path = OUT / "traffic_2024_sites_provisional.geojson"
if traffic_path.exists():
    for _, row in read_layer(traffic_path).iterrows():
        if row.geometry is None or row.geometry.is_empty or row.geometry.geom_type != "Point":
            continue
        volume = pd.to_numeric(row.get("weekday_08_09_mean_vehicles"), errors="coerce")
        volume = number(volume)
        if volume is not None:
            traffic.append({
                "point": xy(row.geometry.x, row.geometry.y),
                "value": volume,
                "street": str(row.get("street", "")),
                "direction": str(row.get("direction", "")),
                "dates": str(row.get("observed_dates", "")),
            })

stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
folder = OUT / ("Grasshopper_Export_" + stamp)
folder.mkdir(parents=True)
payload = {
    "schema": 1,
    "crs": "EPSG:2263",
    "units": "US survey feet",
    "origin_xy": [origin_x, origin_y],
    "thresholds": thresholds,
    "boundary": polygon_rings(boundary),
    "plots": records,
    "tracts": tracts,
    "traffic": traffic,
}
data_path = folder / "gh_plot_atlas.json"
data_path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")
columns = ["item_id", "plot_id", "space_type", *fields.values()]
candidates[columns].to_csv(folder / "candidate_items.csv", index=False)
zip_path = shutil.make_archive(str(folder), "zip", root_dir=folder)

print("输入地块", len(plots), "｜裁切后可绘制", len(mapped), "｜卡片", len(candidates))
print("下载 Drive 中的 ZIP 并解压", zip_path)
display(candidates[columns].head(20))
