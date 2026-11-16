# -*- coding: utf-8 -*-
"""مولّد بلوكات البرنامج (decisions/0006) — SimaticML لادر لـ TIA V15.1.

    py tools\\build_blocks.py          # بيكتب build\\blocks\\*.xml

وبعدين الاستيراد بالترتيب اللي بيطبعه (DBs قبل البلوكات اللي بتستخدمها،
والـ FB قبل الـ instance DB، والـ OB في الآخر):

    powershell -ExecutionPolicy Bypass -File tools\\Apply-Blocks.ps1 -Files <...>

كل network عنوانه رقم صف من الـ C&E أو سطر من docs/التشغيل.md. والمعامل
بيتكتب بصيغة TIA: '"Tag"' و'"DB".Member' و'#Local' و'#T_X.Q' و'700' و'T#10S'
و'TRUE'. وبتات Word بصيغة '#Alarms.%X0' (slice على العضو).
"""
from __future__ import print_function
import io, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ladxml as L
import panel_text as P

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'blocks')
MULTI_RUNG = True


# ======================================================================
#  المعاملات وشكل الشبكة
# ======================================================================
def symbol_component(name, slice_access=None):
    """صيغة الـ slice في مكان واحد؛ Siemens V15.1 SW.PlcBlocks.Access_v3.xsd.

    Component_T: SliceAccessModifier، والنمط ([xbwdXBWD]\\d+)|undef.
    """
    modifier = (' SliceAccessModifier="%s"' % slice_access) if slice_access else ''
    return '        <Component Name="%s"%s />\n' % (L.esc(name), modifier)


class Net(L.Net):
    """L.Net + معاملات بصيغة TIA، ومقارنات، وMOVE، وSUB، وSet/Reset."""

    def operand(self, spec):
        u = self._next()
        if spec.startswith('#'):
            m = re.fullmatch(r'#([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*)(?:\.%X(\d+))?', spec)
            if not m:
                raise ValueError('bad operand ' + spec)
            comps = m.group(1).split('.')
            bit = int(m.group(2)) if m.group(2) is not None else None
            if bit is not None and not 0 <= bit < 16:
                raise ValueError('bad Word bit operand ' + spec)
            self.accesses.append(
                '    <Access Scope="LocalVariable" UId="%s"><Symbol>\n%s'
                '      </Symbol></Access>' % (u, ''.join(
                    symbol_component(c, 'x%d' % bit if bit is not None and i == len(comps) - 1 else None)
                    for i, c in enumerate(comps))))
        elif spec.startswith('"'):
            # HmiAlm Word bit: '"HmiAlm".Common.%X0' -> slice on Common.
            m = re.match(r'^"([^"]+)"((?:\.[A-Za-z0-9_]+)*)(?:\.%X(\d+))?$', spec)
            if not m:
                raise ValueError('bad operand ' + spec)
            comps = [m.group(1)] + [c for c in m.group(2).split('.') if c]
            body = ('    <Access Scope="GlobalVariable" UId="%s">\n      <Symbol>\n%s'
                    '      </Symbol>\n    </Access>')
            bit = int(m.group(3)) if m.group(3) is not None else None
            if bit is not None and (len(comps) < 2 or not 0 <= bit < 16):
                raise ValueError('bad Word bit operand ' + spec)
            self.accesses.append(body % (u, ''.join(
                symbol_component(c, 'x%d' % bit if bit is not None and i == len(comps) - 1 else None)
                for i, c in enumerate(comps))))
        elif spec.upper().startswith('T#'):
            self.accesses.append(
                '    <Access Scope="TypedConstant" UId="%s">\n      <Constant>\n'
                '        <ConstantValue>%s</ConstantValue>\n      </Constant>\n'
                '    </Access>' % (u, spec))
        else:
            if spec in ('TRUE', 'FALSE'):
                ctype = 'Bool'
            elif re.match(r'^-?\d+$', spec):
                ctype = 'Int'
            else:
                raise ValueError('bad operand ' + spec)
            self.accesses.append(
                '    <Access Scope="LiteralConstant" UId="%s">\n      <Constant>\n'
                '        <ConstantType>%s</ConstantType>\n'
                '        <ConstantValue>%s</ConstantValue>\n      </Constant>\n'
                '    </Access>' % (u, ctype, spec))
        return self.ident(u)

    def part(self, xml_fmt):
        u = self._next()
        self.parts.append(xml_fmt % u)
        return u

    def cmp_part(self, op, typ):
        return self.part('    <Part Name="%s" UId="%%s">\n'
                         '      <TemplateValue Name="SrcType" Type="Type">%s</TemplateValue>\n'
                         '    </Part>' % (op, typ))

    def scoil(self):
        return self.part('    <Part Name="SCoil" UId="%s" />')

    def move(self):
        return self.part('    <Part Name="Move" UId="%s" DisabledENO="false">\n'
                         '      <TemplateValue Name="Card" Type="Cardinality">1</TemplateValue>\n'
                         '    </Part>')

    def sub(self, typ):
        # SUB ليه دخلين ثابتين، فمالوش Card (عكس ADD)
        return self.part('    <Part Name="Sub" UId="%%s" DisabledENO="false">\n'
                         '      <TemplateValue Name="SrcType" Type="Type">%s</TemplateValue>\n'
                         '    </Part>' % typ)

    def add(self, typ):
        # ADD عدد دخوله متغيّر، فليه Card
        return self.part('    <Part Name="Add" UId="%%s" DisabledENO="false">\n'
                         '      <TemplateValue Name="Card" Type="Cardinality">2</TemplateValue>\n'
                         '      <TemplateValue Name="SrcType" Type="Type">%s</TemplateValue>\n'
                         '    </Part>' % typ)


