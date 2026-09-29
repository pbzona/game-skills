#!/usr/bin/env python3
"""Drive a three.js/WebGL/WebGPU canvas with raw mouse events via the agent-browser CLI.

Wraps the agent-browser CLI to do what element clicks cannot: press the button on a
canvas, move across it in steps, and release — the sequence canvas apps (three.js
OrbitControls, drag controls, paint apps) actually respond to.

Requires: agent-browser on PATH (or AGENT_BROWSER_BIN env var) and an open session
(`agent-browser open <url>`).

Usage:
  # Drag inside a canvas (all coordinates are canvas-local; negative/oversized
  # values are clamped to the canvas edge):
  canvas-drag.py --selector canvas --from 100,100 --to 300,250 --steps 12

  # Click at a point:
  canvas-drag.py --from 100,100

  # Smooth / human-like drag:
  canvas-drag.py --from 100,100 --to 300,250 --human --seed 42

  # Against a named session:
  canvas-drag.py --session mytest --from 10,10 --to 200,200
"""
import argparse
import json
import os
import shutil
import subprocess
import sys


def run(ab, args, timeout=30):
    proc = subprocess.run(
        [ab] + args, capture_output=True, text=True, timeout=timeout
    )
    return proc.returncode, proc.stdout, proc.stderr


def parse_output(out):
    out = out.strip()
    if not out:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}


def clamp(v, lo, hi):
    return max(lo, min(v, hi))


def main():
    p = argparse.ArgumentParser(description="Raw mouse drag/click on a canvas element")
    p.add_argument("--session", default=None, help="agent-browser session name")
    p.add_argument("--selector", default="canvas",
                   help="CSS selector of the canvas (default: first <canvas>)")
    p.add_argument("--from", dest="src", required=True, metavar="X,Y",
                   help="start point, canvas-local coordinates")
    p.add_argument("--to", dest="dst", default=None, metavar="X,Y",
                   help="end point; omit for a click at --from")
    p.add_argument("--steps", type=int, default=10,
                   help="mouse-move steps between start and end (default 10)")
    p.add_argument("--button", default="left", choices=["left", "right", "middle"])
    p.add_argument("--human", action="store_true",
                   help="curved eased movement (agent-browser --human)")
    p.add_argument("--seed", type=int, default=None,
                   help="seed for --human reproducible curves")
    p.add_argument("--bin", default=os.environ.get("AGENT_BROWSER_BIN", "agent-browser"),
                   help="agent-browser binary (default: PATH or AGENT_BROWSER_BIN)")
    args = p.parse_args()

    ab = shutil.which(args.bin) or args.bin
    session_args = ["--session", args.session] if args.session else []

    def pt(s):
        x, y = s.split(",")
        return int(x), int(y)

    sx, sy = pt(args.src)

    # Locate the canvas and its on-screen box so canvas-local coords become page coords.
    box = None
    if args.selector:
        code, out, err = run(ab, session_args + ["--json", "get", "box", args.selector])
        data = parse_output(out).get("data") or {}
        box = data if "x" in data else None
        if box is None:
            print(json.dumps({
                "error": f"cannot locate element {args.selector!r} "
                         f"(run `agent-browser open <url>` first)",
                "stderr": (err or out).strip()[:200],
            }))
            sys.exit(1)
        if box.get("width", 0) <= 0:
            print(json.dumps({"error": f"{args.selector!r} has zero size"}))
            sys.exit(1)

    if box:
        ox, oy = box["x"], box["y"]
        cw, ch = box["width"], box["height"]
        sx = clamp(ox + sx, ox, ox + cw)
        sy = clamp(oy + sy, oy, oy + ch)

    def mouse(*rest):
        code, out, err = run(ab, session_args + ["--json", "mouse"] + list(rest))
        return parse_output(out)

    # Move to start BEFORE pressing so apps see a normal hover-then-press sequence.
    r = mouse("move", str(sx), str(sy))
    if not r.get("success"):
        print(json.dumps({"error": "mouse move failed", "detail": r}))
        sys.exit(1)

    if not args.dst:
        mouse("down", args.button)
        mouse("up", args.button)
        print(json.dumps({"ok": True, "action": "click", "x": sx, "y": sy}))
        return

    ex, ey = pt(args.dst)
    if box:
        ex = clamp(ox + ex, ox, ox + cw)
        ey = clamp(oy + ey, oy, oy + ch)

    move = ["move", str(ex), str(ey)]
    if args.human:
        move += ["--human"]
        if args.seed is not None:
            move += ["--seed", str(args.seed)]
    else:
        move += ["--duration", "250", "--steps", str(args.steps)]

    for cmd in (["down", args.button], move, ["up", args.button]):
        r = mouse(*cmd)
        if not r.get("success"):
            print(json.dumps({"error": f"mouse {' '.join(cmd[:1])} failed", "detail": r}))
            sys.exit(1)

    print(json.dumps({
        "ok": True,
        "action": "drag",
        "from": [sx, sy],
        "to": [ex, ey],
        "steps": args.steps,
        "canvas": args.selector,
    }))


if __name__ == "__main__":
    main()