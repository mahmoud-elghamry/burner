#!/usr/bin/env python3
"""
lad2text.py - render TIA Portal SimaticML (FlgNet) LAD networks as readable
boolean/assignment pseudo-code so the logic can be reviewed as text.

Usage:  python lad2text.py <block.xml> [block2.xml ...]
        python lad2text.py --all <dir>
"""
import sys, os, glob
import xml.etree.ElementTree as ET

FLG = '{http://www.siemens.com/automation/Openness/SW/NetworkSource/FlgNet/v3}'


def lname(el):
    return el.tag.split('}')[-1]


def text_of_multilingual(parent, composition):
    """Pull the en-US text of a MultilingualText child with the given CompositionName."""
    for mt in parent:
        if lname(mt) == 'MultilingualText' and mt.get('CompositionName') == composition:
            for item in mt.iter():
                if lname(item) == 'MultilingualTextItem':
                    culture = txt = None
                    for a in item.iter():
                        if lname(a) == 'Culture':
                            culture = (a.text or '').strip()
                        elif lname(a) == 'Text':
                            txt = (a.text or '').strip()
                    if txt:
                        return txt
    return ''


class Net(object):
    """One LAD network (rung group) decoded into an expression graph."""

    # parts that produce a statement rather than a boolean value
    STATEMENTS = ('Coil', 'SCoil', 'RCoil', 'Move', 'Normalize', 'Scale_X', 'Sr', 'Rs')

    def __init__(self, flgnet):
        self.access = {}     # uid -> operand text
        self.parts = {}      # uid -> Part element
        self.negated = {}    # uid -> set of pin names drawn negated
        self.instance = {}   # uid -> instance (timer/counter DB) name
        self.calls = {}      # uid -> Call element
        self.order = []      # uids in document order
        self.driver = {}     # (uid, pin) -> connection tuple
        self._busy = set()   # recursion guard

        parts = flgnet.find(FLG + 'Parts')
        for el in (parts if parts is not None else []):
            kind = lname(el)
            uid = el.get('UId')
            if kind == 'Access':
                self.access[uid] = self._access_text(el)
            elif kind == 'Part':
                self.parts[uid] = el
                self.order.append(uid)
                negs = set()
                for ch in el:
                    if lname(ch) == 'Negated':
                        negs.add(ch.get('Name'))
                    elif lname(ch) == 'Instance':
                        self.instance[uid] = self._symbol_text(ch)
                self.negated[uid] = negs
            elif kind == 'Call':
                self.calls[uid] = el
                self.parts[uid] = el
                self.order.append(uid)
                self.negated[uid] = set()
                for ci in el:
                    if lname(ci) == 'CallInfo':
                        for ch in ci:
                            if lname(ch) == 'Instance':
                                self.instance[uid] = self._symbol_text(ch)

        wires = flgnet.find(FLG + 'Wires')
        for w in (wires if wires is not None else []):
            conns = [self._conn(c) for c in w]
            if not conns:
                continue
            src, sinks = conns[0], conns[1:]
            for s in sinks:
                if s[0] == 'pin':
                    self.driver[(s[1], s[2])] = src
            # Output-side wires are listed the other way round: the part pin is
            # the wire source and the operand/variable is the sink. Record those
            # too, otherwise coil operands and FB output parameters look unwired.
            if src[0] == 'pin':
                for s in sinks:
                    if s[0] == 'ident':
                        self.driver.setdefault((src[1], src[2]), s)

    # ---------------------------------------------------------------- helpers
    def _symbol_text(self, el):
        comps = [c.get('Name') for c in el.iter() if lname(c) == 'Component']
        return '.'.join([c for c in comps if c])

    def _access_text(self, el):
        scope = el.get('Scope') or ''
        for ch in el:
            if lname(ch) == 'Symbol':
                name = self._symbol_text(ch)
                return ('#' + name) if scope == 'LocalVariable' else '"%s"' % name
            if lname(ch) == 'Constant':
                val = ctype = ''
                for a in ch:
                    if lname(a) == 'ConstantValue':
                        val = (a.text or '').strip()
                    elif lname(a) == 'ConstantType':
                        ctype = (a.text or '').strip()
                return val if val else ('<%s>' % ctype)
        return '<?>'

    def _conn(self, c):
        k = lname(c)
        if k == 'Powerrail':
            return ('rail',)
        if k == 'IdentCon':
            return ('ident', c.get('UId'))
        if k == 'NameCon':
            return ('pin', c.get('UId'), c.get('Name'))
        if k == 'OpenCon':
            return ('open',)
        return ('?',)

    def _operand(self, uid, pin='operand'):
        d = self.driver.get((uid, pin))
        if d is None:
            return '<unwired>'
        if d[0] == 'ident':
            return self.access.get(d[1], '<?>')
        return self.val(d)

    def _pins(self, uid, prefix='in'):
        """Ordered in1..inN pins actually wired on a variadic part."""
        out = []
        i = 1
        while (uid, '%s%d' % (prefix, i)) in self.driver:
            out.append(self.driver[(uid, '%s%d' % (prefix, i))])
            i += 1
        return out

    # ------------------------------------------------------------- rendering
    def val(self, conn):
        """Render a connection as a value/boolean expression."""
        if conn is None:
            return '<unwired>'
        if conn[0] == 'rail':
            return ''          # power rail = TRUE, shown as empty
        if conn[0] == 'open':
            return '<open>'
        if conn[0] == 'ident':
            return self.access.get(conn[1], '<?>')
        if conn[0] == 'pin':
            return self.part_out(conn[1], conn[2])
        return '<?>'

    def _series(self, base, term):
        if base == '':
            return term
        return '%s AND %s' % (base, term)

    def part_out(self, uid, pin):
        if uid in self._busy:
            return '<cycle>'
        self._busy.add(uid)
        try:
            return self._part_out(uid, pin)
        finally:
            self._busy.discard(uid)

    def _part_out(self, uid, pin):
        el = self.parts.get(uid)
        if el is None:
            return '<?%s>' % uid
        if uid in self.calls:
            return '%s.%s' % (self.instance.get(uid, 'CALL'), pin)

        name = el.get('Name')
        neg = self.negated.get(uid, set())

        if name == 'Contact':
            base = self.val(self.driver.get((uid, 'in')))
            term = self._operand(uid)
            if 'operand' in neg:
                term = 'NOT ' + term
            return self._series(base, term)

        if name == 'Not':
            base = self.val(self.driver.get((uid, 'in')))
            return 'NOT (%s)' % (base if base else 'TRUE')

        if name == 'O':
            terms = [self.val(c) for c in self._pins(uid)]
            terms = [t if t != '' else 'TRUE' for t in terms]
            return '(' + ' OR '.join(terms) + ')' if terms else '<empty OR>'

        if name == 'A':
            terms = [self.val(c) for c in self._pins(uid)]
            return ' AND '.join([t for t in terms if t])

        if name in ('TON', 'TOF', 'TP', 'TONR'):
            inst = self.instance.get(uid, '?timer')
            inp = self.val(self.driver.get((uid, 'IN')))
            pt = self.val(self.driver.get((uid, 'PT')))
            body = '%s(IN:=%s, PT:=%s)' % (name, inp if inp else 'TRUE', pt)
            if pin in ('Q', 'ET'):
                return '%s[%s].%s' % (body, inst, pin)
            return body

        if name in ('Sr', 'Rs'):
            s = self.val(self.driver.get((uid, 's')))
            r = self.val(self.driver.get((uid, 'r1')))
            return '%s(S:=%s, R1:=%s).Q' % (name.upper(), s, r)

        if name in ('Ge', 'Gt', 'Le', 'Lt', 'Eq', 'Ne'):
            op = {'Ge': '>=', 'Gt': '>', 'Le': '<=', 'Lt': '<', 'Eq': '=', 'Ne': '<>'}[name]
            base = self.val(self.driver.get((uid, 'pre')))
            a = self._operand(uid, 'in1')
            b = self._operand(uid, 'in2')
            cmp_ = '(%s %s %s)' % (a, op, b)
            return self._series(base, cmp_)

        if name in ('Normalize', 'Scale_X'):
            return '%s(...)' % name

        if name == 'Move':
            return 'MOVE(...)'

        # generic fallback
        return '%s(...).%s' % (name, pin)

    # ------------------------------------------------------------ statements
    def statements(self):
        out = []
        for uid in self.order:
            el = self.parts[uid]
            if uid in self.calls:
                out.append(self._stmt_call(uid, el))
                continue
            name = el.get('Name')
            if name not in self.STATEMENTS:
                continue
            neg = self.negated.get(uid, set())

            if name in ('Coil', 'SCoil', 'RCoil'):
                target = self._operand(uid)
                rlo = self.val(self.driver.get((uid, 'in')))
                rlo = rlo if rlo else 'TRUE'
                arrow = {'Coil': ':=', 'SCoil': ':= S', 'RCoil': ':= R'}[name]
                if 'operand' in neg:
                    target = 'NOT ' + target
                out.append('%s %s %s' % (target, arrow, rlo))

            elif name == 'Move':
                en = self.val(self.driver.get((uid, 'en')))
                src = self._operand(uid, 'in')
                dsts = self._pins(uid, 'out')
                dst = ', '.join([self.val(d) if d[0] != 'ident' else self.access.get(d[1], '?')
                                 for d in dsts]) or self._operand(uid, 'out1')
                guard = ('IF %s THEN  ' % en) if en else ''
                out.append('%sMOVE  %s  ->  %s' % (guard, src, dst))

            elif name in ('Normalize', 'Scale_X'):
                en = self.val(self.driver.get((uid, 'en')))
                args = []
                for p in ('MIN', 'VALUE', 'MAX', 'OUT'):
                    if (uid, p) in self.driver:
                        args.append('%s:=%s' % (p, self._operand(uid, p)))
                guard = ('IF %s THEN  ' % en) if en else ''
                out.append('%s%s(%s)' % (guard, name, ', '.join(args)))

            elif name in ('Sr', 'Rs'):
                tgt = self._operand(uid)
                s = self.val(self.driver.get((uid, 's')))
                r = self.val(self.driver.get((uid, 'r1')))
                out.append('%s := %s(S:=%s, R1:=%s)'
                           % (tgt, name.upper(), s, r))
        return out

    def _stmt_call(self, uid, el):
        info = None
        for ci in el:
            if lname(ci) == 'CallInfo':
                info = ci
        bname = info.get('Name') if info is not None else '?'
        btype = info.get('BlockType') if info is not None else '?'
        inst = self.instance.get(uid, '')
        en = self.val(self.driver.get((uid, 'en')))
        args = []
        if info is not None:
            for p in info:
                if lname(p) == 'Parameter':
                    pn = p.get('Name')
                    if (uid, pn) in self.driver:
                        args.append('%s := %s' % (pn, self._operand(uid, pn)))
                    else:
                        args.append('%s := <unwired>' % pn)
        head = 'CALL %s "%s"' % (btype, bname)
        if inst:
            head += ' [instance %s]' % inst
        if en:
            head = 'IF %s THEN  ' % en + head
        if args:
            return head + '(\n        ' + ',\n        '.join(args) + ')'
        return head


