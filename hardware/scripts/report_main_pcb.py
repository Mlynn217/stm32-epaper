#!/usr/bin/env python3
"""Routed-length report for the main board: per bus group, the longest net, the skew and the
limits from stm32-epaper.kicad_dru (KiCad's DRC enforces those; this shows the margins).

    kicad python3.11 hardware/scripts/report_main_pcb.py [board.kicad_pcb]
"""
import fnmatch
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, '..', 'kicad', 'stm32-epaper.kicad_pcb')

# name, net patterns, max length (mm), max skew (mm) - keep in step with the .kicad_dru
GROUPS = [
    ('SDRAM', ['FMC_A*', 'FMC_D*', 'FMC_BA*', 'FMC_NBL*', 'FMC_SDN*', 'FMC_SDCKE0', 'SDRAM_CLK'],
     45, 10),
    ('SDIO', ['SDIO_CMD', 'SDIO_D?', 'SDCARD_CLK'], 50, 5),
    ('QSPI', ['QUADSPI_BK1_IO?', 'QSPI_FLASH_CLK'], 45, 5),
    ('USB', ['USB_D?'], None, 2),
    ('Crystals', ['*/HSE_IN', '*/HSE_OUT', '*/LSE_IN', '*/LSE_OUT'], 12, None),
    ('Touch', ['*TOUCH_*'], 60, None),
]


def main():
    board = pcbnew.LoadBoard(sys.argv[1] if len(sys.argv) > 1 else BOARD)
    length = {}
    for t in board.GetTracks():
        n = t.GetNetname()
        length[n] = length.get(n, 0.0) + pcbnew.ToMM(t.GetLength())
    ok = True
    for name, pats, lmax, smax in GROUPS:
        nets = {n: l for n, l in length.items() if any(fnmatch.fnmatchcase(n, p) for p in pats)}
        if not nets:
            print('%-8s no routed nets' % name)
            continue
        longest = max(nets, key=nets.get)
        skew = max(nets.values()) - min(nets.values())
        bad = (lmax and nets[longest] > lmax) or (smax and skew > smax)
        ok &= not bad
        print('%-8s %2d nets  longest %5.1f mm (%s)%s  skew %5.1f mm%s  %s' % (
            name, len(nets), nets[longest], longest, ' / max %d' % lmax if lmax else '',
            skew, ' / max %d' % smax if smax else '', 'FAIL' if bad else 'ok'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
