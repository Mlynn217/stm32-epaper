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
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
BOARD = os.path.join(ROOT, 'hardware', 'kicad', 'stm32-epaper.kicad_pcb')
SCH = os.path.join(ROOT, 'hardware', 'kicad', 'stm32-epaper.kicad_sch')
LOG = os.path.join(ROOT, 'hardware', 'kicad', 'routing-log.md')
LAST_DRC = os.path.join(ROOT, 'hardware', 'kicad', 'drc-last.json')   # not tracked
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
    ap.add_argument('--variant', choices=('none', 'planes', 'fanout', 'iterate', 'lastmile'), required=True)
    ap.add_argument('--radius', type=float, default=3.0, help='iterate: rip-up radius, mm')
    ap.add_argument('--passes', type=int, default=20)
    ap.add_argument('--tries', type=int, default=1,
                    help='parallel freerouting runs on the same DSN; the best result is kept')
    ap.add_argument('--fresh', action='store_true')
    ap.add_argument('--note', default='')
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix='route-')
    dsn, ses, net = (os.path.join(tmp, n) for n in ('main.dsn', 'main.ses', 'main.xml'))

    if a.fresh:
        run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', net, SCH])
        print(kpy('gen_main_pcb.py', net, '--force').splitlines()[0])
        print(kpy('place_main_pcb.py').strip().splitlines()[-1])
    if a.variant == 'iterate':
        # Rip-up pass on the current board, driven by the previous attempt's DRC report.
        if not os.path.exists(LAST_DRC):
            sys.exit('iterate needs %s from a previous attempt' % LAST_DRC)
        print(kpy('ripup_main_pcb.py', LAST_DRC, str(a.radius)).strip())
    elif a.variant == 'lastmile':
        # Our own A* router on the gaps the previous attempt's DRC report lists; no freerouting.
        if not os.path.exists(LAST_DRC):
            sys.exit('lastmile needs %s from a previous attempt' % LAST_DRC)
        print(kpy('lastmile_main_pcb.py', LAST_DRC).strip())
    elif a.variant != 'none':
        print(kpy('preroute_main_pcb.py', *(['--fanout'] if a.variant == 'fanout' else [])).strip())
    if a.variant == 'lastmile':
        rpt = os.path.join(tmp, 'drc.json')
        run(['kicad-cli', 'pcb', 'drc', '--schematic-parity', '--refill-zones', '--format', 'json',
             '--severity-all', '-o', rpt, BOARD])
        return report(a, rpt)
    print(kpy('route_main_pcb.py', 'export', dsn).strip())
    # freerouting's results vary run to run (multi-threaded search), so optionally run several
    # in parallel on the same DSN and keep the best: fewest unconnected, then fewest DRC errors.
    threads = max(2, 16 // a.tries)
    procs = []
    for i in range(a.tries):
        fr_log = os.path.join(tmp, 'freerouting-%d.log' % i)
        out = os.path.join(tmp, 'main-%d.ses' % i)
        print('freerouting run %d log (live): %s' % (i, fr_log))
        procs.append((out, subprocess.Popen(
            ['java', '-jar', JAR, '-de', dsn, '-do', out, '-mp', str(a.passes), '-mt', str(threads),
             '--gui.enabled=false', '--api_server.enabled=false'],
            cwd=tmp, stdout=open(fr_log, 'w'), stderr=subprocess.STDOUT)))
    results = []
    for i, (out, pr) in enumerate(procs):
        pr.wait()
        if pr.returncode != 0 or not os.path.exists(out):
            print('run %d failed' % i)
            continue
        copy = os.path.join(tmp, 'try-%d.kicad_pcb' % i)
        shutil.copy(BOARD, copy)
        for ext in ('.kicad_pro', '.kicad_dru'):
            shutil.copy(BOARD[:-len('.kicad_pcb')] + ext, copy[:-len('.kicad_pcb')] + ext)
        kpy('route_main_pcb.py', 'import', out, copy)
        rpt_i = os.path.join(tmp, 'drc-%d.json' % i)
        run(['kicad-cli', 'pcb', 'drc', '--schematic-parity', '--refill-zones', '--format', 'json',
             '--severity-all', '-o', rpt_i, copy])
        d_i = json.load(open(rpt_i))
        score = (len(d_i.get('unconnected_items', [])),
                 sum(1 for v in d_i.get('violations', []) if v.get('severity') == 'error'))
        print('run %d: %d unconnected, %d DRC errors' % ((i,) + score))
        results.append((score, i, copy, rpt_i))
    if not results:
        sys.exit('all freerouting runs failed')
    score, best, copy, rpt = min(results)
    shutil.copy(copy, BOARD)
    print('kept run %d of %d' % (best, a.tries))
    return report(a, rpt)


def report(a, rpt):
    d = json.load(open(rpt))
    json.dump(d, open(LAST_DRC, 'w'))
    viol = [v for v in d.get('violations', []) if v.get('severity') == 'error']
    kinds = {}
    for v in d.get('violations', []):
        kinds[v['type']] = kinds.get(v['type'], 0) + 1
    unconnected = d.get('unconnected_items', [])
    nets = sorted({i.get('description', '') for u in unconnected for i in u.get('items', [])})
    unrouted_nets = sorted({m.group(1) for n in nets for m in [re.search(r'\[([^\]]+)\]', n)] if m})
    vias = sum(1 for _ in re.finditer(r'^\s*\(via\b', open(BOARD).read(), re.M))

    note = a.note + (' (best of %d)' % a.tries if a.tries > 1 else '')
    line = '| %s | %s | %d | %d | %d | %d | %s | %s |' % (
        datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), a.variant, a.passes, len(unconnected),
        len(viol), vias, ', '.join('%s %d' % kv for kv in sorted(kinds.items())
                                   if kv[0] not in ('unconnected_items',)), note)
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
