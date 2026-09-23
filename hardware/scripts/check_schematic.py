#!/usr/bin/env python3
"""Check the hardware/kicad schematic against design intent, beyond what ERC can see.

Runs kicad-cli ERC + netlist export, then:
  1. ERC: no findings other than library-table configuration warnings (local-install dependent).
  2. Power sheet: every net, restricted to Power-sheet parts (refs < 100), matches EXPECTED.
  3. MCU pin mux: every sheet_mcu.PINMAP entry is on its intended net AND the pin really provides
     the required alternate function (per the KiCad symbol's alternate list); no pin used twice.
  4. Memory: every SDRAM/QSPI/microSD pin sits on its intended net, and each such bus net
     reaches exactly one MCU pin, whose PINMAP function matches the net name.
  5. No net has a single connection (a label typo / unmatched global label shows up here).
  6. Every connected symbol pin exists as a pad on the part's assigned footprint (catches
     symbol/footprint numbering mismatches, e.g. an exposed pad numbered differently).

Usage:  KICAD_CLI=<path to kicad-cli> KICAD_SYMBOL_DIR=<kicad share>/symbols \
        python3 check_schematic.py
"""
import os
import subprocess
import sys
import tempfile

import kicad_gen
import sheet_memory
import sheet_mcu
from sexp import find, find1, parse

HERE = os.path.dirname(os.path.abspath(__file__))
SCH = os.path.join(HERE, '..', 'kicad', 'stm32-epaper.kicad_sch')
CLI = os.environ.get('KICAD_CLI', 'kicad-cli')

EXPECTED = {
    # rails
    'VBUS': 'C1.1 D1.2 J1.A4 J1.A9 J1.B4 J1.B9 Q1.1 R4.1 R5.1 U1.1 U1.2 U5.5',
    'VSYS': 'C11.1 C4.1 C5.1 C6.1 D1.1 L2.1 Q1.2 R17.1 R6.1 U2.10 U3.3 U6.10',
    '+BATT': 'C2.1 D3.2 J2.1 Q1.3 U1.3 U1.4',
    '+3V3': 'C8.1 C9.1 R13.1 R18.1 R7.1 R9.1 U2.6 U4.1 U4.2 U4.4',
    '+5V': 'C12.1 C13.1 R10.1 U3.6',
    '3V3_PERIPH': 'R13.2 U4.7 U4.8',
    '3V3_AON': 'C7.1 R18.2 U6.6',
    'GND': 'C1.2 C11.2 C12.2 C13.2 C14.2 C2.2 C3.2 C4.2 C5.2 C6.2 C7.2 C8.2 C9.2 J1.A1 J1.A12 '
           'J1.B1 J1.B12 J1.SH J2.2 R1.2 R11.2 R12.2 R14.2 R15.2 R16.2 R2.2 R3.2 R5.2 R8.2 U1.11 '
           'U1.8 U1.9 U2.2 U2.3 U2.8 U3.4 U4.5 U4.9 U5.2 U6.11 U6.2 U6.3 U6.4 U6.8',
    # signals leaving the sheet
    'USB_DP': 'J1.A6 J1.B6 U5.1 U5.6',
    'USB_DM': 'J1.A7 J1.B7 U5.3 U5.4',
    'CHG_STAT': 'D2.1 U1.7',
    '3V3_PG': 'R9.2 U2.5',
    'EPD_5V_EN': 'R12.1 U3.2',
    'VBAT_RTC': 'C3.1 D3.1',
    'PERIPH_EN': 'R14.1 U4.3',
    # local nets
    '/Power/CC1': 'J1.A5 R1.1',
    '/Power/CC2': 'J1.B5 R2.1',
    '/Power/PROG': 'R3.1 U1.10',
    '/Power/CHG_LED': 'D2.2 R4.2',
    '/Power/BB_EN': 'R15.1 R6.2 U2.1',  # UVLO divider tap on TPS63802 EN
    '/Power/BB_L1': 'L1.1 U2.9',
    '/Power/BB_L2': 'L1.2 U2.7',
    '/Power/BB_FB': 'R7.2 R8.1 U2.4',
    '/Power/BST_SW': 'L2.2 U3.5',
    '/Power/BST_FB': 'R10.2 R11.1 U3.1',
    '/Power/LS_CT': 'C14.1 U4.6',
    '/Power/AON_EN': 'R17.2 U6.1',
    '/Power/AON_CFG3': 'R16.1 U6.5',
    '/Power/AON_LX1': 'L3.1 U6.9',
    '/Power/AON_LX2': 'L3.2 U6.7',
    # deliberately unconnected
    'unconnected-(J1-SBU1-PadA8)': 'J1.A8',
    'unconnected-(J1-SBU2-PadB8)': 'J1.B8',
    'unconnected-(U1-NC-Pad5)': 'U1.5',
    'unconnected-(U1-NC-Pad6)': 'U1.6',
}
ENV_ONLY = ('[lib_symbol_issues]', '[footprint_link_issues]')


def _refnum(ref):
    digits = ''.join(c for c in ref if c.isdigit())
    return int(digits) if digits else -1


