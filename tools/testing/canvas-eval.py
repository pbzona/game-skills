#!/usr/bin/env python3
"""Assert on a three.js/WebGL canvas by evaluating JS in the live page via agent-browser.

The canvas itself is opaque to the accessibility tree and click-testing; the way to
test a three.js scene is `eval` against the app's own objects. This script evaluates
an arbitrary JS expression (or a named assertion: frames, backend, world2screen,
pixel) and prints the JSON envelope from agent-browser.

Requires: agent-browser on PATH (or AGENT_BROWSER_BIN env var) and an open session.

Usage:
  # Did the render loop actually run? (app must set on-demand frame hooks, or
  # expose its renderer; see SKILL.md "On-demand frame hooks")
  canvas-eval.py frames

  # Which backend did three.js actually get?
  canvas-eval.py backend

  # Project a world point to screen coordinates (perspective camera assumed):
  canvas-eval.py world2screen --camera camera --x 0 --y 0 --z -5

  # Arbitrary expression:
  canvas-eval.py expr "scene.children.length"

  # Raw passthrough of any JS (parsed from stdin) with --json output:
  echo "(1+2)" | canvas-eval.py stdin
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

# Paths probed for a three.js renderer instance. Adjust if your app stores it
# elsewhere (e.g. window.app.renderer).
RENDERER_PROBE = """
  window.__renderer || window.renderer || window.__three_renderer ||
  (window.app && window.app.renderer) || (window.__APP__ && window.__APP__.renderer)
