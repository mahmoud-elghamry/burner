# -*- coding: utf-8 -*-
"""
بيولّد تاجات الشاشة وخمس صفحات (decisions/0007) في build/hmi/، وApply-Hmi.ps1 بيعمل import.

الشكل متاخد من exports حقيقية لـ V15.1: عيّنة P1 (IO field، وتاج Int على HMI_Connection_1)،
وشاشات الأوناش (TextField وButton وCircle وRectangle وRangeAppearance وSingleBitVisibility).

- الشاشة بتكتب في تاجات Par بس (PARAMS في build_blocks.py، H-01). كل حقل تاني Output.
- مفيش أي زرار بيكتب في الـ PLC. الزراير بتغيّر الشاشة بس (ActivateScreen).
- أسماء أعضاء الـ DBs بتتراجع على جداول build_blocks.py، فلو اسم اتغيّر هناك السكريبت بيقف.
- الحرارة بعُشر الدرجة: الحقل بيعرضها بـ ShiftDecimalPoint=1 (700 -> 70.0)، من غير scaling.
- شاشة Alarms مش بتتولّد: فيها Alarm View معمول بالإيد (0007 §6).
- قبل الاستيراد: py tools/check_hmi_xml.py بيراجع أسماء الخصائص والتركيبات على نفس الـ exports.
"""
from __future__ import print_function
import io, os, re, sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'build', 'hmi')
sys.path.insert(0, HERE)
import build_blocks as B  # noqa: E402

CONN = 'HMI_Connection_1'
TEMPLATE = 'Template_1'          # اللي عمله الـ wizard
W, H = 480, 272

# ---------------------------------------------------------------- الألوان
BG = '236, 238, 241'
BAR = '33, 52, 82'
WHITE = '255, 255, 255'
INK = '30, 30, 30'
DIM = '205, 208, 212'
PANEL_BORDER = '150, 155, 160'
GREY = '160, 160, 160'
GREEN = '0, 160, 70'
AMBER = '245, 170, 0'
RED = '210, 30, 30'
BLUE = '40, 110, 200'

# ======================================================================
#  التاجات
# ======================================================================
TYPES = {'Bool': 1, 'Int': 2, 'Word': 2, 'Time': 4}
# الشاشة مالهاش نوع Time ولا Word ("The HMI data type ... was not found"):
# الـ Time بيتقري DInt بالـ ms، والـ Word بيتقري UInt.
HMI_TYPE = {'Time': 'DInt', 'Word': 'UInt'}


def _members():
    """كل الأعضاء اللي ينفع الشاشة تقراها، من نفس الجداول اللي بتولّد البلوكات."""
    br = {n: t for n, t, *_ in B.BR_IN}
    br.update({n: t for n, t, *_ in B.BR_OUT})
    br.update({n: t for n, t, *_ in B.BR_STAT})
    scrub = {n: 'Bool' for n, _ in B.SCRUB_IN}
    scrub.update({n: 'Word' if n == 'Alarms' else 'Bool' for n, _ in B.SCRUB_OUT})
    scrub.update({n: t for n, t, _ in B.SCRUB_STAT})
    par = {n: t for n, t, *_ in B.PARAMS}
    return {'BR01_DB': br, 'BR02_DB': br, 'Scrubber_DB': scrub, 'Par': par}


MEMBERS = _members()
BR_READ = ['TeA', 'TeB', 'Tmax', 'TcOkA', 'TcOkB', 'TcOk', 'Enabled', 'HeatReq',
           'Stage2', 'RunFb', 'Lockout', 'LevelOK', 'Auto', 'TOn',
           'TStg', 'TStgOff', 'TcBad', 'NoRun', 'RunWrong']
# Public screen aliases survive the PLC member renames (0010).
BR_MEMBERS = {'Tmax': 'ControlTemp', 'Enabled': 'StartEnabled',
              'TOn': 'AutoRestartTemp', 'TStg': 'SecondStageOnTemp',
              'TStgOff': 'SecondStageOffTemp'}
TAGS = []   # (اسم الشاشة، DB، العضو)
for br in ('BR01', 'BR02'):
    extra = ['Pause24'] if br == 'BR01' else ['Fuel']
    TAGS += [(br + '_' + m, br + '_DB', BR_MEMBERS.get(m, m)) for m in BR_READ + extra]
TAGS += [('Scrub_' + m, 'Scrubber_DB', m) for m in
         ['PSH', 'LSH', 'LSHH', 'Tripped', 'Cause_PSH', 'Cause_LSHH',
          'FlareCmd', 'DrainCmd', 'SuctionCmd', 'F_DrainTO']]
TAGS += [('Par_' + n, 'Par', n) for n, *_ in B.PARAMS]
TAGS += [('Scrub_EStopOK', 'Scrubber_DB', 'EStopOK')]
ALARM_DBS = {'Common': 'Scrubber_DB', 'BR01': 'BR01_DB', 'BR02': 'BR02_DB'}
TAGS += [('Alm_' + w, db, 'Alarms') for w, db in ALARM_DBS.items()]
# H-01: الحقول اللي بتكتب. أي Input على تاج مش هنا = السكريبت يقف.
WRITABLE = {'Par_' + n for n, *_ in B.PARAMS}

