"""Rhino 8 Grasshopper Python 3 Script Mode.

Keep x connected to the existing JSON path or export folder.
Optional outputs: Base, MapBlockBoundaries, MapPlots, BlockCards, BlockLabelPoints, BlockLabels,
Plots, Selected, Boxes, LabelPoints, Labels, MapLinks, RowLinks, BlockIDs,
PlotTree, BlockCardPlots, BlockCardMarkers, TextCurves.
a previews the labeled block plans and exploded plots.
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
GROUP_GAP = 500.0
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
BlockCardPlots, BlockCardMarkers, TextCurves = [], [], []
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


def add_text(value, x, y, height, bold=False):
    plane = rg.Plane(rg.Point3d(x, y, 0), rg.Vector3d.ZAxis)
    outlines = rg.Curve.CreateTextOutlines(
        value, "Arial", height, int(bold), True, plane, 1.0, BLOCK_TOLERANCE
    )
    if outlines:
        TextCurves.extend(outlines)


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
    half_box = BOX / 2
    left = first_header_x - half_box
    add_text("BLOCK PLAN   /   EXPLODED TAX LOTS", left, first_row_y + 1130, 160, bold=True)
    add_text("Circle on plan / box in row = selected plot", left, first_row_y + 890, 105)
    for block_index, block in enumerate(BlockIDs):
        lots = sorted(grouped[block], key=lambda lot: (-lot[5], lot[0]))
        selected_count = sum(bool(lot[1]) for lot in lots)
        parcel_outlines = [curve for lot in lots for curve in lot[2]]
        source_block = block_outlines.get(block) or dissolve_block(lots)
        if source_block:
            MapBlockBoundaries.extend(source_block)
        else:
            missing_boundaries.append(block)
            Base.extend(parcel_outlines)
        block_bounds, block_span = measure(parcel_outlines + (source_block or []))
        # An actual point on the source block outline identifies the map endpoint.
        anchor = (source_block or parcel_outlines)[0].PointAtStart
        cy = first_row_y - row_index * STEP_Y - block_index * GROUP_GAP
        link = line(anchor.X, anchor.Y, first_header_x - BOX / 2, cy)
        MapLinks.append(link)

        for offset in range(0, len(lots), MAX_PER_ROW):
            row = lots[offset:offset + MAX_PER_ROW]
            cy = first_row_y - row_index * STEP_Y - block_index * GROUP_GAP
            BlockCards.extend(fit(source_block or [], block_bounds.Center, block_span, first_header_x, cy))
            BlockCardPlots.extend(fit(parcel_outlines, block_bounds.Center, block_span, first_header_x, cy))
            block_scale = (BOX - 2 * MARGIN) / block_span
            for _, label, _, _, center, _ in lots:
                if label:
                    marker = rg.Point3d(
                        first_header_x + (center.X - block_bounds.Center.X) * block_scale,
                        cy + (center.Y - block_bounds.Center.Y) * block_scale, 0
                    )
                    BlockCardMarkers.append(rg.Circle(marker, 36).ToNurbsCurve())

            BlockLabelPoints.append(rg.Point3d(left, cy - half_box - 145, 0))
            suffix = " (cont.)" if offset else ""
            BlockLabels.append(f"Block {block}{suffix} | {len(lots)} plots | {selected_count} selected")
            add_text(f"BLOCK {block}{suffix}", left, cy - half_box - 235, 130, bold=True)
            add_text(f"{len(lots)} plots / {selected_count} selected", left, cy - half_box - 410, 92)
            end_x = first_header_x + len(row) * STEP_X
            rail_y = cy - half_box - 65
            RowLinks.append(line(first_header_x, rail_y, end_x, rail_y))

            for col, (bbl, label, curves, area, center, span) in enumerate(row, 1):
                cx = first_header_x + col * STEP_X
                destination = Selected if label else Others
                for curve in fit(curves, center, span, cx, cy):
                    destination.append(curve)
                    PlotTree.Add(curve, GH_Path(block_index))
                add_text(bbl, cx - half_box, cy - half_box - 235, 106)
                if label:
                    h = half_box
                    box = [(cx-h, cy-h), (cx+h, cy-h), (cx+h, cy+h),
                           (cx-h, cy+h), (cx-h, cy-h)]
                    Boxes.append(ring_curve(box))
                    LabelPoints.append(rg.Point3d(cx - h, cy - h - 145, 0))
                    Labels.append(f"{label} | {bbl}")
                    add_text(f"{label}  SELECTED", cx - h, cy - h - 410, 102, bold=True)
                BBL.append(bbl)
                Area.append(area)
            row_index += 1

    Blocks = BlockCards + BlockCardPlots + BlockCardMarkers
    Plots = Others
    Cards = Others + Selected
    Links = MapLinks + RowLinks
    Base.extend(MapBlockBoundaries)
    a = Blocks + Cards + Boxes + RowLinks + TextCurves
    Info = (f"{len(BBL):,} of {len(records):,} plots shown | {len(BlockIDs):,} blocks with selected plots"
            f" | {row_index:,} rows | {len(Labels)} selected"
            f" | {len(BlockIDs) - len(missing_boundaries):,} blocks outlined")
    if missing_boundaries:
        Info += "\nCheck block boundaries: " + ", ".join(missing_boundaries)
else:
    Info = "Connect the original plot export path to x."
print(Info)


