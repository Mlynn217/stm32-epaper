"""Minimal S-expression reader/writer for KiCad files (bootstrap tooling only)."""
import re

_tok = re.compile(r'\s*(\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+)')


class Sym(str):
    """Bare (unquoted) atom."""


def parse(text):
    pos, stack, cur = 0, [], []
    while True:
        m = _tok.match(text, pos)
        if not m:
            break
        pos = m.end()
        t = m.group(1)
        if t == '(':
            stack.append(cur)
            cur = []
        elif t == ')':
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif t.startswith('"'):
            cur.append(re.sub(r'\\(.)', lambda m: '\n' if m.group(1) == 'n' else m.group(1), t[1:-1]))
        else:
            cur.append(Sym(t))
    return cur[0]


def dump(e, ind=0):
    if not isinstance(e, list):
        if isinstance(e, Sym):
            return str(e)
        if isinstance(e, (int, float)):
            return fmt_num(e)
        return '"' + str(e).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'
    if e and isinstance(e[0], str) and not isinstance(e[0], Sym):
        e = [Sym(e[0])] + list(e[1:])  # list heads are always bare keywords
    tab = '\t' * ind
    simple = all(not isinstance(x, list) for x in e)
    if simple:
        return tab + '(' + ' '.join(dump(x) for x in e) + ')'
    head = []
    rest = list(e)
    while rest and not isinstance(rest[0], list):
        head.append(dump(rest.pop(0)))
    out = tab + '(' + ' '.join(head)
    for x in rest:
        out += '\n' + (dump(x, ind + 1) if isinstance(x, list) else '\t' * (ind + 1) + dump(x))
    return out + '\n' + tab + ')'


def fmt_num(v):
    v = round(float(v), 4)
    if v == int(v):
        return str(int(v))
    return ('%.4f' % v).rstrip('0').rstrip('.')


def find(e, key):
    return [x for x in e if isinstance(x, list) and x and x[0] == key]


def find1(e, key):
    r = find(e, key)
    return r[0] if r else None