TAG_TYPE = {}
for name, db, m in TAGS:
    if m not in MEMBERS[db]:
        sys.exit('build_hmi: %s.%s not in build_blocks.py' % (db, m))
    TAG_TYPE[name] = MEMBERS[db][m]


# Rev. B: comments come from the same tables that build the blocks.
_COMMENTS = {
    'Burner': {n: c for n, _t, c in B.BR_IN + B.BR_OUT + B.BR_STAT},
    'Scrubber': dict(B.SCRUB_IN + B.SCRUB_OUT + [(n, c) for n, _t, c in B.SCRUB_STAT]),
    'Par': B.PAR_TEXT,
}


def _tag_comment(name, db, member_name):
    if member_name == 'Alarms':
        word = next(word for word, alarm_db in ALARM_DBS.items() if alarm_db == db)
        bits = sorted((bit, title) for alarm_word, bit, _signal, title, _clears, _ref
                      in B.HMI_ALARMS if alarm_word == word)
        if [bit for bit, _title in bits] != list(range(len(bits))):
            raise ValueError('Alarm bits must start at x0 without gaps: ' + word)
        return ('%s alarm display word; each bit 1 displays its alarm. ' % word +
                '; '.join('x%d %s' % (bit, title) for bit, title in bits))
    group = ('Burner' if db.startswith('BR0') else
             'Scrubber' if db == 'Scrubber_DB' else db)
    text = _COMMENTS.get(group, {}).get(member_name)
    if not text:
        raise ValueError('No English HMI comment for %s -> %s.%s' % (name, db, member_name))
    context = db[:-3] if db.startswith('BR0') else 'Scrubber' if db == 'Scrubber_DB' else None
    return '%s: %s' % (context, text) if context else text


class Ids(object):
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return '%X' % self.n


def mltext(ids, comp, text=''):
    body = '<body><p>%s</p></body>' % escape(text) if text else ''
    return ('<MultilingualText ID="%s" CompositionName="%s"><ObjectList>'
            '<MultilingualTextItem ID="%s" CompositionName="Items"><AttributeList>'
            '<Culture>en-US</Culture><Text>%s</Text></AttributeList></MultilingualTextItem>'
            '</ObjectList></MultilingualText>' % (ids(), comp, ids(), body))


def head(kind):
    return ('<?xml version="1.0" encoding="utf-8"?>\n<Document>\n'
            '  <Engineering version="V15.1" />\n'
            '  <DocumentInfo><Created>2026-11-01T00:00:00Z</Created>'
            '<ExportSetting>WithDefaults</ExportSetting></DocumentInfo>\n')


def tag_table():
    ids = Ids()
    ids()   # ID 0 = الجدول
    out = [head('tags'), '  <Hmi.Tag.TagTable ID="0"><AttributeList><Name>LCP01</Name>'
           '</AttributeList><ObjectList>\n']
    for name, db, m in TAGS:
        t = TAG_TYPE[name]
        out.append(
            '<Hmi.Tag.Tag ID="%s" CompositionName="Tags"><AttributeList>'
            '<AcquisitionTriggerMode>%s</AcquisitionTriggerMode>'
            '<AddressAccessMode>Symbolic</AddressAccessMode><Coding>Binary</Coding>'
            '<ConfirmationType>None</ConfirmationType><GmpRelevant>false</GmpRelevant>'
            '<JobNumber>0</JobNumber><Length>%d</Length><LinearScaling>false</LinearScaling>'
            '<LogicalAddress /><MandatoryCommenting>false</MandatoryCommenting>'
            '<Name>%s</Name><Persistency>false</Persistency><QualityCode>false</QualityCode>'
            '<ScalingHmiHigh>100</ScalingHmiHigh><ScalingHmiLow>0</ScalingHmiLow>'
            '<ScalingPlcHigh>10</ScalingPlcHigh><ScalingPlcLow>0</ScalingPlcLow>'
            '<StartValue /><SubstituteValue /><SubstituteValueUsage>None</SubstituteValueUsage>'
            '<Synchronization>false</Synchronization><UpdateMode>ProjectWide</UpdateMode>'
            '<UseMultiplexing>false</UseMultiplexing></AttributeList><LinkList>'
            '<AcquisitionCycle TargetID="@OpenLink"><Name>1 s</Name></AcquisitionCycle>'
            '<Connection TargetID="@OpenLink"><Name>%s</Name></Connection>'
            '<ControllerTag TargetID="@OpenLink"><Name>%s.%s</Name></ControllerTag>'
            '<DataType TargetID="@OpenLink"><Name>%s</Name></DataType>'
            '<HmiDataType TargetID="@OpenLink"><Name>%s</Name></HmiDataType>'
            '</LinkList><ObjectList>%s%s%s</ObjectList></Hmi.Tag.Tag>\n'
            % (ids(), 'Continuous' if name in ('Alm_Common', 'Alm_BR01', 'Alm_BR02') else 'Visible',
               TYPES[t], name, CONN, db, m, t, HMI_TYPE.get(t, t),
               mltext(ids, 'Comment', _tag_comment(name, db, m)),
               mltext(ids, 'DisplayName'), mltext(ids, 'TagValue')))
    out.append('  </ObjectList></Hmi.Tag.TagTable>\n</Document>\n')
    return ''.join(out)


