# Hero Time — Alpha 4

Enable **Options → Gameplay → Extras → Hero Time** (OFF by default). First
transform into a compatible ordinary form, then press **L3 / F** for its matching
Ultimate. Ben cannot request an Ultimate directly. Supported pairs are Spider
Monkey, Humungousaur, Echo Echo, Swampfire and Big Chill. Way Big is excluded.

The original energy meter is the timer: up to **60 seconds**. Return early with
the same button, or wait for expiry. Ben then recharges for **time used / 3**, at
most **20 seconds**. Using 30 seconds gives 10 seconds recharge. Early return
preserves the corresponding meter fraction. Accepted Ultimate requests use the
original green transformation effect. Gameplay pause does not consume the timer.

The user confirmed attacks, the meter, the green flash and proportional early
return. Authored VM tests cover readiness, eligible pairs, lifecycle, resource
accounting and interruption. Every ability and the full campaign are unverified.
Ultimate Big Chill's geometric wing border remains open; so does camera flicker
above 30 FPS. This mode does not certify stable 60 FPS. No character assets ship.
