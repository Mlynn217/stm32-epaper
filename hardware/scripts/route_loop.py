#!/usr/bin/env python3
"""One measured routing attempt on the main board, logged to hardware/kicad/routing-log.md.

    python3 hardware/scripts/route_loop.py --variant planes|fanout|none [--passes 20] [--fresh]
                                           [--note "..."]

Steps: [--fresh: re-bootstrap + place from the schematic] -> pre-route (variant) -> DSN export ->
freerouting (headless, offline) -> SES import -> KiCad DRC -> one line in the log, plus the list of
nets still unconnected. Commit after each attempt so a good board can always be recovered.

Needs: the KiCad AppImage wrappers (`kicad`, `kicad-cli`), Java, the freerouting jar, and the
enclosure build's out/pcb_placement.json (for --fresh).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
BOARD = os.path.join(ROOT, 'hardware', 'kicad', 'stm32-epaper.kicad_pcb')
SCH = os.path.join(ROOT, 'hardware', 'kicad', 'stm32-epaper.kicad_sch')
LOG = os.path.join(ROOT, 'hardware', 'kicad', 'routing-log.md')
JAR = os.path.expanduser('~/.local/share/freerouting/freerouting-2.4.1.jar')


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit('FAILED: %s\n%s\n%s' % (' '.join(cmd), r.stdout[-2000:], r.stderr[-2000:]))
    return r.stdout


def kpy(script, *args):
    out = run(['kicad', 'python3.11', os.path.join(HERE, script), *args])
    return '\n'.join(l for l in out.splitlines() if 'memory leak' not in l)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', choices=('none', 'planes', 'fanout'), required=True)
    ap.add_argument('--passes', type=int, default=20)
    ap.add_argument('--fresh', action='store_true')
    ap.add_argument('--note', default='')
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix='route-')
    dsn, ses, net = (os.path.join(tmp, n) for n in ('main.dsn', 'main.ses', 'main.xml'))

    if a.fresh:
        run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', net, SCH])
        print(kpy('gen_main_pcb.py', net, '--force').splitlines()[0])
        print(kpy('place_main_pcb.py').strip().splitlines()[-1])
    if a.variant != 'none':
        print(kpy('preroute_main_pcb.py', *(['--fanout'] if a.variant == 'fanout' else [])).strip())
    print(kpy('route_main_pcb.py', 'export', dsn).strip())
    fr_log = os.path.join(tmp, 'freerouting.log')
    print('freerouting log (live):', fr_log)
    with open(fr_log, 'w') as f:
        r = subprocess.run(['java', '-jar', JAR, '-de', dsn, '-do', ses, '-mp', str(a.passes),
                            '-mt', '8', '--gui.enabled=false', '--api_server.enabled=false'],
                           cwd=tmp, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode != 0 or not os.path.exists(ses):
        sys.exit('freerouting failed, see %s' % fr_log)
    print(kpy('route_main_pcb.py', 'import', ses).strip())

    rpt = os.path.join(tmp, 'drc.json')
    run(['kicad-cli', 'pcb', 'drc', '--schematic-parity', '--refill-zones', '--format', 'json',
         '--severity-all', '-o', rpt, BOARD])
    d = json.load(open(rpt))
    viol = [v for v in d.get('violations', []) if v.get('severity') == 'error']
    kinds = {}
    for v in d.get('violations', []):
        kinds[v['type']] = kinds.get(v['type'], 0) + 1
    unconnected = d.get('unconnected_items', [])
    nets = sorted({i.get('description', '') for u in unconnected for i in u.get('items', [])})
    unrouted_nets = sorted({m.group(1) for n in nets for m in [re.search(r'\[([^\]]+)\]', n)] if m})
    vias = sum(1 for _ in re.finditer(r'^\s*\(via\b', open(BOARD).read(), re.M))

    line = '| %s | %s | %d | %d | %d | %d | %s | %s |' % (
        datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), a.variant, a.passes, len(unconnected),
        len(viol), vias, ', '.join('%s %d' % kv for kv in sorted(kinds.items())
                                   if kv[0] not in ('unconnected_items',)), a.note)
    if not os.path.exists(LOG):
        open(LOG, 'w').write('# Main board routing attempts\n\nOne line per `route_loop.py` run '
                             '(newest last). "Unconnected" and "errors" are from KiCad DRC.\n\n'
                             '| When | Variant | Passes | Unconnected | DRC errors | Vias | DRC items '
                             '| Note |\n|---|---|---|---|---|---|---|---|\n')
    open(LOG, 'a').write(line + '\n')
    print(line)
    print('unrouted nets (%d): %s' % (len(unrouted_nets), ', '.join(unrouted_nets[:60])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
