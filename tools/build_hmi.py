# -*- coding: utf-8 -*-
"""
بيولّد تاجات الشاشة والشاشات الست (decisions/0007) في build/hmi/، وApply-Hmi.ps1 بيعمل import.

الشكل متاخد من exports حقيقية لـ V15.1: عيّنة P1 (IO field، وتاج Int على HMI_Connection_1)،
وشاشات الأوناش (TextField وButton وCircle وRectangle وRangeAppearance وSingleBitVisibility).

- الشاشة بتكتب في 4 تاجات بس: Par_SP وPar_HYST وPar_STG وPar_TStart (H-01). كل حقل تاني Output.
- مفيش أي زرار بيكتب في الـ PLC. الزراير بتغيّر الشاشة بس (ActivateScreen).
- أسماء أعضاء الـ DBs بتتراجع على جداول build_blocks.py، فلو اسم اتغيّر هناك السكريبت بيقف.
- الحرارة بعُشر الدرجة: الحقل بيعرضها بـ ShiftDecimalPoint=1 (700 -> 70.0)، من غير scaling.
- شاشة Alarms فيها مكان فاضي للـ alarm view: Openness V15.1 مش بيعمله import (0007 §6).
- قبل الاستيراد: py tools/check_hmi_xml.py بيراجع أسماء الخصائص والتركيبات على نفس الـ exports.
"""
from __future__ import print_function
import io, os, sys
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
    br.update({n: t for n, t in B.BR_STAT})
    scrub = {n: 'Bool' for n, _ in B.SCRUB_IN}
    scrub.update({n: 'Bool' for n, _ in B.SCRUB_OUT})
    scrub.update({n: 'Bool' for n, _ in B.SCRUB_CAUSES})
    scrub['FirstOut'] = 'Int'
    par = {}
    for n, t, *_ in B.PARAMS:
        par[n] = t
        par[n + '_V'] = t
    sys_ = {n: 'Bool' for n, _ in B.SYS}
    return {'BR01_DB': br, 'BR02_DB': br, 'Scrubber_DB': scrub, 'Par': par, 'Sys': sys_,
            'HmiAlm': {'Common': 'Word', 'BR01': 'Word', 'BR02': 'Word'}}


MEMBERS = _members()
BR_READ = ['TeA', 'TeB', 'Tmax', 'TcOkA', 'TcOkB', 'TcOk', 'State', 'Enabled', 'HeatReq',
           'Stage2', 'RunFb', 'Lockout', 'LevelOK', 'Auto', 'PwrUpDone', 'SP_Act', 'TOn',
           'TStg', 'TStgOff', 'ParPending', 'F_EStop', 'F_TC', 'F_Lockout', 'F_NoStart',
           'F_RunLost', 'F_RunWrong']
TAGS = []   # (اسم الشاشة، DB، العضو)
for br in ('BR01', 'BR02'):
    extra = ['Pause24'] if br == 'BR01' else ['Fuel']
    TAGS += [(br + '_' + m, br + '_DB', m) for m in BR_READ + extra]
TAGS += [('Scrub_' + m, 'Scrubber_DB', m) for m in
         ['PSH', 'LSH', 'LSHH', 'Tripped', 'ValvesNormal', 'Cause_EStop', 'Cause_PSH',
          'Cause_LSHH', 'Cause_PwrUp', 'FirstOut']]
TAGS += [('Par_' + n, 'Par', n) for n, *_ in B.PARAMS]
TAGS += [('Par_' + n + '_V', 'Par', n + '_V') for n, *_ in B.PARAMS]
TAGS += [('Sys_' + m, 'Sys', m) for m in ['EStopOK', 'Alm_EStop', 'Alm_ParRejected']]
TAGS += [('Alm_' + w, 'HmiAlm', w) for w in ['Common', 'BR01', 'BR02']]
# H-01: الحقول اللي بتكتب. أي Input على تاج مش هنا = السكريبت يقف.
WRITABLE = {'Par_' + n for n, *_ in B.PARAMS}

