#!/usr/bin/env python3
"""Autoroute the main board with freerouting (offline, headless) via a Specctra DSN round trip.

    kicad python3.11 hardware/scripts/route_main_pcb.py export /tmp/main.dsn
    java -jar ~/.local/share/freerouting/freerouting-2.4.1.jar -de /tmp/main.dsn -do /tmp/main.ses \\
         -mp 40 -mt 8 --gui.enabled=false --api_server.enabled=false
    kicad python3.11 hardware/scripts/route_main_pcb.py import /tmp/main.ses

The import step replaces the board's tracks and vias with the routed session and refills zones.
(The freerouting MCP server in .mcp.json exposes the same engine to Claude Code sessions.)
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, '..', 'kicad', 'stm32-epaper.kicad_pcb')


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ('export', 'import'):
        sys.exit(__doc__)
    board = pcbnew.LoadBoard(BOARD)
    if sys.argv[1] == 'export':
        ok = pcbnew.ExportSpecctraDSN(board, sys.argv[2])
        print('exported' if ok else 'EXPORT FAILED', sys.argv[2])
    else:
        ok = pcbnew.ImportSpecctraSES(board, sys.argv[2])
        if not ok:
            sys.exit('import failed')
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(BOARD, board)
        print('imported %s: %d tracks/vias' % (sys.argv[2], len(board.GetTracks())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
