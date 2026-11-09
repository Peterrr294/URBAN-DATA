"""Rhino 8 Grasshopper Python 3 Script Mode.

Keep x connected to the existing JSON path or export folder.
Optional outputs: Plots, Selected, Boxes, LabelPoints, Labels, BlockIDs,
PlotTree. a is the complete row layout. y is unused.
"""
import csv
import json
import os
from collections import defaultdict
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path
from System import Object
import Rhino.FileIO as rio
import Rhino.Geometry as rg

BOX = 1500.0
MARGIN = 150.0
STEP_X = 1800.0
STEP_Y = 1950.0
MAX_PER_ROW = 100

# Legacy named outputs are initialized for existing definitions.
a, Base, Sites, Blocks, Cards, Links, Theme, Colors, TrafficLabels = (
    [], [], [], [], [], [], [], [], []
)
Plots, Others, Selected, Boxes, LabelPoints, Labels, BlockIDs, BBL, Area = (
    [], [], [], [], [], [], [], [], []
)
SelectedPts = LabelPoints
PlotTree = DataTree[Object]()
Info = ""


def ring_curve(ring):
    return rg.PolylineCurve([rg.Point3d(float(p[0]), float(p[1]), 0) for p in ring])


def read_inputs(path):
    names = [
        ("block_plot_source.3dm", "block_plot_index.csv"),
        ("source_plots.3dm", "plots_for_grasshopper.csv"),
    ]
    if os.path.isdir(path):
        choices = [os.path.join(path, model) for model, index in names
                   if os.path.isfile(os.path.join(path, model))
                   and os.path.isfile(os.path.join(path, index))]
        json_path = os.path.join(path, "gh_plot_atlas.json")
        if os.path.isfile(json_path):
            choices.append(json_path)
        if len(choices) != 1:
            raise ValueError("Point x to the specific JSON or 3DM if the folder has multiple exports.")
        path = choices[0]

    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8-sig") as stream:
            atlas = json.load(stream)
        if atlas.get("schema") != 1:
            raise ValueError("Unsupported plot JSON schema.")
        return [
            (str(plot["plot_id"]), str(plot["plot_id"])[:6], plot.get("item_id") or "",
             [ring_curve(ring) for ring in plot["rings"] if len(ring) >= 4], None)
            for plot in atlas["plots"]
        ]

    folder, filename = os.path.split(path)
    pair = next((pair for pair in names if filename.lower() in pair), None)
    if pair is None:
        raise ValueError("Use the previously exported gh_plot_atlas.json or a Block/All Plots export.")
    with open(os.path.join(folder, pair[1]), encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter=";"))
    by_bbl = {row["BBL"]: row for row in rows}
    if not by_bbl or len(by_bbl) != len(rows):
        raise ValueError("Plot index is empty or contains duplicate BBLs.")
    model = rio.File3dm.Read(os.path.join(folder, pair[0]))
    if model is None:
        raise IOError("Cannot read " + pair[0])
    curves = defaultdict(list)
    for obj in model.Objects:
        key = obj.Attributes.Name
        if key in by_bbl and isinstance(obj.Geometry, rg.Curve):
            # Duplicate before the File3dm is released.
            curves[key].append(obj.Geometry.DuplicateCurve())
    if set(curves) != set(by_bbl):
        raise ValueError("The 3DM and CSV have different plot IDs. Use one matching export.")
    return [
        (key, row.get("block_id") or key[:6],
         (row.get("item_id") or key) if row["selected"] == "1" else "",
         curves[key], float(row["area_sqft"]))
        for key, row in by_bbl.items()
    ]


if x:
    path = os.path.expanduser(str(x).strip().strip('"'))
    records = read_inputs(path)
    if not records:
        raise ValueError("No plots found.")
    if len({r[0] for r in records}) != len(records):
        raise ValueError("Plot IDs must be unique.")

    grouped = defaultdict(list)
    for bbl, block, label, curves, area in records:
        if not curves:
            raise ValueError("Missing plot outline: " + bbl)
        bounds = curves[0].GetBoundingBox(True)
        for curve in curves[1:]:
            bounds.Union(curve.GetBoundingBox(True))
        span = max(bounds.Max.X - bounds.Min.X, bounds.Max.Y - bounds.Min.Y)
        if span <= 0:
            raise ValueError("Invalid outline size: " + bbl)
        grouped[block].append((bbl, label, curves, area, bounds.Center, span))

    BlockIDs = sorted(grouped)
    row_index = 0
    for block_index, block in enumerate(BlockIDs):
        # Left-aligned rows, longest original outlines first within each block.
        lots = sorted(grouped[block], key=lambda lot: (-lot[5], lot[0]))
        for i, (bbl, label, curves, area, center, span) in enumerate(lots):
            wrap, col = divmod(i, MAX_PER_ROW)
            cx, cy = col * STEP_X, -(row_index + wrap) * STEP_Y
            scaling = rg.Transform.Scale(center, (BOX - 2 * MARGIN) / span)
            move = rg.Transform.Translation(cx - center.X, cy - center.Y, -center.Z)
            destination = Selected if label else Others
            for original in curves:
                curve = original.DuplicateCurve()
                curve.Transform(scaling)
                curve.Transform(move)
                destination.append(curve)
                PlotTree.Add(curve, GH_Path(block_index))
            if label:
                h = BOX / 2
                box = [(cx-h, cy-h), (cx+h, cy-h), (cx+h, cy+h),
                       (cx-h, cy+h), (cx-h, cy-h)]
                Boxes.append(ring_curve(box))
                LabelPoints.append(rg.Point3d(cx - h, cy - h - 60, 0))
                Labels.append(f"{label} | {bbl}")
            BBL.append(bbl)
            Area.append(area)
        row_index += (len(lots) + MAX_PER_ROW - 1) // MAX_PER_ROW

    Plots = Others
    Cards = Others + Selected
    a = Cards + Boxes
    Info = f"{len(BBL):,} plots | {len(BlockIDs):,} blocks | {row_index:,} rows | {len(Labels)} selected"
else:
    Info = "Connect the original plot export path to x."
print(Info)
