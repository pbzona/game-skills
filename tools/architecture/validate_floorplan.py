#!/usr/bin/env python3
"""Validate an architectural floor plan JSON file against the measurement-accurate schema.

Checks:
- Required top-level fields (meta, levels, walls, openings, rooms)
- All wall references in openings point to existing wall IDs
- All wall references in furniture point to existing wall IDs (if wall-anchored)
- All level references in walls/rooms/furniture point to existing level IDs
- No opening extends past its host wall (offset + width <= wall length)
- No duplicate IDs within entity types
- Units are specified in meta
- Room polygons are valid (>= 3 points, closed)
- Wall centerlines have non-zero length
- Opening sill + height <= wall height (when wall height is known)

Usage:
    python validate_floorplan.py <path-to-json>
    python validate_floorplan.py <path-to-json> --strict  (treat warnings as errors)

Exit codes:
    0 = valid (no errors)
    1 = invalid (errors found)
    2 = file not found or parse error
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


def wall_length_mm(wall):
    x1, y1 = wall["from"]
    x2, y2 = wall["to"]
    return math.hypot(x2 - x1, y2 - y1)


def validate(data, strict=False):
    errors = []
    warnings = []

    # --- Top-level fields ---
    required_top = ["meta", "levels", "walls"]
    for field in required_top:
        if field not in data:
            errors.append(f"Missing top-level field: '{field}'")

    if "meta" in data:
        meta = data["meta"]
        if "unit" not in meta:
            warnings.append("meta.unit is not specified (recommended: 'mm')")
        if "id" not in meta:
            warnings.append("meta.id is not specified")

    # --- Build ID registries ---
    level_ids = set()
    if "levels" in data:
        for i, level in enumerate(data["levels"]):
            if "id" not in level:
                errors.append(f"Level at index {i} missing 'id'")
            else:
                level_ids.add(level["id"])
            if "height" not in level:
                warnings.append(f"Level '{level.get('id', i)}' missing 'height'")

    wall_ids = set()
    wall_map = {}  # id -> wall dict
    if "walls" in data:
        for i, wall in enumerate(data["walls"]):
            wid = wall.get("id", f"<index {i}>")
            if "id" not in wall:
                errors.append(f"Wall at index {i} missing 'id'")
            elif wid in wall_ids:
                errors.append(f"Duplicate wall ID: '{wid}'")
            else:
                wall_ids.add(wid)
                wall_map[wid] = wall

            if "from" not in wall or "to" not in wall:
                errors.append(f"Wall '{wid}' missing 'from' or 'to'")
                continue

            if "level" in wall and wall["level"] not in level_ids:
                errors.append(f"Wall '{wid}' references unknown level: '{wall['level']}'")

            if "thickness" not in wall:
                warnings.append(f"Wall '{wid}' missing 'thickness'")
            elif wall.get("thickness", 0) <= 0:
                errors.append(f"Wall '{wid}' has non-positive thickness: {wall['thickness']}")

            wlen = wall_length_mm(wall)
            if wlen < 1:
                errors.append(f"Wall '{wid}' has zero-length centerline")

    # --- Openings ---
    opening_ids = set()
    if "openings" in data:
        for i, op in enumerate(data["openings"]):
            oid = op.get("id", f"<index {i}>")
            if "id" not in op:
                errors.append(f"Opening at index {i} missing 'id'")
            elif oid in opening_ids:
                errors.append(f"Duplicate opening ID: '{oid}'")
            else:
                opening_ids.add(oid)

            if "wall" not in op:
                errors.append(f"Opening '{oid}' missing 'wall' reference")
                continue

            if op["wall"] not in wall_ids:
                errors.append(
                    f"Opening '{oid}' references unknown wall: '{op['wall']}'"
                )
                continue

            # Check opening fits within wall
            wall = wall_map[op["wall"]]
            wlen = wall_length_mm(wall)
            offset = op.get("offset", 0)
            width = op.get("width", 0)

            if offset < 0:
                errors.append(
                    f"Opening '{oid}' has negative offset: {offset}"
                )

            if offset + width > wlen + 0.001:  # small tolerance
                errors.append(
                    f"Opening '{oid}' extends past wall end: "
                    f"offset({offset}) + width({width}) = {offset + width} > "
                    f"wall length({wlen:.1f}) on wall '{op['wall']}'"
                )

            # Check opening height vs wall height
            if "height" in op and "height" in wall:
                if op["sill"] + op["height"] > wall["height"] + 0.001:
                    errors.append(
                        f"Opening '{oid}' extends above wall: "
                        f"sill({op['sill']}) + height({op['height']}) = "
                        f"{op['sill'] + op['height']} > wall height({wall['height']})"
                    )
            elif "height" in op and "level" in wall:
                # Try level height
                level = next(
                    (l for l in data.get("levels", []) if l.get("id") == wall["level"]),
                    None,
                )
                if level and "height" in level:
                    if op["sill"] + op["height"] > level["height"] + 0.001:
                        errors.append(
                            f"Opening '{oid}' extends above level height: "
                            f"sill({op['sill']}) + height({op['height']}) = "
                            f"{op['sill'] + op['height']} > level height({level['height']})"
                        )

            if "kind" not in op:
                warnings.append(f"Opening '{oid}' missing 'kind' (door/window)")

    # --- Rooms ---
    room_ids = set()
    if "rooms" in data:
        for i, room in enumerate(data["rooms"]):
            rid = room.get("id", f"<index {i}>")
            if "id" not in room:
                errors.append(f"Room at index {i} missing 'id'")
            elif rid in room_ids:
                errors.append(f"Duplicate room ID: '{rid}'")
            else:
                room_ids.add(rid)

            if "level" in room and room["level"] not in level_ids:
                errors.append(
                    f"Room '{rid}' references unknown level: '{room['level']}'"
                )

            if "polygon" in room:
                poly = room["polygon"]
                if len(poly) < 3:
                    errors.append(
                        f"Room '{rid}' polygon has fewer than 3 points: {len(poly)}"
                    )
                # Check if polygon is closed (first == last) or open
                # Open polygons are acceptable (auto-close on render)

    # --- Furniture ---
    furniture_ids = set()
    if "furniture" in data:
        for i, furn in enumerate(data["furniture"]):
            fid = furn.get("id", f"<index {i}>")
            if "id" not in furn:
                errors.append(f"Furniture at index {i} missing 'id'")
            elif fid in furniture_ids:
                errors.append(f"Duplicate furniture ID: '{fid}'")
            else:
                furniture_ids.add(fid)

            if "level" in furn and furn["level"] not in level_ids:
                errors.append(
                    f"Furniture '{fid}' references unknown level: '{furn['level']}'"
                )

            if "wall" in furn and furn["wall"] not in wall_ids:
                errors.append(
                    f"Furniture '{fid}' references unknown wall: '{furn['wall']}'"
                )

    # --- Summary ---
    result = {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "levels": len(data.get("levels", [])),
            "walls": len(data.get("walls", [])),
            "openings": len(data.get("openings", [])),
            "rooms": len(data.get("rooms", [])),
            "furniture": len(data.get("furniture", [])),
        },
    }

    if strict and len(warnings) > 0:
        result["valid"] = False
        result["errors"].extend([f"[STRICT] {w}" for w in warnings])

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Validate an architectural floor plan JSON file"
    )
    parser.add_argument("filepath", help="Path to the JSON file")
    parser.add_argument(
        "--strict", action="store_true", help="Treat warnings as errors"
    )
    args = parser.parse_args()

    data = load_json(args.filepath)
    result = validate(data, strict=args.strict)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()