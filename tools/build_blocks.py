# -*- coding: utf-8 -*-
"""مولّد بلوكات البرنامج (decisions/0006) — SimaticML لادر لـ TIA V15.1.

    py tools\\build_blocks.py          # بيكتب build\\blocks\\*.xml

وبعدين الاستيراد بالترتيب اللي بيطبعه (DBs قبل البلوكات اللي بتستخدمها،
والـ FB قبل الـ instance DB، والـ OB في الآخر):

    powershell -ExecutionPolicy Bypass -File tools\\Apply-Blocks.ps1 -Files <...>

كل network عنوانه رقم صف من الـ C&E أو سطر من docs/التشغيل.md. والمعامل
بيتكتب بصيغة TIA: '"Tag"' و'"DB".Member' و'#Local' و'#T_X.Q' و'700' و'T#10S'
و'TRUE'.
"""
from __future__ import print_function
import io, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ladxml as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'blocks')


# ======================================================================
#  المعاملات وشكل الشبكة
# ======================================================================
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
            m = re.match(r'^"([^"]+)"((?:\.[A-Za-z0-9_]+)*)$', spec)
            if not m:
                raise ValueError('bad operand ' + spec)
            comps = [m.group(1)] + [c for c in m.group(2).split('.') if c]
            body = ('    <Access Scope="GlobalVariable" UId="%s">\n      <Symbol>\n%s'
                    '      </Symbol>\n    </Access>')
            self.accesses.append(body % (u, ''.join(
                '        <Component Name="%s" />\n' % L.esc(c) for c in comps)))
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
    if typ == 'TON_TIME':
        if short_ton:
            return ('<Member Name="%s" Datatype="TON_TIME" Remanence="NonRetain" '
                    'Accessibility="Public" />' % name)
        return TON_FULL % name
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
    units = [L.compile_unit(ids, flg, title) for title, flg in networks]
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
               name, number, L.mltext(ids, 'Comment'), L.mltext(ids, 'Title'), tag))


# ======================================================================
#  Par و Sys — Global DBs
# ======================================================================
# الحرارة كلها بعُشر الدرجة، زي قراءة كارت الـ TC (700 = 70.0 °C).
# (اسم، نوع، افتراضي، أقل، أعلى، وصف) — المدى من شيت Parameters في الـ C&E.
PARAMS = [
    ('SP', 'Int', '700', '400', '900', 'Setpoint, 0.1 degC (C07b)'),
    ('HYST', 'Int', '50', '30', '100', 'Restart hysteresis, 0.1 degC (C07b)'),
    ('STG', 'Int', '100', '50', '300', '2nd stage below SP - STG, 0.1 degC (C07c)'),
    ('TStart', 'Time', 'T#2M', 'T#90S', 'T#5M', 'Max. time heat request -> RUN (C07f)'),
]


def par_db():
    mems = []
    for n, t, d, lo, hi, txt in PARAMS:
        mems.append(member(n, t, d, retain=True, comment='HMI entry: ' + txt))
    for n, t, d, lo, hi, txt in PARAMS:
        mems.append(member(n + '_V', t, d, retain=True,
                           comment='Validated value used by the program (R-11)'))
    return db_block('SW.Blocks.GlobalDB', 'Par', 1, interface([('Static', mems)]))


SYS = [
    ('FirstScan', 'Set by OB100, cleared at the end of Main (C02)'),
    ('EStopOK', 'E-STOP latch: 1 = released and RESET given (C01)'),
    ('ResetPulse', 'RESET S2 rising edge, one scan (R-06)'),
    ('ResetMem', 'RESET edge memory (R-06)'),
    ('Alm_EStop', 'HMI alarm: E-STOP (C01)'),
    ('Alm_ParRejected', 'HMI alarm: a parameter entry was out of range (R-11)'),
]


def sys_db():
    mems = [member(n, 'Bool', retain=False, comment=c) for n, c in SYS]
    return db_block('SW.Blocks.GlobalDB', 'Sys', 2, interface([('Static', mems)]))


