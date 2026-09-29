# Measurement-Accurate Architectural Modeling in Three.js

**Source skill:** `cmue6r1qw0as707ad26gsizq9`  
**Relationship:** Adjacent building-editor reference, not a procedural city-generation guide. The source skill's exposed summary covers data-driven, measurement-accurate floor plans and 3D architectural editors.

## Source scope

- Units and coordinate conventions; canonical JSON schemas for rooms, walls and openings.
- Orthographic plan views and per-wall elevation views, including clipping/section cuts.
- Wall construction with door/window openings; subdivision versus CSG tradeoffs.
- Architectural dimension lines, ticks and readable text sprites.
- Priority-scored snapping (grid, endpoints, midpoints) and raycaster-based drag placement with live measurements.
- Dirty-flag scene rebuild patterns, validation, and common geometry pitfalls.

## Included helper tools

- [`../tools/architecture/validate_floorplan.py`](../tools/architecture/validate_floorplan.py) validates JSON floor plans: unit declarations, duplicate IDs, wall/opening/room references, opening bounds, polygon validity and wall centerline length.
- [`../tools/architecture/compute_geometry.py`](../tools/architecture/compute_geometry.py) computes wall lengths/angles, room area/perimeter, opening positions, elevation-camera bounds and dimension suggestions, with unit conversion.

The source skill’s full 499-line reference body was not exposed in the retrieval response; this repository file records the complete surfaced summary and ships its two registered scripts without inventing the missing detail.
