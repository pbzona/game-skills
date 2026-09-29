#!/usr/bin/env python3
"""Calculate movement tuning values for platformer character controllers.

Given desired time-to-max-speed, max speed, and tuning style, derives
acceleration, friction, and curve parameters for both linear and
non-linear (ADSR-inspired) velocity profiles. Also computes air control
values, braking deceleration, and provides feel-quality checks.

Usage:
  python movement_tuning.py [options]

Options:
  --max-speed FLOAT       Max movement speed in units/s (default: 10.0)
  --time-to-max FLOAT     Time to reach max speed in seconds (default: 0.08)
  --time-to-stop FLOAT    Time to come to rest from max speed (default: 0.06)
  --curve STRING          Velocity curve type: "linear" or "nonlinear" (default: "nonlinear")
  --air-control FLOAT     Air control as fraction of ground (0.5-1.0) (default: 0.8)
  --brake-mult FLOAT      Braking deceleration as multiple of accel (default: 1.0)
  --sprint-mult FLOAT     Sprint speed multiplier (default: 1.0 = no sprint)
  --unit-name STRING      Name of the unit (default: "units")
  --style STRING          Preset style: "arcade", "momentum", "action", "heavy" (default: "action")

Examples:
  python movement_tuning.py --max-speed 10 --time-to-max 0.08 --style action
  python movement_tuning.py --style momentum
  python movement_tuning.py --max-speed 12 --time-to-max 0.12 --curve linear --unit-name "uu"
"""
import argparse
import json
import math
import sys


# ─── Style Presets ───────────────────────────────────────────────────────────
STYLES = {
    "arcade": {
        "description": "Snappy, responsive — instant-ish acceleration, quick stops",
        "max_speed": 10.0,
        "time_to_max": 0.05,
        "time_to_stop": 0.04,
        "curve": "nonlinear",
        "air_control": 1.0,
        "brake_mult": 1.5,
        "sprint_mult": 1.0,
    },
    "action": {
        "description": "Balanced — responsive but with some weight and expressiveness",
        "max_speed": 10.0,
        "time_to_max": 0.08,
        "time_to_stop": 0.06,
        "curve": "nonlinear",
        "air_control": 0.8,
        "brake_mult": 1.0,
        "sprint_mult": 1.0,
    },
    "momentum": {
        "description": "Sonic-style — longer acceleration ramps, maintain speed through skill",
        "max_speed": 15.0,
        "time_to_max": 0.18,
        "time_to_stop": 0.15,
        "curve": "nonlinear",
        "air_control": 0.6,
        "brake_mult": 0.7,
        "sprint_mult": 1.0,
    },
    "heavy": {
        "description": "Weighty, deliberate — like Assassin's Creed, prioritizes animation fidelity",
        "max_speed": 8.0,
        "time_to_max": 0.15,
        "time_to_stop": 0.12,
        "curve": "nonlinear",
        "air_control": 0.5,
        "brake_mult": 0.8,
        "sprint_mult": 1.0,
    },
}