TAG_TYPE = {}
for name, db, m in TAGS:
    if m not in MEMBERS[db]:
        sys.exit('build_hmi: %s.%s not in build_blocks.py' % (db, m))
    TAG_TYPE[name] = MEMBERS[db][m]


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
            '<AcquisitionTriggerMode>Visible</AcquisitionTriggerMode>'
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
            % (ids(), TYPES[t], name, CONN, db, m, t, HMI_TYPE.get(t, t),
               mltext(ids, 'Comment'), mltext(ids, 'DisplayName'), mltext(ids, 'TagValue')))
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

    def oname(self, kind):
        self.count[kind] = self.count.get(kind, 0) + 1
        return '%s_%d' % (kind, self.count[kind])

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
    def rect(self, x, y, w, h, back, border=None, anims=()):
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
               self.oname('Rectangle'), y, w, ''.join(anims)))

    def text(self, x, y, w, h, s, size=12, bold=False, fore=INK, back=None, align='Left',
             anims=()):
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
               self.oname('Text'), y, w, ''.join(anims), self.font(size, bold),
               mltext(self.ids, 'Text', s)))

    def io(self, x, y, w, h, tag, write=False, shift=1, length=5, size=13):
        if write and tag not in WRITABLE:
            sys.exit('build_hmi: %s is not one of the four writable settings (H-01)' % tag)
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
               self.oname('IOField'), shift, 1 if write else -1, y, w,
               self.font(size, True), mltext(self.ids, 'HelpText'), self.ids(), self.ids(), tag))

    def lamp(self, x, y, tag, label, on=GREEN, w=140):
        """دايرة + كلمة. الدايرة رمادي لما التاج 0، وبلون on لما 1."""
        anim = self.anim_range(tag, [(0, 0, GREY, INK), (1, 1, on, INK)])
        self.items.append(
            '<Hmi.Screen.Circle ID="%s" CompositionName="ScreenItems"><AttributeList>'
            '<BackColor>%s</BackColor><BackFillStyle>Solid</BackFillStyle><BorderColor>80, 80, 80</BorderColor>'
            '<BorderWidth>1</BorderWidth><EdgeStyle>Solid</EdgeStyle><Flashing>None</Flashing>'
            '<Height>12</Height><Left>%d</Left><ObjectName>%s</ObjectName><Radius>6</Radius>'
            '<TabIndex>-1</TabIndex><Top>%d</Top><UseDesignColorSchema>false</UseDesignColorSchema>'
            '<Width>12</Width></AttributeList><ObjectList>%s</ObjectList></Hmi.Screen.Circle>'
            % (self.ids(), GREY, x, self.oname('Circle'), y + 3, anim))
        self.text(x + 16, y, w - 16, 18, label, size=11)

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
               self.oname('Button'), y, w, self.ids(), self.ids(), self.ids(), self.ids(), screen,
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
    # E-STOP في العنوان: ظاهر لما Sys.Alm_EStop = 1
    s.text(330, 3, 146, 20, 'E-STOP / RESET', size=12, bold=True, fore=WHITE, back=RED,
           align='Center', anims=[s.anim_vis('Sys_Alm_EStop', True)])
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
    s.text(x + 124, y, 26, 20, 'C', size=11)


BR_STATE = [(0, 'IDLE', GREY), (1, 'START', AMBER), (2, 'RUN', GREEN), (3, 'FAULT', RED)]
FIRST = [(1, 'E-STOP', RED), (2, 'PSH-101', RED), (3, 'LSHH-103', RED), (4, 'POWER-UP', AMBER)]


def panel(s, x, y, w, h, title):
    s.rect(x, y, w, h, WHITE, PANEL_BORDER)
    s.text(x + 4, y + 2, w - 8, 20, title, size=12, bold=True)


# ======================================================================
#  الشاشات
# ======================================================================
def overview():
    s = Screen('Root screen', 1, 'Overview')
    frame(s)
    pw, y, h = 156, 30, 202
    # Scrubber
    x = 2
    panel(s, x, y, pw, h, 'SCRUBBER')
    segments(s, x + 4, y + 24, pw - 8, 'Scrub_Tripped',
             [(0, 'NORMAL', GREEN), (1, 'TRIP', RED)])
    s.text(x + 4, y + 46, pw - 8, 18, 'First cause:', size=11)
    segments(s, x + 4, y + 64, pw - 8, 'Scrub_FirstOut', FIRST, cols=1, h=16)
    s.text(x + 4, y + 140, pw - 8, 18, 'RESET required', size=11, bold=True, fore=RED,
           anims=[s.anim_vis('Scrub_Tripped', True)])
    s.text(x + 4, y + 160, pw - 8, 18, 'Valves: normal', size=11,
           anims=[s.anim_vis('Scrub_ValvesNormal', True)])
    s.text(x + 4, y + 160, pw - 8, 18, 'Valves: safe position', size=11, bold=True, fore=RED,
           anims=[s.anim_vis('Scrub_ValvesNormal', False)])
    # البيرنرين
    for i, (br, tk) in enumerate([('BR01', 'TK01'), ('BR02', 'TK02')]):
        x = 2 + (i + 1) * (pw + 3)
        panel(s, x, y, pw, h, '%s  %s' % (br, tk))
        segments(s, x + 4, y + 24, pw - 8, br + '_State', BR_STATE)
        temp(s, x + 4, y + 66, br + '_Tmax', br + '_TcOk', 'T max')
        s.text(x + 4, y + 90, 70, 18, 'AUTO', size=11, bold=True,
               anims=[s.anim_vis(br + '_Auto', True)])
        s.text(x + 4, y + 90, 70, 18, 'MAN', size=11, bold=True, fore=BLUE,
               anims=[s.anim_vis(br + '_Auto', False)])
        s.lamp(x + 4, y + 110, br + '_HeatReq', 'Heat request')
        s.lamp(x + 4, y + 130, br + '_Stage2', '2nd stage request')
        s.lamp(x + 4, y + 150, br + '_RunFb', 'RUN feedback')
        s.text(x + 4, y + 176, pw - 8, 18, 'Setting pending', size=11, bold=True, fore=AMBER,
               anims=[s.anim_vis(br + '_ParPending', True)])
    return s


