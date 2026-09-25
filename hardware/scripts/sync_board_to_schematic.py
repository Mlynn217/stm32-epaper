#!/usr/bin/env python3
"""Re-link the main board's footprints to the schematic after a redraw (no layout changes).

    kicad python3.11 hardware/scripts/sync_board_to_schematic.py <netlist.xml> [OLD=NEW ...]

A schematic redraw that doesn't change the circuit still changes symbol UUIDs (the generator
numbers them in drawing order) and may renumber moved parts. The board links each footprint to
its symbol by that path, so DRC's schematic-parity check would flag every one. This rewrites each
footprint's reference (OLD=NEW renames) and symbol path from the netlist, touching nothing else:
positions, nets, tracks and zones stay exactly as they are. Run compare_netlists.py first to
prove the circuit itself is unchanged.
"""
import os
import sys
import xml.etree.ElementTree as ET

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, '..', 'kicad', 'stm32-epaper.kicad_pcb')


def main():
    args = [a for a in sys.argv[1:] if '=' not in a]
    rename = dict(a.split('=') for a in sys.argv[1:] if '=' in a)
    if not args:
        sys.exit(__doc__)
    root = ET.parse(args[0]).getroot()
    paths = {c.get('ref'): c.find('sheetpath').get('tstamps') + c.findtext('tstamps').split()[0]
             for c in root.iter('comp')}
    board = pcbnew.LoadBoard(BOARD)
    renamed = relinked = 0
    missing = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref in rename:
            fp.SetReference(rename[ref])
            ref = rename[ref]
            renamed += 1
        if ref in paths:
            fp.SetPath(pcbnew.KIID_PATH(paths[ref]))
            relinked += 1
        else:
            missing.append(ref)
    pcbnew.SaveBoard(BOARD, board)
    print('synced: %d footprints re-linked, %d renamed%s' % (
        relinked, renamed, ('; NOT in schematic: ' + ', '.join(missing)) if missing else ''))


if __name__ == '__main__':
    main()