def calculate_movement_tuning(
    max_speed: float,
    time_to_max: float,
    time_to_stop: float,
    curve: str,
    air_control: float,
    brake_mult: float,
    sprint_mult: float,
    unit_name: str = "units",
) -> dict:
    """Calculate movement tuning values from designer targets.

    Args:
        max_speed: Maximum ground movement speed in units/s.
        time_to_max: Time to accelerate from 0 to max speed in seconds.
        time_to_stop: Time to decelerate from max speed to 0 in seconds.
        curve: "linear" or "nonlinear" velocity profile.
        air_control: Air acceleration as fraction of ground (0.5–1.0).
        brake_mult: Braking deceleration as multiple of acceleration.
        sprint_mult: Sprint speed as multiple of max_speed (1.0 = no sprint).
        unit_name: Name of distance unit for display.

    Returns:
        Dictionary with all computed values and implementation guidance.
    """
    # ─── Linear acceleration ─────────────────────────────────────────────────
    # v = a * t → a = v_max / t
    linear_accel = max_speed / time_to_max if time_to_max > 0 else float("inf")
    linear_decel = max_speed / time_to_stop if time_to_stop > 0 else float("inf")
    linear_friction = linear_accel * 0.30  # 25-30% of accel is recommended

    # ─── Non-linear (ADSR-inspired) curve ────────────────────────────────────
    # Attack curve: v = 1 - (1-t)², where t is normalized [0,1]
    # This gives quick initial response, diminishing near max
    # The "effective acceleration" at any point is the derivative: dv/dt = 2(1-t)
    # At t=0 (start): accel = 2 * max_speed / time_to_max (steepest)
    # At t=1 (at max): accel = 0 (eased)
    nonlinear_initial_accel = 2.0 * max_speed / time_to_max if time_to_max > 0 else float("inf")

    # Release curve: v = (1-t)², where t is normalized [0,1] from start of decel
    # Initial decel is steepest: dv/dt = -2(1-t), at t=0: -2 * max_speed / time_to_stop
    nonlinear_initial_decel = 2.0 * max_speed / time_to_stop if time_to_stop > 0 else float("inf")

    # ─── Air control ─────────────────────────────────────────────────────────
    air_accel = linear_accel * air_control if curve == "linear" else nonlinear_initial_accel * air_control
    air_max_speed = max_speed  # Usually same max, but harder to reach due to lower accel

    # ─── Braking deceleration ────────────────────────────────────────────────
    brake_decel = linear_decel * brake_mult if curve == "linear" else nonlinear_initial_decel * brake_mult

    # ─── Sprint ──────────────────────────────────────────────────────────────
    sprint_speed = max_speed * sprint_mult
    sprint_accel = linear_accel * sprint_mult  # Scaled, preserving relative feel

    # ─── Feel quality checks ─────────────────────────────────────────────────
    warnings = []

    if time_to_max > 0.20:
        warnings.append(f"time_to_max ({time_to_max*1000:.0f}ms) is > 200ms — may feel floaty/sluggish for a platformer")
    if time_to_max < 0.03:
        warnings.append(f"time_to_max ({time_to_max*1000:.0f}ms) is < 30ms — essentially instant, may feel too twitchy for casual players")
    if time_to_max > 0.50:
        warnings.append(f"time_to_max ({time_to_max*1000:.0f}ms) is > 500ms — VERY floaty, only suitable for momentum games like Sonic")

    friction_ratio = linear_friction / linear_accel if linear_accel > 0 else 0
    if friction_ratio > 0.40:
        warnings.append(f"friction is {friction_ratio*100:.0f}% of acceleration — may feel like rubber-banding (recommended: 25-30%)")
    if friction_ratio < 0.15:
        warnings.append(f"friction is {friction_ratio*100:.0f}% of acceleration — may feel too slidey (recommended: 25-30%)")

    if air_control > 1.0:
        warnings.append(f"air_control ({air_control:.2f}) > 1.0 — air control exceeds ground, arcs will feel uncommitted")
    if air_control < 0.3:
        warnings.append(f"air_control ({air_control:.2f}) < 0.3 — very limited air steering, jumps will feel locked-in")

    # ─── Frame timing ────────────────────────────────────────────────────────
    frames_to_max_60 = round(time_to_max * 60)
    frames_to_max_30 = round(time_to_max * 30)
    frames_to_stop_60 = round(time_to_stop * 60)
    frames_to_stop_30 = round(time_to_stop * 30)

    # ─── Build result ────────────────────────────────────────────────────────
    result = {
        "designer_targets": {
            "max_speed": f"{max_speed:.1f} {unit_name}/s",
            "time_to_max_speed": f"{time_to_max:.3f} s ({time_to_max*1000:.0f} ms)",
            "time_to_stop": f"{time_to_stop:.3f} s ({time_to_stop*1000:.0f} ms)",
            "curve_type": curve,
            "unit": unit_name,
        },
        "frame_timing": {
            "frames_to_max_60fps": frames_to_max_60,
            "frames_to_max_30fps": frames_to_max_30,
            "frames_to_stop_60fps": frames_to_stop_60,
            "frames_to_stop_30fps": frames_to_stop_30,
        },
    }

    if curve == "linear":
        result["linear_model"] = {
            "acceleration": f"{linear_accel:.2f} {unit_name}/s²",
            "deceleration": f"{linear_decel:.2f} {unit_name}/s²",
            "friction": f"{linear_friction:.2f} {unit_name}/s²",
            "friction_as_pct_of_accel": f"{friction_ratio*100:.1f}%",
            "implementation": "Apply constant acceleration toward input, subtract friction, clamp to max_speed",
        }
    else:
        result["nonlinear_model"] = {
            "curve_formula_attack": "v = 1 - (1-t)², where t = elapsed_time / time_to_max",
            "curve_formula_release": "v = (1-t)², where t = elapsed_time / time_to_stop",
            "initial_acceleration": f"{nonlinear_initial_accel:.2f} {unit_name}/s²",
            "acceleration_at_max": f"0 {unit_name}/s² (eased)",
            "initial_deceleration": f"{nonlinear_initial_decel:.2f} {unit_name}/s²",
            "deceleration_at_rest": f"0 {unit_name}/s² (eased)",
            "implementation": (
                "Track normalized time t on the curve. Each frame:\n"
                "  Attack: t += delta / time_to_max; speed = (1 - (1-t)²) * max_speed\n"
                "  Release: t += delta / time_to_stop; speed = (1-t)² * max_speed\n"
                "  Clamp t to [0,1]. Reset t when input state changes."
            ),
        }

    result["air_control_values"] = {
        "air_acceleration": f"{air_accel:.2f} {unit_name}/s²",
        "air_control_fraction": f"{air_control:.2f}",
        "air_max_speed": f"{air_max_speed:.1f} {unit_name}/s",
        "note": "Lower air control (<1.0) gives committed, punchy arcs. Higher = more steerable but less weight.",
    }

    result["braking"] = {
        "brake_deceleration": f"{brake_decel:.2f} {unit_name}/s²",
        "brake_mult": f"{brake_mult:.2f}×",
        "note": "Higher brake_mult = quicker stops. Very quick stops can feel jarring; conserving momentum feels more natural.",
    }

    if sprint_mult > 1.0:
        result["sprint"] = {
            "sprint_speed": f"{sprint_speed:.1f} {unit_name}/s",
            "sprint_acceleration": f"{sprint_accel:.2f} {unit_name}/s²",
            "note": "Sprint defined as scalar on default values, preserving relative feel when base is adjusted.",
        }

    result["feel_quality_checks"] = warnings if warnings else ["All values within typical feel ranges"]

    result["implementation_notes"] = [
        f"Max speed: {max_speed:.1f} {unit_name}/s — LOCK this early, it determines level scale",
        f"Time to max: {time_to_max*1000:.0f}ms — {'snappy' if time_to_max < 0.08 else 'moderate' if time_to_max < 0.15 else 'momentum-based'}",
        f"Friction: ~{friction_ratio*100:.0f}% of acceleration (recommended: 25-30%)",
        f"Air control: {air_control:.0%} of ground acceleration",
        f"Curve: {curve} — {'instant snap to speed' if curve == 'linear' and time_to_max < 0.03 else 'smooth ramp with expressiveness'}",
        "Camera-relative: compute movement direction from camera forward/right, not world axes",
        "Debug: graph acceleration/velocity over time in screen space to verify smoothness",
    ]

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Calculate movement tuning values for platformer character controllers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python movement_tuning.py --max-speed 10 --time-to-max 0.08 --style action\n"
               "  python movement_tuning.py --style momentum\n"
               "  python movement_tuning.py --max-speed 12 --time-to-max 0.12 --curve linear\n",
    )
    parser.add_argument("--max-speed", type=float, default=None,
                        help="Max movement speed in units/s")
    parser.add_argument("--time-to-max", type=float, default=None,
                        help="Time to reach max speed in seconds")
    parser.add_argument("--time-to-stop", type=float, default=None,
                        help="Time to come to rest from max speed (seconds)")
    parser.add_argument("--curve", type=str, choices=["linear", "nonlinear"], default=None,
                        help="Velocity curve type")
    parser.add_argument("--air-control", type=float, default=None,
                        help="Air control as fraction of ground (0.5-1.0)")
    parser.add_argument("--brake-mult", type=float, default=None,
                        help="Braking deceleration as multiple of accel")
    parser.add_argument("--sprint-mult", type=float, default=None,
                        help="Sprint speed multiplier (1.0 = no sprint)")
    parser.add_argument("--unit-name", type=str, default="units",
                        help='Name of the unit (default: "units")')
    parser.add_argument("--style", type=str, choices=list(STYLES.keys()), default="action",
                        help="Preset style (default: action)")

    args = parser.parse_args()

    # Start with style defaults, override with explicit args
    style = STYLES[args.style]
    max_speed = args.max_speed if args.max_speed is not None else style["max_speed"]
    time_to_max = args.time_to_max if args.time_to_max is not None else style["time_to_max"]
    time_to_stop = args.time_to_stop if args.time_to_stop is not None else style["time_to_stop"]
    curve = args.curve if args.curve is not None else style["curve"]
    air_control = args.air_control if args.air_control is not None else style["air_control"]
    brake_mult = args.brake_mult if args.brake_mult is not None else style["brake_mult"]
    sprint_mult = args.sprint_mult if args.sprint_mult is not None else style["sprint_mult"]

    print(f"# Style: {args.style}")
    print(f"# {style['description']}")
    print()

    result = calculate_movement_tuning(
        max_speed=max_speed,
        time_to_max=time_to_max,
        time_to_stop=time_to_stop,
        curve=curve,
        air_control=air_control,
        brake_mult=brake_mult,
        sprint_mult=sprint_mult,
        unit_name=args.unit_name,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()