def render_block(path):
    tree = ET.parse(path)
    root = tree.getroot()
    lines = []
    blk = None
    for el in root:
        if lname(el).startswith('SW.Blocks.'):
            blk = el
    if blk is None:
        return '%s: no block found' % path

    attrs = {}
    al = blk.find('AttributeList')
    if al is not None:
        for a in al:
            if lname(a) in ('Name', 'Number', 'ProgrammingLanguage', 'SecondaryType', 'MemoryLayout'):
                attrs[lname(a)] = (a.text or '').strip()

    lines.append('#' * 78)
    lines.append('# BLOCK %s   %s   (%s, No.%s, %s)' % (
        lname(blk).replace('SW.Blocks.', ''), attrs.get('Name', ''),
        attrs.get('ProgrammingLanguage', ''), attrs.get('Number', ''),
        attrs.get('SecondaryType', attrs.get('MemoryLayout', ''))))
    lines.append('#' * 78)

    # block interface
    for iface in blk.iter():
        if lname(iface) == 'Interface':
            for sec in iface.iter():
                if lname(sec) == 'Section':
                    members = [m for m in sec if lname(m) == 'Member']
                    if not members:
                        continue
                    lines.append('')
                    lines.append('  VAR_%s' % sec.get('Name').upper())
                    for m in members:
                        lines.append('    %-34s : %s' % (m.get('Name'), m.get('Datatype')))
            break

    ol = blk.find('ObjectList')
    n = 0
    for cu in (ol if ol is not None else []):
        if lname(cu) != 'SW.Blocks.CompileUnit':
            continue
        n += 1
        cu_ol = cu.find('ObjectList')
        title = text_of_multilingual(cu_ol, 'Title') if cu_ol is not None else ''
        comment = text_of_multilingual(cu_ol, 'Comment') if cu_ol is not None else ''
        lines.append('')
        lines.append('-' * 78)
        hdr = 'NETWORK %d' % n
        if title:
            hdr += '  --  %s' % title
        lines.append(hdr)
        if comment:
            for cl in comment.splitlines():
                lines.append('   // %s' % cl)
        lines.append('-' * 78)

        flg = None
        for x in cu.iter(FLG + 'FlgNet'):
            flg = x
        if flg is None:
            lines.append('   (empty)')
            continue
        net = Net(flg)
        stmts = net.statements()
        if not stmts:
            lines.append('   (no statements decoded)')
        for s in stmts:
            lines.append('   ' + s)
    return '\n'.join(lines)


def main(argv):
    files = []
    if argv and argv[0] == '--all':
        files = sorted(glob.glob(os.path.join(argv[1], '*.xml')))
    else:
        files = argv
    chunks = []
    for f in files:
        if os.path.basename(f).endswith('_DB.xml'):
            continue
        chunks.append(render_block(f))
    print('\n\n'.join(chunks))


if __name__ == '__main__':
    main(sys.argv[1:])