def main():
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        rpt, net = os.path.join(tmp, 'erc.rpt'), os.path.join(tmp, 'n.net')
        subprocess.run([CLI, 'sch', 'erc', '-o', rpt, SCH], check=True, capture_output=True)
        subprocess.run([CLI, 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', net, SCH],
                       check=True, capture_output=True)
        lines = open(rpt).read().splitlines()
        nets = parse(open(net).read())

    def fail(msg):
        nonlocal ok
        ok = False
        print(msg)

    # 1. ERC
    for i, line in enumerate(lines):
        if line.startswith('[') and not line.startswith(ENV_ONLY):
            fail('ERC: ' + '\n     '.join(lines[i:i + 4]))

    node_net = {}   # 'U101.124' -> net name
    members = {}    # net name -> sorted list of 'REF.PIN'
    for n in find(find1(nets, 'nets'), 'net'):
        name = find1(n, 'name')[1]
        nodes = sorted('%s.%s' % (find1(x, 'ref')[1], find1(x, 'pin')[1]) for x in find(n, 'node'))
        members[name] = nodes
        for nd in nodes:
            node_net[nd] = name

    # 2. Power sheet
    for name in sorted(EXPECTED):
        want = ' '.join(sorted(EXPECTED[name].split()))
        got = ' '.join(nd for nd in members.get(name, []) if _refnum(nd.split('.')[0]) < 100)
        if want != got:
            fail('POWER NET %-26s expected: %s\n%37s actual:   %s' % (name, want, '', got))

    # 3. MCU pin mux
    sym = kicad_gen.load_stock(*sheet_mcu.MCU_LIB.split(':'))
    pin_alts, pin_num = {}, {}
    for sub in find(sym, 'symbol'):
        for p in find(sub, 'pin'):
            nm = find1(p, 'name')[1]
            pin_alts[nm] = {a[1] for a in find(p, 'alternate')}
            pin_num[nm] = find1(p, 'number')[1]
    seen = {}
    af_of_net = {}
    for pin, net_name, af in sheet_mcu.PINMAP:
        if pin in seen:
            fail('PINMAP: %s used twice (%s, %s)' % (pin, seen[pin], net_name))
        seen[pin] = net_name
        if af and af not in pin_alts.get(pin, ()):
            fail('PINMAP: %s cannot be %s (has %s)' % (pin, af, sorted(pin_alts.get(pin, ()))))
        got = node_net.get('U101.' + pin_num[pin])
        if (got or '').split('/')[-1] != net_name:  # sheet-local nets come back as /MCU/<name>
            fail('PINMAP: %s (U101.%s) is on %s, expected %s' % (pin, pin_num[pin], got, net_name))
        af_of_net[net_name] = af

    # 4. Memory devices -> MCU
    for ref, table in (('U201', sheet_memory.SDRAM), ('U202', sheet_memory.QSPI),
                       ('J201', sheet_memory.SD)):
        lib = {'U201': ('Memory_RAM', 'IS42S16400J-xT'), 'U202': ('Memory_Flash', 'W25Q128JVS'),
               'J201': ('Connector', 'Micro_SD_Card_Det2')}[ref]
        pins = kicad_gen._pins_of(kicad_gen.load_stock(*lib))
        for num, (_, _, _, pname) in pins.items():
            want = table.get(pname)
            got = node_net.get('%s.%s' % (ref, num))
            if want is None:
                continue
            if got != want:
                fail('MEM: %s.%s (%s) on %s, expected %s' % (ref, num, pname, got, want))
            if want.startswith(('FMC_', 'QUADSPI_', 'SDIO_')):
                mcu = [nd for nd in members.get(want, []) if nd.startswith('U101.')]
                if len(mcu) != 1 or af_of_net.get(want) != want:
                    fail('MEM: net %s reaches MCU pins %s (PINMAP function %s)'
                         % (want, mcu, af_of_net.get(want)))

    # 5. single-connection nets
    for name, nodes in members.items():
        if len(nodes) < 2 and not name.startswith('unconnected-'):
            fail('NET %s has a single connection %s (label typo / unmatched global?)'
                 % (name, nodes))

    # 6. pins vs footprint pads
    fp_root = os.path.join(os.path.dirname(kicad_gen.STOCK.rstrip('/')), 'footprints')
    pads_cache = {}

    def pads(fp):
        if fp not in pads_cache:
            lib, name = fp.split(':')
            d = (os.path.join(HERE, '..', 'kicad', 'epaper.pretty') if lib == 'epaper'
                 else os.path.join(fp_root, lib + '.pretty'))
            doc = parse(open(os.path.join(d, name + '.kicad_mod')).read())
            pads_cache[fp] = {p[1] for p in find(doc, 'pad')}
        return pads_cache[fp]

    comp_fp = {find1(c, 'ref')[1]: (find1(c, 'footprint') or [None, ''])[1]
               for c in find(find1(nets, 'components'), 'comp')}
    for name, nodes in members.items():
        for nd in nodes:
            ref, pin = nd.split('.', 1)
            fp = comp_fp.get(ref)
            if not fp:
                fail('FOOTPRINT: %s has no footprint assigned' % ref)
                comp_fp[ref] = 'reported'
            elif fp != 'reported' and pin not in pads(fp):
                fail('FOOTPRINT: %s pin %s has no pad in %s' % (ref, pin, fp))

    print('%d nets, %d MCU pins, %d power-sheet nets checked: %s'
          % (len(members), len(sheet_mcu.PINMAP), len(EXPECTED), 'OK' if ok else 'MISMATCH'))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
