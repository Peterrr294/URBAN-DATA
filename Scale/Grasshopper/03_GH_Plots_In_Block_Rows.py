"""Rhino 8 Grasshopper Python 3 Script Mode.

Keep x connected to the existing JSON path or export folder.
Optional outputs: Base, MapBlockBoundaries, MapPlots, BlockCards, BlockLabelPoints, BlockLabels,
Plots, Selected, Boxes, LabelPoints, Labels, MapLinks, RowLinks, BlockIDs,
PlotTree. a previews the exploded plots of blocks containing selected plots.
Base and MapLinks can be previewed separately for site context. y is unused.
"""
import csv
import json
import os
from collections import defaultdict
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path
from System import Object
from System.Collections.Generic import List
import Rhino.FileIO as rio
import Rhino.Geometry as rg

BOX = 1500.0
MARGIN = 150.0
STEP_X = 1800.0
STEP_Y = 2250.0
MAX_PER_ROW = 12
BLOCK_TOLERANCE = 0.01  # Local export coordinates are in feet.

# Legacy named outputs are initialized for existing definitions.
a, Base, Sites, Blocks, Cards, Links, Theme, Colors, TrafficLabels = (
    [], [], [], [], [], [], [], [], []
)
Plots, Others, Selected, Boxes, LabelPoints, Labels, BlockIDs, BBL, Area = (
    [], [], [], [], [], [], [], [], []
)
SelectedPts = LabelPoints
MapPlots, BlockCards, BlockLabelPoints, BlockLabels = [], [], [], []
MapBlockBoundaries = []
MapLinks, RowLinks = [], []
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
        records = [
            (str(plot["plot_id"]), str(plot["plot_id"])[:6], plot.get("item_id") or "",
             [ring_curve(ring) for ring in plot["rings"] if len(ring) >= 4], None)
            for plot in atlas["plots"]
        ]
        boundary = [ring_curve(ring) for ring in atlas.get("boundary", []) if len(ring) >= 4]
        return records, {}, boundary

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
    curves, block_outlines = defaultdict(list), defaultdict(list)
    boundary = []
    for obj in model.Objects:
        key = obj.Attributes.Name or ""
        if not isinstance(obj.Geometry, rg.Curve):
            continue
        if key in by_bbl:
            curves[key].append(obj.Geometry.DuplicateCurve())
        elif key.startswith("BLOCK-"):
            block_outlines[key[6:]].append(obj.Geometry.DuplicateCurve())
        elif key == "BOUNDARY":
            boundary.append(obj.Geometry.DuplicateCurve())
    if set(curves) != set(by_bbl):
        raise ValueError("The 3DM and CSV have different plot IDs. Use one matching export.")
    records = [
        (key, row.get("block_id") or key[:6],
         (row.get("item_id") or key) if row["selected"] == "1" else "",
         curves[key], float(row["area_sqft"]))
        for key, row in by_bbl.items()
    ]
    return records, block_outlines, boundary


def measure(curves):
    bounds = curves[0].GetBoundingBox(True)
    for curve in curves[1:]:
        bounds.Union(curve.GetBoundingBox(True))
    span = max(bounds.Max.X - bounds.Min.X, bounds.Max.Y - bounds.Min.Y)
    if span <= 0:
        raise ValueError("An outline has no usable width or height.")
    return bounds, span


def dissolve_block(lots):
    """Build a block footprint from closed plot rings, keeping holes."""
    if len(lots) == 1:
        return lots[0][2]

    faces = List[rg.Brep]()
    for _, _, curves, _, _, _ in lots:
        loops = List[rg.Curve]()
        for curve in curves:
            loops.Add(curve)
        plot_faces = rg.Brep.CreatePlanarBreps(loops, BLOCK_TOLERANCE)
        if not plot_faces:
            return []
        for face in plot_faces:
            faces.Add(face)

    merged = rg.Brep.CreatePlanarUnion(faces, rg.Plane.WorldXY, BLOCK_TOLERANCE)
    return [loop.To3dCurve() for face in (merged or []) for loop in face.Loops]


def fit(curves, center, span, cx, cy):
    scaling = rg.Transform.Scale(center, (BOX - 2 * MARGIN) / span)
    move = rg.Transform.Translation(cx - center.X, cy - center.Y, -center.Z)
    result = []
    for original in curves:
        curve = original.DuplicateCurve()
        curve.Transform(scaling)
        curve.Transform(move)
        result.append(curve)
    return result


