# Three.js Browser Game Prototyping and Performance

**Source skill:** `cmu3jgy8j01ny07adxk47q8jv`  
**Focus:** Browser action-game scaffolding, third-person camera/controller foundations, scene performance, bundling and verification.

## Scene and renderer

Set up a scene, camera and renderer with explicit shadow budget. Keep the render buffer within a pixel-ratio/pixel-count cap (a high-DPR phone can otherwise render many times more pixels than expected). Use soft shadows sparingly; scope directional-light shadow cameras tightly to the playable area. Use shared lighting/materials and reserve expensive physical features for hero objects.

## Third-person camera

Keep camera orbit state separate from player facing. Smoothly follow an offset target and raycast from the player's head to the desired camera location. Clamp before wall hits, allow the desired distance to recover after occlusion, and pad for the camera FOV so screen edges do not reveal geometry. Wall thickness or collision-only occluders address backface leaks.

## Fixed-timestep character simulation

Accumulate wall-clock time, clamp long frame gaps, and step gameplay/physics at a fixed interval (e.g. 1/60 s). Interpolate render transforms between previous/current simulation states. Move and resolve AABB collisions axis-by-axis for a simple static-world controller; use swept tests or substeps where speed/tunneling demands more. Read input consistently before logic/physics and update camera after the character to avoid one-frame lag.

## Geometry and material budget

Batch static, non-interactive geometry; use `InstancedMesh` for repeated same-shape objects and share materials. Merged geometry needs matching attribute layouts and indexing and requires transforms baked into vertices. Dispose source geometry after merging. Keep independently interactive or moving objects separate. Prefer simpler materials for large screen-covering terrain; transmission and other physical extensions can be expensive.

## Adaptive resolution

Manually size the drawing buffer, cap DPR or total pixels, and optionally lower render scale when a smoothed frame-time budget is exceeded. Restore quality more slowly than it is reduced to avoid oscillation. Recompute camera aspect on resize. Distinguish the cost of each frame (shading, shadows, post) from the cost of how many frames are rendered.

## Bundling and distribution

For a self-contained HTML distribution, bundle JS/TS with esbuild, inline resulting JS and CSS into a template, and only inline small essential assets (base64 adds overhead). Preserve script/style closing-tag safety; avoid overly large embedded binary payloads.

## Headless verification

Expose stable test hooks for readiness and game state. Wait for the canvas/renderer to produce frames, send held keyboard input as down/wait/up, and assert observable state changes. Use WebGL/WebGPU-capable Chromium settings in CI; software renderers are useful for correctness but can be slow and are not reliable performance benchmarks.

## Current Three.js/WebGPU caveats surfaced by this skill

- In recent Three.js r18x builds, `PCFSoftShadowMap` has been removed; use supported shadow modes and set radius as appropriate.
- `THREE.Clock` is deprecated in newer releases; use `THREE.Timer` where applicable.
- Dynamic changes to the number of scene lights can trigger lit-material recompilation. Prefer preallocated/reused lights for transient effects.
- A test-only deterministic timestep hook, explicit app-ready flag, and world-to-screen helper make automated interactions more reliable.
- In sandboxed iframes, `localStorage` can throw; provide a safe fallback. Workers may be blocked, so retain a main-thread fallback where needed.

## Registered helpers

- [`../tools/rendering/bundle_game.py`](../tools/rendering/bundle_game.py) bundles a JS/TS entry and injects it into a self-contained HTML file.
- [`../tools/rendering/verify_game.py`](../tools/rendering/verify_game.py) boots a headless Chromium game URL, checks rendering/state and can capture screenshots.

## Related guide

[`threejs-rendering-performance.md`](threejs-rendering-performance.md) contains more explicit GPU-budget defaults (frame pacing, shadow invalidation, adaptive scale and measurement methodology). Keep both: this guide emphasizes end-to-end prototype/shipping workflow.

## Additional field-tested details from the current source

### Vite, Three.js r186 and WebGPU

- `THREE.PCFSoftShadowMap` is removed in recent WebGPURenderer builds; use `PCFShadowMap` and tune `shadow.radius` where supported. `THREE.Clock` is deprecated; prefer `THREE.Timer` (`connect(document)`, `update()`, `getDelta()`).
- `THREE.Color.setHex`/`set()` already convert sRGB input to the linear working space. Do not call `convertSRGBToLinear()` again; double conversion creates incorrect shadow and dusk tints.
- Three.js postprocessing uses `THREE.RenderPipeline`; bloom is available through the TSL `BloomNode` path.
- Add/remove lights changes the light count and may recompile lit materials. Reuse a pre-existing point-light pool; intensity zero still incurs lighting cost, so visibility/state strategy must be measured.

### Deterministic test hooks and headless rendering

- In SwiftShader Chromium, `navigator.gpu` is exposed only on a secure origin such as localhost. WebGPU flags used by the source include `--enable-unsafe-webgpu`, `--enable-unsafe-swiftshader`, and `--use-webgpu-adapter=swiftshader`.
- For deterministic browser testing, expose a small debug surface (fixed-step `tick`, capture, `screenOf`, setters such as time-of-day), game readiness, and stable state. Project world positions through the camera before sending real pointer input.
- SwiftShader can run at only a few frames per second; fixed-timestep URL hooks such as `?fast` or `?dt=...` speed up timer/tween testing. Keep per-job delta values independent in delayed schedulers.
- In some headless Chromium/WebGPU combinations, canvas presentation loses the GPU device or screenshots remain black. An offscreen render-target readback can provide evidence; handle row stride and color-space tagging correctly. On-demand frame counts alone do not prove the WebGPU backend initialized.
- In a sandboxed iframe, guard `localStorage` with a fallback, keep a main-thread fallback if workers are blocked, and avoid `location.reload()` for UI setting changes. Loading overlays should stop intercepting pointer input after fade; rebuilding button markup during pointer down/up can cancel a click.

### Game-specific edge cases

For tall board-game pieces, highlighted destinations can be occluded or missed by raycasts. Draw markers without depth testing at an appropriately high render order, fade pieces between the camera and targets, and prioritize highlighted-square hits. For Vite single-HTML output, use a replacement callback when injecting minified JS so `$` sequences are not interpreted by `String.replace`; inline workers and the favicon where distribution requires a single file.

For repository pushes through the GitHub integration, file payloads are text-only. Keep binary assets as base64 text and decode them in a build plugin; compose large multi-file payloads from disk rather than placing large source strings inline.