# ======================================================================
#  Common (FC1)
# ======================================================================
def common_fc():
    nets = [
        rung('R-06 — RESET edge (not on first scan)',
             ('&', '"S2_FaultReset"', ('!', '"Sys".ResetMem'), ('!', '"Sys".FirstScan')),
             ('=', '"Sys".ResetPulse')),
        rung('R-06 — RESET edge memory', '"S2_FaultReset"', ('=', '"Sys".ResetMem')),
        rung('C01 — E-STOP pressed (NC1 open) drops the latch',
             ('!', '"S0_EStopStatus"'), ('R', '"Sys".EStopOK')),
        rung('C01 — E-STOP latch back after RESET (or at power-up if released)',
             ('&', '"S0_EStopStatus"', ('|', '"Sys".ResetPulse', '"Sys".FirstScan')),
             ('S', '"Sys".EStopOK')),
        rung('C01 — E-STOP alarm', ('!', '"Sys".EStopOK'), ('=', '"Sys".Alm_EStop')),
        rung('R-11 — RESET clears the parameter alarm', '"Sys".ResetPulse',
             ('R', '"Sys".Alm_ParRejected')),
    ]
    for n, t, d, lo, hi, txt in PARAMS:
        p, v = '"Par".%s' % n, '"Par".%s_V' % n
        nets += [
            rung('R-11 — %s: stored value bad after power-up -> default' % n,
                 ('&', '"Sys".FirstScan', ('|', ('Lt', t, v, lo), ('Gt', t, v, hi))),
                 ('MOVE', d, v)),
            rung('R-11 — %s: entry in range -> used' % n,
                 ('&', ('Ge', t, p, lo), ('Le', t, p, hi)), ('MOVE', p, v)),
            rung('R-11 — %s: entry out of range -> old value back, alarm' % n,
                 ('|', ('Lt', t, p, lo), ('Gt', t, p, hi)),
                 ('MOVE', v, p), ('S', '"Sys".Alm_ParRejected')),
        ]
    iface = interface([('Input', []), ('Output', []), ('InOut', []), ('Temp', []),
                       ('Constant', []), ('Return', ['<Member Name="Ret_Val" Datatype="Void" />'])])
    return code_block('SW.Blocks.FC', 'Common', 1, iface, nets,
                      comment='E-STOP latch, RESET edge, parameter check (decisions/0006)')


# ======================================================================
#  Scrubber (FB2)
# ======================================================================
SCRUB_IN = [('PSH', 'PSH-101 healthy (contact closed)'), ('LSH', 'LSH-102 healthy'),
            ('LSHH', 'LSHH-103 healthy'), ('EStopOK', 'Sys.EStopOK'),
            ('ResetPulse', 'Sys.ResetPulse'), ('FirstScan', 'Sys.FirstScan')]
SCRUB_OUT = [('Tripped', 'Scrubber in trip, valves to safe position'),
             ('ValvesNormal', 'Q0.2..Q0.4 energised (flare/drain closed, suction open)'),
             ('Alm_PSH', 'HMI alarm C03'), ('Alm_LSH', 'HMI alarm C04'),
             ('Alm_LSHH', 'HMI alarm C05')]


def scrubber_fb():
    nets = [
        rung('C04 — LSH-102 high level: alarm only', ('!', '#LSH'), ('=', '#Alm_LSH')),
        rung('C03 / C05 — trip causes shown on the HMI', ('!', '#PSH'), ('=', '#Alm_PSH')),
        rung('C05 — LSHH-103 alarm', ('!', '#LSHH'), ('=', '#Alm_LSHH')),
        rung('C03 / C05 / C01 — RESET once every cause is gone',
             ('&', '#ResetPulse', '#PSH', '#LSHH', '#EStopOK'), ('R', '#Tripped')),
        rung('S-01 / C03 / C05 / C01 — trip (also at power-up)',
             ('|', ('!', '#PSH'), ('!', '#LSHH'), ('!', '#EStopOK'), '#FirstScan'),
             ('S', '#Tripped')),
        rung('S-01 — valves in normal position only while not tripped',
             ('!', '#Tripped'), ('=', '#ValvesNormal')),
    ]
    iface = interface([
        ('Input', [member(n, 'Bool', retain=None, comment=c) for n, c in SCRUB_IN]),
        ('Output', [member(n, 'Bool', retain=False, comment=c) for n, c in SCRUB_OUT]),
        ('InOut', []), ('Static', []), ('Temp', []), ('Constant', [])])
    return code_block('SW.Blocks.FB', 'Scrubber', 2, iface, nets,
                      comment='Gas scrubber, docs/التشغيل.md §1')


