#!/usr/bin/env python3
"""Prove a schematic redraw changed nothing electrically: compare two KiCad XML netlists.

    python3 hardware/scripts/compare_netlists.py before.xml after.xml [OLD=NEW ...]

Compares every net as its set of (reference, pin) nodes, and every part's value and footprint.
Net *names* of auto-named nets can legitimately change with the drawing, so nets are matched by
their node sets; named nets must keep their names. OLD=NEW renames references that moved (e.g.
R304=R105). Exits non-zero, listing the differences, if anything else changed.
"""
import sys
import xml.etree.ElementTree as ET


def load(path, rename):
    r = ET.parse(path).getroot()
    parts = {}
    for c in r.iter('comp'):
        ref = rename.get(c.get('ref'), c.get('ref'))
        parts[ref] = (c.findtext('value'), c.findtext('footprint'))
    nets = {}
    for n in r.iter('net'):
        nodes = frozenset((rename.get(x.get('ref'), x.get('ref')), x.get('pin')) for x in n.iter('node'))
        nets[nodes] = n.get('name')
    return parts, nets


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    rename = dict(a.split('=') for a in sys.argv[3:])
    pa, na = load(sys.argv[1], rename)
    pb, nb = load(sys.argv[2], {})
    bad = []
    for ref in sorted(set(pa) | set(pb)):
        if pa.get(ref) != pb.get(ref):
            bad.append('part %s: %s -> %s' % (ref, pa.get(ref), pb.get(ref)))
    for nodes in set(na) ^ set(nb):
        side = 'only before' if nodes in na else 'only after'
        bad.append('net %s (%s): %s' % (na.get(nodes) or nb.get(nodes), side, sorted(nodes)[:6]))
    for nodes in set(na) & set(nb):
        a, b = na[nodes], nb[nodes]
        if a != b and not (a.startswith(('Net-(', 'unconnected-')) and b.startswith(('Net-(', 'unconnected-'))):
            bad.append('net renamed: %s -> %s' % (a, b))
    if bad:
        print('\n'.join(bad))
        sys.exit('%d differences' % len(bad))
    print('electrically identical: %d parts, %d nets' % (len(pb), len(nb)))


if __name__ == '__main__':
    main()
