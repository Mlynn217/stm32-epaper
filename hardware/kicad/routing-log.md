# Main board routing attempts

One line per `route_loop.py` run (newest last). "Unconnected" and "errors" are from KiCad DRC.

| When | Variant | Passes | Unconnected | DRC errors | Vias | DRC items | Note |
|---|---|---|---|---|---|---|---|
| 2026-09-23 20:43 | none | 15 | 81 | 86 | 259 | hole_clearance 8, isolated_copper 1, length_out_of_range 21, silk_over_copper 28, silk_overlap 21, skew_out_of_range 43, track_width 14, via_dangling 3 | baseline: split In2 planes + smd_smd fix, no pre-route |
| 2026-09-23 21:20 | planes | 15 | 43 | 85 | 423 | clearance 5, hole_clearance 8, hole_to_hole 5, holes_co_located 2, length_out_of_range 22, silk_over_copper 28, silk_overlap 21, skew_out_of_range 38, track_width 12 | scripted plane vias (locked) |
| 2026-09-23 21:57 | planes | 15 | 49 | 84 | 418 | clearance 5, hole_clearance 8, length_out_of_range 11, silk_over_copper 30, silk_overlap 22, skew_out_of_range 45, track_width 15 | placement optimiser (MCU 90 deg) + class-aware plane vias |
| 2026-09-23 22:22 | planes | 15 | 35 | 37 | 433 | clearance 2, hole_clearance 8, length_out_of_range 8, silk_over_copper 30, silk_overlap 19, skew_out_of_range 8, track_width 11, via_dangling 27 | Power 0.3 mm, Touch 0.25 mm clearance, crystals placed first |
