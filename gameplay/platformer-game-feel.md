# Third-Person Platformer Game Feel

**Source skill:** `cmu3jgwla01lw07adabopxymw`  
**Focus:** Movement response, jump forgiveness, assisted traversal, camera behavior and contextual interaction.

## Movement response

Use acceleration and braking curves rather than snapping from zero to full speed. The ADSR-inspired model is useful: quick initial acceleration that eases toward top speed, plus decisive initial braking that tapers into a controlled stop. Tune absolute values as well as ratios; lock max speed early because it determines world scale, jump distances and level spacing. Drive 3D motion from camera-relative forward/right vectors and rotate the character toward velocity. Treat sprint as a scalar on base movement, and keep air control separately tunable.

Useful starting ranges from the source:

- Time to max speed: about 50–200 ms for responsive ground movement.
- Ground acceleration time: about 0.03–0.12 s for snappy movement; longer reads as momentum-heavy.
- Air acceleration: commonly 0.5–1.0× ground acceleration.
- Braking is a separate parameter; excessive friction feels rubbery, too little feels slippery.

Graph local-space acceleration/velocity over time during tuning. Change values substantially (often halve/double first), then bisect toward a good feel.

## Jump forgiveness and control

Stack small windows that align simulation with player perception:

- **Coyote time:** allow a jump briefly after leaving a ledge. Typical range: 0.05–0.15 s; clear the timer when a jump is consumed.
- **Input buffer:** retain a jump pressed shortly before landing (often 0.08–0.18 s) and consume it once when grounded. Clear it on invalidating state changes.
- **Variable jump height:** on release while rising, reduce upward velocity (a 0.3–0.6 multiplier is a useful starting band).
- **Apex hang:** reduce gravity near the jump apex, commonly to 0.4–0.6×, to extend steering time.
- **Asymmetric gravity:** make falling gravity stronger than rising gravity (about 1.5–2.5×) for a more decisive descent.

Derive physics from design targets rather than guessing. For peak height `h` and time-to-apex `t`, use `g = 2h/t²` and launch speed `v = 2h/t`; estimate airtime as `2t` before any fall multiplier. Then validate jump distance against walk speed and actual level dimensions.

## Ledges and mantling

For context-sensitive mantling, require an airborne player, forward intent, a nearby climbable surface, appropriate facing/proximity, and enough clearance. Pair a full-body/capsule surface probe with an eye-height trace to distinguish a wall from a low floor edge. Detect the top in two stages: verify there is open space above the face, then find a walkable landing surface with a downward trace. Average nearby hit normals at corners, smooth orientation, and correct depth drift against the surface.

Compute a target immediately before a scripted vault/mantle and temporarily use a traversal movement/collision mode. Restore ordinary movement on completion. Keep obstacle height bands and clearance assumptions consistent with level geometry and animation arcs.

## Follow camera

Separate player rotation and camera orbit. Follow a chest/head pivot with a spring arm or collision probe; smooth ordinary motion and make entering collision correction faster than returning to the desired distance. Preserve the player's yaw choice on a camera-driven collision. When the player moves and stops orbiting, gradually reorient behind motion rather than snapping.

A three-ray aperture check (center, left, right) can decide whether to pull inward or slide around an obstruction. Frame climbs, mantles, drops and wall jumps deliberately so the landing area and travel direction remain legible. Log the active camera, collision state and rays in a debug view.

## Contextual interaction

A single action can trigger the best available context action, but define deterministic priority from player state, approach angle, geometry, speed, clearance and proximity. Show the intended action before commitment; avoid rapidly changing prompts and ambiguous controls. Reuse buttons where actions are coherent, split them where they oppose one another, and keep interactable size/spacing rules consistent for level design.

## Tuning and testing order

1. Establish acceleration, braking and max speed.
2. Derive jump gravity/velocity from a target height and apex time.
3. Tune fall multiplier, variable jump cut, coyote and buffer windows.
4. Add apex hang, ledge traversal, camera correction and auto-orientation.
5. Test late-edge presses, early landing presses and heavy-scene frame pacing; have unfamiliar players try it.

Keep tuneable values in data for accessibility/difficulty adjustments. Avoid consuming jump forgiveness timers incorrectly, camera snapping, and changing movement scale late in level production.

## Registered helpers

- [`../tools/platformer/jump_arc_calculator.py`](../tools/platformer/jump_arc_calculator.py) derives jump parameters from target height and time-to-apex.
- [`../tools/platformer/movement_tuning.py`](../tools/platformer/movement_tuning.py) derives acceleration/braking values from movement feel targets.
