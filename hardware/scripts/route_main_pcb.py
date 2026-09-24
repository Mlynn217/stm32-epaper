#!/usr/bin/env python3
"""Autoroute the main board with freerouting (offline, headless) via a Specctra DSN round trip.

    kicad python3.11 hardware/scripts/route_main_pcb.py export /tmp/main.dsn
    java -jar ~/.local/share/freerouting/freerouting-2.4.1.jar -de /tmp/main.dsn -do /tmp/main.ses \\
         -mp 40 -mt 8 --gui.enabled=false --api_server.enabled=false
    kicad python3.11 hardware/scripts/route_main_pcb.py import /tmp/main.ses [board.kicad_pcb]

The import step replaces the board's tracks and vias with the routed session and refills zones.
(The freerouting MCP server in .mcp.json exposes the same engine to Claude Code sessions.)
"""
import os
import re
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, '..', 'kicad', 'stm32-epaper.kicad_pcb')
PLANE_LAYERS = ('In1.Cu', 'In2.Cu')   # GND / 3.3 V planes (place_main_pcb.py)
SMD_SMD_UM = 120                     # pad-to-pad clearance, um (DSN units)


def main():
    if len(sys.argv) not in (3, 4) or sys.argv[1] not in ('export', 'import'):
        sys.exit(__doc__)
    path = sys.argv[3] if len(sys.argv) == 4 else BOARD
    board = pcbnew.LoadBoard(path)
    if sys.argv[1] == 'export':
        ok = pcbnew.ExportSpecctraDSN(board, sys.argv[2])
        # KiCad exports every copper layer as (type signal); mark the plane layers as power so
        # freerouting keeps them for the planes and routes signals on F.Cu/B.Cu only.
        text = open(sys.argv[2]).read()
        for layer in PLANE_LAYERS:
            text = re.sub(r'(\(layer %s\s*\(type )signal\)' % re.escape(layer), r'\1power)', text)
        # Class rules carry one clearance that freerouting also applies pad-to-pad, so the wide
        # Touch/Power clearances "fail" inside 0.5 mm-pitch parts and block routing there. Give
        # every class the same pad-to-pad (smd_smd) clearance as the .kicad_dru "Pad to pad" rule.
        head, sep, classes = text.partition('(class ')
        classes = re.sub(r'^(\s*)\(clearance ([0-9.]+)\)$',
                         r'\1(clearance \2)\n\1(clearance %d (type smd_smd))' % SMD_SMD_UM,
                         classes, flags=re.M)
        text = head + sep + classes
        open(sys.argv[2], 'w').write(text)
        print('exported' if ok else 'EXPORT FAILED', sys.argv[2])
    else:
        ok = pcbnew.ImportSpecctraSES(board, sys.argv[2])
        if not ok:
            sys.exit('import failed')
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(path, board)
        print('imported %s: %d tracks/vias' % (sys.argv[2], len(board.GetTracks())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