# ---- تعبيرات الرانج -----------------------------------------------------
#   '"X"' أو '#X'          كونتاكت NO
#   ('!', op)              كونتاكت NC
#   ('&', e1, e2, ...)     توالي
#   ('|', e1, e2, ...)     توازي
#   ('Ge', 'Int', a, b)    مقارنة في مسار القدرة (Eq Ne Gt Ge Lt Le)
#   ('TON', '#T_X', pt)    تايمر في مسار القدرة، خرجه Q
CMPS = ('Eq', 'Ne', 'Gt', 'Ge', 'Lt', 'Le')


def emit(net, e, src):
    if isinstance(e, str):
        c = net.contact(False)
        net.wire(src, net.pin(c, 'in'))
        net.wire(net.operand(e), net.pin(c, 'operand'))
        return net.pin(c, 'out')
    k = e[0]
    if k == '!':
        c = net.contact(True)
        net.wire(src, net.pin(c, 'in'))
        net.wire(net.operand(e[1]), net.pin(c, 'operand'))
        return net.pin(c, 'out')
    if k == '&':
        for sub in e[1:]:
            src = emit(net, sub, src)
        return src
    if k == '|':
        outs = [emit(net, sub, src) for sub in e[1:]]
        o = net.or_box(len(outs))
        for i, out in enumerate(outs, 1):
            net.wire(out, net.pin(o, 'in%d' % i))
        return net.pin(o, 'out')
    if k in CMPS:
        _, typ, a, b = e
        c = net.cmp_part(k, typ)
        net.wire(src, net.pin(c, 'pre'))      # المقارنة: دخل القدرة اسمه pre مش in
        net.wire(net.operand(a), net.pin(c, 'in1'))
        net.wire(net.operand(b), net.pin(c, 'in2'))
        return net.pin(c, 'out')
    if k == 'TON':
        _, inst, pt = e
        t = net.ton(inst.lstrip('#'))
        net.wire(src, net.pin(t, 'IN'))
        net.wire(net.operand(pt), net.pin(t, 'PT'))
        net.wire(net.pin(t, 'ET'), net.openc())
        return net.pin(t, 'Q')
    raise ValueError('unknown expression %r' % (e,))


# ---- مخارج الرانج (على التوازي في آخره) ---------------------------------
#   ('=', op)  ('S', op)  ('R', op)
#   ('MOVE', src, dst)    ('SUB', 'Int', a, b, dst)
def outputs(net, node, outs):
    for o in outs:
        k = o[0]
        if k in ('=', 'S', 'R'):
            c = {'=': net.coil, 'S': net.scoil, 'R': net.rcoil}[k]()
            net.wire(node, net.pin(c, 'in'))
            net.wire(net.pin(c, 'operand'), net.operand(o[1]))
        elif k == 'MOVE':
            m = net.move()
            net.wire(node, net.pin(m, 'en'))
            net.wire(net.operand(o[1]), net.pin(m, 'in'))
            net.wire(net.pin(m, 'out1'), net.operand(o[2]))
        elif k in ('SUB', 'ADD'):
            _, typ, a, b, dst = o
            s = net.sub(typ) if k == 'SUB' else net.add(typ)
            net.wire(node, net.pin(s, 'en'))
            net.wire(net.operand(a), net.pin(s, 'in1'))
            net.wire(net.operand(b), net.pin(s, 'in2'))
            net.wire(net.pin(s, 'out'), net.operand(dst))
        else:
            raise ValueError('unknown output %r' % (o,))


def rung(title, expr, *outs):
    net = Net()
    node = emit(net, expr, net.rail()) if expr is not None else net.rail()
    outputs(net, node, outs)
    return title, net.render()


def network(title, rungs):
    """One topic, ordered rungs, one shared power rail (Net.render groups sources).

    Export evidence: D:/tasks/PH_tower_v15.1_Zain/export/xml/PLC_PLC_1/
    ProgramBlocks/Hydraulic System.xml, network 1, Wire 57: one rail feeds
    contacts 38/46/51/53 (three independent coils and a separate timer rung).
    export/xml/PLC_PLC_1/ProgramBlocks/Burner.xml, networks 3/5 also shares
    one rail wire between parallel branch starts.
    MULTI_RUNG=False preserves rung order and comments as single-rung units.
    """
    if not MULTI_RUNG:
        short, explanation = title.split(' :: ', 1)
        return [rung(N('%s (%d/%d)' % (short, i, len(rungs)), explanation), expr, *outs)
                for i, (expr, *outs) in enumerate(rungs, 1)]
    net = Net()
    for expr, *outs in rungs:
        node = emit(net, expr, net.rail()) if expr is not None else net.rail()
        outputs(net, node, outs)
    return [(title, net.render())]


def call(title, name, block_type, instance=None, params=()):
    """params = [(name, Section, Type, operand), ...].

    Input: operand -> call pin. Output: call pin -> operand.
    Omitted output pins remain unwired.
    """
    net = Net()
    u = net._next()
    iu = net._next()
    pxml = ''.join('\n          <Parameter Name="%s" Section="%s" Type="%s" />'
                   % (n, s, t) for n, s, t, _ in params)
    inst = ''
    if instance:
        inst = ('\n        <Instance Scope="GlobalVariable" UId="%s">\n'
                '          <Component Name="%s" />\n        </Instance>' % (iu, instance))
    net.parts.append('    <Call UId="%s">\n      <CallInfo Name="%s" BlockType="%s">%s%s\n'
                     '      </CallInfo>\n    </Call>' % (u, name, block_type, inst, pxml))
    net.wire(net.rail(), net.pin(u, 'en'))
    for n, s, t, op in params:
        if s == 'Input':
            net.wire(net.operand(op), net.pin(u, n))
        elif s == 'Output':
            net.wire(net.pin(u, n), net.operand(op))
        else:
            raise ValueError('unsupported call section ' + s)
    return title, net.render()


