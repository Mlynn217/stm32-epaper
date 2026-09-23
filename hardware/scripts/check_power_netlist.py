#!/usr/bin/env python3
"""Check hardware/kicad's Power sheet against the intended connectivity.

Runs kicad-cli ERC + netlist export and compares every net to EXPECTED below — a design-intent
review in table form. Exits non-zero on any mismatch or on any ERC finding other than library-table
configuration warnings (those depend on the local KiCad install, not on the design).

Usage:  KICAD_CLI=<path to kicad-cli> python3 check_power_netlist.py
"""
import os
import subprocess
import sys
import tempfile

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


def main():
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        rpt, net = os.path.join(tmp, 'erc.rpt'), os.path.join(tmp, 'n.net')
        subprocess.run([CLI, 'sch', 'erc', '-o', rpt, SCH], check=True, capture_output=True)
        subprocess.run([CLI, 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', net, SCH],
                       check=True, capture_output=True)
        lines = open(rpt).read().splitlines()
        nets = parse(open(net).read())
    for i, line in enumerate(lines):
        if line.startswith('[') and not line.startswith(ENV_ONLY):
            ok = False
            print('ERC:', '\n     '.join(lines[i:i + 4]))
    actual = {}
    for n in find(find1(nets, 'nets'), 'net'):
        actual[find1(n, 'name')[1]] = ' '.join(sorted(
            '%s.%s' % (find1(x, 'ref')[1], find1(x, 'pin')[1]) for x in find(n, 'node')))
    for name in sorted(set(EXPECTED) | set(actual)):
        want = ' '.join(sorted(EXPECTED.get(name, '').split()))
        got = actual.get(name, '')
        if want != got:
            ok = False
            print('NET %-28s expected: %s\n    %-28s actual:   %s' % (name, want, '', got))
    print('%d nets checked: %s' % (len(actual), 'OK' if ok else 'MISMATCH'))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
