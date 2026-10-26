# -*- coding: utf-8 -*-
"""مولّد SimaticML للادر — الجزء المشترك بين كل سكريبتات البناء.

القواعد البنيوية اللي الـ XSD مبيمسكهاش والـ importer بيرفض عليها موجودة
في سكيل `tia-openness`. اللي متطبّق هنا:

* جوه `<Parts>`: **كل `Access` قبل كل `Part`/`Call`** وإلا رسالة مضلّلة
  `The required attribute 'UId' is missing`.
* **`OpenCon` له `UId` خاص به** — هو عقدة حقيقية في الشبكة.
* **قضيب قدرة واحد لكل شبكة**: كل الأطراف المتغذّية منه في `<Wire>` واحدة.
* **كل مصدر بيظهر في `<Wire>` واحدة بس**، بتعدّد كل اللي بيغذّيهم —
  وده اللي `render()` بيعمله بالتجميع.

أسماء الأطراف حسّاسة لحالة الحروف ومش متسقة: الكونتاكت `in`/`out`/`operand`،
التايمر `IN`/`PT`/`Q`/`ET`، `Sr` بيستخدم `s`/`r1`/`q`، والنداء `en`/`eno`.
اقراها من استخراج حقيقي بدل ما تخمّنها.
"""
from __future__ import print_function
import io, re


def esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;')
             .replace('>', '&gt;').replace('"', '&quot;'))


class IdGen(object):
    """أرقام الـ Document ID — سداسية وفريدة داخل المستند الواحد."""

    def __init__(self, start=0):
        self.n = start

    def next(self):
        v = self.n
        self.n += 1
        return format(v, 'X')


class Net(object):
    """بيبني `FlgNet` واحدة (شبكة لادر واحدة)."""

    def __init__(self):
        self.uid = 20
        # كل Access لازم تسبق كل Part/Call، فبنجمّعهم في قايمتين منفصلتين
        self.accesses = []
        self.parts = []
        self.wires = []

    def _next(self):
        self.uid += 1
        return str(self.uid)

    # ---- معاملات -------------------------------------------------------
    def glob(self, name):
        u = self._next()
        self.accesses.append(
            '    <Access Scope="GlobalVariable" UId="%s">\n'
            '      <Symbol>\n'
            '        <Component Name="%s" />\n'
            '      </Symbol>\n'
            '    </Access>' % (u, esc(name)))
        return u

    def local(self, name):
        """متغير محلي للبلوك (Static / Temp / Constant)."""
        u = self._next()
        self.accesses.append(
            '    <Access Scope="LocalVariable" UId="%s">\n'
            '      <Symbol>\n'
            '        <Component Name="%s" />\n'
            '      </Symbol>\n'
            '    </Access>' % (u, esc(name)))
        return u

    def const(self, value):
        u = self._next()
        self.accesses.append(
            '    <Access Scope="TypedConstant" UId="%s">\n'
            '      <Constant>\n'
            '        <ConstantValue>%s</ConstantValue>\n'
            '      </Constant>\n'
            '    </Access>' % (u, esc(value)))
        return u

    # ---- عناصر ----------------------------------------------------------
    def contact(self, negated=False):
        u = self._next()
        if negated:
            self.parts.append('    <Part Name="Contact" UId="%s">\n'
                              '      <Negated Name="operand" />\n'
                              '    </Part>' % u)
        else:
            self.parts.append('    <Part Name="Contact" UId="%s" />' % u)
        return u

    def coil(self):
        u = self._next()
        self.parts.append('    <Part Name="Coil" UId="%s" />' % u)
        return u

    def rcoil(self):
        u = self._next()
        self.parts.append('    <Part Name="RCoil" UId="%s" />' % u)
        return u

    def or_box(self, n):
        u = self._next()
        self.parts.append(
            '    <Part Name="O" UId="%s">\n'
            '      <TemplateValue Name="Card" Type="Cardinality">%d</TemplateValue>\n'
            '    </Part>' % (u, n))
        return u

    def ton(self, instance_name):
        u = self._next()
        iu = self._next()
        self.parts.append(
            '    <Part Name="TON" Version="1.0" UId="%s">\n'
            '      <Instance Scope="LocalVariable" UId="%s">\n'
            '        <Component Name="%s" />\n'
            '      </Instance>\n'
            '      <TemplateValue Name="time_type" Type="Type">Time</TemplateValue>\n'
            '    </Part>' % (u, iu, esc(instance_name)))
        return u

    def sr(self):
        u = self._next()
        self.parts.append('    <Part Name="Sr" UId="%s" />' % u)
        return u

    def call(self, fb_name, instance_db, params=()):
        u = self._next()
        iu = self._next()
        pstr = ''.join(
            '\n          <Parameter Name="%s" Section="%s" Type="%s" />'
            % (esc(n), s, t) for n, s, t in params)
        self.parts.append(
            '    <Call UId="%s">\n'
            '      <CallInfo Name="%s" BlockType="FB">\n'
            '        <Instance Scope="GlobalVariable" UId="%s">\n'
            '          <Component Name="%s" />\n'
            '        </Instance>%s\n'
            '      </CallInfo>\n'
            '    </Call>' % (u, esc(fb_name), iu, esc(instance_db), pstr))
        return u

    # ---- توصيل ----------------------------------------------------------
    def wire(self, *conns):
        self.wires.append(list(conns))

    @staticmethod
    def rail():
        return '<Powerrail />'

    @staticmethod
    def ident(u):
        return '<IdentCon UId="%s" />' % u

    @staticmethod
    def pin(u, name):
        return '<NameCon UId="%s" Name="%s" />' % (u, name)

    def openc(self):
        return '<OpenCon UId="%s" />' % self._next()

    def series(self, source, operands):
        """كونتاكتات على التوالي. operands = [(اسم التاج, معكوس), ...]."""
        prev = source
        for name, neg in operands:
            c = self.contact(neg)
            self.wire(prev, self.pin(c, 'in'))
            self.wire(self.ident(self.glob(name)), self.pin(c, 'operand'))
            prev = self.pin(c, 'out')
        return prev

    def render(self):
        # كل مصدر لازم يظهر في وصلة واحدة بس، بتعدّد كل اللي بيغذّيهم.
        order, groups = [], {}
        for conns in self.wires:
            if not conns:
                continue
            src, sinks = conns[0], conns[1:]
            if src not in groups:
                groups[src] = []
                order.append(src)
            groups[src].extend(sinks)
        w = []
        for src in order:
            u = self._next()
            body = '\n'.join('      ' + c for c in [src] + groups[src])
            w.append('    <Wire UId="%s">\n%s\n    </Wire>' % (u, body))
        return (
            '<FlgNet xmlns="http://www.siemens.com/automation/Openness/SW/'
            'NetworkSource/FlgNet/v3">\n'
            '  <Parts>\n%s\n  </Parts>\n'
            '  <Wires>\n%s\n  </Wires>\n'
            '</FlgNet>' % ('\n'.join(self.accesses + self.parts), '\n'.join(w)))


