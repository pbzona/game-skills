# Parametric Procedural House Generation and In-World Edit Handles

**Source skill:** `cmulr8gtu02n507ad5ztx10sl`  
**Scope:** Tiny Glade-style procedural houses and direct manipulation in Three.js. The source skill’s techniques are field-tested in a Three.js WebGPU house editor and a cove-village builder.

## Generator architecture

- Use one shared layout function to define storey rectangles, wall bays, doors, stilt state, roof direction and roof lean. Reuse it for mesh generation, editor picking and path finding so the visible geometry and interaction model cannot drift apart.
- Choose generated windows with a stable per-bay hash keyed by side, floor and slot. Store overrides in a per-volume `openings[key]` map so changing one wall does not reshuffle other openings.
- Define roof height through one `roofAt(c)` function, including the curve profile. Gables, dormers and chimneys should query this same surface to stay attached during pitch/curve edits.
- Cap eave drop and lift the roof as needed; steep slopes should not lower eaves to knee height.

## Joining volumes and solving roofs

- Treat volumes as joined when rectangle edges touch and overlap. Skip wall bays whose outward probes fall inside another walled volume; joined walls are interior.
- Remove jetties along joined sides. For a ridge extending into a neighboring wing, extend the roof to meet it without an intervening gable; joined eaves may call for a flipped ridge or lean-to, capped below the neighboring wall plate.
- Keep dormers and chimneys out of joined spans and away from one another.
- For round towers, use one bay per curved segment; share the same circle definition (center, radius, bay count, seeded phase) between rendering and picking so doors/windows and wall interaction work like the flat-wall path.

## In-world editing

- Record a pointer-to-handle grab offset at drag start to avoid jumps when handles sit away from the surface.
- Update handle world matrices before raycasting, including before the first render/offscreen test.
- Hide stretch handles on joined faces; constrain a wing's move handle to slide along its parent wall.
- Rebuild edits from an original snapshot while dragging. Check overlap/validity with the same predicate used for the placement ghost; roll invalid edits back.
- Keep UI tool state synchronized after initialization when the UI is constructed before the tool system.

## Wings, floors, walkways, and paths

- Split walls into short grid-aligned segments and expose wing-extrusion handles only where a segment is not already covered. A drag creates a same-height volume oriented with its gable outward; refuse overlap.
- A partial floor lift can split one volume into as many as three pieces. Lower adjacent pieces form usable flat-roof terraces; openings can connect a wall bay to a same-level terrace.
- After every edit, relink walkways: snap the far end to the linked house's facing wall and slide the walkway laterally to maintain attachment. Check nearby-house overlap and roll back if needed; if a valid connection is no longer possible, unlink it and notify the player.
- Model raised decks and upper walkways as bridges for occupancy checks: permit paths and low props underneath, while refusing terrain changes and new buildings. Refit bridges against buildings, not low underpass props.
- Record the terrain/path cells painted by an object's auto-path so they can be reverted when the object moves or is removed.

## Procedural walls

- Store walls as polylines on a half-unit grid; generate thin terrain-conforming slices along each leg. Rebuild when terrain or paint changes.
- Mark slices crossing path/cobble paint as openings, then ensure gateways are wide enough to walk through. Use arches for stone/castle walls, simple gaps with gateposts for garden walls, and pillars at endpoints/corners.
- Use draggable corner and mid-leg handles; merge collinear legs and drop tiny legs after edits. Cache the cells occupied by walls against a world version and exclude buildings/walls from one another. Lock terraforming beneath them.

## Terrain and raised foundations

- A rock-outcrop foundation can activate when the height variation under the footprint exceeds roughly 1.1 units. Use a stepped, flared ring pedestal with noisy superellipse offsets, plus boulder forms where a wall backs onto higher ground.
- Keep shared helpers for stairs and entrances so decks and front doors land at actual terrain height.

## Migrating a block kit

For an old grid-based town, flood-fill contiguous block clusters, split by storey height, then greedily fit maximal rectangles largest-first. Derive the main volume from the largest rectangle and use the majority old roof type. Convert post-supported roofs into open pavilions and narrow all-stone runs into walls. Avoid retaining decks/stairs if the parametric generator will generate them; report conversion totals.

## Rebuild and preview performance

- Cache each house's mesh-builder result by house data, terrain version and nearby live walkway nodes. Freeze parts into typed arrays and merge them with owner metadata remapped by stable key.
- Defer decorative scatter while a drag is active. In the source cove builder, caching/rebuild changes reduced a full-village rebuild from about 95 ms to about 28 ms per handle drag.
- Do not assign empty `BufferGeometry` to a mesh using a node material; hide the mesh instead, or the material may compile without needed attributes and later previews can remain invisible.

## Further source notes

- Boats whose hull gunwale is at waterline need a freeboard offset. A depth-only lid slightly above the waterline prevents transparent water from drawing inside the hull; wind its faces upward to avoid culling.
- Tiny Glade-style affordances in the source notes include roofs with adjustable ridge width/curve, auto-supported raised volumes, and paths that create doors, archways, stairs or stepping stones as they intersect geometry.

## Related tools

The measurement-accurate architecture tools in [measurement-accurate architecture](measurement-accurate-architecture.md) are adjacent, but solve a different problem: dimensionally exact architectural plans rather than stylized procedural village generation.

## More precise source patterns

- Model wing adjacency as touching rectangle edges with overlap. Probe outward from wall bays to identify interior faces. A ridge entering a neighboring wing can extend by roughly half the wing depth without an end gable; an eave-side join at equal height can flip the ridge, while a taller neighbor calls for a lean-to below its wall plate.
- For a stable gridless layout, snap bay centers to a half-unit lattice and use a stable hash for generated openings. This preserves the rest of a facade when one window is edited. Keep the shared roof-height evaluator authoritative for gables, dormers and chimneys.
- Split wing-extrusion handles into segments around one unit (in 0.5-unit increments) and suppress handles already covered by another volume. For a partial-floor lift, split into at most three pieces; a one-unit-wide lift may read visually as a thin tower, so use wider snapping where that matters.
- When a walkway joins a building, choose only the best-overlapping wall bay for its side door, one per link, and match deck height for upper-floor bridges. Relink from edited snapshots and roll back conflicts.
- Drag-out walls can open where terrain paint indicates a path; widen walkable gateways to at least about 0.7 units. Drop wall legs shorter than about 0.5 units after handle edits and merge collinear legs. Sample the line for building exclusion and cache its occupied cells by world version.
- For rock-backed structures, the source foundation activates when terrain height span under the footprint exceeds about 1.1 units; its base flares as a stepped, noisy superellipse. Keep entrances and deck stairs on the true terrain height.
- Cache generated house parts by house data, terrain revision, and nearby walkway nodes. During manipulation, rebuild from the original snapshot and defer scatter work; one tested cove-village pass reduced whole-scene rebuild time from roughly 95 ms to 28 ms per drag.

## Source pointers

The source skill references the [Tiny Glade gridless-building page](https://tinyglade.wiki.gg/wiki/Gridless_building) and a [Tiny Glade Builder’s Basics community guide](https://steamcommunity.com/sharedfiles/filedetails/?id=3336822132). The implementation patterns above are paraphrased from the field-tested Three.js editor and cove-builder notes associated with this skill.