# ======================================================================
#  الواجهات والمستندات
# ======================================================================
TON_FULL = ('<Member Name="%s" Datatype="TON_TIME" Version="1.0" Remanence="NonRetain" '
            'Accessibility="Public"><AttributeList><BooleanAttribute Name="ExternalAccessible" '
            'SystemDefined="true">true</BooleanAttribute><BooleanAttribute Name="ExternalVisible" '
            'SystemDefined="true">true</BooleanAttribute><BooleanAttribute Name="ExternalWritable" '
            'SystemDefined="true">true</BooleanAttribute></AttributeList><Sections><Section '
            'Name="None"><Member Name="PT" Datatype="Time" /><Member Name="ET" Datatype="Time" />'
            '<Member Name="IN" Datatype="Bool" /><Member Name="Q" Datatype="Bool" /></Section>'
            '</Sections></Member>')


def member(name, typ, start=None, retain=False, short_ton=False, comment=None):
    comment_xml = ('<Comment><MultiLanguageText Lang="en-US">%s</MultiLanguageText></Comment>'
                   % L.esc(comment)) if comment else ''
    if typ == 'TON_TIME':
        if short_ton:
            return ('<Member Name="%s" Datatype="TON_TIME" Remanence="NonRetain" '
                    'Accessibility="Public">%s</Member>' % (name, comment_xml))
        return (TON_FULL % name).replace('</AttributeList>', '</AttributeList>' + comment_xml, 1)
    attrs = 'Name="%s" Datatype="%s"' % (name, typ)
    if retain is not None:
        attrs += ' Remanence="%s"' % ('Retain' if retain else 'NonRetain')
    attrs += ' Accessibility="Public"'
    inner = ''
    if comment:
        inner += ('<Comment><MultiLanguageText Lang="en-US">%s</MultiLanguageText></Comment>'
                  % L.esc(comment))
    if start is not None:
        inner += '<StartValue>%s</StartValue>' % start
    return '<Member %s>%s</Member>' % (attrs, inner) if inner else '<Member %s />' % attrs


def interface(sections):
    """sections = [(اسم القسم, [members xml])]"""
    out = ['<Interface><Sections xmlns="http://www.siemens.com/automation/Openness/SW/Interface/v3">']
    for name, mems in sections:
        if mems:
            out.append('  <Section Name="%s">' % name)
            out.extend('    ' + m for m in mems)
            out.append('  </Section>')
        else:
            out.append('  <Section Name="%s" />' % name)
    out.append('</Sections></Interface>')
    return '\n'.join(out)


HEAD = ('<?xml version="1.0" encoding="utf-8"?>\n<Document>\n'
        '  <Engineering version="V15.1" />\n')


def code_block(tag, name, number, iface, networks, extra_attrs='', comment=''):
    ids = L.IdGen(1)
    # Rev. B: a title 'Short title :: explanation' carries its own English text;
    # otherwise the text comes from panel_text.NETWORK_TEXT (whole block, no gaps).
    inline = all(' :: ' in t for t, _ in networks)
    descriptions = {} if inline else P.NETWORK_TEXT[name]
    if not inline and (len(descriptions) != len(networks) or
                       set(descriptions) != {title for title, _ in networks}):
        raise ValueError('Network text does not cover the current ' + name + ' networks')
    units = []
    for source_title, flg in networks:
        if inline:
            title, explanation = source_title.split(' :: ', 1)
        else:
            title, explanation = descriptions[source_title]
        unit = L.compile_unit(ids, flg, title)
        # Keep the shared ladxml serializer unchanged: its first empty Text is
        # the network Comment; the following multilingual object is the Title.
        units.append(unit.replace('<Text />', '<Text>%s</Text>' % L.esc(explanation), 1))
    comment = P.BLOCK_COMMENTS[name]
    return (HEAD +
            '  <%s ID="0">\n    <AttributeList>\n'
            '      <AutoNumber>false</AutoNumber>\n'
            '      <HeaderAuthor />\n      <HeaderFamily />\n      <HeaderName />\n'
            '      <HeaderVersion>0.1</HeaderVersion>\n'
            '      %s\n'
            '      <IsIECCheckEnabled>false</IsIECCheckEnabled>\n'
            '      <MemoryLayout>Optimized</MemoryLayout>\n%s'
            '      <Name>%s</Name>\n      <Number>%d</Number>\n'
            '      <ProgrammingLanguage>LAD</ProgrammingLanguage>\n%s'
            '      <SetENOAutomatically>False</SetENOAutomatically>\n'
            '    </AttributeList>\n    <ObjectList>\n%s\n%s\n%s\n'
            '    </ObjectList>\n  </%s>\n</Document>\n'
            % (tag, iface,
               '      <MemoryReserve>100</MemoryReserve>\n' if tag == 'SW.Blocks.FB' else '',
               name, number, extra_attrs,
               L.mltext(ids, 'Comment', comment).replace('      <', '      <'),
               '\n'.join(units),
               L.mltext(ids, 'Title', name),
               tag))