def line(x1, y1, x2, y2):
    return rg.LineCurve(rg.Point3d(x1, y1, 0), rg.Point3d(x2, y2, 0))


if x:
    path = os.path.expanduser(str(x).strip().strip('"'))
    records, block_outlines, boundary = read_inputs(path)
    if not records:
        raise ValueError("No plots found.")
    if len({r[0] for r in records}) != len(records):
        raise ValueError("Plot IDs must be unique.")

    selected_blocks = {block for _, block, label, _, _ in records if label}
    if not selected_blocks:
        raise ValueError("No selected plots are marked in this export. Use the full export with selection flags.")

    grouped = defaultdict(list)
    for bbl, block, label, curves, area in records:
        if block not in selected_blocks:
            continue
        if not curves:
            raise ValueError("Missing plot outline: " + bbl)
        bounds, span = measure(curves)
        grouped[block].append((bbl, label, curves, area, bounds.Center, span))
        MapPlots.extend(curves)

    site_bounds, _ = measure(boundary if boundary else MapPlots)
    first_header_x = site_bounds.Max.X + 3 * STEP_X
    first_row_y = site_bounds.Max.Y
    Base = list(boundary)
    BlockIDs = sorted(grouped)
    row_index = 0
    missing_boundaries = []
    for block_index, block in enumerate(BlockIDs):
        lots = sorted(grouped[block], key=lambda lot: (-lot[5], lot[0]))
        selected_count = sum(bool(lot[1]) for lot in lots)
        source_block = block_outlines.get(block) or dissolve_block(lots)
        if source_block:
            MapBlockBoundaries.extend(source_block)
        else:
            missing_boundaries.append(block)
            source_block = [curve for lot in lots for curve in lot[2]]
            Base.extend(source_block)
        block_bounds, block_span = measure(source_block)
        # An actual point on the source block outline identifies the map endpoint.
        anchor = source_block[0].PointAtStart
        cy = first_row_y - row_index * STEP_Y
        link = line(anchor.X, anchor.Y, first_header_x - BOX / 2, cy)
        MapLinks.append(link)

        for offset in range(0, len(lots), MAX_PER_ROW):
            row = lots[offset:offset + MAX_PER_ROW]
            cy = first_row_y - row_index * STEP_Y
            BlockCards.extend(fit(source_block, block_bounds.Center, block_span, first_header_x, cy))
            BlockLabelPoints.append(rg.Point3d(first_header_x - BOX / 2, cy - BOX / 2 - 145, 0))
            suffix = " (cont.)" if offset else ""
            BlockLabels.append(f"Block {block}{suffix} | {len(lots)} plots | {selected_count} selected")
            end_x = first_header_x + len(row) * STEP_X
            rail_y = cy - BOX / 2 - 30
            RowLinks.append(line(first_header_x, rail_y, end_x, rail_y))

            for col, (bbl, label, curves, area, center, span) in enumerate(row, 1):
                cx = first_header_x + col * STEP_X
                destination = Selected if label else Others
                for curve in fit(curves, center, span, cx, cy):
                    destination.append(curve)
                    PlotTree.Add(curve, GH_Path(block_index))
                if label:
                    h = BOX / 2
                    box = [(cx-h, cy-h), (cx+h, cy-h), (cx+h, cy+h),
                           (cx-h, cy+h), (cx-h, cy-h)]
                    Boxes.append(ring_curve(box))
                    LabelPoints.append(rg.Point3d(cx - h, cy - h - 145, 0))
                    Labels.append(f"{label} | {bbl}")
                BBL.append(bbl)
                Area.append(area)
            row_index += 1

    Blocks = BlockCards
    Plots = Others
    Cards = Others + Selected
    Links = MapLinks + RowLinks
    Base.extend(MapBlockBoundaries)
    a = BlockCards + Cards + Boxes + RowLinks
    Info = (f"{len(BBL):,} of {len(records):,} plots shown | {len(BlockIDs):,} blocks with selected plots"
            f" | {row_index:,} rows | {len(Labels)} selected"
            f" | {len(BlockIDs) - len(missing_boundaries):,} blocks outlined")
    if missing_boundaries:
        Info += "\nCheck block boundaries: " + ", ".join(missing_boundaries)
else:
    Info = "Connect the original plot export path to x."
print(Info)


