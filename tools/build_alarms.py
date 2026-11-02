# -*- coding: utf-8 -*-
"""
بيولّد ملف Excel للإنذارات (discrete alarms) بتاعة الـ KTP400، بنفس شكل Export بتاع TIA V15.1،
عشان يتعمل Import من محرر HMI alarms بدوسة. Openness V15.1 مالوش API لإنذارات Comfort (0007 §6).

- المصدر للربط والمراجع: HMI_ALARMS في build_blocks.py؛ نصوص المشغّل والتصنيف هنا بس.
- الـ trigger: تاج الشاشة Alm_<Word> (UInt) والبت من الجدول.
- الـ class: Fault = "No Acknowledgement"؛ Warning = "Warnings" (مفيش Ack؛ RESET من الباب).
- الأعمدة متاخدة من Export حقيقي (build/alarms_sample.xlsx، 2026-11-02).
- عنوان الإنذار إنجليزي قصير؛ الشرح (Info text) بالعربي المصري عشان الفني يفهمه (المستخدم 2026-11-03).
  النسخة الإنجليزية اللي راجعها Astra في commit 7d43cac، والعربي نفس المعنى جملة بجملة.
"""
from __future__ import print_function
import os, sys, re
from collections import Counter
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build_blocks as B  # noqa: E402

OUT = os.path.join(ROOT, 'build', 'hmi', 'Alarms_LCP01.xlsx')
HEADER = ('ID', 'Name', 'Alarm text [en-US], Alarm text', 'FieldInfo [Alarm text]', 'Class',
          'Trigger tag', 'Trigger bit', 'Acknowledgement tag', 'Acknowledgement bit',
          'PLC acknowledgement tag', 'PLC acknowledgement bit', 'Group', 'Report',
          'Info text [en-US], Info text')
NONE = '<No value>'
CLASSES = {'Fault': 'No Acknowledgement', 'Warning': 'Warnings'}
MAX_ALARM_TEXT = 40
BANNED_PANEL_WORDS = ('recorded', 'heat request', 'stage request', 'requests',
                      'permissives', 'fault causes', 'commanded', 'RUN signal',
                      'NC', 'PLC', 'latched', 'indication')

