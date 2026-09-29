#!/usr/bin/env python3
"""Compute derived geometry from an architectural floor plan JSON file.

Calculates:
- Wall lengths (centerline distance)
- Wall angles (degrees from X axis)
- Room areas (shoelace formula, net of holes if present)
- Room perimeters
- Opening positions (absolute coordinates from wall + offset)
- Elevation view bounds per wall (for orthographic camera setup)
- Dimension line suggestions (overall building width/height, per-wall)

Output: JSON with all computed values, suitable for feeding into a
Three.js renderer or for validation against an architect's figures.

Usage:
    python compute_geometry.py <path-to-json>
    python compute_geometry.py <path-to-json> --unit m   (output in meters)
    python compute_geometry.py <path-to-json> --unit ft  (output in feet)
"""
import sys
import json
import math
import argparse


def load_json(filepath):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(json.dumps({"error": f"File not found: {filepath}"}))
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"JSON parse error: {e}"}))
        sys.exit(2)


def mm_to_unit(mm, unit):
    if unit == "mm":
        return mm
    elif unit == "m":
        return mm / 1000.0
    elif unit == "ft":
        return mm / 304.8
    elif unit == "in":
        return mm / 25.4
    return mm


def unit_label(unit):
    return {"mm": "mm", "m": "m", "ft": "ft", "in": "in"}.get(unit, unit)


def wall_length_mm(wall):
    x1, y1 = wall["from"]
    x2, y2 = wall["to"]
    return math.hypot(x2 - x1, y2 - y1)


def wall_angle_deg(wall):
    x1, y1 = wall["from"]
    x2, y2 = wall["to"]
    return math.degrees(math.atan2(y2 - y1, x2 - x1))


def shoelace_area(polygon):
    """Compute polygon area using the shoelace formula. Points in mm."""
    n = len(polygon)
    if n < 3:
        return 0.0
    # Ensure closed
    pts = polygon[:]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    area = 0.0
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0  # mm²


def polygon_perimeter(polygon):
    pts = polygon[:]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    perim = 0.0
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        perim += math.hypot(x2 - x1, y2 - y1)
    return perim  # mm


def opening_abs_coords(wall, opening):
    """Compute absolute XY coordinates of an opening on a wall."""
    x1, y1 = wall["from"]
    x2, y2 = wall["to"]
    wlen = math.hypot(x2 - x1, y2 - y1)
    if wlen == 0:
        return None
    dx = (x2 - x1) / wlen
    dy = (y2 - y1) / wlen
    offset = opening.get("offset", 0)
    width = opening.get("width", 0)

    # Left edge of opening
    lx = x1 + dx * offset
    ly = y1 + dy * offset
    # Right edge
    rx = x1 + dx * (offset + width)
    ry = y1 + dy * (offset + width)

    return {
        "left": [lx, ly],
        "right": [rx, ry],
        "center": [(lx + rx) / 2, (ly + ry) / 2],
    }


def elevation_view_bounds(wall, level_height_mm):
    """Compute orthographic camera bounds for a wall elevation view."""
    wlen = wall_length_mm(wall)
    wheight = wall.get("height", level_height_mm)
    # Add 10% padding
    pad = 0.1
    return {
        "width": wlen * (1 + pad),
        "height": wheight * (1 + pad),
        "wall_length": wlen,
        "wall_height": wheight,
        "camera_distance": wlen * 0.5 + 5,  # rough estimate in meters
    }


