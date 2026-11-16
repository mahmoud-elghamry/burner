# -*- coding: utf-8 -*-
"""مولّد بلوكات البرنامج (decisions/0006) — SimaticML لادر لـ TIA V15.1.

    py tools\\build_blocks.py          # بيكتب build\\blocks\\*.xml

وبعدين الاستيراد بالترتيب اللي بيطبعه (DBs قبل البلوكات اللي بتستخدمها،
والـ FB قبل الـ instance DB، والـ OB في الآخر):

    powershell -ExecutionPolicy Bypass -File tools\\Apply-Blocks.ps1 -Files <...>

كل network عنوانه رقم صف من الـ C&E أو سطر من docs/التشغيل.md. والمعامل
بيتكتب بصيغة TIA: '"Tag"' و'"DB".Member' و'#Local' و'#T_X.Q' و'700' و'T#10S'
و'TRUE'. وبتات Word بصيغة '"HmiAlm".Common.%X0' (slice على العضو).
"""
from __future__ import print_function
import io, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ladxml as L
import panel_text as P

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'blocks')


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
            comps = spec[1:].split('.')
            body = ('    <Access Scope="LocalVariable" UId="%s">\n      <Symbol>\n%s'
                    '      </Symbol>\n    </Access>')
            self.accesses.append(body % (u, ''.join(
                '        <Component Name="%s" />\n' % L.esc(c) for c in comps)))
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


def call(title, name, block_type, instance=None, params=()):
    """params = [(اسم, Section, Type, معامل), ...] — الدخول بس بتتوصّل."""
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
        net.wire(net.operand(op), net.pin(u, n))
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
#  Scrubber (FB2) — السكرابر وحافة RESET
# ======================================================================
SCRUB_IN = [('PSH', 'PSH-101 healthy: 1 = contact closed (normal pressure)'),
            ('LSH', 'LSH-102 healthy: 1 = level below high'),
            ('LSHH', 'LSHH-103 healthy: 1 = level below very high'),
            ('EStopOK', 'Raw E-STOP status: 1 = released (C01)'),
            ('ResetPB', 'Raw RESET S2 push button; rising edge detected locally')]
SCRUB_OUT = [('FlareCmd', 'XV-401 flare (NO): 1 = energised = closed'),
             ('DrainCmd', 'XV-402 drain (NC): 1 = energised = open'),
             ('SuctionCmd', 'XV-403 suction (NC): 1 = energised = open')]
SCRUB_STAT = [
    ('ResetMem', 'Bool', 'RESET button state from the previous scan; seeded TRUE by OB100'),
    ('ResetPulse', 'Bool', 'One-scan pulse on a new RESET press'),
    ('Tripped', 'Bool', 'Scrubber trip (PSH, LSHH, E-STOP, power-up): suction closed, both burners stopped, until RESET'),
    ('FlareTrip', 'Bool', 'Flare trip (PSH, E-STOP, power-up): flare open until RESET'),
    ('Cause_PSH', 'Bool', 'PSH-101 tripped the scrubber; kept for the HMI until RESET (C06a)'),
    ('Cause_LSHH', 'Bool', 'LSHH-103 tripped the scrubber; kept for the HMI until RESET (C06a)'),
    ('F_DrainTO', 'Bool', 'Drain open 10 min without stop: drain closed until RESET (C04a)'),
]
SCRUB_TON = [('T_DrnMax', 'Drain open time, 10 min limit (C04a)')]