"""

FRAMES_SNIPPET = """
(async () => {
  const r = %RENDERER%;
  if (r) {
    const info = r.info;
    const n = (info && info.render && info.render.frame) || 0;
    return { source: 'renderer.info.render.frame', frames: n };
  }
  // Fallback: hook rAF and count one frame.
  const n = await new Promise(res => {
    let done = false;
    requestAnimationFrame(() => { done = true; res(1); });
    setTimeout(() => { if (!done) res(0); }, 1000);
  });
  return { source: 'rAF tick', frames: n, note: 'no renderer object found; rAF fired (0 = page frozen)' };
})()
"""

BACKEND_SNIPPET = """
(async () => {
  const out = {};
  const r = %RENDERER%;
  if (r) {
    out.renderer = r.backend
      ? 'three.js backend: ' + r.backend.constructor.name
      : 'renderer found (no .backend -> likely WebGLRenderer)';
    if (r.info && r.info.render) out.frames = r.info.render.frame;
  }
  if (!navigator.gpu) {
    out.webgpu = 'unavailable (navigator.gpu missing: not a secure context or old Chrome)';
  } else {
    for (let i = 0; i < 2; i++) {
      try {
        const a = await Promise.race([
          navigator.gpu.requestAdapter(),
          new Promise(res => setTimeout(() => res(null), 3000)),
        ]);
        if (a) {
          const v = (a.info && (a.info.vendor || a.info.description)) || '';
          out.webgpu = 'available' + (v ? ' (' + v + ')' : '');
          break;
        }
        out.webgpu = 'requestAdapter() null - relaunch with --webgpu';
      } catch (e) {
        out.webgpu = 'requestAdapter error: ' + e.message;
      }
    }
  }
  const c = document.querySelector('canvas');
  if (c) {
    const gl = c.getContext('webgl2') || c.getContext('webgl');
    if (gl) out.canvasContext = 'webgl';
    else out.canvasContext = c.getContext('webgpu') ? 'webgpu' : 'none';
  }
  return out;
})()
"""

WORLD2SCREEN_SNIPPET = """
(() => {
  const _cam = %CAM%;
  if (!_cam || !_cam.isPerspectiveCamera) {
    return { error: 'perspective camera not found at %CAMDESC%; pass --camera <expr>' };
  }
  // Derive THREE.Vector3 from the camera's position so we don't need a global THREE.
  const V3 = _cam.position.constructor;
  const wp = new V3(%X%, %Y%, %Z%);
  if (!wp || typeof wp.project !== 'function') {
    return { error: 'cannot project: need window.THREE or camera.position.constructor '
      + 'to be THREE.Vector3; got ' + (V3 && V3.name) + '. For a mock/standalone camera, '
      + 'pass --camera pointing at a real THREE.PerspectiveCamera' };
  }
  wp.project(_cam);
  const canvas = document.querySelector('canvas');
  const w = (canvas && canvas.clientWidth) || window.innerWidth;
  const h = (canvas && canvas.clientHeight) || window.innerHeight;
  return {
    screen: { x: Math.round((wp.x * 0.5 + 0.5) * w), y: Math.round((-wp.y * 0.5 + 0.5) * h) },
    ndc: { x: wp.x, y: wp.y, z: wp.z },
    canvas: { width: w, height: h },
  };
})()
"""

PIXEL_SNIPPET = """
(() => {
  const c = document.querySelector('canvas');
  if (!c) return { error: 'no canvas' };
  try {
    const gl = c.getContext('webgl2') || c.getContext('webgl');
    if (gl && gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== 0) {
      const px = new Uint8Array(4);
      gl.readPixels(gl.drawingBufferWidth >> 1, gl.drawingBufferHeight >> 1, 1, 1,
                    gl.RGBA, gl.UNSIGNED_BYTE, px);
      return { note: 'webgl readPixels center pixel', rgba: Array.from(px) };
    }
  } catch (e) { /* fall through to 2d */ }
  try {
    const ctx = c.getContext('2d');
    if (ctx) {
      const d = ctx.getImageData(c.width >> 1, c.height >> 1, 1, 1).data;
      return { note: '2d center pixel', rgba: Array.from(d) };
    }
  } catch (e) { /* tainted canvas etc. */ }
  return { error: 'canvas not pixel-readable (WebGPU or tainted); use agent-browser screenshot instead' };
})()
"""


def fill(tpl, **kw):
    out = tpl
    for k, v in kw.items():
        out = out.replace("%" + k.upper() + "%", v)
    return out


def main():
    p = argparse.ArgumentParser(description="Assert on three.js scenes via agent-browser eval")
    p.add_argument("mode", choices=["frames", "backend", "world2screen", "pixel", "expr", "stdin"])
    p.add_argument("--camera", default="camera",
                   help="JS expression resolving to the THREE.PerspectiveCamera (default: `camera`)")
    p.add_argument("--x", type=float, default=0.0, dest="wx")
    p.add_argument("--y", type=float, default=0.0, dest="wy")
    p.add_argument("--z", type=float, default=-5.0, dest="wz")
    p.add_argument("expression", nargs="?", default=None,
                   help="JS expression (for `expr` mode)")
    p.add_argument("--session", default=None, help="agent-browser session name")
    p.add_argument("--bin", default=os.environ.get("AGENT_BROWSER_BIN", "agent-browser"),
                   help="agent-browser binary (default: PATH or AGENT_BROWSER_BIN)")
    args = p.parse_args()

    if args.mode == "expr" and not args.expression:
        p.error("expr mode requires a JS expression")
    if args.mode == "stdin" and sys.stdin.isatty():
        p.error("stdin mode requires piped JS")

    ab = shutil.which(args.bin) or args.bin
    session_args = ["--session", args.session] if args.session else []

    if args.mode == "frames":
        js = fill(FRAMES_SNIPPET, renderer=RENDERER_PROBE.strip())
    elif args.mode == "backend":
        js = fill(BACKEND_SNIPPET, renderer=RENDERER_PROBE.strip())
    elif args.mode == "world2screen":
        js = fill(WORLD2SCREEN_SNIPPET, cam=args.camera,
                  camdesc=args.camera,
                  x=repr(args.wx), y=repr(args.wy), z=repr(args.wz))
    elif args.mode == "pixel":
        js = PIXEL_SNIPPET
    elif args.mode == "expr":
        js = f"(() => ({args.expression}))()"
    else:  # stdin
        js = sys.stdin.read()

    stdin_mode = args.mode == "stdin"
    cmd = [ab] + session_args + (["eval", "--stdin"] if stdin_mode else ["eval", js])
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          input=js if stdin_mode else None, timeout=60)
    out = proc.stdout.strip()

    def fail(msg):
        print(json.dumps({"error": msg}))
        sys.exit(1)

    # agent-browser eval prints the bare JS value of the expression, which is
    # usually JSON-parseable (numbers, objects, quoted strings). Unquoted string
    # results (e.g. `webgl (ANGLE Metal...)`) get wrapped so output is always JSON.
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError:
        parsed = out if out else None

    if isinstance(parsed, dict) and "error" in parsed:
        fail(parsed["error"])
    if proc.returncode != 0:
        fail((proc.stderr or out or "eval failed").strip()[:300])
    if parsed is None or out == "":
        fail("eval produced no output")
    print(json.dumps(parsed))
    sys.exit(0)


if __name__ == "__main__":
    main()