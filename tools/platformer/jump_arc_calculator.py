#!/usr/bin/env python3
"""Calculate platformer jump physics from designer feel targets.

Given desired peak height and time-to-apex, derives gravity, initial
jump velocity, total airtime, and max horizontal distance. Supports
asymmetric gravity (fall multiplier), variable jump height (cut factor),
apex hang, and coyote/buffer window suggestions.

Usage:
  python jump_arc_calculator.py [options]

Options:
  --height FLOAT        Desired jump height in units (default: 4.0)
  --time FLOAT          Time to apex in seconds (default: 0.35)
  --walk-speed FLOAT    Horizontal walk speed in units/s (default: 8.0)
  --fall-mult FLOAT     Fall gravity multiplier (default: 2.0)
  --cut-factor FLOAT    Variable jump cut factor 0-1 (default: 0.5)
  --apex-mult FLOAT     Apex hang gravity multiplier (default: 0.5)
  --apex-threshold FLOAT  Vertical speed threshold for apex hang (default: 50.0)
  --coyote FLOAT        Coyote time window in seconds (default: 0.10)
  --buffer FLOAT        Jump buffer window in seconds (default: 0.12)
  --unit-name STRING    Name of the unit (e.g. "tiles", "meters") (default: "units")
  --presets             Show reference presets from known games
  --game STRING         Show a specific game preset ("celeste", "mario", "hollowknight", "psychonauts2")

Examples:
  python jump_arc_calculator.py --height 4 --time 0.35 --walk-speed 8 --unit-name tiles
  python jump_arc_calculator.py --presets
  python jump_arc_calculator.py --game celeste
"""
import argparse
import json
import math
import sys


# ─── Presets from researched games ───────────────────────────────────────────
PRESETS = {
    "celeste": {
        "description": "Tight precision platformer with forgiving forgiveness windows",
        "height": 4.0,
        "time_to_apex": 0.30,
        "walk_speed": 8.0,
        "fall_mult": 2.5,
        "cut_factor": 0.5,
        "apex_mult": 0.5,
        "apex_threshold": 40.0,
        "coyote": 0.10,
        "buffer": 0.10,
        "unit_name": "tiles",
    },
    "mario": {
        "description": "Classic responsive platformer with moderate floatiness",
        "height": 4.0,
        "time_to_apex": 0.40,
        "walk_speed": 7.0,
        "fall_mult": 2.0,
        "cut_factor": 0.4,
        "apex_mult": 0.5,
        "apex_threshold": 50.0,
        "coyote": 0.10,
        "buffer": 0.12,
        "unit_name": "tiles",
    },
    "hollowknight": {
        "description": "Action platformer with committed arcs and longer forgiveness",
        "height": 4.5,
        "time_to_apex": 0.38,
        "walk_speed": 9.0,
        "fall_mult": 2.2,
        "cut_factor": 0.5,
        "apex_mult": 0.6,
        "apex_threshold": 50.0,
        "coyote": 0.12,
        "buffer": 0.15,
        "unit_name": "units",
    },
    "psychonauts2": {
        "description": "Multi-phase jump: quick launch, floaty apex, sharp drop",
        "height": 5.0,
        "time_to_apex": 0.35,
        "walk_speed": 10.0,
        "fall_mult": 1.5,
        "cut_factor": 0.5,
        "apex_mult": 0.26,
        "apex_threshold": 175.0,
        "coyote": 0.20,
        "buffer": 0.12,
        "unit_name": "uu",
        "note": "P2 uses multi-phase gravity: Launch 1.45×, Float A/B 0.26×, Fall 1.5×. "
                "Launch velocity 1560 uu/s. Pre-jump at 25% gravity for 0.15s during coyote.",
    },
}


