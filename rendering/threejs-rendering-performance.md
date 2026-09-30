# Three.js Rendering Performance and GPU-Frugal Defaults

**Source skill:** `cmu3jgmxs01kc07adwelapxkk`  
**Focus:** A practical performance reference for interactive browser 3D scenes, including the user's preference for frugal GPU use on varied hardware.

## Frame pacing

Do not assume an uncapped animation loop is free: it may run at 120–144 Hz. For editors and builder scenes, target roughly 60 fps during active input/animation, 30 fps idle, and lower rates while unfocused; stop work when the document is hidden. Offer a profiling override. Keep input responsiveness distinct from animation rate.

## Shadows, lights, and shader work

- Disable automatic shadow-map refresh for static scenes; mark shadows dirty only while casters move.
- Keep transient lights preallocated rather than adding/removing lights at runtime, which may recompile every lit material. Reuse a fixed pool and prewarm relevant states if needed.
- Small continuous movers such as leaves should not cast shadows if that forces perpetual map updates.
- Bake static procedural patterns/lighting when possible; limit ground planes to the visible region.
- Make procedural shader cost explicit (for example, compile-time noise-octave settings); use few octaves on broad scenery and reserve more for hero surfaces.

## Materials, batching, resolution

Choose the least expensive material that meets the visual target. Avoid costly transmission where a full-scene extra pass is not worth it. Merge static geometry, instance repeated geometry, and share material instances. Cap DPR (roughly 1.5 on higher-quality settings and 1.0 on lighter settings) and cap total pixel count; use adaptive scale within a bounded range when frame time exceeds budget. Manual drawing-buffer sizing keeps postprocessing and picking dimensions predictable.

## Measure rather than guess

CPU timing under SwiftShader (especially synchronous readback) is only a proxy and can exaggerate DPR effects. Use GPU timer queries when available and compare interleaved baselines to reduce thermal/clock drift. Measure a consistent full frame while toggling one cost center at a time: shadow refresh, bloom, grading, terrain shader, postprocessing. Fewer frames and cheaper frames are independent savings.

## Practical debugging notes

- Static scenes should not continuously recompute render targets or shadows without a reason.
- Dynamic resolution should use smoothed frame-time history and hysteresis to prevent rapid quality oscillation.
- A high-end visual pass still needs a low-cost path for users on integrated/mobile GPUs.
- When using Three.js WebGPU/TSL, avoid double-converting colors that Three.js already converts from sRGB to linear; verify postprocessing color-space and readback assumptions.

## How this overlaps with the prototype guide

[`threejs-game-prototyping.md`](threejs-game-prototyping.md) covers controller/camera architecture, bundling and automated correctness tests. This file concentrates on steady-state render budget, GPU cost attribution and resource-frugal defaults. The source guides overlap in batching and resolution advice; their distinct operational detail is retained here.

## Expanded measurement and quality-budget notes

- Frame pacing and per-frame cost are separate levers. A 26 ms frame capped at 30 fps still uses roughly 80% of the frame budget; reduce unnecessary frames as well as shader work.
- Use an EMA of frame interval and bounded render scale (about 0.5–1.0) with hysteresis. A lower internal resolution should not create oscillation between quality states.
- CPU-side SwiftShader measurements—especially synchronous `readPixels`—are a poor proxy for device GPU cost and exaggerate some DPR effects. When available, measure `render()` with `EXT_disjoint_timer_query_webgl2` and discard samples while `GPU_DISJOINT_EXT` is true.
- Compare each variant against interleaved full-frame baselines to reduce clock/thermal drift. Isolate one change at a time: shadow-map refresh, bloom, color grading, ground shader complexity, then postprocessing.
- For static procedural scenes, bake repeated fragment patterns into a mipmapped render target and static skies into a cube target when the runtime cost justifies the memory/startup expense. Limit large ground planes to the visible area; use a cheaper outer surface.
- Keep a low-cost material path for integrated/mobile GPUs. Noise octave count should be explicit and low on large scenery; use higher detail only for hero surfaces. If shader defines are used, include them in `customProgramCacheKey`.
- Do not leave animated low-value debris casting shadows or repeatedly refresh static maps. 1024–2048 shadow maps often suffice; 4096 is rarely worthwhile for these scenes. Mark maps dirty only when relevant casters change.
- A permanently attached light at intensity zero still costs per-pixel lighting. If reusing lights to avoid shader recompiles, measure the hidden/visible strategy and prewarm supported states rather than assuming zero intensity is free.