def scrubber_db():
    iface = interface([
        ('Input', [member(n, 'Bool', retain=False) for n, _ in SCRUB_IN]),
        ('Output', [member(n, 'Bool', retain=False) for n, _ in SCRUB_OUT]),
        ('InOut', []), ('Static', [])])
    return db_block('SW.Blocks.InstanceDB', 'Scrubber_DB', 5, iface, instance_of='Scrubber')


# ======================================================================
#  Burner (FB1) — نفس البلوك لـ BR01 وBR02
# ======================================================================
BR_IN = [
    ('Auto', 'Bool', 'AUTO/MAN selector, 1 = AUTO'),
    ('StartPB', 'Bool', 'START push button (NO)'),
    ('StopOK', 'Bool', 'STOP push button (NC): 1 = released'),
    ('LevelOK', 'Bool', 'Tank LSL reached (C07a)'),
    ('RunFb', 'Bool', 'Burner RUN feedback'),
    ('Lockout', 'Bool', 'Burner lockout signal (C07e)'),
    ('Fuel', 'Bool', 'Fuel mode (BR02 Rfuel2, R-12); FALSE for BR01'),
    ('TeA', 'Int', 'Thermocouple A raw, 0.1 degC'),
    ('TeB', 'Int', 'Thermocouple B raw, 0.1 degC'),
    ('Use24h', 'Bool', '24 h forced stop enabled (C07h, BR01 only)'),
    ('EStopOK', 'Bool', 'Sys.EStopOK'),
    ('ResetPulse', 'Bool', 'Sys.ResetPulse'),
    ('FirstScan', 'Bool', 'Sys.FirstScan'),
    ('SP', 'Int', 'Par.SP_V'),
    ('HYST', 'Int', 'Par.HYST_V'),
    ('STG', 'Int', 'Par.STG_V'),
    ('TStart', 'Time', 'Par.TStart_V'),
]
BR_OUT = [
    ('HeatReq', 'Bool', 'Heat request TL / L (E1 / E3)'),
    ('Stage2', 'Bool', '2nd stage TR / T2 (E2 / E4)'),
    ('State', 'Int', '0 IDLE, 1 STARTING, 2 RUNNING, 3 FAULT'),
    ('Enabled', 'Bool', 'START given and not taken back (B-01)'),
    ('Tmax', 'Int', 'Higher of the two thermocouples, 0.1 degC'),
    ('F_EStop', 'Bool', 'Fault C01'),
    ('F_TC', 'Bool', 'Fault C0xd thermocouple'),
    ('F_Lockout', 'Bool', 'Fault C0xe lockout'),
    ('F_NoStart', 'Bool', 'Fault C0xf failed to start'),
    ('F_RunLost', 'Bool', 'Fault C0xg stopped by itself'),
    ('F_RunWrong', 'Bool', 'Fault R-09 RUN without request'),
]
BR_STAT = [
    ('StartEdge', 'Bool'), ('StartMem', 'Bool'), ('AutoChg', 'Bool'), ('AutoMem', 'Bool'),
    ('FuelChg', 'Bool'), ('FuelMem', 'Bool'), ('TcOkA', 'Bool'), ('TcOkB', 'Bool'),
    ('TcOk', 'Bool'), ('TcBad', 'Bool'), ('Demand', 'Bool'), ('HeatNeed', 'Bool'),
    ('Ready', 'Bool'), ('Active', 'Bool'), ('Pause24', 'Bool'), ('RunWrong', 'Bool'),
    ('NoStart', 'Bool'), ('PwrUpDone', 'Bool'), ('TcSlow', 'Bool'), ('SP_Act', 'Int'), ('HYST_Act', 'Int'), ('STG_Act', 'Int'),
    ('TStart_Act', 'Time'), ('TOn', 'Int'), ('TStg', 'Int'), ('TStgOff', 'Int'),
]
BR_TON = ['T_PwrUp', 'T_TcBad', 'T_24h', 'T_Pause', 'T_RunOff', 'T_Start']

IDLE, STARTING, RUNNING, FAULT = '0', '1', '2', '3'