# ======================================================================
#  عناصر الشاشة
# ======================================================================
class Screen(object):
    def __init__(self, name, number, title):
        self.name, self.number, self.title = name, number, title
        self.ids = Ids()
        self.items = []
        self.count = {}
        self.names = set()

    def oname(self, kind, semantic):
        """Build a stable, legal object name, adding a suffix only for collisions."""
        token = re.sub(r'[^A-Za-z0-9_]+', '_', semantic).strip('_')
        token = re.sub(r'_+', '_', token) or kind
        if not token[0].isalpha():
            token = kind + '_' + token
        base = kind + '_' + token
        n = self.count.get(base, 0) + 1
        candidate = base if n == 1 else '%s_%d' % (base, n)
        while candidate in self.names:
            n += 1
            candidate = '%s_%d' % (base, n)
        self.count[base] = n
        self.names.add(candidate)
        return candidate

    def font(self, size, bold):
        return ('<Hmi.Globalization.MultiLingualFont ID="%s" CompositionName="Font"><ObjectList>'
                '<Hmi.Globalization.FontItem ID="%s" CompositionName="Items"><AttributeList>'
                '<Culture>en-US</Culture><FontFamily>Tahoma</FontFamily>'
                '<FontSize>%d</FontSize><FontStyle>%s</FontStyle></AttributeList>'
                '</Hmi.Globalization.FontItem></ObjectList>'
                '</Hmi.Globalization.MultiLingualFont>'
                % (self.ids(), self.ids(), size, 'Bold' if bold else 'Regular'))

    # ---- الحركة
    def anim_range(self, tag, ranges):
        """ranges: [(من، لحد، لون الخلفية، لون الكلام)]"""
        rv = ''.join(
            '<Hmi.Dynamic.Range ID="%s" CompositionName="RangeValues"><AttributeList>'
            '<BackColor>%s</BackColor><FlashingType>No</FlashingType><ForeColor>%s</ForeColor>'
            '<LowerLimit>%d</LowerLimit><UpperLimit>%d</UpperLimit></AttributeList>'
            '</Hmi.Dynamic.Range>' % (self.ids(), bc, fc, lo, hi) for lo, hi, bc, fc in ranges)
        return ('<Hmi.Dynamic.RangeAppearanceAnimation ID="%s" CompositionName="Animations">'
                '<AttributeList><Name>RangeAppearanceAnimation</Name></AttributeList><ObjectList>'
                '<Hmi.Dynamic.TagElementTrigger ID="%s" CompositionName="RangeTag"><LinkList>'
                '<Tag TargetID="@OpenLink"><Name>%s</Name></Tag></LinkList>'
                '</Hmi.Dynamic.TagElementTrigger>%s</ObjectList>'
                '</Hmi.Dynamic.RangeAppearanceAnimation>' % (self.ids(), self.ids(), tag, rv))

    def anim_vis(self, tag, show_when_set, bit=0):
        """ظاهر لما البت = 1 (show_when_set)، أو مستخبي لما البت = 1."""
        return ('<Hmi.Dynamic.SingleBitVisibilityAnimation ID="%s" CompositionName="Animations">'
                '<AttributeList><BitPosition>%d</BitPosition><Name>VisibilityAnimation</Name>'
                '<Visible>%s</Visible></AttributeList><ObjectList>'
                '<Hmi.Dynamic.TagElementTrigger ID="%s" CompositionName="VisibilityTag"><LinkList>'
                '<Tag TargetID="@OpenLink"><Name>%s</Name></Tag></LinkList>'
                '</Hmi.Dynamic.TagElementTrigger></ObjectList>'
                '</Hmi.Dynamic.SingleBitVisibilityAnimation>'
                % (self.ids(), bit, 'true' if show_when_set else 'false', self.ids(), tag))

    # ---- العناصر
    def rect(self, x, y, w, h, back, border=None, anims=(), name='Panel'):
        self.items.append(
            '<Hmi.Screen.Rectangle ID="%s" CompositionName="ScreenItems"><AttributeList>'
            '<BackColor>%s</BackColor><BackFillStyle>Solid</BackFillStyle>'
            '<BorderColor>%s</BorderColor><BorderWidth>%d</BorderWidth>'
            '<EdgeStyle>Solid</EdgeStyle><Flashing>None</Flashing><Height>%d</Height>'
            '<Left>%d</Left><ObjectName>%s</ObjectName>'
            '<RoundCornerHeight>0</RoundCornerHeight><RoundCornerWidth>0</RoundCornerWidth>'
            '<TabIndex>-1</TabIndex><Top>%d</Top>'
            '<UseDesignColorSchema>false</UseDesignColorSchema><Width>%d</Width></AttributeList>'
            '<ObjectList>%s</ObjectList></Hmi.Screen.Rectangle>'
            % (self.ids(), back, border or back, 1 if border else 0, h, x,
               self.oname('Panel', name), y, w, ''.join(anims)))

    def text(self, x, y, w, h, s, size=12, bold=False, fore=INK, back=None, align='Left',
             anims=(), name=None):
        trigger_tags = re.findall(r'<Tag TargetID="@OpenLink"><Name>([^<]+)</Name></Tag>',
                                  ''.join(anims))
        semantic = name or s
        if trigger_tags:
            semantic += '_' + '_'.join(trigger_tags)
        self.items.append(
            '<Hmi.Screen.TextField ID="%s" CompositionName="ScreenItems"><AttributeList>'
            '<BackColor>%s</BackColor><BackFillStyle>%s</BackFillStyle>'
            '<BorderBackColor>255, 255, 255</BorderBackColor><BorderColor>0, 0, 0</BorderColor>'
            '<BorderWidth>0</BorderWidth><BottomMargin>1</BottomMargin><CornerRadius>0</CornerRadius>'
            '<EdgeStyle>Solid</EdgeStyle><FitToLargest>false</FitToLargest><Flashing>None</Flashing>'
            '<ForeColor>%s</ForeColor><Height>%d</Height><HorizontalAlignment>%s</HorizontalAlignment>'
            '<Left>%d</Left><LeftMargin>2</LeftMargin><ObjectName>%s</ObjectName>'
            '<RightMargin>2</RightMargin><TabIndex>-1</TabIndex>'
            '<TextOrientation>Horizontal</TextOrientation><Top>%d</Top><TopMargin>1</TopMargin>'
            '<UseDesignColorSchema>false</UseDesignColorSchema><VerticalAlignment>Middle</VerticalAlignment>'
            '<Width>%d</Width></AttributeList><ObjectList>%s%s%s</ObjectList></Hmi.Screen.TextField>'
            % (self.ids(), back or WHITE, 'Solid' if back else 'Transparent', fore, h, align, x,
               self.oname('Text', semantic), y, w, ''.join(anims), self.font(size, bold),
               mltext(self.ids, 'Text', s)))

    def io(self, x, y, w, h, tag, write=False, shift=1, length=5, size=13):
        if write and tag not in WRITABLE:
            sys.exit('build_hmi: %s is not one of the writable settings (H-01)' % tag)
        self.items.append(
            '<Hmi.Screen.IOField ID="%s" CompositionName="ScreenItems"><AttributeList>'
            '<AboveUpperLimitColor>237, 88, 97</AboveUpperLimitColor><BackColor>%s</BackColor>'
            '<BackFillStyle>Solid</BackFillStyle><BelowLowerLimitColor>241, 161, 44</BelowLowerLimitColor>'
            '<BorderBackColor>101, 103, 115</BorderBackColor><BorderColor>%s</BorderColor>'
            '<BorderWidth>%d</BorderWidth><BottomMargin>1</BottomMargin><CornerRadius>2</CornerRadius>'
            '<DataFormat>Decimal</DataFormat><EdgeStyle>Solid</EdgeStyle><Enabled>true</Enabled>'
            '<FieldLength>%d</FieldLength><FitToLargest>false</FitToLargest><Flashing>None</Flashing>'
            '<ForeColor>%s</ForeColor><FormatPattern>%s</FormatPattern><Height>%d</Height>'
            '<HiddenInput>false</HiddenInput><HorizontalAlignment>Right</HorizontalAlignment>'
            '<Left>%d</Left><LeftMargin>2</LeftMargin><Mode>%s</Mode><ObjectName>%s</ObjectName>'
            '<RightMargin>3</RightMargin><ShiftDecimalPoint>%d</ShiftDecimalPoint>'
            '<ShowLeadingZeros>false</ShowLeadingZeros><TabIndex>%d</TabIndex>'
            '<TextOrientation>Horizontal</TextOrientation><Top>%d</Top><TopMargin>1</TopMargin>'
            '<Unit /><UseDesignColorSchema>false</UseDesignColorSchema>'
            '<UseTwoHandOperation>false</UseTwoHandOperation><VerticalAlignment>Middle</VerticalAlignment>'
            '<Width>%d</Width></AttributeList><ObjectList>%s%s'
            '<Hmi.Screen.Property ID="%s" CompositionName="Properties"><AttributeList>'
            '<Name>ProcessValue</Name></AttributeList><ObjectList>'
            '<Hmi.Dynamic.TagConnectionDynamic ID="%s" CompositionName="Dynamic"><AttributeList>'
            '<Indirect>false</Indirect></AttributeList><LinkList><Tag TargetID="@OpenLink">'
            '<Name>%s</Name></Tag></LinkList></Hmi.Dynamic.TagConnectionDynamic></ObjectList>'
            '</Hmi.Screen.Property></ObjectList></Hmi.Screen.IOField>'
            % (self.ids(), WHITE if write else BG, BLUE if write else BG, 2 if write else 0,
               length, INK, 's' + '9' * length, h, x, 'InOutput' if write else 'Output',
               self.oname('IO', tag), shift, 1 if write else -1, y, w,
               self.font(size, True), mltext(self.ids, 'HelpText'),
               self.ids(), self.ids(), tag))

    def lamp(self, x, y, tag, label, on=GREEN, off=GREY, w=140):
        """Digital status lamp: choose active and inactive colors per signal meaning."""
        anim = self.anim_range(tag, [(0, 0, off, INK), (1, 1, on, INK)])
        self.items.append(
            '<Hmi.Screen.Circle ID="%s" CompositionName="ScreenItems"><AttributeList>'
            '<BackColor>%s</BackColor><BackFillStyle>Solid</BackFillStyle><BorderColor>80, 80, 80</BorderColor>'
            '<BorderWidth>1</BorderWidth><EdgeStyle>Solid</EdgeStyle><Flashing>None</Flashing>'
            '<Height>12</Height><Left>%d</Left><ObjectName>%s</ObjectName><Radius>6</Radius>'
            '<TabIndex>-1</TabIndex><Top>%d</Top><UseDesignColorSchema>false</UseDesignColorSchema>'
            '<Width>12</Width></AttributeList><ObjectList>%s</ObjectList></Hmi.Screen.Circle>'
            % (self.ids(), GREY, x, self.oname('Lamp', tag), y + 3, anim))
        self.text(x + 16, y, w - 16, 18, label, size=11)

    def fault_badge(self, x, y, w, tag, bit, label):
        """Show a red text badge when the corresponding alarm word bit is set."""
        self.text(x, y, w, 18, label, size=11, bold=True, fore=RED,
                  anims=[self.anim_vis(tag, True, bit)],
                  name='Fault_%s_Bit%d_%s' % (tag, bit, label))

    def button(self, x, y, w, h, label, screen):
        self.items.append(
            '<Hmi.Screen.Button ID="%s" CompositionName="ScreenItems"><AttributeList>'
            '<BackColor>%s</BackColor><BackFillStyle>Solid</BackFillStyle><BitNumber>0</BitNumber>'
            '<BorderBackColor>255, 255, 255</BorderBackColor><BorderColor>%s</BorderColor>'
            '<BorderWidth>1</BorderWidth><CornerRadius>3</CornerRadius><CornerStyle>Pointed</CornerStyle>'
            '<EdgeStyle>Solid</EdgeStyle><Enabled>true</Enabled><FitToLargest>false</FitToLargest>'
            '<Flashing>None</Flashing><FocusColor>148, 182, 231</FocusColor><FocusWidth>2</FocusWidth>'
            '<ForeColor>%s</ForeColor><Height>%d</Height><HorizontalAlignment>Center</HorizontalAlignment>'
            '<HorizontalPictureAlignment>Center</HorizontalPictureAlignment><HotKey>0</HotKey>'
            '<Left>%d</Left><Mode>Text</Mode><ObjectName>%s</ObjectName>'
            '<PictureAreaBottomMargin>0</PictureAreaBottomMargin><PictureAreaLeftMargin>0</PictureAreaLeftMargin>'
            '<PictureAreaRightMargin>0</PictureAreaRightMargin><PictureAreaTopMargin>0</PictureAreaTopMargin>'
            '<PictureAutoSizing>StretchPicture</PictureAutoSizing><TabIndex>-1</TabIndex>'
            '<TextAreaBottomMargin>0</TextAreaBottomMargin><TextAreaLeftMargin>0</TextAreaLeftMargin>'
            '<TextAreaRightMargin>0</TextAreaRightMargin><TextAreaTopMargin>0</TextAreaTopMargin>'
            '<TextOrientation>Horizontal</TextOrientation><Top>%d</Top>'
            '<UseDesignColorSchema>false</UseDesignColorSchema><UseFirstGradient>false</UseFirstGradient>'
            '<UseSecondGradient>false</UseSecondGradient><UseTwoHandOperation>false</UseTwoHandOperation>'
            '<VerticalAlignment>Middle</VerticalAlignment><VerticalPictureAlignment>Middle</VerticalPictureAlignment>'
            '<Width>%d</Width></AttributeList><ObjectList>'
            '<Hmi.Event.Event ID="%s" CompositionName="Events"><AttributeList><Name>Press</Name>'
            '</AttributeList><ObjectList><Hmi.Event.FunctionListEventHandler ID="%s" CompositionName="EventHandler">'
            '<ObjectList><Hmi.Event.FunctionListEntry ID="%s" CompositionName="FunctionListEntries">'
            '<AttributeList><Name>ActivateScreen</Name><Type>SystemFunction</Type></AttributeList><ObjectList>'
            '<Hmi.Event.FunctionListEntryParameter ID="%s" CompositionName="Parameters"><AttributeList>'
            '<Name>Screen name</Name></AttributeList><LinkList><Value TargetID="@OpenLink"><Name>%s</Name>'
            '</Value></LinkList></Hmi.Event.FunctionListEntryParameter>'
            '<Hmi.Event.FunctionListEntryParameter ID="%s" CompositionName="Parameters"><AttributeList>'
            '<Name>Object number</Name><Value Type="System.Int32">0</Value></AttributeList>'
            '</Hmi.Event.FunctionListEntryParameter></ObjectList></Hmi.Event.FunctionListEntry>'
            '</ObjectList></Hmi.Event.FunctionListEventHandler></ObjectList></Hmi.Event.Event>'
            '%s%s%s%s</ObjectList></Hmi.Screen.Button>'
            % (self.ids(), BAR if screen != self.name else BLUE, BAR, WHITE, h, x,
               self.oname('Nav', screen), y, w, self.ids(), self.ids(), self.ids(), self.ids(), screen,
               self.ids(), self.font(11, True), mltext(self.ids, 'HelpText'),
               mltext(self.ids, 'TextOff', label), mltext(self.ids, 'TextOn', label)))

    def xml(self):
        ids = self.ids
        return (head('screen') +
                '  <Hmi.Screen.Screen ID="%s"><AttributeList><ActiveLayer>0</ActiveLayer>'
                '<BackColor>%s</BackColor><GridColor>0, 0, 0</GridColor><Height>%d</Height>'
                '<Name>%s</Name><Number>%d</Number><Visible>true</Visible><Width>%d</Width>'
                '</AttributeList><LinkList><Template TargetID="@OpenLink"><Name>%s</Name>'
                '</Template></LinkList><ObjectList>%s'
                '<Hmi.Screen.ScreenLayer ID="%s" CompositionName="Layers"><AttributeList>'
                '<Index>0</Index><Name /><VisibleES>true</VisibleES></AttributeList><ObjectList>\n%s\n'
                '</ObjectList></Hmi.Screen.ScreenLayer></ObjectList></Hmi.Screen.Screen>\n</Document>\n'
                % (ids(), BG, H, self.name, self.number, W, TEMPLATE, mltext(ids, 'HelpText'),
                   ids(), '\n'.join(self.items)))