def db_block(tag, name, number, iface, instance_of=None):
    ids = L.IdGen(1)
    inst = ''
    if instance_of:
        inst = ('      <InstanceOfName>%s</InstanceOfName>\n'
                '      <InstanceOfType>FB</InstanceOfType>\n' % instance_of)
    return (HEAD +
            '  <%s ID="0">\n    <AttributeList>\n'
            '      <AutoNumber>false</AutoNumber>\n'
            '      <HeaderAuthor />\n      <HeaderFamily />\n      <HeaderName />\n'
            '      <HeaderVersion>0.1</HeaderVersion>\n%s'
            '      %s\n'
            '      <MemoryLayout>Optimized</MemoryLayout>\n%s'
            '      <Name>%s</Name>\n      <Number>%d</Number>\n'
            '      <ProgrammingLanguage>DB</ProgrammingLanguage>\n'
            '    </AttributeList>\n    <ObjectList>\n%s\n%s\n'
            '    </ObjectList>\n  </%s>\n</Document>\n'
            % (tag, inst, iface,
               '' if instance_of else '      <MemoryReserve>100</MemoryReserve>\n',
               name, number, L.mltext(ids, 'Comment', P.BLOCK_COMMENTS[name]),
               L.mltext(ids, 'Title', name), tag))


# ======================================================================
#  Par — Global DB
# ======================================================================
# Rev. B (docs/تبسيط الكود.md): تلات إعدادات بس على الشاشة. الحرارة بعُشر الدرجة
# زي كارت الـ TC (700 = 70.0 °C). الأوقات كلها ثابتة جوه البلوكات.
# (اسم، نوع، افتراضي، أقل، أعلى، وصف) — المدى من شيت Parameters في الـ C&E Rev. B.
PARAMS = [
    ('SP', 'Int', '700', '400', '900', 'Stop temperature, 0.1 degC (C07b)'),
    ('HYST', 'Int', '50', '30', '100', 'Restart difference below SP, 0.1 degC (C07b)'),
    ('STG', 'Int', '100', '50', '300', 'Stage 2 below SP - STG, 0.1 degC (C07c)'),
]
PAR_TEXT = {
    'SP': 'Stop temperature, 0.1 degC (700 = 70.0 degC). HMI entry; PLC keeps it inside 400..900.',
    'HYST': 'Restart difference below SP, 0.1 degC (50 = 5.0 degC). PLC keeps it inside 30..100.',
    'STG': 'Stage 2 runs below SP - STG, 0.1 degC (100 = 10.0 degC). PLC keeps it inside 50..300.',
}


def par_db():
    mems = [member(n, t, d, retain=True, comment=PAR_TEXT[n]) for n, t, d, lo, hi, txt in PARAMS]
    return db_block('SW.Blocks.GlobalDB', 'Par', 1, interface([('Static', mems)]))


def N(title, explanation):
    """Network title with its English explanation (shown in TIA under the title)."""
    return '%s :: %s' % (title, explanation)


# ======================================================================
#  Scrubber (FB2)
# ======================================================================
SCRUB_IN = [('PSH', 'PSH-101 healthy: 1 = contact closed (normal pressure)'),
            ('LSH', 'LSH-102 healthy: 1 = level below high'),
            ('LSHH', 'LSHH-103 healthy: 1 = level below very high'),
            ('EStopOK', 'Raw E-STOP status: 1 = released (C01)'),
            ('ResetPB', 'Raw RESET S2 push button; rising edge detected locally')]
SCRUB_OUT = [('FlareCmd', 'XV-401 flare (NO): 1 = energised = closed'),
             ('DrainCmd', 'XV-402 drain (NC): 1 = energised = open'),
             ('SuctionCmd', 'XV-403 suction (NC): 1 = energised = open'),
             ('Tripped', 'Latched scrubber trip until healthy RESET'),
             ('Alarms', 'Alarm display word (Common bits 0..5)')]
SCRUB_STAT = [
    ('FlareTrip', 'Bool', 'Flare trip (PSH, E-STOP, power-up): flare open until RESET'),
    ('ResetMem', 'Bool', 'RESET state from previous scan; set by OB100'),
    ('ResetPulse', 'Bool', 'One-scan new RESET press'),
    ('Cause_PSH', 'Bool', 'PSH-101 tripped the scrubber; kept for the HMI until RESET (C06a)'),
    ('Cause_LSHH', 'Bool', 'LSHH-103 tripped the scrubber; kept for the HMI until RESET (C06a)'),
    ('F_DrainTO', 'Bool', 'Drain open 10 min without stop: drain closed until RESET (C04a)'),
]
SCRUB_TON = [('T_DrnMax', 'Drain open time, 10 min limit (C04a)')]