def st(n):
    return ('Eq', 'Int', '#State', n)


def burner_fb():
    active = ('|', st(STARTING), st(RUNNING))
    nets = [
        # ---- الزراير ------------------------------------------------------
        rung('R-05 — START edge: not on first scan, only after seen released, STOP wins',
             ('&', '#StartPB', ('!', '#StartMem'), ('!', '#FirstScan'), '#StopOK'),
             ('=', '#StartEdge')),
        rung('R-05 — START edge memory', '#StartPB', ('=', '#StartMem')),
        rung('R-02 — AUTO/MAN changed',
             ('|', ('&', '#Auto', ('!', '#AutoMem')), ('&', ('!', '#Auto'), '#AutoMem')),
             ('=', '#AutoChg')),
        rung('R-02 — AUTO/MAN memory', '#Auto', ('=', '#AutoMem')),
        rung('R-12 — fuel mode changed',
             ('|', ('&', '#Fuel', ('!', '#FuelMem')), ('&', ('!', '#Fuel'), '#FuelMem')),
             ('=', '#FuelChg')),
        rung('R-12 — fuel mode memory', '#Fuel', ('=', '#FuelMem')),
        # ---- الحرارة ------------------------------------------------------
        rung('C0xd — channel A valid: -20.0 .. 150.0 degC (32767 / -32768 fall outside)',
             ('&', ('Ge', 'Int', '#TeA', '-200'), ('Le', 'Int', '#TeA', '1500')),
             ('=', '#TcOkA')),
        rung('C0xd — channel B valid',
             ('&', ('Ge', 'Int', '#TeB', '-200'), ('Le', 'Int', '#TeB', '1500')),
             ('=', '#TcOkB')),
        rung('C0xd — both channels valid, each checked before MAX', ('&', '#TcOkA', '#TcOkB'),
             ('=', '#TcOk')),
        rung('R-10 — power-up window (TC card calibrating) is over after 10 s',
             ('&', ('!', '#FirstScan'), ('TON', '#T_PwrUp', 'T#10S')), ('=', '#PwrUpDone')),
        # مراجعة 2026-10-28: المهلة كانت دايمًا، فسلك سايب أقل من 10 ث كان بيوقّف
        # ويولّع من غير عطل. دلوقتي المهلة بعد رجوع الكهربا بس (R-10)، وبعدها فوري.
        # تايمر جوه فرع توازي مش مسموح ("network is not supported")، فرانجين.
        rung('C0xd / R-10 — invalid for 10 s', ('&', ('!', '#TcOk'),
                                                ('TON', '#T_TcBad', 'T#10S')),
             ('=', '#TcSlow')),
        rung('C0xd / R-10 — invalid = fault: at once, or after 10 s right after power-up',
             ('&', ('!', '#TcOk'), ('|', '#PwrUpDone', '#TcSlow')), ('=', '#TcBad')),
        rung('C0xb — temperature = higher channel (A)', ('Ge', 'Int', '#TeA', '#TeB'),
             ('MOVE', '#TeA', '#Tmax')),
        rung('C0xb — temperature = higher channel (B)', ('Lt', 'Int', '#TeA', '#TeB'),
             ('MOVE', '#TeB', '#Tmax')),
        # ---- الأرقام ------------------------------------------------------
        rung('R-11 — burner not heating: take all parameters', ('!', '#Active'),
             ('MOVE', '#SP', '#SP_Act'), ('MOVE', '#STG', '#STG_Act'),
             ('MOVE', '#TStart', '#TStart_Act')),
        rung('R-11 — lower SP applies at once', ('Le', 'Int', '#SP', '#SP_Act'),
             ('MOVE', '#SP', '#SP_Act')),
        rung('R-11 — higher STG (less 2nd stage) applies at once',
             ('Ge', 'Int', '#STG', '#STG_Act'), ('MOVE', '#STG', '#STG_Act')),
        rung('R-11 — HYST only acts while stopped, so it is taken at once', None,
             ('MOVE', '#HYST', '#HYST_Act')),
        rung('C0xb / C0xc — restart and 2nd-stage limits', None,
             ('SUB', 'Int', '#SP_Act', '#HYST_Act', '#TOn'),
             ('SUB', 'Int', '#SP_Act', '#STG_Act', '#TStg')),
        rung('C0xc / F41 — 2nd stage back to 1st at SP - STG + 2.0 degC', None,
             ('ADD', 'Int', '#TStg', '20', '#TStgOff')),
        rung('C0xb — AUTO demand on at T <= SP - HYST', ('Le', 'Int', '#Tmax', '#TOn'),
             ('S', '#Demand')),
        rung('C0xb — AUTO demand off at T >= SP, or no valid temperature',
             ('|', ('Ge', 'Int', '#Tmax', '#SP_Act'), ('!', '#TcOk')), ('R', '#Demand')),
        rung('B-01 — heat needed: AUTO = hysteresis, MAN = below SP',
             ('&', '#TcOk', ('|', ('&', '#Auto', '#Demand'),
                             ('&', ('!', '#Auto'), ('Lt', 'Int', '#Tmax', '#SP_Act')))),
             ('=', '#HeatNeed')),
        # ---- الشروط والتايمرات ----------------------------------------------
        rung('C0xa / C0xd / C01 / C0xe / C07h — ready to fire',
             ('&', '#LevelOK', '#TcOk', '#EStopOK', ('!', '#Lockout'), ('!', '#Pause24')),
             ('=', '#Ready')),
        rung('C07h / R-08 — 24 h of continuous request: forced stop',
             ('&', '#Use24h', '#Active', ('TON', '#T_24h', 'T#24H')), ('S', '#Pause24')),
        rung('R-08 — restart allowed after RUN has been off 60 s',
             ('&', '#Pause24', ('!', '#RunFb'), ('TON', '#T_Pause', 'T#60S')),
             ('R', '#Pause24')),
        rung('R-09 — RUN on without our request for 30 s',
             ('&', '#RunFb', ('!', '#Active'), ('TON', '#T_RunOff', 'T#30S')),
             ('=', '#RunWrong')),
        rung('C0xf — no RUN within T_START', ('&', st(STARTING),
                                             ('TON', '#T_Start', '#TStart_Act')),
             ('=', '#NoStart')),
        # ---- السماح (START / STOP) -----------------------------------------
        rung('R-01 / B-01 — START accepted: IDLE, ready, and in MAN only if heat is needed',
             ('&', '#StartEdge', st(IDLE), '#Ready', ('|', '#Auto', '#HeatNeed')),
             ('S', '#Enabled')),
        rung('B-01 / R-02 / R-12 — STOP, AUTO/MAN change or fuel change take the START back',
             ('|', ('!', '#StopOK'), '#AutoChg', '#FuelChg'), ('R', '#Enabled')),
        # ---- الحالات (الأولوية بالترتيب: الأخير بيكسب) ------------------------
        rung('B-01 — IDLE -> STARTING (R-09: not if RUN is already on)',
             ('&', st(IDLE), '#Enabled', '#Ready', '#HeatNeed', ('!', '#RunFb')),
             ('MOVE', STARTING, '#State')),
        rung('B-01 — STARTING -> RUNNING on RUN', ('&', st(STARTING), '#RunFb'),
             ('MOVE', RUNNING, '#State')),
        rung('C0xa / C0xb / C07h / B-01 — STARTING or RUNNING -> IDLE',
             ('&', active, ('|', ('!', '#Ready'), ('!', '#HeatNeed'), ('!', '#Enabled'))),
             ('MOVE', IDLE, '#State')),
        rung('R-03 — MAN: one cycle; any stop needs a new START',
             ('&', ('!', '#Auto'), st(IDLE), '#Active'), ('R', '#Enabled')),
        rung('C0xf — failed to start', ('&', st(STARTING), '#NoStart'),
             ('MOVE', FAULT, '#State'), ('S', '#F_NoStart')),
        rung('C0xg — RUN lost while running, no lockout, not stopped by us',
             ('&', st(RUNNING), ('!', '#RunFb'), ('!', '#Lockout')),
             ('MOVE', FAULT, '#State'), ('S', '#F_RunLost')),
        rung('R-06 / R-07 — RESET leaves FAULT only when every cause is gone',
             ('&', st(FAULT), '#ResetPulse', '#EStopOK', ('!', '#Lockout'), '#TcOk',
              ('!', '#RunFb')),
             ('MOVE', IDLE, '#State'), ('R', '#F_EStop'), ('R', '#F_TC'), ('R', '#F_Lockout'),
             ('R', '#F_NoStart'), ('R', '#F_RunLost'), ('R', '#F_RunWrong')),
        rung('C01 — E-STOP', ('!', '#EStopOK'), ('MOVE', FAULT, '#State'), ('S', '#F_EStop')),
        rung('C0xe — burner lockout', '#Lockout', ('MOVE', FAULT, '#State'),
             ('S', '#F_Lockout')),
        rung('C0xd — thermocouple fault', '#TcBad', ('MOVE', FAULT, '#State'), ('S', '#F_TC')),
        rung('R-09 — RUN without request', '#RunWrong', ('MOVE', FAULT, '#State'),
             ('S', '#F_RunWrong')),
        rung('B-02 — FAULT takes the START back', st(FAULT), ('R', '#Enabled')),
        # ---- المخارج ------------------------------------------------------
        rung('E1 / E3 — heat request while STARTING or RUNNING', active,
             ('=', '#Active'), ('=', '#HeatReq')),
        rung('C0xc — 2nd stage on: RUNNING and T < SP - STG',
             ('&', st(RUNNING), ('Lt', 'Int', '#Tmax', '#TStg')), ('S', '#Stage2')),
        rung('C0xc / F41 — 2nd stage off at SP - STG + 2 degC, or when not RUNNING',
             ('|', ('Ge', 'Int', '#Tmax', '#TStgOff'), ('Ne', 'Int', '#State', RUNNING)),
             ('R', '#Stage2')),
    ]
    stat = [member(n, t, retain=False) for n, t in BR_STAT] + [TON_FULL % t for t in BR_TON]
    iface = interface([
        ('Input', [member(n, t, retain=None, comment=c) for n, t, c in BR_IN]),
        ('Output', [member(n, t, retain=False, comment=c) for n, t, c in BR_OUT]),
        ('InOut', []), ('Static', stat), ('Temp', []), ('Constant', [])])
    return code_block('SW.Blocks.FB', 'Burner', 1, iface, nets,
                      comment='One burner, docs/التشغيل.md §2 and decisions/0006')