def mltext(ids, composition, text=''):
    body = ('<Text>%s</Text>' % esc(text)) if text else '<Text />'
    return (
        '      <MultilingualText ID="%s" CompositionName="%s">\n'
        '        <ObjectList>\n'
        '          <MultilingualTextItem ID="%s" CompositionName="Items">\n'
        '            <AttributeList>\n'
        '              <Culture>en-US</Culture>\n'
        '              %s\n'
        '            </AttributeList>\n'
        '          </MultilingualTextItem>\n'
        '        </ObjectList>\n'
        '      </MultilingualText>' % (ids.next(), composition, ids.next(), body))


def compile_unit(ids, flgnet, title):
    return (
        '      <SW.Blocks.CompileUnit ID="%s" CompositionName="CompileUnits">\n'
        '        <AttributeList>\n'
        '          <NetworkSource>%s</NetworkSource>\n'
        '          <ProgrammingLanguage>LAD</ProgrammingLanguage>\n'
        '        </AttributeList>\n'
        '        <ObjectList>\n%s\n%s\n        </ObjectList>\n'
        '      </SW.Blocks.CompileUnit>'
        % (ids.next(), flgnet,
           mltext(ids, 'Comment').replace('      <', '          <'),
           mltext(ids, 'Title', title).replace('      <', '          <')))


def insert_unit(src_xml, unit_xml, after=0):
    """بيحقن CompileUnit جديدة قبل الشبكة رقم `after` (صفر = في الأول).

    عملية **نصية** بحتة: كل بايت تاني في المستند بينسخ زي ما هو، فمفيش
    احتمال إن منطق موجود اتلمس. الشبكات اللي بعدها بتنزل رقم واحد وبس.
    """
    marker = '      <SW.Blocks.CompileUnit '
    i = -1
    for _ in range(after + 1):
        i = src_xml.index(marker, i + 1)
    return src_xml[:i] + unit_xml + '\n' + src_xml[i:]


def insert_first_unit(src_xml, unit_xml):
    """اختصار — بيحقن في الأول."""
    return insert_unit(src_xml, unit_xml, after=0)
