#!/usr/bin/env python3
"""
Headless verification of a browser canvas game using Playwright.

Boots a headless Chromium browser, loads the game URL, waits for the canvas
to render, dispatches keyboard events (WASD, Space, etc.), and verifies that
the game responds correctly by reading exposed game state from the page.

The game must expose state on `window` for assertions, e.g.:
  window.__playerPosition = { x, y, z }
  window.__gameState = { started, paused, gameOver }

Usage:
  python3 verify_game.py <url> [options]

Options:
  --key <KeyW> --hold <ms>   Dispatch a keydown, hold for N ms, then keyup
  --press <Space>            Quick press (keydown + keyup)
  --check <expression>       JS expression to evaluate for pass/fail
  --timeout <ms>             Max wait for canvas boot (default 10000)
  --screenshot <path>        Save a screenshot to path

Example:
  python3 verify_game.py http://localhost:3000/game.html \
    --press Space \
    --key KeyW --hold 500 \
    --check "window.__playerPosition.z < -0.01"

Requires: playwright installed (pip install playwright && playwright install chromium)
"""
import os
import sys
import json
import argparse
import subprocess

# Check if playwright is available
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


def check_playwright_installed():
    """Check if playwright Python package and browser are installed."""
    if not HAS_PLAYWRIGHT:
        return False, "playwright package not found. Install with: pip install playwright && playwright install chromium"
    
    # Check if chromium browser binary exists
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True, None
    except Exception as e:
        return False, f"Playwright browser not available: {e}. Run: playwright install chromium"


def verify_game(url, key_sequences=None, checks=None, timeout_ms=10000, screenshot_path=None):
    """
    Boot a headless browser, load the game, dispatch keyboard events,
    and run verification checks.
    
    Args:
        url: URL of the game HTML file
        key_sequences: List of dicts: [{"type": "press"|"hold", "key": "KeyW", "hold_ms": 500}, ...]
        checks: List of JS expressions to evaluate (must return truthy for pass)
        timeout_ms: Max wait for canvas to render
        screenshot_path: Optional path to save screenshot
    
    Returns:
        dict with status, details, and check results
    """
    results = {
        "url": url,
        "booted": False,
        "canvas_found": False,
        "canvas_has_content": False,
        "checks": [],
        "keys_dispatched": [],
        "screenshot": None,
        "errors": []
    }
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--enable-unsafe-swiftshader']  # Software WebGL for CI
            )
            page = browser.new_page()
            
            # Navigate to the game
            page.goto(url, wait_until='networkidle', timeout=timeout_ms)
            results["booted"] = True
            
            # Wait for canvas element to appear
            try:
                page.wait_for_selector('canvas', timeout=timeout_ms)
                results["canvas_found"] = True
            except Exception as e:
                results["errors"].append(f"Canvas not found: {e}")
                browser.close()
                return results
            
            # Wait for canvas to have rendered content (not blank)
            try:
                page.wait_for_function(
                    """() => {
                        const canvas = document.querySelector('canvas');
                        if (!canvas) return false;
                        try {
                            const dataUrl = canvas.toDataURL();
                            return dataUrl.length > 1000;
                        } catch(e) { return false; }
                    }""",
                    timeout=timeout_ms
                )
                results["canvas_has_content"] = True
            except Exception as e:
                results["errors"].append(f"Canvas appears blank or WebGL not ready: {e}")
                # Continue anyway — some games render on first interaction
            
            # Click canvas to ensure focus for keyboard events
            page.click('canvas')
            
            # Dispatch keyboard sequences
            if key_sequences:
                for seq in key_sequences:
                    key = seq.get("key", "")
                    if not key:
                        continue
                    
                    if seq.get("type") == "hold":
                        hold_ms = seq.get("hold_ms", 500)
                        page.keyboard.down(key)
                        page.wait_for_timeout(hold_ms)
                        page.keyboard.up(key)
                        results["keys_dispatched"].append({
                            "key": key, "type": "hold", "duration_ms": hold_ms
                        })
                    else:  # press
                        page.keyboard.press(key)
                        page.wait_for_timeout(100)
                        results["keys_dispatched"].append({
                            "key": key, "type": "press"
                        })
            
            # Run verification checks
            if checks:
                for check_expr in checks:
                    try:
                        value = page.evaluate(check_expr)
                        results["checks"].append({
                            "expression": check_expr,
                            "passed": bool(value),
                            "value": value
                        })
                    except Exception as e:
                        results["checks"].append({
                            "expression": check_expr,
                            "passed": False,
                            "error": str(e)
                        })
            
            # Take screenshot if requested
            if screenshot_path:
                try:
                    page.screenshot(path=screenshot_path)
                    results["screenshot"] = os.path.abspath(screenshot_path)
                except Exception as e:
                    results["errors"].append(f"Screenshot failed: {e}")
            
            browser.close()
    
    except Exception as e:
        results["errors"].append(f"Browser error: {e}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Headless verification of a browser canvas game via Playwright."
    )
    parser.add_argument("url", help="URL of the game HTML (e.g., http://localhost:3000/game.html)")
    parser.add_argument("--key", action="append", nargs=2, metavar=("KEY", "HOLD_MS"),
                        help="Hold a key for N ms (e.g., --key KeyW 500). Can repeat.")
    parser.add_argument("--press", action="append", metavar="KEY",
                        help="Quick press a key (e.g., --press Space). Can repeat.")
    parser.add_argument("--check", action="append", metavar="EXPR",
                        help="JS expression to evaluate for pass/fail (must return truthy). Can repeat.")
    parser.add_argument("--timeout", type=int, default=10000,
                        help="Max wait for canvas boot in ms (default 10000)")
    parser.add_argument("--screenshot", metavar="PATH",
                        help="Save a screenshot to the given path")
    
    args = parser.parse_args()
    
    # Check playwright availability
    available, error = check_playwright_installed()
    if not available:
        print(json.dumps({
            "error": error,
            "hint": "Install with: pip install playwright && playwright install chromium"
        }))
        return
    
    # Build key sequences
    key_sequences = []
    if args.key:
        for key, hold_ms in args.key:
            key_sequences.append({
                "type": "hold",
                "key": key,
                "hold_ms": int(hold_ms)
            })
    if args.press:
        for key in args.press:
            key_sequences.append({
                "type": "press",
                "key": key
            })
    
    # Run verification
    results = verify_game(
        url=args.url,
        key_sequences=key_sequences,
        checks=args.check,
        timeout_ms=args.timeout,
        screenshot_path=args.screenshot
    )
    
    # Determine overall status
    all_checks_passed = all(c.get("passed", False) for c in results["checks"]) if results["checks"] else True
    has_errors = len(results["errors"]) > 0
    
    if has_errors and not results["canvas_found"]:
        overall = "fail"
    elif not all_checks_passed:
        overall = "fail"
    elif results["canvas_found"] and results["canvas_has_content"]:
        overall = "pass"
    else:
        overall = "incomplete"
    
    output = {
        "status": overall,
        **results
    }
    
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()