def burner_db(name, number):
    iface = interface([
        ('Input', [member(n, t, retain=False) for n, t, _ in BR_IN]),
        ('Output', [member(n, t, retain=False) for n, t, _ in BR_OUT]),
        ('InOut', []),
        ('Static', [member(n, t, retain=False) for n, t in BR_STAT] +
         [member(t, 'TON_TIME', short_ton=True) for t in BR_TON])])
    return db_block('SW.Blocks.InstanceDB', name, number, iface, instance_of='Burner')


# ======================================================================
#  Outputs (FC2) — المكان الوحيد اللي بيكتب %Q
# ======================================================================
def outputs_fc():
    nets = [
        rung('E1 — BR01 heat request TL (R1, H1)',
             ('&', '"BR01_DB".HeatReq', '"Sys".EStopOK'), ('=', '"BR01_TL_Cmd"')),
        rung('E2 — BR01 2nd stage TR (R2, H2)',
             ('&', '"BR01_DB".Stage2', '"Sys".EStopOK'), ('=', '"BR01_TR_Cmd"')),
        rung('E3 / F13 — BR02 start L (R6) and 1st stage lamp H5 (R8)',
             ('&', '"BR02_DB".HeatReq', '"Sys".EStopOK'),
             ('=', '"BR02_L_Cmd"'), ('=', '"BR02_Stage1Lamp_Cmd"')),
        rung('E4 / F13 — BR02 high fire T2 (R7) and 2nd stage lamp H6 (R9)',
             ('&', '"BR02_DB".Stage2', '"Sys".EStopOK'),
             ('=', '"BR02_T2_Cmd"'), ('=', '"BR02_Stage2Lamp_Cmd"')),
        rung('E5 / E6 / E7 — scrubber valves energised = normal (flare/drain closed, suction open)',
             '"Scrubber_DB".ValvesNormal',
             ('=', '"XV_401_Cmd"'), ('=', '"XV_402_Cmd"'), ('=', '"XV_403_Cmd"')),
    ]
    iface = interface([('Input', []), ('Output', []), ('InOut', []), ('Temp', []),
                       ('Constant', []), ('Return', ['<Member Name="Ret_Val" Datatype="Void" />'])])
    return code_block('SW.Blocks.FC', 'Outputs', 2, iface, nets,
                      comment='The only block that writes %Q (decisions/0006 rule 3)')