def scrubber_fb():
    nets = (
        network(N('RESET', 'Detect RESET, remember button, then clear trips only with healthy causes. C01 / C03 / C05.'), [
            (('&', '#ResetPB', ('!', '#ResetMem')), ('=', '#ResetPulse')),
            ('#ResetPB', ('=', '#ResetMem')),
            (('&', '#ResetPulse', '#PSH', '#LSHH', '#EStopOK'), ('R', '#Tripped'), ('R', '#FlareTrip'), ('R', '#Cause_PSH'), ('R', '#Cause_LSHH')),
        ]) +
        network(N('Trip', 'Trip SET follows RESET so an active cause wins. C01 / C03 / C05 / C06a.'), [
            (('|', ('!', '#PSH'), ('!', '#LSHH'), ('!', '#EStopOK')), ('S', '#Tripped')),
            (('|', ('!', '#PSH'), ('!', '#EStopOK')), ('S', '#FlareTrip')),
            (('!', '#PSH'), ('S', '#Cause_PSH')),
            (('!', '#LSHH'), ('S', '#Cause_LSHH')),
        ]) +
        network(N('Valves', 'Flare and suction follow trip memories; drain follows level while E-STOP released. C01 / C04 / C05 / E5 / E6 / E7.'), [
            (('!', '#FlareTrip'), ('=', '#FlareCmd')),
            (('!', '#Tripped'), ('=', '#SuctionCmd')),
            (('&', ('|', ('!', '#LSH'), ('!', '#LSHH')), '#EStopOK', ('!', '#F_DrainTO')), ('=', '#DrainCmd')),
        ]) +
        network(N('Drain time limit', 'Valve command precedes timeout SET; RESET follows SET and wins. C04a.'), [
            (('&', '#DrainCmd', ('TON', '#T_DrnMax', 'T#10M')), ('S', '#F_DrainTO')),
            ('#ResetPulse', ('R', '#F_DrainTO')),
        ])
    )
    nets += network(N('Alarms', 'Display Common bits 0..5 from HMI_ALARMS. C01 / C02 / C03 / C04 / C04a / C05 / C06a.'), alarm_rungs('Common'))
    iface = interface([
        ('Input', [member(n, 'Bool', retain=False, comment=c) for n, c in SCRUB_IN]),
        ('Output', [member(n, 'Word' if n == 'Alarms' else 'Bool', retain=False, comment=c) for n, c in SCRUB_OUT]),
        ('InOut', []),
        ('Static', [member(n, t, retain=False, comment=c) for n, t, c in SCRUB_STAT] +
         [member(t, 'TON_TIME', comment=c) for t, c in SCRUB_TON]),
        ('Temp', []), ('Constant', [])])
    return code_block('SW.Blocks.FB', 'Scrubber', 2, iface, nets)


def scrubber_db():
    iface = interface([
        ('Input', [member(n, 'Bool', retain=False, comment=c) for n, c in SCRUB_IN]),
        ('Output', [member(n, 'Word' if n == 'Alarms' else 'Bool', retain=False, comment=c) for n, c in SCRUB_OUT]),
        ('InOut', []),
        ('Static', [member(n, t, retain=False, comment=c) for n, t, c in SCRUB_STAT] +
         [member(t, 'TON_TIME', short_ton=True, comment=c) for t, c in SCRUB_TON])])
    return db_block('SW.Blocks.InstanceDB', 'Scrubber_DB', 5, iface, instance_of='Scrubber')


# ======================================================================
#  Burner (FB1) — نفس البلوك لـ BR01 وBR02
# ======================================================================
BR_IN = [
    ('Auto', 'Bool', 'AUTO/MAN selector: 1 = AUTO'),
    ('StartPB', 'Bool', 'START push button (NO): 1 = pressed'),
    ('StopOK', 'Bool', 'STOP push button (NC): 1 = released'),
    ('LevelOK', 'Bool', 'Tank low-level switch: 1 = level OK (C0xa)'),
    ('RunFb', 'Bool', 'RUN from the burner control box: 1 = firing'),
    ('Lockout', 'Bool', 'LOCKOUT from the burner control box: 1 = locked out (C0xe)'),
    ('Fuel', 'Bool', 'BR02 fuel selector: 1 = diesel. BR01: FALSE'),
    ('TeA', 'Int', 'Thermocouple A, 0.1 degC'),
    ('TeB', 'Int', 'Thermocouple B, 0.1 degC'),
    ('EStopOK', 'Bool', 'Raw E-STOP status: 1 = released (C01)'),
    ('ScrubTrip', 'Bool', 'Scrubber trip cancels START (C03 / C05)'),
    ('SP', 'Int', 'Stop temperature, 0.1 degC (C0xb)'),
    ('HYST', 'Int', 'Restart difference, 0.1 degC (C0xb)'),
    ('STG', 'Int', 'Stage 2 difference, 0.1 degC (C0xc)'),
    ('Use24h', 'Bool', 'Daily stop used for BR01 only (C07h)'),
]
BR_OUT = [
    ('HeatReq', 'Bool', 'Heat request to the burner: TL / L (E1 / E3)'),
    ('Stage2', 'Bool', 'Stage 2 request to the burner: TR / T2 (E2 / E4)'),
    ('HeatLamp', 'Bool', 'Lamp follows HeatReq (E1 / E3)'),
    ('Stage2Lamp', 'Bool', 'Lamp follows Stage2 (E2 / E4)'),
    ('Alarms', 'Word', 'Alarm display word, bits 0..4 (C07 / C08)'),
]
BR_STAT = [
    ('StartEdge', 'Bool', 'New START press, one scan'),
    ('StartMem', 'Bool', 'START button state from the previous scan'),
    ('FuelChg', 'Bool', 'Fuel selector changed, one scan'),
    ('FuelMem', 'Bool', 'Fuel selector state from the previous scan'),
    ('TcOkA', 'Bool', 'Thermocouple A inside -20.0 .. 150.0 degC'),
    ('TcOkB', 'Bool', 'Thermocouple B inside -20.0 .. 150.0 degC'),
    ('TcOk', 'Bool', 'Both thermocouples valid'),
    ('TcBad', 'Bool', 'Thermocouple fault: invalid for 10 s (C0xd)'),
    ('ControlTemp', 'Int', 'Higher of the two thermocouples, 0.1 degC'),
    ('AutoRestartTemp', 'Int', 'AUTO restart temperature = SP - HYST, 0.1 degC'),
    ('SecondStageOnTemp', 'Int', 'Stage 2 ON below SP - STG, 0.1 degC'),
    ('SecondStageOffTemp', 'Int', 'Stage 2 OFF at SP - STG + 2.0 degC, 0.1 degC'),
    ('Demand', 'Bool', 'AUTO: heat demand between restart temperature and SP'),
    ('HeatNeed', 'Bool', 'Heat is needed in the selected mode'),
    ('Trip', 'Bool', 'Burner must stop and needs a new START: E-STOP, scrubber trip, lockout, thermocouple fault or fuel change'),
    ('StartEnabled', 'Bool', 'START accepted; cleared by STOP or Trip'),
    ('Pause24', 'Bool', 'Daily stop after 24 h of request (BR01, C07h)'),
    ('NoRun', 'Bool', 'Alarm: heat request without RUN for 120 s (C0xf)'),
    ('RunWrong', 'Bool', 'Alarm: RUN without heat request for 30 s (C0xg)'),
]
BR_TON = [
    ('T_TcBad', 'Thermocouple invalid time, 10 s'),
    ('T_24h', 'Heat request time for the daily stop, 24 h'),
    ('T_Pause', 'RUN off time to end the daily stop, 60 s'),
    ('T_Stage2', 'Time on stage 1 after RUN before stage 2, 30 s'),
    ('T_NoRun', 'Heat request without RUN, 120 s'),
    ('T_RunWrong', 'RUN without heat request, 30 s'),
]


