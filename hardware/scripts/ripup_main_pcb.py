#!/usr/bin/env python3
"""Prepare an incremental rip-up pass: keep what routed, free up the areas that didn't.

    kicad python3.11 hardware/scripts/ripup_main_pcb.py <drc.json> [radius_mm]

From a KiCad DRC JSON report (kicad-cli pcb drc --format json): deletes the vias it flags as
dangling (autorouter leftovers), locks every track and via, then unlocks all copper within
`radius_mm` (default 3) of each unconnected item. The next freerouting run treats locked copper as
protected and may rip up / reroute the unlocked neighbourhoods to finish the missing connections.
"""
import json
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, '..', 'kicad', 'stm32-epaper.kicad_pcb')


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    drc = json.load(open(sys.argv[1]))
    radius = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
    board = pcbnew.LoadBoard(BOARD)

    dangling = {i['uuid'] for v in drc.get('violations', []) if v['type'] == 'via_dangling'
                for i in v['items']}
    hot = [(i['pos']['x'], i['pos']['y']) for u in drc.get('unconnected_items', [])
           for i in u['items']]

    removed = unlocked = locked = 0
    # Take the list once: after board.Remove(), KiCad 10's SWIG wrapper can no longer iterate
    # GetTracks() in the same session.
    tracks = list(board.GetTracks())
    keep = []
    for t in tracks:
        if t.m_Uuid.AsString() in dangling and not t.IsLocked():
            board.Remove(t)
            removed += 1
        else:
            keep.append(t)
    for t in keep:
        pts = [t.GetStart(), t.GetEnd()] if t.Type() != pcbnew.PCB_VIA_T else [t.GetPosition()]
        near = any(math.hypot(pcbnew.ToMM(p.x) - hx, pcbnew.ToMM(p.y) - hy) < radius
                   for p in pts for hx, hy in hot)
        t.SetLocked(not near)
        if near:
            unlocked += 1
        else:
            locked += 1
    pcbnew.SaveBoard(BOARD, board)
    print('rip-up prep: %d dangling vias removed, %d items unlocked near %d unconnected ends '
          '(r=%.1f mm), %d locked' % (removed, unlocked, len(hot), radius, locked))


if __name__ == '__main__':
    main()