# Rev B: operator overrides only. PLC mapping and engineering refs stay in HMI_ALARMS.
# A sequence (rather than a dict literal) lets validation detect duplicate keys.
# ((word, bit), operator class, alarm text, info text)
OPERATOR_ALARMS = [
    (('Common', 0), 'Fault', 'E-STOP pressed or not reset',
     'اتداس على زرار الطوارئ E-STOP، والإنذار ده هيفضل لحد RESET. '
     'اللوحة إدّت أمر للبيرنرين يقفوا، ولصمام الفلير يفتح، ولصمامي الساكشن والدرين يقفلوا. '
     'فك زرار الطوارئ واضغط RESET على باب اللوحة؛ الصمامات ممكن تتحرك تاني، وكل بيرنر محتاج START.'),
    (('Common', 1), 'Fault', 'Scrubber high pressure: RESET needed',
     'حساس الضغط PSH-101 بيقول إن ضغط السكرابر عالي. '
     'اللوحة إدّت أمر لصمام الفلير يفتح ولصمام الساكشن يقفل. '
     'ده مش بيغيّر أوامر البيرنرات ولا تحكّم الدرين. '
     'لما الضغط يرجع طبيعي، والمستوى العالي جدًا يروح، وزرار الطوارئ يكون مفكوك، اضغط RESET على باب اللوحة. '
     'الـ RESET بيمسح الإنذار وممكن يحرّك الصمامات.'),
    (('Common', 2), 'Fault', 'Scrubber very high level: RESET needed',
     'حساس المستوى LSHH-103 بيقول إن المية في السكرابر عالية جدًا. '
     'اللوحة إدّت أمر لصمام الساكشن يقفل؛ والفلير وأوامر البيرنرات زي ما هي. '
     'حساسات المستوى لسه بتتحكم في الدرين. '
     'لما الضغط يرجع طبيعي، والمستوى العالي جدًا يروح، وزرار الطوارئ يكون مفكوك، اضغط RESET على باب اللوحة. '
     'الـ RESET بيمسح الإنذار وممكن يحرّك الصمامات.'),
    (('Common', 3), 'Fault', 'Scrubber waiting after power-up',
     'بعد ما الكهربا رجعت، اللوحة إدّت أمر لصمام الفلير يفتح ولصمام الساكشن يقفل. '
     'الدرين بيشتغل عادي حتى قبل RESET. '
     'لما الضغط يكون طبيعي، والمستوى العالي جدًا مش موجود، وزرار الطوارئ مفكوك، اضغط RESET على باب اللوحة. '
     'الـ RESET بيمسح الإنذار وممكن يحرّك الصمامات. '
     'البيرنرات محتاجة START بعد رجوع الكهربا، والـ RESET بتاع السكرابر مش بيشغّلها ولا بيوقّفها.'),
    (('Common', 4), 'Warning', 'Scrubber level high (LSH-102)',
     'بص على مستوى المية في السكرابر؛ الإنذار ده بيروح لوحده لما LSH-102 يرجع طبيعي. '
     'أي حساس مستوى من الاتنين ممكن يفتح الدرين بعد شوية. '
     'التأخير العادي: 3 ثواني قبل ما يفتح، و5 ثواني قبل ما يقفل بعد ما الحساسين يرجعوا طبيعي. '
     'الدرين مش هيفتح لو فيه طوارئ مستنية RESET، أو إنذار إن وقت الدرين خلص. '
     'الإنذار ده مش بيوقّف البيرنرات.'),
    (('Common', 5), 'Fault', 'Setting outside allowed range',
     'رقم اتكتب برّه الحدود المسموحة. '
     'اللوحة رجّعت آخر رقم صحيح. '
     'اتأكد من الحدود قبل ما تجرّب تاني، واضغط RESET على باب اللوحة عشان الإنذار يروح.'),
    (('Common', 6), 'Fault', 'Scrubber drain time limit reached',
     'الدرين فضل مطلوب مفتوح أكتر من الوقت المسموح. '
     'اللوحة إدّت أمر للدرين يقفل، وسابت البيرنرات زي ما هي. '
     'شوف ليه الدرين فضل مفتوح كل ده قبل ما تضغط RESET، لأن الـ RESET ممكن يفتحه تاني على طول.'),
    (('Common', 7), 'Fault', 'Scrubber level switch problem',
     'لمدة 5 ثواني، حساس LSHH-103 قال إن المستوى عالي جدًا، بس حساس LSH-102 ماقالش إنه عالي. '
     'المستوى العالي جدًا لسه بيقفل الساكشن، والدرين شغال عادي. '
     'الإنذار ده مش بيوقّف البيرنرات. '
     'افحص الحساسين والسلك بتاعهم. '
     'لما الاختلاف ده يروح، اضغط RESET على باب اللوحة.'),
    (('BR01', 0), 'Fault', 'BR01 E-STOP: RESET needed',
     'حصل تريب طوارئ على BR01، والإنذار ده هيفضل لحد RESET. '
     'اللوحة إدّت أمر لـ BR01 يقف. '
     'فك زرار الطوارئ وصلّح أي مشكلة تانية؛ ولما BR01 مايبقاش بيقول إنه شغال، اضغط RESET على باب اللوحة، وبعدين START بتاع BR01.'),
    (('BR01', 1), 'Fault', 'BR01 temperature sensor problem',
     'حساس حرارة في التانك بيدّي قراية غلط (TE-501 أو TE-502)؛ افحص الحساسين والسلك. '
     'اللوحة إدّت أمر لـ BR01 يقف. '
     'صلّح كل المشاكل؛ ولما BR01 مايبقاش بيقول إنه شغال، اضغط RESET على باب اللوحة، وبعدين START بتاع BR01.'),
    (('BR01', 2), 'Fault', 'BR01 burner lockout',
     'علبة الأمان بتاعة البيرنر BR01 نفسه طلّعت عطل. '
     'اللوحة إدّت أمر لـ BR01 يقف. '
     'صلّح المشكلة واعمل ريسيت للبيرنر نفسه من عنده الأول؛ ولما مايبقاش بيقول إنه شغال، اضغط RESET على باب اللوحة، وبعدين START بتاع BR01.'),
    (('BR01', 3), 'Fault', 'BR01 failed to start',
     'BR01 ماقالش إنه شغال قبل ما وقت الولعة المضبوط يخلص؛ افحص البيرنر. '
     'اللوحة إدّت أمر لـ BR01 يقف. '
     'صلّح كل المشاكل؛ ولما BR01 مايبقاش بيقول إنه شغال، اضغط RESET على باب اللوحة، وبعدين START بتاع BR01.'),
    (('BR01', 4), 'Fault', 'BR01 no longer reports running',
     'BR01 بطّل يقول إنه شغال؛ افحص البيرنر والسلك. '
     'وبعدها اللوحة إدّت أمر لـ BR01 يقف. '
     'صلّح كل المشاكل؛ ولما BR01 مايبقاش بيقول إنه شغال، اضغط RESET على باب اللوحة، وبعدين START بتاع BR01.'),
    (('BR01', 5), 'Fault', 'BR01 reports running while told off',
     'BR01 قال إنه شغال لمدة 30 ثانية من غير ما حد يطلب منه؛ افحص البيرنر والسلك. '
     'اللوحة بتدّي أمر لـ BR01 يفضل طافي. '
     'صلّح كل المشاكل؛ ولما BR01 مايبقاش بيقول إنه شغال، اضغط RESET على باب اللوحة، وبعدين START بتاع BR01.'),
    (('BR01', 6), 'Fault', 'TK01 level too low for BR01',
     'التانك TK01 بيقول إن المستوى واطي؛ اللوحة إدّت أمر لـ BR01 يقف، والإنذار بيروح لوحده لما المستوى يرجع. '
     'في AUTO، البيرنر يرجع يشتغل بس لو الـ START اللي اتداس قبل كده لسه قايم، والتانك محتاج تسخين، وكل الشروط تمام. '
     'في MAN، اضغط START بتاع BR01 تاني بعد ما الدورة اتقطعت.'),
    (('BR02', 0), 'Fault', 'BR02 E-STOP: RESET needed',
     'حصل تريب طوارئ على BR02، والإنذار ده هيفضل لحد RESET. '
     'اللوحة إدّت أمر لـ BR02 يقف. '
     'فك زرار الطوارئ وصلّح أي مشكلة تانية؛ ولما BR02 مايبقاش بيقول إنه شغال، اضغط RESET على باب اللوحة، وبعدين START بتاع BR02.'),
    (('BR02', 1), 'Fault', 'BR02 temperature sensor problem',
     'حساس حرارة في التانك بيدّي قراية غلط (TE-503 أو TE-504)؛ افحص الحساسين والسلك. '
     'اللوحة إدّت أمر لـ BR02 يقف. '
     'صلّح كل المشاكل؛ ولما BR02 مايبقاش بيقول إنه شغال، اضغط RESET على باب اللوحة، وبعدين START بتاع BR02.'),
    (('BR02', 2), 'Fault', 'BR02 burner lockout',
     'علبة الأمان بتاعة البيرنر BR02 نفسه طلّعت عطل. '
     'اللوحة إدّت أمر لـ BR02 يقف. '
     'صلّح المشكلة واعمل ريسيت للبيرنر نفسه من عنده الأول؛ ولما مايبقاش بيقول إنه شغال، اضغط RESET على باب اللوحة، وبعدين START بتاع BR02.'),
    (('BR02', 3), 'Fault', 'BR02 failed to start',
     'BR02 ماقالش إنه شغال قبل ما وقت الولعة المضبوط يخلص؛ افحص البيرنر. '
     'اللوحة إدّت أمر لـ BR02 يقف. '
     'صلّح كل المشاكل؛ ولما BR02 مايبقاش بيقول إنه شغال، اضغط RESET على باب اللوحة، وبعدين START بتاع BR02.'),
    (('BR02', 4), 'Fault', 'BR02 no longer reports running',
     'BR02 بطّل يقول إنه شغال؛ افحص البيرنر والسلك. '
     'وبعدها اللوحة إدّت أمر لـ BR02 يقف. '
     'صلّح كل المشاكل؛ ولما BR02 مايبقاش بيقول إنه شغال، اضغط RESET على باب اللوحة، وبعدين START بتاع BR02.'),
    (('BR02', 5), 'Fault', 'BR02 reports running while told off',
     'BR02 قال إنه شغال لمدة 30 ثانية من غير ما حد يطلب منه؛ افحص البيرنر والسلك. '
     'اللوحة بتدّي أمر لـ BR02 يفضل طافي. '
     'صلّح كل المشاكل؛ ولما BR02 مايبقاش بيقول إنه شغال، اضغط RESET على باب اللوحة، وبعدين START بتاع BR02.'),
    (('BR02', 6), 'Fault', 'TK02 level too low for BR02',
     'التانك TK02 بيقول إن المستوى واطي؛ اللوحة إدّت أمر لـ BR02 يقف، والإنذار بيروح لوحده لما المستوى يرجع. '
     'في AUTO، البيرنر يرجع يشتغل بس لو الـ START اللي اتداس قبل كده لسه قايم، والتانك محتاج تسخين، وكل الشروط تمام. '
     'في MAN، اضغط START بتاع BR02 تاني بعد ما الدورة اتقطعت.'),
]


