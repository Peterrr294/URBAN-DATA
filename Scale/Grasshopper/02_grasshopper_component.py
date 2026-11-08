"""Rhino 8 Grasshopper Python 3 Script-Mode.
Inputs: x (JSON path, text), y (metric, text, optional).
Optional inputs: Cols (int), CardWidth (float), CardHeight (float), Gap (float).
Outputs: Base, Sites, Cards, Links, LabelPoints, Labels, Theme, Colors, TrafficLabels, Info.
Geometry coordinates use the exported local origin and retain feet.
"""
import json
import math
import os
import Rhino.Geometry as rg
from System.Drawing import Color

Base, Sites, Cards, Links = [], [], [], []
LabelPoints, Labels, Theme, Colors, TrafficLabels = [], [], [], [], []
Info = ""

def point(xy, z=0):
    return rg.Point3d(float(xy[0]), float(xy[1]), z)

def ring_curves(rings, z=0):
    return [rg.PolylineCurve([point(xy, z) for xy in ring])
            for ring in rings if len(ring) >= 4]

def value_text(value, decimals=0, suffix=""):
    return "n/a" if value is None else f"{value:.{decimals}f}{suffix}"

def theme_color(value, lo, hi):
    if value is None:
        return Color.FromArgb(170, 178, 180)
    t = .5 if hi == lo else max(0., min(1., (value - lo) / (hi - lo)))
    return Color.FromArgb(round(44 + 199*t), round(108 - 44*t), round(163 - 110*t))

def positive(value, default, label):
    result = float(default if value is None else value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(label + " must be positive.")
    return result

if not x:
    Info = "Connect a Panel containing the full path to gh_plot_atlas.json."
else:
    data_path = os.path.expanduser(str(x).strip().strip('"'))
    with open(data_path, encoding="utf-8-sig") as stream:
        atlas = json.load(stream)
    if atlas.get("schema") != 1:
        raise ValueError("Unsupported atlas format.")
    metric = str(y or "").strip().lower()
    allowed = {"building", "food", "crashes", "pedestrian", "age", "asthma", "traffic"}
    if metric and metric not in allowed:
        raise ValueError("Unknown metric. Use " + ", ".join(sorted(allowed)))

    boundary_xy = [xy for ring in atlas["boundary"] for xy in ring]
    xmin = min(xy[0] for xy in boundary_xy)
    xmax = max(xy[0] for xy in boundary_xy)
    ymax = max(xy[1] for xy in boundary_xy)
    width = xmax - xmin
    plots = atlas["plots"]
    candidates = sorted(
        (p for p in plots if p["item_id"]),
        key=lambda p: int(p["item_id"][1:])
    )
    if not candidates:
        raise ValueError("No candidate plots in JSON.")
    Base = ring_curves(atlas["boundary"])
    for plot in plots:
        Base.extend(ring_curves(plot["rings"]))

    # A single scale is shared across all card outlines.
    cols = int(positive(globals().get("Cols"), min(5, math.ceil(math.sqrt(len(candidates)))), "Cols"))
    if cols < 1:
        raise ValueError("Cols must be at least one.")
    cell_width = positive(globals().get("CardWidth"), width / cols, "CardWidth")
    cell_height = positive(globals().get("CardHeight"), cell_width * .6, "CardHeight")
    gap = positive(globals().get("Gap"), cell_height * .6, "Gap")
    reach = max(
        max(abs(v[0] - p["anchor"][0]), abs(v[1] - p["anchor"][1]))
        for p in candidates for ring in p["rings"] for v in ring
    )
    scale = min(cell_width * .37, cell_height * .22) / max(reach, 1e-9)
    for i, plot in enumerate(candidates):
        column, row = i % cols, i // cols
        ax, ay = plot["anchor"]
        cx = xmin + (column + .5) * cell_width
        cy = ymax + gap + (row + .6) * cell_height
        Sites.extend(ring_curves(plot["rings"], z=1))
        for ring in plot["rings"]:
            shifted = [(cx + (v[0]-ax)*scale, cy + (v[1]-ay)*scale) for v in ring]
            Cards.extend(ring_curves([shifted], z=2))
        Links.append(rg.LineCurve(point((ax, ay), 1), point((cx, cy), 2)))
        LabelPoints.append(point((cx - cell_width*.32, cy - cell_height*.26), 2))
        v = plot["values"]
        Labels.append(
            f"{plot['item_id']} | {plot['type']} | {plot['plot_id']}\n"
            f"Building {value_text(v['building'], 1, '%')}  |  Food {value_text(v['food'])}\n"
            f"Crashes {value_text(v['crashes'])}  |  Ped. {value_text(v['pedestrian'])}\n"
            f"Age 65+ {value_text(v['age'], 1, '%')}  |  Asthma {value_text(v['asthma'], 1, '%')}"
        )

    if metric in {"age", "asthma"}:
        features = atlas["tracts"][metric]
    elif metric == "traffic":
        features = atlas["traffic"]
    elif metric:
        features = [{"rings": p["rings"], "value": p["values"][metric]} for p in plots]
    else:
        features = []
    values = [f["value"] for f in features if f["value"] is not None]
    lo, hi = (min(values), max(values)) if values else (0, 1)
    for feature in features:
        if metric == "traffic":
            radius = width * (.004 + .008 * (feature["value"]-lo) / (hi-lo if hi>lo else 1))
            geometries = [rg.Circle(point(feature["point"], 1), radius).ToNurbsCurve()]
            TrafficLabels.append(
                f"{feature['street']} {feature['direction']}: {feature['value']:.1f} veh/h ({feature['dates']} dates)"
            )
        else:
            geometries = ring_curves(feature["rings"], z=1)
        Theme.extend(geometries)
        Colors.extend([theme_color(feature["value"], lo, hi)] * len(geometries))
    Info = (f"{len(plots):,} mapped plots | {len(candidates)} cards | units: {atlas['units']}\n"
            f"Metric: {metric or 'off'} | observed range: "
            f"{value_text(min(values), 2) if values else 'n/a'} to "
            f"{value_text(max(values), 2) if values else 'n/a'}\n"
            f"Shared card scale: {scale:.3f} | Grid: {cols} columns")
