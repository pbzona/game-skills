# agent-browser CLI for Web and Three.js Testing

**Source skill:** `cmumlsr6m08zl07adnacecmi9`  
**Focus:** Browser automation for web apps and opaque WebGL/WebGPU canvases, using Vercel Labs' `agent-browser` CLI.

## Core workflow

The standard loop is open → snapshot/ref lookup → act → inspect errors/screenshot. CLI examples:

```sh
agent-browser open http://localhost:5173
agent-browser snapshot -i
agent-browser click @e2
agent-browser get text @e1
agent-browser screenshot page.png
agent-browser errors
agent-browser close
```

Use isolated named sessions for parallel sites, and supply launch flags on the initial launch (a running daemon may ignore new launch flags). Prefer waits tied to a meaningful state (`--fn`, text, URL, selector) over `networkidle` for apps with polling or sockets.

## Canvas and editor interaction

DOM locators cannot directly describe objects in a Three.js canvas. Evaluate app state or project a world-space point through the live camera to screen pixels, then use raw mouse movement/down/up. For drag interactions, use a sequence of move → down → stepped move → up; DOM click synthesis is insufficient for many canvas tools. Add a URL/debug hook for deterministic stepping, readiness, render counts and state inspection when you control the app.

Registered helpers:

- [`../tools/testing/canvas-drag.py`](../tools/testing/canvas-drag.py) converts canvas-relative drag coordinates to page coordinates and sends raw mouse events.
- [`../tools/testing/canvas-eval.py`](../tools/testing/canvas-eval.py) supports JSON checks for frame counts, WebGPU backend, world-to-screen coordinates, pixels and arbitrary JS expressions.

## WebGPU validation

Use `agent-browser --webgpu` for a WebGPU launch preset and verify an actual rendered frame/backend; `WebGPURenderer` can silently fall back to WebGL2. WebGPU requires a secure origin (`https`, `localhost`, or `file`). Software SwiftShader helps in Linux CI but has throughput/capture limits. Some headless platform/browser combinations render successfully but capture black canvas screenshots; in-page readback or a headed capture may be needed.

## Evidence and diagnostics

- Check uncaught exceptions after navigation and important actions.
- Capture screenshots only after a readiness/rendered-frame condition.
- Prefer app-specific readback or screenshot comparison for WebGPU; `drawImage` cannot reliably inspect a WebGPU canvas.
- Use `--if-changed` and a tolerance threshold for animated scenes, and record console/network details when failures reproduce.

## Environment notes

The `agent-browser` install downloads a compatible Chrome build; use `doctor` for setup diagnostics. Supply an alternate Chromium via `--executable-path` if installation/network policy prevents fetching its browser. On Linux, missing Vulkan/Mesa components can prevent software WebGPU; use the CLI's own diagnostics before changing the environment.