# ======================================================================
#  OB100 و OB1
# ======================================================================
def startup_ob():
    # MOVE على Bool مش مسموح في LAD، وSys مش retain فـ FirstScan = 0 هنا دايمًا
    nets = [rung('C02 — power-up: first-scan flag (scrubber trips, burners need START)',
                 ('!', '"Sys".FirstScan'), ('S', '"Sys".FirstScan'))]
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
        io = ['"S4_BR01_Auto"', '"S1_BR01_Start"', '"S3_BR01_Stop"', '"LSL_TK01"',
              '"BR01_Run"', '"BR01_Fault"', 'FALSE', '"TE_501_Raw"', '"TE_502_Raw"', 'TRUE']
    else:
        io = ['"S5_BR02_Auto"', '"S6_BR02_Start"', '"S7_BR02_Stop"', '"LSL_TK02"',
              '"BR02_Run"', '"BR02_Fault"', '"Rfuel2_BR02_DieselMode"', '"TE_503_Raw"',
              '"TE_504_Raw"', 'FALSE']
    io += ['"Sys".EStopOK', '"Sys".ResetPulse', '"Sys".FirstScan',
           '"Par".SP_V', '"Par".HYST_V', '"Par".STG_V', '"Par".TStart_V']
    return [(n, 'Input', t, op) for (n, t, _), op in zip(BR_IN, io)]


