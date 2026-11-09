"""Rhino 8 Grasshopper Python 3 Script-Mode.
Inputs: x (JSON path, text), y (metric, text, optional).
Optional inputs: Cols (int), CardWidth (float), CardHeight (float), Gap (float).
Outputs: Base, Sites, Cards, Boxes, Links, LabelPoints, Labels, Theme, Colors, TrafficLabels, Info.
Geometry coordinates use the exported local origin and retain feet.
"""
import json
import math
import os
import Rhino.Geometry as rg
from System.Drawing import Color

Base, Sites, Cards, Boxes, Links = [], [], [], [], []
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

    # Fit each card to a 1500 x 1500 square with a 150-ft margin on every side.
    box_size = 1500.0
    half_box = box_size / 2
    fit_span = box_size - 2 * 150.0
    cols = int(positive(globals().get("Cols"), min(5, math.ceil(math.sqrt(len(candidates)))), "Cols"))
    if cols < 1:
        raise ValueError("Cols must be at least one.")
    cell_width = max(box_size + 150.0, positive(globals().get("CardWidth"), width / cols, "CardWidth"))
    cell_height = max(box_size + 450.0, positive(globals().get("CardHeight"), cell_width * .6, "CardHeight"))
    gap = positive(globals().get("Gap"), cell_height * .6, "Gap")
    for i, plot in enumerate(candidates):
        column, row = i % cols, i // cols
        ax, ay = plot["anchor"]
        cx = xmin + (column + .5) * cell_width
        cy = ymax + gap + half_box + row * cell_height
        rings = [ring for ring in plot["rings"] if len(ring) >= 4]
        vertices = [v for ring in rings for v in ring]
        if not vertices:
            raise ValueError(f"{plot['item_id']} has no drawable outline.")
        px0 = min(v[0] for v in vertices)
        px1 = max(v[0] for v in vertices)
        py0 = min(v[1] for v in vertices)
        py1 = max(v[1] for v in vertices)
        span = max(px1 - px0, py1 - py0)
        if not math.isfinite(span) or span <= 0:
            raise ValueError(f"{plot['item_id']} has an invalid outline size.")
        mx, my = (px0 + px1) / 2, (py0 + py1) / 2
        card_scale = fit_span / span

        def card_xy(v):
            return cx + (v[0] - mx) * card_scale, cy + (v[1] - my) * card_scale

        Sites.extend(ring_curves(rings, z=1))
        Cards.extend(ring_curves([[card_xy(v) for v in ring] for ring in rings], z=2))
        left, right = cx - half_box, cx + half_box
        bottom, top = cy - half_box, cy + half_box
        Boxes.extend(ring_curves([[(left, bottom), (right, bottom), (right, top),
                                  (left, top), (left, bottom)]], z=2))
        Links.append(rg.LineCurve(point((ax, ay), 1), point(card_xy((ax, ay)), 2)))
        LabelPoints.append(point((left, bottom - 60.0), 2))
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
            f"Box: {box_size:g} x {box_size:g} ft | Card span: {fit_span:g} ft | Grid: {cols} columns")

# Default Script component outputs for a quick preview.
a = Base + Sites + Cards + Boxes + Links
print(Info)
