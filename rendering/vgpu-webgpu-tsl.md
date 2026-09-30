# vgpu WebGPU and Three.js TSL

**Source skill:** `cmuewdrl700fw06adhiopu1zy`  
**Focus:** Typed WGSL modules, vgpu's browser/headless/mock APIs, and using WGSL helpers from Three.js TSL node materials.

## Conceptual model

`vgpu` resolves `.wgsl` import graphs, prunes unreachable declarations and exposes explicit rendering APIs. In a Three.js integration, Three.js still owns the renderer, scene and render loop; `vgpu/three`'s `tslExports()` bridges exported WGSL helper functions into TSL nodes. Imported WGSL modules are pure helpers: resource bindings belong in the entry module, not in imported helpers.

## API surfaces

- `vgpu`: browser runtime (`init`, `effect`, `draw`, `frame`, `frameLoop`, `surface`, `target`).
- `vgpu/node`: headless Node/Dawn entry points.
- `vgpu/mock`: deterministic test adapter.
- `vgpu/client` / `vgpu/three`: Vite shader plugin and TSL bridge.

The `Gpu` context returned by `init()` is passed explicitly into API calls. `surface()` wraps a canvas; `target()` creates an offscreen surface; `effect()` compiles fullscreen WGSL; `frame()` batches passes; `frameLoop()` provides an animation loop. Dispose headless contexts to stop the Dawn polling loop.

## WGSL module rules

- Imports go before declarations. Use relative, package or configured root aliases.
- Imported modules may export functions, structs, types and constants, but must not own `@group`/`@binding` resources.
- Keep resource bindings in the entry shader. The resolver follows imports, checks module rules, avoids name collisions and tree-shakes unused declarations.
- Exported functions for TSL must be direct `export fn` declarations returning a value. Do not export entry points, void functions, re-export syntax or resource-owning modules.

## Three.js TSL bridge

Configure Vite with `wgslVitePlugin()` and pass the full imported `ShaderSource` artifact to `tslExports()`—not only its `.wgsl` text, because authored-to-minified export metadata is needed. Select the named exports and call them with an object keyed by authored WGSL parameter names; pass TSL nodes or compatible JS numbers. Define a local TypeScript contract for the inputs/exports because the type declaration cannot prove it matches WGSL. Errors carry stable `code` values; match those rather than relying on `instanceof`.

## Validation and diagnostics

- Use `npx vgpu check shader.wgsl`; `--require-validation` makes device validation a strict CI gate.
- Use `npx vgpu doctor` to diagnose headless adapter/render support.
- Use `npx vgpu docs` and `npx vgpu examples` to search/read bundled docs and inspect sample source. Example retrieval does not execute fetched code.
- For a small headless test, render to a small target, read back pixels, compare against expected values and call `gpu.dispose()`.
- For complex shader logic, encode intermediate values into a tiny render target and compare to a CPU reference within the output format's quantization tolerance.

## Frequent failure classes

| Symptom/code family | Likely fix |
|---|---|
| Import order, unresolved export, import cycle | Move imports to the top, correct the symbol/path, or break the cycle. |
| Imported-module binding error | Move all resources to the entry WGSL file; export helpers/types only. |
| Binding never set / incompatible resource | Set each reflected binding with its correct value/resource type. |
| Ownership flip | Choose JS-value or user-resource ownership on first `set()` and keep it consistent. |
| Stale bundle or incompatible target | Re-record after resource identity/signature changes. |
| `tslExports()` missing exports | Pass full `ShaderSource`; check direct export names and function signatures. |
| No WebGPU adapter | Run `vgpu doctor`; choose mock/software/real adapter according to test intent. |

## Three.js-specific cautions

- For Vite + Three.js TSL, the source reference recommends `wgslVitePlugin({ minify: true })` and `tslExports()` with a handwritten type contract.
- Shader loaders may skip device validation during bundling; run the CLI validation as a separate check.
- Keep color-space conversions explicit and consistent. Three.js `Color.setHex` already converts sRGB inputs; applying a second sRGB-to-linear conversion can cause incorrect dark/blue tints.
- The source skill notes that current vgpu 0.5.0 supports a broad Three.js 0.180–0.199 range; prefer the installed package's documentation/version over stale examples.

## API details worth keeping close

- `surface(gpu, canvas, { dpr: [1, 2] })` clamps canvas DPR; `texelSize` and `onResize()` support size-dependent uniforms. `target(gpu, { size, format })` creates an offscreen target; `color.read({ mipLevel: 0, region: "all" })` returns tightly packed row-major RGBA bytes.
- `effect()` supplies a fullscreen vertex stage and UV input. The first `set()` call establishes binding ownership: plain JS values are library-owned and updated in place; GPU resources are caller-owned. Switching ownership later raises `VGPU-R1-OWNERSHIP-FLIP`.
- `frame()` makes multi-pass order explicit; `frameLoop()` is the animation helper. `gpu.dispose()` matters in Node so Dawn polling stops and the process exits.
- The standard WGSL library includes hash/PCG, Perlin and simplex noise, Voronoi, color transforms/tonemapping, math, sampling sequences and fullscreen helpers. Simplex has a steeper/larger output range than Perlin at the same scale; the source suggests roughly 0.4–0.5 input scaling when migrating comparable patterns.
- `tslExports()` accepts only directly exported, value-returning helper functions. Function inputs are a single object keyed by authored names. Imported helpers cannot own resources; only the entry module declares bindings. Use one shared `tslExports(module)` include and select the exports for the material.
- Bundler loaders perform resolution but do not necessarily validate against a device. Run `npx vgpu check --require-validation` separately in CI when actual device validation is mandatory.

## CLI and diagnostics details

`npx vgpu docs` searches its bundled documentation offline (`ls`, `cat`, `grep`, `find`, `path`, `symbols`); `npx vgpu examples` searches and reads vetted example source without executing it. `npx vgpu doctor` checks adapter/render health and suggests fixes. Use small offscreen targets for headless tests; compare pixel values with quantization tolerance and always dispose the GPU context.

Typical error fixes: resolve import order/path/export/cycle problems before validation; keep resources out of imported modules; set every reflected binding with a matching value/resource; do not change a binding’s ownership type after the first `set()`; and rebuild a recorded bundle when resource identity or render signature changes.
