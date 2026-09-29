#!/usr/bin/env python3
"""
Bundle a JavaScript/TypeScript entry point and an HTML template into a
single self-contained HTML file using esbuild.

Reads a JS/TS entry file, bundles + minifies it with esbuild, then injects
the result into an HTML template (with optional CSS) to produce one file.

Usage:
  python3 bundle_game.py <entry.js> [--html template.html] [--css style.css] [--output game.html]

If no HTML template is provided, a minimal default is used.
If no CSS file is provided, inline styles are used.
The output file is fully self-contained — no external dependencies.

Requires: esbuild installed (npm install -g esbuild or npx esbuild)
Requires: Python 3.6+
"""
import os
import sys
import json
import argparse
import subprocess
import tempfile

DEFAULT_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>__TITLE__</title>
__CSS__
</head>
<body>
__JS__
</body>
</html>"""

DEFAULT_CSS = """  <style>
    body { margin: 0; overflow: hidden; background: #000; }
    canvas { display: block; }
  </style>"""


def find_esbuild():
    """Find the esbuild binary. Tries 'esbuild' on PATH, then 'npx esbuild'."""
    # Try direct esbuild binary first
    try:
        result = subprocess.run(
            ["esbuild", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return ["esbuild"]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Fall back to npx esbuild
    return ["npx", "esbuild"]


def run_esbuild(entry_path, minify=True, sourcemap=False):
    """Run esbuild on the entry file, returning bundled JS as a string."""
    esbuild_cmd = find_esbuild()
    
    # Build esbuild command
    cmd = esbuild_cmd + [
        entry_path,
        "--bundle",
        "--format=iife",
        "--target=es2020",
        f"--minify={'true' if minify else 'false'}",
    ]
    
    if sourcemap:
        cmd.append("--sourcemap=inline")
    
    # Add loaders for common binary assets
    cmd.extend([
        "--loader:.glb=dataurl",
        "--loader:.gltf=dataurl",
        "--loader:.png=dataurl",
        "--loader:.jpg=dataurl",
        "--loader:.jpeg=dataurl",
        "--loader:.webp=dataurl",
    ])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            return None, result.stderr.strip()
        return result.stdout, None
    except subprocess.TimeoutExpired:
        return None, "esbuild timed out after 60 seconds"
    except FileNotFoundError:
        return None, "esbuild not found. Install with: npm install -g esbuild"
    except Exception as e:
        return None, str(e)


def build_html(js_code, css_code, title="Game Prototype"):
    """Inject JS and CSS into the HTML template."""
    # Escape </script> inside the JS to prevent premature closing
    js_escaped = js_code.replace("</script>", "<\\/script>")
    js_tag = f"  <script>\n{js_escaped}\n  </script>"
    
    css_block = css_code if css_code else DEFAULT_CSS
    
    html = DEFAULT_HTML_TEMPLATE
    html = html.replace("__TITLE__", title)
    html = html.replace("__CSS__", css_block)
    html = html.replace("__JS__", js_tag)
    
    return html


def main():
    parser = argparse.ArgumentParser(
        description="Bundle JS/TS + HTML into a single self-contained HTML file using esbuild."
    )
    parser.add_argument("entry", help="Path to JS/TS entry file (e.g., main.js)")
    parser.add_argument("--html", help="Path to custom HTML template (optional)")
    parser.add_argument("--css", help="Path to CSS file to inline (optional)")
    parser.add_argument("--output", "-o", default="game.html", help="Output HTML file path")
    parser.add_argument("--title", default="Game Prototype", help="HTML title")
    parser.add_argument("--no-minify", action="store_true", help="Disable JS minification")
    parser.add_argument("--sourcemap", action="store_true", help="Include inline sourcemap")
    
    args = parser.parse_args()
    
    # Validate entry file
    if not os.path.isfile(args.entry):
        print(json.dumps({"error": f"Entry file not found: {args.entry}"}))
        return
    
    # Read custom HTML template if provided
    html_template = None
    if args.html:
        if not os.path.isfile(args.html):
            print(json.dumps({"error": f"HTML template not found: {args.html}"}))
            return
        with open(args.html, "r") as f:
            html_template = f.read()
    
    # Read CSS if provided
    css_code = None
    if args.css:
        if not os.path.isfile(args.css):
            print(json.dumps({"error": f"CSS file not found: {args.css}"}))
            return
        with open(args.css, "r") as f:
            css_code = f"  <style>\n{f.read()}\n  </style>"
    
    # Step 1: Bundle JS with esbuild
    print(f"Bundling {args.entry} with esbuild...", file=sys.stderr)
    js_code, error = run_esbuild(
        args.entry,
        minify=not args.no_minify,
        sourcemap=args.sourcemap
    )
    
    if error:
        print(json.dumps({"error": f"esbuild failed: {error}"}))
        return
    
    js_size = len(js_code.encode('utf-8'))
    print(f"  Bundled JS: {js_size:,} bytes ({'minified' if not args.no_minify else 'unminified'})", file=sys.stderr)
    
    # Step 2: Build HTML
    if html_template:
        # Use custom template — replace placeholders if they exist
        html_output = html_template
        js_escaped = js_code.replace("</script>", "<\\/script>")
        html_output = html_output.replace("__JS__", f"<script>{js_escaped}</script>")
        if css_code:
            html_output = html_output.replace("__CSS__", css_code)
        html_output = html_output.replace("__TITLE__", args.title)
    else:
        html_output = build_html(js_code, css_code, args.title)
    
    # Step 3: Write output
    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html_output)
    
    total_size = os.path.getsize(output_path)
    print(json.dumps({
        "status": "success",
        "output": output_path,
        "js_bytes": js_size,
        "total_bytes": total_size,
        "minified": not args.no_minify,
        "sourcemap": args.sourcemap,
    }, indent=2))
    
    print(f"  Output: {output_path} ({total_size:,} bytes total)", file=sys.stderr)


if __name__ == "__main__":
    main()