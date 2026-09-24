# Main board routing attempts

One line per `route_loop.py` run (newest last). "Unconnected" and "errors" are from KiCad DRC.

| When | Variant | Passes | Unconnected | DRC errors | Vias | DRC items | Note |
|---|---|---|---|---|---|---|---|
| 2026-09-23 20:43 | none | 15 | 81 | 86 | 259 | hole_clearance 8, isolated_copper 1, length_out_of_range 21, silk_over_copper 28, silk_overlap 21, skew_out_of_range 43, track_width 14, via_dangling 3 | baseline: split In2 planes + smd_smd fix, no pre-route |