def scrubber_fb():
    healthy_reset = ('&', '#ResetPulse', '#PSH', '#LSHH', '#EStopOK')
    nets = [
        rung(N('RESET: new press', 'One-scan pulse on a new S2 press; OB100 seeds ResetMem so a held button is ignored. C01 / C02.'),
             ('&', '#ResetPB', ('!', '#ResetMem')), ('=', '#ResetPulse')),
        rung(N('RESET: remember the button', 'Save S2 for the next scan.'),
             '#ResetPB', ('=', '#ResetMem')),
        rung(N('RESET the scrubber trip', 'RESET with pressure, very high level and E-STOP healthy clears both trips and the saved causes. C03 / C05.'),
             healthy_reset, ('R', '#Tripped'), ('R', '#FlareTrip'),
             ('R', '#Cause_PSH'), ('R', '#Cause_LSHH')),
        rung(N('Scrubber trip', 'High pressure, very high level or E-STOP: trip. OB100 trips at power-up. C01 / C02 / C03 / C05.'),
             ('|', ('!', '#PSH'), ('!', '#LSHH'), ('!', '#EStopOK')),
             ('S', '#Tripped')),
        rung(N('Flare trip', 'High pressure or E-STOP open the flare. OB100 opens it at power-up. Very high level alone does not. C01 / C02 / C03.'),
             ('|', ('!', '#PSH'), ('!', '#EStopOK')),
             ('S', '#FlareTrip')),
        rung(N('Save cause: high pressure', 'Keep PSH-101 for the HMI even if the pressure comes back. C06a.'),
             ('!', '#PSH'), ('S', '#Cause_PSH')),
        rung(N('Save cause: very high level', 'Keep LSHH-103 for the HMI even if the level comes back. C06a.'),
             ('!', '#LSHH'), ('S', '#Cause_LSHH')),
        rung(N('XV-401 flare', 'Normally open valve: energise to close while there is no flare trip. E5.'),
             ('!', '#FlareTrip'), ('=', '#FlareCmd')),
        rung(N('XV-403 suction', 'Normally closed valve: energise to open while there is no scrubber trip. E7.'),
             ('!', '#Tripped'), ('=', '#SuctionCmd')),
        rung(N('XV-402 drain', 'Normally closed valve: open while LSH-102 or LSHH-103 shows high level. Not during E-STOP or after the 10 min limit. C04 / C05 / E6.'),
             ('&', ('|', ('!', '#LSH'), ('!', '#LSHH')), '#EStopOK', ('!', '#F_DrainTO')),
             ('=', '#DrainCmd')),
        rung(N('Drain open too long', 'Drain open 10 min without a stop: close it and alarm. Protects against a broken LSH-102 wire. C04a.'),
             ('&', '#DrainCmd', ('TON', '#T_DrnMax', 'T#10M')), ('S', '#F_DrainTO')),
        rung(N('RESET the drain limit', 'RESET lets the drain follow the level again. C04a.'),
             '#ResetPulse', ('R', '#F_DrainTO')),
    ]
    iface = interface([
        ('Input', [member(n, 'Bool', retain=None, comment=c) for n, c in SCRUB_IN]),
        ('Output', [member(n, 'Bool', retain=False, comment=c) for n, c in SCRUB_OUT]),
        ('InOut', []),
        ('Static', [member(n, t, retain=False, comment=c) for n, t, c in SCRUB_STAT] +
         [member(t, 'TON_TIME', comment=c) for t, c in SCRUB_TON]),
        ('Temp', []), ('Constant', [])])
    return code_block('SW.Blocks.FB', 'Scrubber', 2, iface, nets)


