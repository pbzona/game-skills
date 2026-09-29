# Game Skills — Catalog

Curated from the Hyperagent knowledge base for procedural village/city builders and browser game development. The source skill names and IDs below are retained for traceability; extracted guidance is organized by the problem it helps solve. This is an additive snapshot, not a replacement of the repository's existing README.

## Procedural building and world editors

- [Parametric Procedural House Generation and In-World Edit Handles](procedural-building/parametric-procedural-houses.md) — modular footprints, wall bays, roofs, openings, edit handles, linked walkways, procedural walls, and live rebuilds. Source skill `cmulr8gtu02n507ad5ztx10sl`.
- [Measurement-Accurate Architectural Modeling in Three.js](procedural-building/measurement-accurate-architecture.md) — data-driven, to-scale plan/elevation editors, dimensions, snapping, and validation. Adjacent rather than strictly procedural; useful for building-editor workflows. Source skill `cmue6r1qw0as707ad26gsizq9`.

## Gameplay and game feel

- [Third-Person Platformer Game Feel](gameplay/platformer-game-feel.md) — movement curves, jump forgiveness, ledge traversal, cameras, contextual interactions. Source skill `cmu3jgwla01lw07adabopxymw`.

## Browser rendering and WebGPU

- [Three.js Browser Game Prototyping and Performance](rendering/threejs-game-prototyping.md) — scene setup, camera/controller patterns, batching, responsive render quality, single-file bundling, and headless verification. Source skill `cmu3jgy8j01ny07adxk47q8jv`.
- [Three.js Rendering Performance and GPU-Frugal Defaults](rendering/threejs-rendering-performance.md) — broader draw-call/material/shadow/resolution tuning and practical frame pacing. It overlaps with the prototyping guide but carries distinct GPU-budget and field-tested advice. Source skill `cmu3jgmxs01kc07adwelapxkk`.
- [vgpu WebGPU and Three.js TSL](rendering/vgpu-webgpu-tsl.md) — WGSL modules, the vgpu API, TSL integration, diagnostics, and shader testing. Source skill `cmuewdrl700fw06adhiopu1zy`.

## Browser testing

- [agent-browser for Web and Three.js Testing](testing/agent-browser-threejs-testing.md) — CLI sessions, deterministic canvas interaction, WebGPU checks, screenshots, and test hooks. Source skill `cmumlsr6m08zl07adnacecmi9`.

## Helper scripts

- `tools/platformer/` — jump-arc calculator and movement-tuning calculator.
- `tools/rendering/` — HTML bundler and browser game verifier.
- `tools/testing/` — raw canvas drag and page-evaluation helpers for agent-browser.
- `tools/architecture/` — floor-plan geometry computation and schema validation.

See [Tools README](tools/README.md) for intended usage and source mapping. Source skill docs contain broader references and examples; these files are an organized extraction, with the two near-duplicate rendering guides deliberately kept distinct.