def burner_fb():
    # One FB serves both instances: the local bit mapping must be identical.
    burner_alarms = alarm_rungs('BR01')
    if burner_alarms != alarm_rungs('BR02'):
        raise ValueError('BR01/BR02 alarm bits or local operands differ for shared Burner FB')
    nets = (
        network(N('Buttons', 'START edge and fuel change, in Rev B order. OB100 suppresses held START. B-01 / C08h.'), [
            (('&', '#StartPB', ('!', '#StartMem'), '#StopOK'), ('=', '#StartEdge')),
            ('#StartPB', ('=', '#StartMem')),
            (('|', ('&', '#Fuel', ('!', '#FuelMem')), ('&', ('!', '#Fuel'), '#FuelMem')), ('=', '#FuelChg')),
            ('#Fuel', ('=', '#FuelMem')),
        ]) +
        network(N('Temperature', 'Validate both sensors, select MAX, calculate thresholds in Rev B order. C07b / C08b / C07c / C08c / C07d / C08d.'), [
            (('&', ('Ge', 'Int', '#TeA', '-200'), ('Le', 'Int', '#TeA', '1500')), ('=', '#TcOkA')),
            (('&', ('Ge', 'Int', '#TeB', '-200'), ('Le', 'Int', '#TeB', '1500')), ('=', '#TcOkB')),
            (('&', '#TcOkA', '#TcOkB'), ('=', '#TcOk')),
            (('&', ('!', '#TcOk'), ('TON', '#T_TcBad', 'T#10S')), ('=', '#TcBad')),
            (('Ge', 'Int', '#TeA', '#TeB'), ('MOVE', '#TeA', '#ControlTemp')),
            (('Lt', 'Int', '#TeA', '#TeB'), ('MOVE', '#TeB', '#ControlTemp')),
            (None, ('SUB', 'Int', '#SP', '#HYST', '#AutoRestartTemp'), ('SUB', 'Int', '#SP', '#STG', '#SecondStageOnTemp')),
            (None, ('ADD', 'Int', '#SecondStageOnTemp', '20', '#SecondStageOffTemp')),
        ]) +
        network(N('Heat demand', 'SET before RESET: invalid temperature or SP wins. C07b / C08b / B-01.'), [
            (('Le', 'Int', '#ControlTemp', '#AutoRestartTemp'), ('S', '#Demand')),
            (('|', ('Ge', 'Int', '#ControlTemp', '#SP'), ('!', '#TcOk')), ('R', '#Demand')),
            (('&', '#TcOk', ('|', ('&', '#Auto', '#Demand'), ('&', ('!', '#Auto'), ('Lt', 'Int', '#ControlTemp', '#SP')))), ('=', '#HeatNeed')),
        ]) +
        network(N('Trip', 'Raw E-STOP, scrubber, lockout, temperature or fuel trip before START/STOP. C01 / C03 / C05 / C07d / C08d / C07e / C08e / C08h.'), [
            (('|', ('!', '#EStopOK'), '#ScrubTrip', '#Lockout', '#TcBad', '#FuelChg'), ('=', '#Trip')),
        ]) +
        network(N('START / STOP', 'Accept new START; STOP or trip RESET follows and wins. B-01 / C01 / C03 / C05.'), [
            (('&', '#StartEdge', ('!', '#Trip'), '#LevelOK', ('|', '#Auto', '#HeatNeed')), ('S', '#StartEnabled')),
            (('|', ('!', '#StopOK'), '#Trip'), ('R', '#StartEnabled')),
        ]) +
        network(N('Daily stop', 'Read previous scan HeatReq; 60 s pause RESET follows 24 h SET. C07h.'), [
            (('&', '#Use24h', '#HeatReq', ('TON', '#T_24h', 'T#24H')), ('S', '#Pause24')),
            (('&', '#Pause24', ('!', '#RunFb'), ('TON', '#T_Pause', 'T#60S')), ('R', '#Pause24')),
        ]) +
        network(N('Heat request', 'Request and lamp share rung; MAN cancellation follows. C07a / C08a / C07b / C08b / E1 / E3 / B-01.'), [
            (('&', '#StartEnabled', '#LevelOK', ('!', '#Pause24'), '#HeatNeed'), ('=', '#HeatReq'), ('=', '#HeatLamp')),
            (('&', ('!', '#Auto'), ('!', '#HeatReq')), ('R', '#StartEnabled')),
        ]) +
        network(N('Stage 2', 'SET before RESET, then copy the final stage state to lamp. C07c / C08c / E2 / E4.'), [
            (('&', '#HeatReq', '#RunFb', ('TON', '#T_Stage2', 'T#30S'), ('Lt', 'Int', '#ControlTemp', '#SecondStageOnTemp')), ('S', '#Stage2')),
            (('|', ('Ge', 'Int', '#ControlTemp', '#SecondStageOffTemp'), ('!', '#HeatReq'), ('!', '#RunFb')), ('R', '#Stage2')),
            ('#Stage2', ('=', '#Stage2Lamp')),
        ])
    )
    nets += network(N('Alarms', 'NoRun and RunWrong are alarms only; then display bits from HMI_ALARMS. C07e / C08e / C07d / C08d / C07f / C08f / C07g / C08g / C07a / C08a.'), [
        (('&', '#HeatReq', ('!', '#RunFb'), ('TON', '#T_NoRun', 'T#120S')), ('=', '#NoRun')),
        (('&', '#RunFb', ('!', '#HeatReq'), ('TON', '#T_RunWrong', 'T#30S')), ('=', '#RunWrong')),
    ] + burner_alarms)
    stat = ([member(n, t, retain=False, comment=c) for n, t, c in BR_STAT] +
            [member(t, 'TON_TIME', comment=c) for t, c in BR_TON])
    iface = interface([
        ('Input', [member(n, t, retain=False, comment=c) for n, t, c in BR_IN]),
        ('Output', [member(n, t, retain=False, comment=c) for n, t, c in BR_OUT]),
        ('InOut', []), ('Static', stat), ('Temp', []), ('Constant', [])])
    return code_block('SW.Blocks.FB', 'Burner', 1, iface, nets)