def burner(br):
    tk, te = ('TK01', ('TE-501', 'TE-502')) if br == 'BR01' else ('TK02', ('TE-503', 'TE-504'))
    s = Screen(br, 2 if br == 'BR01' else 3, '%s  %s' % (br, tk))
    frame(s)
    y = 30
    segments(s, 4, y, 472, br + '_State', BR_STATE, cols=4)
    # الحرارة والحدود اللي البيرنر ده شغال بيها (_Act)
    x, y = 4, 54
    panel(s, x, y, 156, 178, 'Temperature  C')
    temp(s, x + 4, y + 24, br + '_TeA', br + '_TcOkA', te[0])
    temp(s, x + 4, y + 46, br + '_TeB', br + '_TcOkB', te[1])
    temp(s, x + 4, y + 68, br + '_Tmax', br + '_TcOk', 'T max')
    for j, (tag, label) in enumerate([('_SP_Act', 'Stop at'), ('_TOn', 'Restart at'),
                                      ('_TStg', '2nd below'), ('_TStgOff', '2nd off at')]):
        s.text(x + 4, y + 94 + j * 20, 70, 20, label, size=11)
        s.io(x + 74, y + 94 + j * 20, 52, 20, br + tag, size=12)
    # الإشارات
    x = 162
    panel(s, x, y, 156, 178, 'Signals')
    rows = [('_Auto', 'AUTO mode', GREEN), ('_Enabled', 'START given', GREEN),
            ('_HeatReq', 'Heat request', GREEN), ('_Stage2', '2nd stage request', GREEN),
            ('_RunFb', 'RUN feedback', GREEN), ('_LevelOK', 'Tank level OK', GREEN),
            ('_Lockout', 'Lockout signal', RED)]
    rows += [('_Pause24', '24 h stop active', AMBER)] if br == 'BR01' else \
        [('_Fuel', 'Fuel mode', BLUE)]
    for j, (tag, label, color) in enumerate(rows):
        s.lamp(x + 4, y + 24 + j * 19, br + tag, label, on=color)
    # الأعطال، كل واحد لوحده
    x = 320
    panel(s, x, y, 156, 178, 'Faults (RESET)')
    faults = [('_F_EStop', 'E-STOP'), ('_F_TC', 'Thermocouple'), ('_F_Lockout', 'Burner lockout'),
              ('_F_NoStart', 'Failed to start'), ('_F_RunLost', 'Stopped by itself'),
              ('_F_RunWrong', 'RUN w/o request')]
    for j, (tag, label) in enumerate(faults):
        s.lamp(x + 4, y + 24 + j * 19, br + tag, label, on=RED)
    s.text(x + 4, y + 142, 148, 18, 'Setting pending', size=11, bold=True, fore=AMBER,
           anims=[s.anim_vis(br + '_ParPending', True)])
    s.text(x + 4, y + 158, 148, 18, 'TC starting up', size=11, fore=AMBER,
           anims=[s.anim_vis(br + '_PwrUpDone', False)])
    return s