def scrubber_db():
    iface = interface([
        ('Input', [member(n, 'Bool', retain=False, comment=c) for n, c in SCRUB_IN]),
        ('Output', [member(n, 'Bool', retain=False, comment=c) for n, c in SCRUB_OUT]),
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
]
BR_OUT = [
    ('HeatReq', 'Bool', 'Heat request to the burner: TL / L (E1 / E3)'),
    ('Stage2', 'Bool', 'Stage 2 request to the burner: TR / T2 (E2 / E4)'),
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
    ('Use24h', 'Bool', 'Daily stop used for this burner (BR01 only)'),
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
    nets = [
        # ---- الزراير ------------------------------------------------------
        rung(N('START: new press', 'One-scan pulse on a new START press; OB100 seeds StartMem so a held button is ignored. STOP wins. C02 / B-01.'),
             ('&', '#StartPB', ('!', '#StartMem'), '#StopOK'),
             ('=', '#StartEdge')),
        rung(N('START: remember the button', 'Save START for the next scan.'),
             '#StartPB', ('=', '#StartMem')),
        rung(N('Fuel selector changed', 'Either direction counts. BR01 has a fixed FALSE. C08h.'),
             ('|', ('&', '#Fuel', ('!', '#FuelMem')), ('&', ('!', '#Fuel'), '#FuelMem')),
             ('=', '#FuelChg')),
        rung(N('Fuel selector: remember', 'Save the fuel selector for the next scan.'),
             '#Fuel', ('=', '#FuelMem')),
        # ---- الحرارة ------------------------------------------------------
        rung(N('Thermocouple A valid', '-20.0 .. 150.0 degC; a broken sensor reads outside. C0xd.'),
             ('&', ('Ge', 'Int', '#TeA', '-200'), ('Le', 'Int', '#TeA', '1500')), ('=', '#TcOkA')),
        rung(N('Thermocouple B valid', 'Same limits for sensor B. C0xd.'),
             ('&', ('Ge', 'Int', '#TeB', '-200'), ('Le', 'Int', '#TeB', '1500')), ('=', '#TcOkB')),
        rung(N('Both thermocouples valid', 'Both are needed to heat. C0xd.'),
             ('&', '#TcOkA', '#TcOkB'), ('=', '#TcOk')),
        rung(N('Thermocouple fault', 'Not valid for 10 s (also right after power-up, while the card starts): fault. C0xd.'),
             ('&', ('!', '#TcOk'), ('TON', '#T_TcBad', 'T#10S')), ('=', '#TcBad')),
        rung(N('Temperature = sensor A', 'Use A when A is the higher one. C0xb.'),
             ('Ge', 'Int', '#TeA', '#TeB'), ('MOVE', '#TeA', '#ControlTemp')),
        rung(N('Temperature = sensor B', 'Use B when B is the higher one. C0xb.'),
             ('Lt', 'Int', '#TeA', '#TeB'), ('MOVE', '#TeB', '#ControlTemp')),
        rung(N('Restart and stage 2 temperatures', 'Restart = SP - HYST. Stage 2 ON below SP - STG. C0xb / C0xc.'), None,
             ('SUB', 'Int', '"Par".SP', '"Par".HYST', '#AutoRestartTemp'),
             ('SUB', 'Int', '"Par".SP', '"Par".STG', '#SecondStageOnTemp')),
        rung(N('Stage 2 OFF temperature', 'Stage 2 ON temperature + 2.0 degC, so relay R2 / R7 does not chatter. C0xc.'), None,
             ('ADD', 'Int', '#SecondStageOnTemp', '20', '#SecondStageOffTemp')),
        rung(N('AUTO: heat demand ON', 'At or below the restart temperature. C0xb.'),
             ('Le', 'Int', '#ControlTemp', '#AutoRestartTemp'), ('S', '#Demand')),
        rung(N('AUTO: heat demand OFF', 'At or above SP, or no valid temperature. C0xb.'),
             ('|', ('Ge', 'Int', '#ControlTemp', '"Par".SP'), ('!', '#TcOk')), ('R', '#Demand')),
        rung(N('Heat needed', 'AUTO: the demand above. MAN: temperature below SP.'),
             ('&', '#TcOk', ('|', ('&', '#Auto', '#Demand'),
                             ('&', ('!', '#Auto'), ('Lt', 'Int', '#ControlTemp', '"Par".SP')))),
             ('=', '#HeatNeed')),
        # ---- START / STOP ------------------------------------------------
        rung(N('Burner trip', 'E-STOP, scrubber trip, burner lockout, thermocouple fault or fuel change: stop; a new START is needed. C01 / C03 / C05 / C0xd / C0xe / C08h.'),
             ('|', ('!', '#EStopOK'), '"Scrubber_DB".Tripped', '#Lockout', '#TcBad', '#FuelChg'),
             ('=', '#Trip')),
        rung(N('START accepted', 'New START with no trip and tank level OK. In MAN only if heat is needed.'),
             ('&', '#StartEdge', ('!', '#Trip'), '#LevelOK', ('|', '#Auto', '#HeatNeed')),
             ('S', '#StartEnabled')),
        rung(N('STOP or trip', 'STOP pressed or burner trip cancels START.'),
             ('|', ('!', '#StopOK'), '#Trip'), ('R', '#StartEnabled')),
        rung(N('Daily stop after 24 h', 'BR01 only: 24 h of continuous heat request stops the burner. RS100 manual 5.10, C07h.'),
             ('&', '#Use24h', '#HeatReq', ('TON', '#T_24h', 'T#24H')), ('S', '#Pause24')),
        rung(N('Daily stop ends', 'After RUN has been off for 60 s the burner may start again. C07h.'),
             ('&', '#Pause24', ('!', '#RunFb'), ('TON', '#T_Pause', 'T#60S')), ('R', '#Pause24')),
        rung(N('Heat request', 'START accepted, tank level OK, no daily stop and heat needed. Goes to TL / L. C0xa / C0xb.'),
             ('&', '#StartEnabled', '#LevelOK', ('!', '#Pause24'), '#HeatNeed'), ('=', '#HeatReq')),
        rung(N('MAN: one heating cycle', 'In MAN, when the heat request stops, START is cancelled; press START again.'),
             ('&', ('!', '#Auto'), ('!', '#HeatReq')), ('R', '#StartEnabled')),
        # ---- المرحلة التانية -----------------------------------------------
        rung(N('Stage 2 ON', 'Heat request, RUN for 30 s and temperature below SP - STG. Goes to TR / T2. C0xc.'),
             ('&', '#HeatReq', '#RunFb', ('TON', '#T_Stage2', 'T#30S'),
              ('Lt', 'Int', '#ControlTemp', '#SecondStageOnTemp')),
             ('S', '#Stage2')),
        rung(N('Stage 2 OFF', 'At SP - STG + 2.0 degC, or no heat request, or no RUN. C0xc.'),
             ('|', ('Ge', 'Int', '#ControlTemp', '#SecondStageOffTemp'), ('!', '#HeatReq'), ('!', '#RunFb')),
             ('R', '#Stage2')),
        # ---- إنذارات بس ---------------------------------------------------
        rung(N('Alarm: no RUN', 'Heat request without RUN for 120 s: alarm only (broken TL / L wire, no burner supply). C0xf.'),
             ('&', '#HeatReq', ('!', '#RunFb'), ('TON', '#T_NoRun', 'T#120S')), ('=', '#NoRun')),
        rung(N('Alarm: RUN without request', 'RUN without heat request for 30 s: alarm only (stuck relay R1 / R6). C0xg.'),
             ('&', '#RunFb', ('!', '#HeatReq'), ('TON', '#T_RunWrong', 'T#30S')), ('=', '#RunWrong')),
    ]
    stat = ([member(n, t, retain=False, comment=c) for n, t, c in BR_STAT] +
            [member(t, 'TON_TIME', comment=c) for t, c in BR_TON])
    iface = interface([
        ('Input', [member(n, t, retain=None, comment=c) for n, t, c in BR_IN]),
        ('Output', [member(n, t, retain=False, comment=c) for n, t, c in BR_OUT]),
        ('InOut', []), ('Static', stat), ('Temp', []), ('Constant', [])])
    return code_block('SW.Blocks.FB', 'Burner', 1, iface, nets)


def burner_db(name, number, use24h=False):
    stat = [member(n, t, retain=False, comment=c,
                   start=('true' if use24h else 'false') if n == 'Use24h' else None)
            for n, t, c in BR_STAT]
    stat += [member(t, 'TON_TIME', short_ton=True, comment=c) for t, c in BR_TON]
    iface = interface([
        ('Input', [member(n, t, retain=False, comment=c) for n, t, c in BR_IN]),
        ('Output', [member(n, t, retain=False, comment=c) for n, t, c in BR_OUT]),
        ('InOut', []),
        ('Static', stat)])
    return db_block('SW.Blocks.InstanceDB', name, number, iface, instance_of='Burner')


# ======================================================================
#  Outputs (FC2) — المكان الوحيد اللي بيكتب %Q
# ======================================================================
def outputs_fc():
    nets = [
        rung(N('BR01: heat request TL', 'Relay R1 and lamp H1. Only with E-STOP healthy. E1.'),
             ('&', '"BR01_DB".HeatReq', '"S0_EStopStatus"'), ('=', '"BR01_TL_Cmd"')),
        rung(N('BR01: stage 2 TR', 'Relay R2 and lamp H2. E2.'),
             ('&', '"BR01_DB".Stage2', '"S0_EStopStatus"'), ('=', '"BR01_TR_Cmd"')),
        rung(N('BR02: heat request L', 'Relay R6 and stage 1 lamp H5 (R8). E3.'),
             ('&', '"BR02_DB".HeatReq', '"S0_EStopStatus"'),
             ('=', '"BR02_L_Cmd"'), ('=', '"BR02_Stage1Lamp_Cmd"')),
        rung(N('BR02: stage 2 T2', 'Relay R7 and stage 2 lamp H6 (R9). E4.'),
             ('&', '"BR02_DB".Stage2', '"S0_EStopStatus"'),
             ('=', '"BR02_T2_Cmd"'), ('=', '"BR02_Stage2Lamp_Cmd"')),
        rung(N('XV-401 flare', 'Output ON closes the normally open flare valve. E5.'),
             '"Scrubber_DB".FlareCmd', ('=', '"XV_401_Cmd"')),
        rung(N('XV-402 drain', 'Output ON opens the normally closed drain valve. E6.'),
             '"Scrubber_DB".DrainCmd', ('=', '"XV_402_Cmd"')),
        rung(N('XV-403 suction', 'Output ON opens the normally closed suction valve. E7.'),
             '"Scrubber_DB".SuctionCmd', ('=', '"XV_403_Cmd"')),
    ]
    iface = interface([('Input', []), ('Output', []), ('InOut', []), ('Temp', []),
                       ('Constant', []), ('Return', ['<Member Name="Ret_Val" Datatype="Void" />'])])
    return code_block('SW.Blocks.FC', 'Outputs', 2, iface, nets)


# ======================================================================
#  HMI — جدول واحد للبتات وتعليقات الـ DB وشبكات النقل
# ======================================================================
# (Word، bit، إشارة PLC، النص، بيختفي إمتى، المرجع).
# '!' قبل المعامل = كونتاكت NC. البت = 1 يعني الإنذار ظاهر. لا Ack.
HMI_ALARMS = [
    ('Common', 0, '!"S0_EStopStatus"', 'E-STOP pressed',
     'Release E-STOP; then RESET the scrubber and START the burners', 'C01'),
    ('Common', 1, '"Scrubber_DB".Tripped', 'Scrubber tripped: reset required',
     'RESET with pressure, very high level and E-STOP healthy', 'C02 / C03 / C05'),
    ('Common', 2, '"Scrubber_DB".Cause_PSH', 'Scrubber trip: high pressure',
     'RESET with all scrubber trip causes healthy', 'C03 / C06a'),
    ('Common', 3, '"Scrubber_DB".Cause_LSHH', 'Scrubber trip: very high level',
     'RESET with all scrubber trip causes healthy', 'C05 / C06a'),
    ('Common', 4, '!"Scrubber_DB".LSH', 'Scrubber high level (LSH-102)',
     'Automatically when level returns', 'C04'),
    ('Common', 5, '"Scrubber_DB".F_DrainTO', 'Scrubber drain time limit reached',
     'RESET (drain follows level again)', 'C04a'),
] + [a for br, tk, c in (('BR01', 'TK01', 'C07'), ('BR02', 'TK02', 'C08')) for a in [
    (br, 0, '"%s_DB".Lockout' % br, '%s burner lockout' % br,
     'Reset at the burner box, then START', c + 'e'),
    (br, 1, '"%s_DB".TcBad' % br, '%s temperature input fault' % br,
     'Automatically when both sensors are valid; then START', c + 'd'),
    (br, 2, '"%s_DB".NoRun' % br, '%s RUN not received' % br,
     'Automatically when RUN arrives or the request stops', c + 'f'),
    (br, 3, '"%s_DB".RunWrong' % br, '%s RUN without request' % br,
     'Automatically when RUN goes off', c + 'g'),
    (br, 4, '!"%s_DB".LevelOK' % br, '%s level too low for %s' % (tk, br),
     'Automatically when level returns', c + 'a'),
]]


def hmi_alm_db():
    mems = [member(word, 'Word', retain=False,
                   comment='; '.join('x%d %s [%s]' % (bit, text, source)
                                     for w, bit, _, text, _, source in HMI_ALARMS if w == word))
            for word in ('Common', 'BR01', 'BR02')]
    return db_block('SW.Blocks.GlobalDB', 'HmiAlm', 6, interface([('Static', mems)]))


def hmi_map_fc():
    nets = []
    for word, bit, operand, text, clears, source in HMI_ALARMS:
        expr = ('!', operand[1:]) if operand.startswith('!') else operand
        nets.append(rung(N('Alarm %s.x%d: %s' % (word, bit, text), 'Clears: %s. %s.' % (clears, source)),
                         expr, ('=', '"HmiAlm".%s.%%X%d' % (word, bit))))
    iface = interface([('Input', []), ('Output', []), ('InOut', []), ('Temp', []),
                       ('Constant', []), ('Return', ['<Member Name="Ret_Val" Datatype="Void" />'])])
    return code_block('SW.Blocks.FC', 'HmiMap', 3, iface, nets)


# ======================================================================
#  OB100 و OB1
# ======================================================================
def startup_ob():
    nets = [rung(N('Power-up', 'Latch scrubber trips and seed START/RESET memories; held buttons need release. FuelMem remains FALSE. C02 / B-01.'),
                 None, ('S', '"Scrubber_DB".Tripped'), ('S', '"Scrubber_DB".FlareTrip'),
                 ('S', '"Scrubber_DB".ResetMem'), ('S', '"BR01_DB".StartMem'), ('S', '"BR02_DB".StartMem'))]
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
    io += ['"S0_EStopStatus"']
    return [(n, 'Input', t, op) for (n, t, _), op in zip(BR_IN, io)]


def main_ob():
    scrub_io = ['"PSH_101"', '"LSH_102"', '"LSHH_103"', '"S0_EStopStatus"', '"S2_FaultReset"']
    nets = []
    for n, t, d, lo, hi, txt in PARAMS:
        p = '"Par".%s' % n
        nets += [
            rung(N('%s below its minimum' % n, '%s below %s: use %s. Sheet Parameters.' % (n, lo, lo)),
                 ('Lt', t, p, lo), ('MOVE', lo, p)),
            rung(N('%s above its maximum' % n, '%s above %s: use %s. Sheet Parameters.' % (n, hi, hi)),
                 ('Gt', t, p, hi), ('MOVE', hi, p)),
        ]
    nets += [
        call(N('Scrubber', 'PSH-101, LSH-102, LSHH-103: trips and valve commands, before the burners.'), 'Scrubber', 'FB', 'Scrubber_DB',
             [(n, 'Input', 'Bool', op) for (n, _), op in zip(SCRUB_IN, scrub_io)]),
        call(N('Burner BR01 on tank TK01', 'Burner block with BR01_DB; BR01 has no fuel selector and uses the daily stop.'), 'Burner', 'FB', 'BR01_DB', burner_params('BR01')),
        call(N('Burner BR02 on tank TK02', 'Same burner block with BR02_DB.'), 'Burner', 'FB', 'BR02_DB', burner_params('BR02')),
        call(N('Outputs', 'The only block that writes the Q outputs.'), 'Outputs', 'FC'),
        call(N('HMI alarms', 'Copies the alarm bits for the panel; no control here.'), 'HmiMap', 'FC'),
    ]
    iface = interface([
        ('Input', ['<Member Name="Initial_Call" Datatype="Bool" Accessibility="Public" '
                   'Informative="true" />',
                   '<Member Name="Remanence" Datatype="Bool" Accessibility="Public" '
                   'Informative="true" />']),
        ('Temp', []), ('Constant', [])])
    return code_block('SW.Blocks.OB', 'Main', 1, iface, nets,
                      extra_attrs='      <SecondaryType>ProgramCycle</SecondaryType>\n',
                      comment='Setting limits, then calls the blocks in a fixed order (decisions/0006)')


# الترتيب ده هو ترتيب الاستيراد.
BLOCKS = [
    ('Par.xml', par_db), ('HmiAlm.xml', hmi_alm_db),
    ('Scrubber.xml', scrubber_fb), ('Scrubber_DB.xml', scrubber_db),
    ('Burner.xml', burner_fb),
    ('BR01_DB.xml', lambda: burner_db('BR01_DB', 3, use24h=True)),
    ('BR02_DB.xml', lambda: burner_db('BR02_DB', 4)),
    ('Outputs.xml', outputs_fc),
    ('HmiMap.xml', hmi_map_fc),
    ('Startup.xml', startup_ob), ('Main.xml', main_ob),
]


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    for obsolete in ('Sys.xml', 'Common.xml'):
        path = os.path.join(OUT, obsolete)
        if os.path.isfile(path):
            os.remove(path)
    for fname, fn in BLOCKS:
        with io.open(os.path.join(OUT, fname), 'w', encoding='utf-8') as f:
            f.write(fn())
    print('wrote %d files to build\\blocks' % len(BLOCKS))
    print('import order: -Files ' + ','.join('blocks\\' + f for f, _ in BLOCKS))


if __name__ == '__main__':
    main()