def burner_db(name, number):
    stat = [member(n, t, retain=False, comment=c) for n, t, c in BR_STAT]
    stat += [member(t, 'TON_TIME', short_ton=True, comment=c) for t, c in BR_TON]
    iface = interface([
        ('Input', [member(n, t, retain=False, comment=c) for n, t, c in BR_IN]),
        ('Output', [member(n, t, retain=False, comment=c) for n, t, c in BR_OUT]),
        ('InOut', []),
        ('Static', stat)])
    return db_block('SW.Blocks.InstanceDB', name, number, iface, instance_of='Burner')


# ======================================================================
#  HMI — جدول واحد للبتات وتعليقات الـ DB وشبكات النقل
# ======================================================================
# (Word، bit، إشارة PLC، النص، بيختفي إمتى، المرجع).
# '!' قبل المعامل = كونتاكت NC. البت = 1 يعني الإنذار ظاهر. لا Ack.
HMI_ALARMS = [
    ('Common', 0, '!#EStopOK', 'E-STOP pressed',
     'Release E-STOP; then RESET the scrubber and START the burners', 'C01'),
    ('Common', 1, '#Tripped', 'Scrubber tripped: reset required',
     'RESET with pressure, very high level and E-STOP healthy', 'C02 / C03 / C05'),
    ('Common', 2, '#Cause_PSH', 'Scrubber trip: high pressure',
     'RESET with all scrubber trip causes healthy', 'C03 / C06a'),
    ('Common', 3, '#Cause_LSHH', 'Scrubber trip: very high level',
     'RESET with all scrubber trip causes healthy', 'C05 / C06a'),
    ('Common', 4, '!#LSH', 'Scrubber high level (LSH-102)',
     'Automatically when level returns', 'C04'),
    ('Common', 5, '#F_DrainTO', 'Scrubber drain time limit reached',
     'RESET (drain follows level again)', 'C04a'),
] + [a for br, tk, c in (('BR01', 'TK01', 'C07'), ('BR02', 'TK02', 'C08')) for a in [
    (br, 0, '#Lockout', '%s burner lockout' % br,
     'Reset at the burner box, then START', c + 'e'),
    (br, 1, '#TcBad', '%s temperature input fault' % br,
     'Automatically when both sensors are valid; then START', c + 'd'),
    (br, 2, '#NoRun', '%s RUN not received' % br,
     'Automatically when RUN arrives or the request stops', c + 'f'),
    (br, 3, '#RunWrong', '%s RUN without request' % br,
     'Automatically when RUN goes off', c + 'g'),
    (br, 4, '!#LevelOK', '%s level too low for %s' % (tk, br),
     'Automatically when level returns', c + 'a'),
]]


def alarm_rungs(word):
    return [(('!', operand[1:]) if operand.startswith('!') else operand,
             ('=', '#Alarms.%%X%d' % bit))
            for w, bit, operand, text, clears, source in HMI_ALARMS if w == word]