# ======================================================================
#  الأجزاء المشتركة
# ======================================================================
SCREENS = [('Root screen', 'Overview'), ('BR01', 'BR01'), ('BR02', 'BR02'),
           ('Scrubber', 'Scrubber'), ('Alarms', 'Alarms'), ('Settings', 'Settings')]


def frame(s):
    s.rect(0, 0, W, 26, BAR)
    s.text(6, 2, 300, 22, 'LCP-01  ' + s.title, size=14, bold=True, fore=WHITE)
    # E-STOP في العنوان: ظاهر لما الدخل الخام = 0 (الزرار مضغوط).
    s.text(330, 3, 146, 20, 'E-STOP pressed', size=12, bold=True, fore=WHITE, back=RED,
           align='Center', anims=[s.anim_vis('Scrub_EStopOK', False)])
    bw = W // len(SCREENS)
    for i, (scr, label) in enumerate(SCREENS):
        s.button(i * bw + 2, 236, bw - 4, 34, label, scr)


def segments(s, x, y, w, tag, items, h=18, cols=2):
    """كلمات ثابتة، واللي قيمته = التاج بس اللي بيتلوّن (زي text list من غير text list)."""
    cw = w // cols
    for i, (val, label, color) in enumerate(items):
        cx, cy = x + (i % cols) * cw, y + (i // cols) * (h + 2)
        s.text(cx, cy, cw - 2, h, label, size=11, bold=True, fore=DIM, back=BG, align='Center',
               anims=[s.anim_range(tag, [(val, val, color, WHITE)])])


def temp(s, x, y, tag, ok_tag, label, w=150):
    s.text(x, y, 70, 20, label, size=11)
    s.io(x + 70, y, 52, 20, tag, size=12)
    # العيّنة مفيهاش Animations على IOField: النص المعتم فوقه بيغطي الرقم لما القناة تبقى بايظة.
    s.text(x + 70, y, 52, 20, '----', size=12, bold=True, fore=RED, back=BG, align='Right',
           anims=[s.anim_vis(ok_tag, False)])
    s.text(x + 124, y, 26, 20, '°C', size=11)




def panel(s, x, y, w, h, title):
    s.rect(x, y, w, h, WHITE, PANEL_BORDER, name=title)
    s.text(x + 4, y + 2, w - 8, 20, title, size=12, bold=True)


def tank_icon(s, x, y, name):
    """Tank outline for identification only; it is not a level graphic."""
    s.rect(x + 7, y + 6, 30, 26, WHITE, PANEL_BORDER, name=name + ' tank')
    s.rect(x + 17, y + 1, 10, 5, WHITE, PANEL_BORDER, name=name + ' neck')


def fault_hint(s, x, y, w, alarm_word_tag, normal_back=WHITE):
    # Rev. B: no burner FAULT state; any alarm bit of this burner shows the hint.
    s.text(x, y, w, 18, 'Check Alarms', size=10, bold=True,
           fore=normal_back, back=normal_back,
           anims=[s.anim_range(alarm_word_tag, [(0, 0, normal_back, normal_back),
                                                (1, 65535, RED, WHITE)])])


def command_row(s, x, y, tag, drawing_tag, on_word, off_word, w=148):
    s.lamp(x, y, tag, drawing_tag, on=GREEN, off=GREY, w=w - 42)
    state_x = x + w - 42
    s.text(state_x, y, 40, 18, on_word, size=10, bold=True,
           anims=[s.anim_vis(tag, True)])
    s.text(state_x, y, 40, 18, off_word, size=10, bold=True, fore=INK,
           anims=[s.anim_vis(tag, False)])


# ======================================================================
#  الشاشات
# ======================================================================
def overview():
    s = Screen('Root screen', 1, 'Overview')
    frame(s)
    pw, y, h = 156, 30, 202
    x = 2
    panel(s, x, y, pw, h, 'SCRUBBER')
    s.text(x + 4, y + 23, pw - 8, 18, 'INPUTS: green = OK', size=10, bold=True, fore=INK)
    s.lamp(x + 4, y + 42, 'Scrub_PSH', 'Pressure', on=GREEN, off=RED, w=148)
    s.lamp(x + 4, y + 62, 'Scrub_LSH', 'High level', on=GREEN, off=AMBER, w=148)
    s.lamp(x + 4, y + 82, 'Scrub_LSHH', 'Very high level', on=GREEN, off=RED, w=148)
    s.text(x + 4, y + 103, pw - 8, 18, 'OUTPUT COMMANDS', size=10, bold=True, fore=INK)
    command_row(s, x + 4, y + 121, 'Scrub_FlareCmd', 'XV-401 flare', 'CLOSE', 'OPEN')
    command_row(s, x + 4, y + 141, 'Scrub_DrainCmd', 'XV-402 drain', 'OPEN', 'CLOSE')
    command_row(s, x + 4, y + 161, 'Scrub_SuctionCmd', 'XV-403 suction', 'OPEN', 'CLOSE')
    s.text(x + 4, y + 181, pw - 8, 18, 'TRIP: RESET required', size=10,
           bold=True, fore=WHITE, back=RED,
           anims=[s.anim_vis('Scrub_Tripped', True)])

    for i, (br, tk) in enumerate([('BR01', 'TK01'), ('BR02', 'TK02')]):
        x = 2 + (i + 1) * (pw + 3)
        panel(s, x, y, pw, h, '%s  %s' % (br, tk))
        tank_icon(s, x + 108, y + 22, tk)
        temp(s, x + 4, y + 62, br + '_Tmax', br + '_TcOk', 'Max temp')
        s.lamp(x + 4, y + 88, br + '_LevelOK', 'Level OK', on=GREEN, off=RED, w=148)
        s.lamp(x + 4, y + 109, br + '_RunFb', 'RUN input', on=GREEN, off=GREY, w=148)
        s.lamp(x + 4, y + 130, br + '_HeatReq', 'Heat request', on=GREEN, off=GREY, w=148)
        s.lamp(x + 4, y + 151, br + '_Stage2', 'Stage 2 request', on=GREEN, off=GREY, w=148)
        fault_hint(s, x + 4, y + 181, pw - 8, 'Alm_' + br)
    return s


def burner(br):
    tk, te = ('TK01', ('TE-501', 'TE-502')) if br == 'BR01' else ('TK02', ('TE-503', 'TE-504'))
    s = Screen(br, 2 if br == 'BR01' else 3, '%s  %s' % (br, tk))
    frame(s)
    fault_hint(s, 4, 30, 472, 'Alm_' + br, normal_back=BG)
    y = 54
    panel(s, 4, y, 204, 178, 'Tank temperature (°C)')
    temp(s, 8, y + 24, br + '_TeA', br + '_TcOkA', te[0])
    temp(s, 8, y + 48, br + '_TeB', br + '_TcOkB', te[1])
    temp(s, 8, y + 72, br + '_Tmax', br + '_TcOk', 'Max temp')
    s.lamp(164, y + 24, br + '_TcOkA', 'OK', on=GREEN, off=RED, w=40)
    s.lamp(164, y + 48, br + '_TcOkB', 'OK', on=GREEN, off=RED, w=40)
    tank_icon(s, 159, y + 124, tk)

    x = 216
    panel(s, x, y, 260, 178, 'Burner signals')
    rows = [('_LevelOK', 'Level OK', GREEN, RED),
            ('_RunFb', 'RUN input', GREEN, GREY),
            ('_HeatReq', 'Heat request', GREEN, GREY),
            ('_Stage2', 'Stage 2 request', GREEN, GREY),
            ('_Lockout', 'Lockout input', RED, GREY),
            ('_Auto', 'AUTO mode', GREEN, GREY),
            ('Scrub_EStopOK', 'E-STOP ready', GREEN, RED)]
    for j, (tag, label, active, inactive) in enumerate(rows):
        s.lamp(x + 6, y + 24 + j * 21, br + tag if tag.startswith('_') else tag, label,
               on=active, off=inactive, w=248)
    return s


def scrubber():
    s = Screen('Scrubber', 4, 'Scrubber')
    frame(s)
    s.text(4, 30, 472, 18, 'TRIP: RESET required', size=11, bold=True,
           fore=WHITE, back=RED, anims=[s.anim_vis('Scrub_Tripped', True)])
    y = 54
    x = 4
    panel(s, x, y, 220, 178, 'Inputs: green = healthy')
    s.lamp(x + 8, y + 28, 'Scrub_PSH', 'PSH-101 Pressure', on=GREEN, off=RED, w=204)
    s.lamp(x + 8, y + 58, 'Scrub_LSH', 'LSH-102 High level', on=GREEN, off=AMBER, w=204)
    s.lamp(x + 8, y + 88, 'Scrub_LSHH', 'LSHH-103 Very high level', on=GREEN, off=RED, w=204)
    s.lamp(x + 8, y + 118, 'Scrub_EStopOK', 'E-STOP ready', on=GREEN, off=RED, w=204)

    x = 232
    panel(s, x, y, 244, 178, 'Valve commands')
    command_row(s, x + 8, y + 28, 'Scrub_FlareCmd', 'XV-401 flare', 'CLOSE', 'OPEN', w=224)
    command_row(s, x + 8, y + 58, 'Scrub_DrainCmd', 'XV-402 drain', 'OPEN', 'CLOSE', w=224)
    command_row(s, x + 8, y + 88, 'Scrub_SuctionCmd', 'XV-403 suction', 'OPEN', 'CLOSE', w=224)
    s.text(x + 8, y + 124, 224, 34, 'Commands only; no valve position feedback.',
           size=10, fore=INK)
    return s


def alarms():
    s = Screen('Alarms', 5, 'Alarms')
    frame(s)
    # مكان الـ alarm view: بيتحط بالإيد (Openness V15.1 مش بيعمله import)
    s.rect(4, 30, 472, 202, WHITE, PANEL_BORDER, name='Alarm list')
    return s


def settings():
    s = Screen('Settings', 6, 'Settings')
    frame(s)
    y = 30
    s.text(8, y, 150, 18, 'Setting', size=11, bold=True)
    s.text(160, y, 76, 18, 'Value', size=11, bold=True, align='Right')
    s.text(244, y, 110, 18, 'Range', size=11, bold=True)
    rows = [('SP', 'Stop at °C', '40.0 - 90.0'), ('HYST', 'Restart gap °C', '3.0 - 10.0'),
            ('STG', 'Stage 2 offset °C', '5.0 - 30.0')]
    if [r[0] for r in rows] != [p[0] for p in B.PARAMS]:
        sys.exit('build_hmi: Settings rows do not match PARAMS')
    for j, (n, label, rng) in enumerate(rows):
        yy = y + 24 + j * 28
        s.text(8, yy, 150, 22, label, size=12)
        s.io(160, yy, 76, 22, 'Par_' + n, write=True, shift=1, length=5)
        s.text(244, yy, 110, 22, rng, size=11, fore=GREY)
    s.text(8, y + 120, 464, 40, 'A value outside the range is set to the nearest limit. '
           'All times are fixed in the program.', size=10, fore=INK)
    s.text(372, y + 24, 104, 20, 'Engineer access', size=10, fore=GREY)
    return s


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    files = [('Tags_LCP01.xml', tag_table())]
    # The Alarms screen is NOT written: it holds the Alarm View added by hand in TIA
    # (Openness V15.1 cannot import it), and Apply-Hmi imports every Screen_*.xml.
    for s in [overview(), burner('BR01'), burner('BR02'), scrubber(), settings()]:
        files.append(('Screen_%s.xml' % s.name.replace(' ', '_'), s.xml()))
    stale = os.path.join(OUT, 'Screen_Alarms.xml')
    if os.path.exists(stale):
        os.remove(stale)
    for fn, text in files:
        with io.open(os.path.join(OUT, fn), 'w', encoding='utf-8') as f:
            f.write(text)
    print('wrote %d files to build\\hmi (%d tags)' % (len(files), len(TAGS)))


if __name__ == '__main__':
    main()