def validate_alarms(alarms, operator_alarms):
    """Fail before export if either table is ambiguous, incomplete or invalid."""
    source_keys = [(word, bit) for word, bit, *_ in alarms]
    operator_keys = [key for key, *_ in operator_alarms]
    errors = []
    for label, keys in [('HMI_ALARMS', source_keys), ('OPERATOR_ALARMS', operator_keys)]:
        duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
        if duplicates:
            errors.append('%s duplicate keys: %r' % (label, duplicates))
    missing = sorted(set(source_keys) - set(operator_keys))
    extra = sorted(set(operator_keys) - set(source_keys))
    if missing:
        errors.append('Missing operator keys: %r' % missing)
    if extra:
        errors.append('Extra operator keys: %r' % extra)
    for key, alarm_class, text, info in operator_alarms:
        if alarm_class not in CLASSES:
            errors.append('%r: invalid class %r' % (key, alarm_class))
        if not text or len(text) > MAX_ALARM_TEXT:
            errors.append('%r: alarm text must be 1..%d characters (got %d)' %
                          (key, MAX_ALARM_TEXT, len(text)))
        if not info:
            errors.append('%r: missing info text' % (key,))
        for phrase in BANNED_PANEL_WORDS:
            if re.search(r'\b' + re.escape(phrase) + r'\b', text + ' ' + info, re.I):
                errors.append('%r: banned panel wording %r' % (key, phrase))
        sentences = len(re.findall(r'[.!?](?:\s|$)', info))
        if info and not 2 <= sentences <= 5:
            errors.append('%r: info text must have 2..5 sentences (up to 5 for the complex scrubber alarms, Astra 2026-11-03) (got %d)' % (key, sentences))
    if errors:
        raise ValueError('\n'.join(errors))
    return {key: (alarm_class, text, info) for key, alarm_class, text, info in operator_alarms}