def main_ob():
    scrub_io = ['"PSH_101"', '"LSH_102"', '"LSHH_103"', '"Sys".EStopOK', '"Sys".ResetPulse',
                '"Sys".FirstScan']
    nets = [
        call('decisions/0006 — Common: E-STOP latch, RESET edge, parameters', 'Common', 'FC'),
        call('C03 .. C05 — scrubber', 'Scrubber', 'FB', 'Scrubber_DB',
             [(n, 'Input', 'Bool', op) for (n, _), op in zip(SCRUB_IN, scrub_io)]),
        call('C07* — BR01 / TK01', 'Burner', 'FB', 'BR01_DB', burner_params('BR01')),
        call('C08* — BR02 / TK02', 'Burner', 'FB', 'BR02_DB', burner_params('BR02')),
        call('E1 .. E7 — outputs', 'Outputs', 'FC'),
        rung('C02 — first scan done', '"Sys".FirstScan', ('R', '"Sys".FirstScan')),
    ]
    iface = interface([
        ('Input', ['<Member Name="Initial_Call" Datatype="Bool" Accessibility="Public" '
                   'Informative="true" />',
                   '<Member Name="Remanence" Datatype="Bool" Accessibility="Public" '
                   'Informative="true" />']),
        ('Temp', []), ('Constant', [])])
    return code_block('SW.Blocks.OB', 'Main', 1, iface, nets,
                      extra_attrs='      <SecondaryType>ProgramCycle</SecondaryType>\n',
                      comment='Calls the blocks in a fixed order; no logic here (decisions/0006)')


# الترتيب ده هو ترتيب الاستيراد.
BLOCKS = [
    ('Par.xml', par_db), ('Sys.xml', sys_db),
    ('Common.xml', common_fc),
    ('Scrubber.xml', scrubber_fb), ('Scrubber_DB.xml', scrubber_db),
    ('Burner.xml', burner_fb),
    ('BR01_DB.xml', lambda: burner_db('BR01_DB', 3)),
    ('BR02_DB.xml', lambda: burner_db('BR02_DB', 4)),
    ('Outputs.xml', outputs_fc),
    ('Startup.xml', startup_ob), ('Main.xml', main_ob),
]


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    for fname, fn in BLOCKS:
        with io.open(os.path.join(OUT, fname), 'w', encoding='utf-8') as f:
            f.write(fn())
    print('wrote %d files to build\\blocks' % len(BLOCKS))
    print('import order: -Files ' + ','.join('blocks\\' + f for f, _ in BLOCKS))


if __name__ == '__main__':
    main()