def calculate_jump_arc(
    height: float,
    time_to_apex: float,
    walk_speed: float,
    fall_mult: float,
    cut_factor: float,
    apex_mult: float,
    apex_threshold: float,
    coyote: float,
    buffer: float,
    unit_name: str = "units",
) -> dict:
    """Calculate all jump physics values from designer targets.

    Args:
        height: Desired peak jump height in units.
        time_to_apex: Time to reach peak in seconds.
        walk_speed: Horizontal speed in units/second.
        fall_mult: Fall gravity multiplier (asymmetric gravity).
        cut_factor: Variable jump cut factor (0-1, fraction of vy retained on release).
        apex_mult: Gravity multiplier near apex (apex hang).
        apex_threshold: Vertical speed threshold (units/s) defining "near apex".
        coyote: Coyote time window in seconds.
        buffer: Jump buffer window in seconds.
        unit_name: Name of the distance unit for display.

    Returns:
        Dictionary with all computed and configured values.
    """
    # Core kinematic equations (y-up convention)
    # gravity = 2h / t²
    # jump_velocity = 2h / t (upward, positive in y-up)
    gravity = 2.0 * height / (time_to_apex * time_to_apex)
    jump_velocity = 2.0 * height / time_to_apex

    # Symmetric airtime (before fall multiplier)
    symmetric_airtime = 2.0 * time_to_apex

    # With asymmetric gravity, fall time is shorter
    # Fall distance equals rise distance (h), fall gravity = gravity * fall_mult
    # Fall time = sqrt(2h / (gravity * fall_mult))
    fall_gravity = gravity * fall_mult
    fall_time = math.sqrt(2.0 * height / fall_gravity) if fall_gravity > 0 else 0.0
    total_airtime_asym = time_to_apex + fall_time

    # Max horizontal distance
    max_dist_symmetric = walk_speed * symmetric_airtime
    max_dist_asymmetric = walk_speed * total_airtime_asym

    # Variable jump: cut velocity by cut_factor while rising
    # New peak height after cut: h_cut = (v_cut)² / (2 * gravity)
    # where v_cut = jump_velocity * cut_factor
    cut_velocity = jump_velocity * cut_factor
    cut_height = (cut_velocity * cut_velocity) / (2.0 * gravity) if gravity > 0 else 0.0
    cut_time_to_apex = cut_velocity / gravity if gravity > 0 else 0.0

    # Apex hang: near apex, gravity is multiplied by apex_mult
    # This extends time near the peak. Approximate additional hang time:
    # The window where |vy| < apex_threshold lasts longer with reduced gravity.
    # Rough estimate: the time spent in the apex zone increases by factor of (1/apex_mult)
    # for the portion of the arc within the threshold.
    apex_zone_ratio = min(apex_threshold / jump_velocity, 1.0) if jump_velocity > 0 else 0.0
    # Time in apex zone without hang: ~2 * apex_zone_ratio * time_to_apex (both rise and fall sides)
    apex_time_normal = 2.0 * apex_zone_ratio * time_to_apex
    # With hang gravity, the time in the apex zone roughly scales by 1/apex_mult
    apex_time_with_hang = apex_time_normal / apex_mult if apex_mult > 0 else apex_time_normal
    extra_hang_time = apex_time_with_hang - apex_time_normal

    # Frames at common framerates
    coyote_frames_60 = round(coyote * 60)
    coyote_frames_30 = round(coyote * 30)
    buffer_frames_60 = round(buffer * 60)
    buffer_frames_30 = round(buffer * 30)

    result = {
        "designer_targets": {
            "peak_height": f"{height:.2f} {unit_name}",
            "time_to_apex": f"{time_to_apex:.3f} s",
            "walk_speed": f"{walk_speed:.1f} {unit_name}/s",
            "unit": unit_name,
        },
        "derived_physics": {
            "gravity": f"{gravity:.2f} {unit_name}/s²",
            "jump_velocity": f"{jump_velocity:.2f} {unit_name}/s",
            "fall_gravity": f"{fall_gravity:.2f} {unit_name}/s²",
            "fall_time": f"{fall_time:.3f} s",
            "total_airtime_symmetric": f"{symmetric_airtime:.3f} s",
            "total_airtime_asymmetric": f"{total_airtime_asym:.3f} s",
            "max_horizontal_distance_symmetric": f"{max_dist_symmetric:.2f} {unit_name}",
            "max_horizontal_distance_asymmetric": f"{max_dist_asymmetric:.2f} {unit_name}",
        },
        "variable_jump": {
            "cut_factor": f"{cut_factor:.2f}",
            "cut_velocity": f"{cut_velocity:.2f} {unit_name}/s",
            "cut_peak_height": f"{cut_height:.2f} {unit_name}",
            "cut_time_to_apex": f"{cut_time_to_apex:.3f} s",
            "height_ratio_tap_vs_hold": f"{(cut_height / height * 100):.1f}%",
        },
        "apex_hang": {
            "gravity_multiplier": f"{apex_mult:.2f}",
            "threshold": f"{apex_threshold:.1f} {unit_name}/s",
            "estimated_extra_hang_time": f"{extra_hang_time:.3f} s",
        },
        "forgiveness_windows": {
            "coyote_time": f"{coyote:.3f} s ({coyote_frames_60} frames @60fps, {coyote_frames_30} @30fps)",
            "jump_buffer": f"{buffer:.3f} s ({buffer_frames_60} frames @60fps, {buffer_frames_30} @30fps)",
        },
        "implementation_notes": [
            f"Set gravity to {gravity:.2f} {unit_name}/s²",
            f"Apply instant upward velocity of {jump_velocity:.2f} {unit_name}/s on jump press",
            f"Use fall_gravity ({fall_gravity:.2f}) when velocity.y < 0 for snappy descent",
            f"On jump release while rising: velocity.y = max(velocity.y * {cut_factor}, 0)",
            f"Near apex (|vy| < {apex_threshold}): gravity *= {apex_mult}",
            f"Coyote: allow jump if grounded OR within {coyote:.3f}s of leaving ground",
            f"Buffer: store jump press for {buffer:.3f}s, execute when landing",
            f"Clamp max fall speed to prevent tunneling",
        ],
    }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Calculate platformer jump physics from designer feel targets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python jump_arc_calculator.py --height 4 --time 0.35 --walk-speed 8 --unit-name tiles\n"
               "  python jump_arc_calculator.py --presets\n"
               "  python jump_arc_calculator.py --game celeste\n",
    )
    parser.add_argument("--height", type=float, default=4.0,
                        help="Desired jump height in units (default: 4.0)")
    parser.add_argument("--time", type=float, default=0.35,
                        help="Time to apex in seconds (default: 0.35)")
    parser.add_argument("--walk-speed", type=float, default=8.0,
                        help="Horizontal walk speed in units/s (default: 8.0)")
    parser.add_argument("--fall-mult", type=float, default=2.0,
                        help="Fall gravity multiplier (default: 2.0)")
    parser.add_argument("--cut-factor", type=float, default=0.5,
                        help="Variable jump cut factor 0-1 (default: 0.5)")
    parser.add_argument("--apex-mult", type=float, default=0.5,
                        help="Apex hang gravity multiplier (default: 0.5)")
    parser.add_argument("--apex-threshold", type=float, default=50.0,
                        help="Vertical speed threshold for apex hang (default: 50.0)")
    parser.add_argument("--coyote", type=float, default=0.10,
                        help="Coyote time window in seconds (default: 0.10)")
    parser.add_argument("--buffer", type=float, default=0.12,
                        help="Jump buffer window in seconds (default: 0.12)")
    parser.add_argument("--unit-name", type=str, default="units",
                        help='Name of the unit (e.g. "tiles", "meters") (default: "units")')
    parser.add_argument("--presets", action="store_true",
                        help="Show reference presets from known games")
    parser.add_argument("--game", type=str, choices=list(PRESETS.keys()),
                        help="Show a specific game preset")

    args = parser.parse_args()

    # Handle presets
    if args.presets:
        print(json.dumps(
            {name: {k: v for k, v in p.items()} for name, p in PRESETS.items()},
            indent=2,
        ))
        return

    if args.game:
        preset = PRESETS[args.game]
        print(f"# Preset: {args.game}")
        if "description" in preset:
            print(f"# {preset['description']}")
        if "note" in preset:
            print(f"# Note: {preset['note']}")
        print()
        result = calculate_jump_arc(
            height=preset["height"],
            time_to_apex=preset["time_to_apex"],
            walk_speed=preset["walk_speed"],
            fall_mult=preset["fall_mult"],
            cut_factor=preset["cut_factor"],
            apex_mult=preset["apex_mult"],
            apex_threshold=preset["apex_threshold"],
            coyote=preset["coyote"],
            buffer=preset["buffer"],
            unit_name=preset.get("unit_name", "units"),
        )
        print(json.dumps(result, indent=2))
        return

    # Calculate with provided arguments
    result = calculate_jump_arc(
        height=args.height,
        time_to_apex=args.time,
        walk_speed=args.walk_speed,
        fall_mult=args.fall_mult,
        cut_factor=args.cut_factor,
        apex_mult=args.apex_mult,
        apex_threshold=args.apex_threshold,
        coyote=args.coyote,
        buffer=args.buffer,
        unit_name=args.unit_name,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()