# ======================================================================
#  OB100 و OB1
# ======================================================================
def startup_ob():
    nets = network(N('Power-up', 'Latch scrubber trips and seed START/RESET memories; held buttons need release. FuelMem remains FALSE. C02 / B-01.'), [
        (None, ('S', '"Scrubber_DB".Tripped'), ('S', '"Scrubber_DB".FlareTrip'),
         ('S', '"Scrubber_DB".ResetMem'), ('S', '"BR01_DB".StartMem'), ('S', '"BR02_DB".StartMem')),
    ])
    iface = interface([
        ('Input', ['<Member Name="LostRetentive" Datatype="Bool" Accessibility="Public" '
                   'Informative="true" />',
                   '<Member Name="LostRTC" Datatype="Bool" Accessibility="Public" '
                   'Informative="true" />']),
        ('Temp', []), ('Constant', [])])
    return code_block('SW.Blocks.OB', 'Startup', 100, iface, nets,
                      extra_attrs='      <SecondaryType>Startup</SecondaryType>\n',
                      comment='Startup OB (decisions/0006)')


def burner_params(br):
    if br == 'BR01':
        io = ['"S4_BR01_Auto"', '"S1_BR01_Start"', '"S3_BR01_Stop"',
              '"LSL_TK01"', '"BR01_Run"', '"BR01_Fault"', 'FALSE',
              '"TE_501_Raw"', '"TE_502_Raw"']
    else:
        io = ['"S5_BR02_Auto"', '"S6_BR02_Start"', '"S7_BR02_Stop"',
              '"LSL_TK02"', '"BR02_Run"', '"BR02_Fault"', '"Rfuel2_BR02_DieselMode"',
              '"TE_503_Raw"', '"TE_504_Raw"']
    io += ['"S0_EStopStatus"', '"Scrubber_DB".Tripped', '"Par".SP', '"Par".HYST', '"Par".STG',
           'TRUE' if br == 'BR01' else 'FALSE']
    params = [(n, 'Input', t, op) for (n, t, _), op in zip(BR_IN, io)]
    outputs = [('HeatReq', '"BR01_TL_Cmd"'), ('Stage2', '"BR01_TR_Cmd"')] if br == 'BR01' else [
        ('HeatReq', '"BR02_L_Cmd"'), ('Stage2', '"BR02_T2_Cmd"'),
        ('HeatLamp', '"BR02_Stage1Lamp_Cmd"'), ('Stage2Lamp', '"BR02_Stage2Lamp_Cmd"')]
    return params + [(n, 'Output', 'Bool', op) for n, op in outputs]


def main_ob():
    limits = []
    for n, t, d, lo, hi, txt in PARAMS:
        p = '"Par".' + n
        limits += [(('Lt', t, p, lo), ('MOVE', lo, p)),
                   (('Gt', t, p, hi), ('MOVE', hi, p))]
    nets = network(N('Settings limits', 'Clamp SP, HYST, STG, minimum then maximum, before calls. C07b / C08b / C07c / C08c; C&E Parameters.'), limits)
    scrub_io = ['"PSH_101"', '"LSH_102"', '"LSHH_103"', '"S0_EStopStatus"', '"S2_FaultReset"']
    scrub_params = [(n, 'Input', 'Bool', op) for (n, _), op in zip(SCRUB_IN, scrub_io)]
    scrub_params += [(n, 'Output', 'Bool', op) for n, op in [
        ('FlareCmd', '"XV_401_Cmd"'), ('DrainCmd', '"XV_402_Cmd"'), ('SuctionCmd', '"XV_403_Cmd"')]]
    nets += [
        call(N('Scrubber', 'All scrubber inputs and valve outputs; evaluated before burners. C01 / C03 / C04 / C05 / E5 / E6 / E7.'), 'Scrubber', 'FB', 'Scrubber_DB', scrub_params),
        call(N('BR01', 'All BR01 I/O, settings, daily stop enabled, fixed gas. C07 / E1 / E2.'), 'Burner', 'FB', 'BR01_DB', burner_params('BR01')),
        call(N('BR02', 'All BR02 I/O including fuel and both lamp relays; daily stop disabled. C08 / E3 / E4.'), 'Burner', 'FB', 'BR02_DB', burner_params('BR02')),
    ]
    iface = interface([
        ('Input', ['<Member Name="Initial_Call" Datatype="Bool" Accessibility="Public" '
                   'Informative="true" />',
                   '<Member Name="Remanence" Datatype="Bool" Accessibility="Public" '
                   'Informative="true" />']),
        ('Temp', []), ('Constant', [])])
    return code_block('SW.Blocks.OB', 'Main', 1, iface, nets,
                      extra_attrs='      <SecondaryType>ProgramCycle</SecondaryType>\n',
                      comment='Setting limits then visible physical I/O on the FB calls')


# الترتيب ده هو ترتيب الاستيراد.
BLOCKS = [
    ('Par.xml', par_db), ('Burner.xml', burner_fb), ('Scrubber.xml', scrubber_fb),
    ('BR01_DB.xml', lambda: burner_db('BR01_DB', 3)),
    ('BR02_DB.xml', lambda: burner_db('BR02_DB', 4)), ('Scrubber_DB.xml', scrubber_db),
    ('Startup.xml', startup_ob), ('Main.xml', main_ob),
]


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    documents = [(fname, fn()) for fname, fn in BLOCKS]
    # Remove only the five obsolete generated block files, never user artifacts.
    for name in ('Sys', 'HmiAlm', 'Common', 'Outputs', 'HmiMap'):
        obsolete = os.path.join(OUT, name + '.xml')
        if os.path.isfile(obsolete):
            os.remove(obsolete)
    for fname, xml in documents:
        with io.open(os.path.join(OUT, fname), 'w', encoding='utf-8') as f:
            f.write(xml)
    print('wrote %d files to build\\blocks' % len(BLOCKS))
    print('import order: -Files ' + ','.join('blocks\\' + f for f, _ in BLOCKS))


if __name__ == '__main__':
    main()
