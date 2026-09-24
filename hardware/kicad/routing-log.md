# Main board routing attempts

One line per `route_loop.py` run (newest last). "Unconnected" and "errors" are from KiCad DRC.

| When | Variant | Passes | Unconnected | DRC errors | Vias | DRC items | Note |
|---|---|---|---|---|---|---|---|
| 2026-09-23 20:43 | none | 15 | 81 | 86 | 259 | hole_clearance 8, isolated_copper 1, length_out_of_range 21, silk_over_copper 28, silk_overlap 21, skew_out_of_range 43, track_width 14, via_dangling 3 | baseline: split In2 planes + smd_smd fix, no pre-route |
| 2026-09-23 21:20 | planes | 15 | 43 | 85 | 423 | clearance 5, hole_clearance 8, hole_to_hole 5, holes_co_located 2, length_out_of_range 22, silk_over_copper 28, silk_overlap 21, skew_out_of_range 38, track_width 12 | scripted plane vias (locked) |
| 2026-09-23 21:57 | planes | 15 | 49 | 84 | 418 | clearance 5, hole_clearance 8, length_out_of_range 11, silk_over_copper 30, silk_overlap 22, skew_out_of_range 45, track_width 15 | placement optimiser (MCU 90 deg) + class-aware plane vias |
| 2026-09-23 22:22 | planes | 15 | 35 | 37 | 433 | clearance 2, hole_clearance 8, length_out_of_range 8, silk_over_copper 30, silk_overlap 19, skew_out_of_range 8, track_width 11, via_dangling 27 | Power 0.3 mm, Touch 0.25 mm clearance, crystals placed first |
| 2026-09-23 22:47 | iterate | 10 | 39 | 38 | 409 | clearance 2, hole_clearance 8, length_out_of_range 8, silk_over_copper 30, silk_overlap 19, skew_out_of_range 9, track_dangling 17, track_width 11, via_dangling 2 | rip-up pass 1 on attempt 4 (r=3 mm) |
| 2026-09-23 23:17 | planes | 20 | 33 | 67 | 432 | clearance 2, hole_clearance 8, length_out_of_range 10, silk_over_copper 30, silk_overlap 19, skew_out_of_range 34, track_width 13, via_dangling 13 | attempt 4 settings + shared-via fallback for blocked plane pads, 20 passes |
| 2026-09-23 23:47 | planes | 20 | 31 | 67 | 429 | clearance 2, hole_clearance 8, length_out_of_range 8, silk_over_copper 30, silk_overlap 19, skew_out_of_range 34, track_dangling 1, track_width 15, via_dangling 13 | thermal-pad vias + pin-to-decoupling-cap stubs (38 plane pads left to router) |
| 2026-09-24 00:18 | planes | 20 | 29 | 59 | 438 | clearance 2, hole_clearance 8, length_out_of_range 10, silk_over_copper 32, silk_overlap 21, skew_out_of_range 29, starved_thermal 1, track_width 9, via_dangling 18 | MCU power vias inward (under body), CAP1188 touch escapes, joined 3V3_PERIPH zone, TPs at their rails |
| 2026-09-24 00:48 | planes | 20 | 13 | 76 | 466 | clearance 2, hole_clearance 8, length_out_of_range 10, silk_over_copper 32, silk_overlap 21, skew_out_of_range 46, track_width 10, via_dangling 1 | MCU power vias perpendicular-inward (fixed), wider CAP1188 escapes |