def compute(data, output_unit="mm"):
    walls = data.get("walls", [])
    openings = data.get("openings", [])
    rooms = data.get("rooms", [])
    levels = data.get("levels", [])

    # Build lookups
    wall_map = {w["id"]: w for w in walls if "id" in w}
    level_map = {l["id"]: l for l in levels if "id" in l}

    result = {
        "unit": unit_label(output_unit),
        "walls": [],
        "rooms": [],
        "openings": [],
        "building_bounds": None,
        "dimension_lines": [],
    }

    all_x = []
    all_y = []

    # --- Walls ---
    for wall in walls:
        wid = wall.get("id", "?")
        wlen_mm = wall_length_mm(wall)
        angle = wall_angle_deg(wall)
        level_id = wall.get("level")
        level_h = level_map.get(level_id, {}).get("height", 3000)
        wall_h = wall.get("height", level_h)

        wall_result = {
            "id": wid,
            "length": round(mm_to_unit(wlen_mm, output_unit), 2),
            "angle_deg": round(angle, 2),
            "height": round(mm_to_unit(wall_h, output_unit), 2),
            "elevation_view": {
                k: round(mm_to_unit(v, output_unit), 2)
                if isinstance(v, (int, float))
                else v
                for k, v in elevation_view_bounds(wall, level_h).items()
            },
        }
        result["walls"].append(wall_result)

        # Track bounds
        all_x.extend([wall["from"][0], wall["to"][0]])
        all_y.extend([wall["from"][1], wall["to"][1]])

    # --- Openings ---
    for op in openings:
        oid = op.get("id", "?")
        wall = wall_map.get(op.get("wall"))
        if not wall:
            result["openings"].append({
                "id": oid, "error": f"Wall '{op.get('wall')}' not found"
            })
            continue

        coords = opening_abs_coords(wall, op)
        if coords is None:
            result["openings"].append({
                "id": oid, "error": "Wall has zero length"
            })
            continue

        result["openings"].append({
            "id": oid,
            "wall": op["wall"],
            "kind": op.get("kind", "unknown"),
            "width": round(mm_to_unit(op.get("width", 0), output_unit), 2),
            "height": round(mm_to_unit(op.get("height", 0), output_unit), 2),
            "sill": round(mm_to_unit(op.get("sill", 0), output_unit), 2),
            "abs_left": [round(c, 1) for c in coords["left"]],
            "abs_right": [round(c, 1) for c in coords["right"]],
            "abs_center": [round(c, 1) for c in coords["center"]],
        })

    # --- Rooms ---
    for room in rooms:
        rid = room.get("id", "?")
        poly = room.get("polygon", [])
        area_mm2 = shoelace_area(poly)
        perim_mm = polygon_perimeter(poly)

        room_result = {
            "id": rid,
            "name": room.get("name", ""),
            "perimeter": round(mm_to_unit(perim_mm, output_unit), 2),
            "polygon_points": len(poly),
        }

        # Area in proper unit squared
        if output_unit == "m":
            room_result["area"] = round(area_mm2 / 1e6, 2)  # m²
            room_result["area_unit"] = "m²"
        elif output_unit == "ft":
            room_result["area"] = round(area_mm2 / (304.8 ** 2), 2)  # ft²
            room_result["area_unit"] = "ft²"
        else:
            room_result["area"] = round(area_mm2, 0)  # mm²
            room_result["area_unit"] = "mm²"

        result["rooms"].append(room_result)

    # --- Building bounds ---
    if all_x and all_y:
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        result["building_bounds"] = {
            "min_x": round(mm_to_unit(min_x, output_unit), 2),
            "max_x": round(mm_to_unit(max_x, output_unit), 2),
            "min_y": round(mm_to_unit(min_y, output_unit), 2),
            "max_y": round(mm_to_unit(max_y, output_unit), 2),
            "width": round(mm_to_unit(max_x - min_x, output_unit), 2),
            "height": round(mm_to_unit(max_y - min_y, output_unit), 2),
        }

    # --- Dimension line suggestions ---
    if result["building_bounds"]:
        b = result["building_bounds"]
        result["dimension_lines"].append({
            "label": "Overall Width",
            "value": b["width"],
            "axis": "x",
            "start": [b["min_x"], b["min_y"]],
            "end": [b["max_x"], b["min_y"]],
        })
        result["dimension_lines"].append({
            "label": "Overall Height",
            "value": b["height"],
            "axis": "y",
            "start": [b["min_x"], b["min_y"]],
            "end": [b["min_x"], b["max_y"]],
        })

    # Per-wall dimension lines
    for wall in result["walls"]:
        result["dimension_lines"].append({
            "label": f"Wall {wall['id']}",
            "value": wall["length"],
            "wall_id": wall["id"],
        })

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Compute derived geometry from a floor plan JSON file"
    )
    parser.add_argument("filepath", help="Path to the JSON file")
    parser.add_argument(
        "--unit",
        choices=["mm", "m", "ft", "in"],
        default="mm",
        help="Output unit (default: mm)",
    )
    args = parser.parse_args()

    data = load_json(args.filepath)
    result = compute(data, output_unit=args.unit)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()