def scrubber():
    s = Screen('Scrubber', 4, 'Scrubber')
    frame(s)
    y = 30
    segments(s, 4, y, 472, 'Scrub_Tripped', [(0, 'NORMAL', GREEN), (1, 'TRIP', RED)], cols=2)
    x, y = 4, 54
    panel(s, x, y, 156, 178, 'Sensors (now)')
    s.lamp(x + 4, y + 24, 'Scrub_PSH', 'PSH-101 healthy')
    s.lamp(x + 4, y + 44, 'Scrub_LSH', 'LSH-102 healthy')
    s.lamp(x + 4, y + 64, 'Scrub_LSHH', 'LSHH-103 healthy')
    s.lamp(x + 4, y + 84, 'Sys_EStopOK', 'E-STOP released')
    x = 162
    panel(s, x, y, 156, 178, 'Trip causes (RESET)')
    s.text(x + 4, y + 22, 148, 18, 'First:', size=11)
    segments(s, x + 4, y + 40, 148, 'Scrub_FirstOut', FIRST, cols=1, h=16)
    s.lamp(x + 4, y + 114, 'Scrub_Cause_EStop', 'E-STOP', on=RED)
    s.lamp(x + 4, y + 132, 'Scrub_Cause_PSH', 'PSH-101', on=RED)
    s.lamp(x + 4, y + 150, 'Scrub_Cause_LSHH', 'LSHH-103', on=RED)
    s.lamp(x + 80, y + 114, 'Scrub_Cause_PwrUp', 'Power-up', on=AMBER, w=72)
    x = 320
    panel(s, x, y, 156, 178, 'Valve commands')
    for j, (tag, normal, safe) in enumerate([('XV-401 flare', 'CLOSE', 'OPEN'),
                                            ('XV-402 drain', 'CLOSE', 'OPEN'),
                                            ('XV-403 suction', 'OPEN', 'CLOSE')]):
        yy = y + 24 + j * 22
        s.text(x + 4, yy, 96, 20, tag, size=11)
        s.text(x + 100, yy, 52, 20, normal, size=11, bold=True,
               anims=[s.anim_vis('Scrub_ValvesNormal', True)])
        s.text(x + 100, yy, 52, 20, safe, size=11, bold=True, fore=RED,
               anims=[s.anim_vis('Scrub_ValvesNormal', False)])
    s.text(x + 4, y + 96, 148, 34, 'Command only: no valve position feedback.', size=10,
           fore=GREY)
    s.text(x + 4, y + 140, 148, 18, 'RESET required', size=12, bold=True, fore=RED,
           anims=[s.anim_vis('Scrub_Tripped', True)])
    return s


def alarms():
    s = Screen('Alarms', 5, 'Alarms')
    frame(s)
    # مكان الـ alarm view: بيتحط بالإيد (Openness V15.1 مش بيعمله import)
    s.rect(4, 30, 472, 202, WHITE, PANEL_BORDER)
    s.text(12, 110, 456, 40, 'Alarm view goes here (placed by hand in TIA, 0007 P6)',
           size=11, fore=GREY, align='Center')
    return s


def settings():
    s = Screen('Settings', 6, 'Settings')
    frame(s)
    y = 30
    s.text(8, y, 110, 18, 'Setting', size=11, bold=True)
    s.text(120, y, 76, 18, 'New', size=11, bold=True, align='Right')
    s.text(200, y, 90, 18, 'Range', size=11, bold=True)
    s.text(292, y, 76, 18, 'Accepted', size=11, bold=True, align='Right')
    rows = [('SP', 'Stop at  C', 1, '40.0 - 90.0'), ('HYST', 'Restart below  C', 1, '3.0 - 10.0'),
            ('STG', '2nd stage below  C', 1, '5.0 - 30.0'), ('TStart', 'Start time  ms', 0, '90000 - 300000')]
    for j, (n, label, shift, rng) in enumerate(rows):
        yy = y + 22 + j * 30
        s.text(8, yy, 112, 26, label, size=11)
        s.io(120, yy, 76, 26, 'Par_' + n, write=True, shift=shift, length=6 if n == 'TStart' else 5)
        s.text(200, yy, 90, 26, rng, size=10, fore=GREY)
        s.io(292, yy, 76, 26, 'Par_' + n + '_V', shift=shift, length=6 if n == 'TStart' else 5)
    s.text(372, y + 22, 104, 54, 'Raising heat applies after STOP + START.', size=10, fore=GREY)
    s.lamp(372, y + 84, 'BR01_ParPending', 'BR01 pending', on=AMBER, w=104)
    s.lamp(372, y + 104, 'BR02_ParPending', 'BR02 pending', on=AMBER, w=104)
    s.text(8, y + 146, 360, 20, 'Setting rejected: out of range (RESET to clear)', size=11,
           bold=True, fore=WHITE, back=RED, anims=[s.anim_vis('Sys_Alm_ParRejected', True)])
    s.text(8, y + 176, 460, 20, 'Settings need log-on (user Engineer).', size=10, fore=GREY)
    return s


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    files = [('Tags_LCP01.xml', tag_table())]
    for s in [overview(), burner('BR01'), burner('BR02'), scrubber(), alarms(), settings()]:
        files.append(('Screen_%s.xml' % s.name.replace(' ', '_'), s.xml()))
    for fn, text in files:
        with io.open(os.path.join(OUT, fn), 'w', encoding='utf-8') as f:
            f.write(text)
    print('wrote %d files to build\\hmi (%d tags)' % (len(files), len(TAGS)))


if __name__ == '__main__':
    main()