def main():
    operator = validate_alarms(B.HMI_ALARMS, OPERATOR_ALARMS)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'DiscreteAlarms'
    ws.append(HEADER)
    for i, (word, bit, _src, _text, _clears, ref) in enumerate(B.HMI_ALARMS, 1):
        alarm_class, text, info = operator[(word, bit)]
        ws.append((i, 'Alm_%s_x%d' % (word, bit), text, '', CLASSES[alarm_class],
                   'Alm_' + word, bit, NONE, 0, NONE, 0, NONE, 'False',
                   info))
        print('%2d %-9s x%d %-7s %2d chars | %s | %s' %
              (i, word, bit, alarm_class, len(text), text, ref))
    if not os.path.isdir(os.path.dirname(OUT)):
        os.makedirs(os.path.dirname(OUT))
    wb.save(OUT)
    print('wrote %s (%d alarms)' % (os.path.relpath(OUT, ROOT), len(B.HMI_ALARMS)))
    counts = Counter(alarm_class for alarm_class, _text, _info in operator.values())
    print('%d Faults, %d Warning; maximum alarm text: %d/%d chars' %
          (counts['Fault'], counts['Warning'], max(len(text) for _, text, _ in operator.values()),
           MAX_ALARM_TEXT))


if __name__ == '__main__':
    main()
