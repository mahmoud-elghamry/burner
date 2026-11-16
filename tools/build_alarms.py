# -*- coding: utf-8 -*-
"""
بيولّد ملف Excel للإنذارات (discrete alarms) بتاعة الـ KTP400، بنفس شكل Export بتاع TIA V15.1،
عشان يتعمل Import من محرر HMI alarms بدوسة. Openness V15.1 مالوش API لإنذارات Comfort (0007 §6).

- المصدر للربط والمراجع: HMI_ALARMS في build_blocks.py؛ نصوص المشغّل والتصنيف هنا بس.
- الـ trigger: تاج الشاشة Alm_<Word> (UInt) والبت من الجدول.
- الـ class: Fault = "No Acknowledgement"؛ Warning = "Warnings" (مفيش Ack؛ RESET من الباب).
- الأعمدة متاخدة من Export حقيقي (build/alarms_sample.xlsx، 2026-11-02).
- Operator-facing alarm titles are short English; Info text is Egyptian Arabic. Mapping and references remain sourced from HMI_ALARMS.
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

# English short titles and simple Arabic operator explanations (0010). PLC mapping and engineering refs stay in HMI_ALARMS.
# A sequence (rather than a dict literal) lets validation detect duplicate keys.
# ((word, bit), operator class, alarm text, info text)
OPERATOR_ALARMS = [
    (('Common', 0), 'Fault', 'E-STOP pressed', 'زرار الطوارئ مضغوط: البيرنرين واقفين، والفلير مفتوح، والساكشن والدرين مقفولين. الإنذار بيروح أول ما تفك الزرار، والدرين يرجع يمشي مع المستوى لو حد وقته مش حاصل. السكرابر يفضل في تريب: لما الأسباب تبقى سليمة اضغط RESET، وبعدها START لكل بيرنر.'),
    (('Common', 1), 'Fault', 'Scrubber tripped: reset required', 'السكرابر عامل تريب: الساكشن مقفول والبيرنرين واقفين. بيحصل من الضغط العالي أو المستوى العالي جدًا أو الطوارئ أو بعد رجوع الكهربا. لما كله يرجع طبيعي اضغط RESET، وبعدها START لكل بيرنر.'),
    (('Common', 2), 'Fault', 'Scrubber trip: high pressure', 'الضغط العالي PSH-101 هو اللي عمل التريب، والإنذار يفضل ظاهر لحد RESET حتى لو الضغط رجع. الفلير مفتوح والساكشن مقفول. اتأكد إن الضغط طبيعي واضغط RESET.'),
    (('Common', 3), 'Fault', 'Scrubber trip: very high level', 'المستوى العالي جدًا LSHH-103 هو اللي عمل التريب، والإنذار يفضل ظاهر لحد RESET حتى لو المستوى نزل. الساكشن مقفول والدرين بيفتح مع المستوى. اتأكد إن المستوى نزل واضغط RESET.'),
    (('Common', 4), 'Warning', 'Scrubber high level (LSH-102)', 'المستوى في السكرابر عالي والدرين مفتوح. الإنذار بيروح لوحده لما المستوى ينزل والدرين يقفل.'),
    (('Common', 5), 'Fault', 'Scrubber drain time limit reached', 'الدرين فضل مفتوح 10 دقايق ورا بعض فاتقفل. ممكن يكون سلك LSH-102 مقطوع أو العوامة معلقة. افحص الحساس وبعدين اضغط RESET، والدرين يرجع يمشي مع المستوى.'),
] + [x for br, tk, te in (('BR01', 'TK01', 'TE-501 / TE-502'), ('BR02', 'TK02', 'TE-503 / TE-504')) for x in [
    ((br, 0), 'Fault', '%s burner lockout' % br, 'علبة البيرنر %s عملت LOCKOUT وقفلت الغاز بنفسها. صلّح السبب واعمل ريسيت من على علبة البيرنر، وبعدها اضغط START.' % br),
    ((br, 1), 'Fault', '%s temperature input fault' % br, 'حساس حرارة %s (%s) بيقرا قراية غلط من 10 ثواني، فالبيرنر وقف. افحص الحساس والسلك. لما القراية ترجع سليمة اضغط START.' % (tk, te)),
    ((br, 2), 'Warning', '%s RUN not received' % br, 'البيرنر %s مطلوب منه يشتغل من دقيقتين ولسه ما ولّعش. افحص كهربا البيرنر وسلك الطلب. الإنذار بيروح لوحده لما البيرنر يولّع.' % br),
    ((br, 3), 'Fault', '%s RUN without request' % br, 'البيرنر %s شغال من 30 ثانية من غير ما اللوحة تطلبه. ممكن ريلاي الطلب يكون لازق. افحص اللوحة فورًا.' % br),
    ((br, 4), 'Warning', '%s level too low for %s' % (tk, br), 'مستوى التانك %s واطي فالبيرنر %s مستني. في AUTO البيرنر بيرجع لوحده لما المستوى يرجع. في MAN اضغط START تاني.' % (tk, br)),
]]


def alarm_id(word, bit):
    """Rev. B: new numbering (alarms are imported again): Common 1-6, BR01 7-11, BR02 12-16."""
    return {'Common': 1, 'BR01': 7, 'BR02': 12}[word] + bit


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
    for word, bit, _src, _text, _clears, ref in B.HMI_ALARMS:
        i = alarm_id(word, bit)
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
