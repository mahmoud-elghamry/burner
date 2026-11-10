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
    (('Common', 0), 'Fault', 'E-STOP active: reset required', 'حصلت طوارئ، والإنذار لسه مستني RESET. اللوحة بتبعت أوامر توقف للبيرنرين، وأمر فتح للفلير، وأمر قفل للساكشن والدرين. فك زرار الطوارئ واضغط RESET؛ أوامر الصمامات ممكن تتغير فورًا، وكل بيرنر محتاج START جديد.'),
    (('Common', 1), 'Fault', 'Scrubber high pressure: reset required', 'حصل إنذار ضغط عالي من PSH-101؛ الإنذار يفضل ظاهر لحد RESET حتى لو الضغط رجع طبيعي. اللوحة بتبعت أوامر توقف للبيرنرين، وأمر فتح للفلير، وأمر قفل للساكشن؛ الدرين يفضل تابع للمستوى. اتأكد إن الضغط طبيعي، وLSHH-103 رجع طبيعي، وE-STOP مفكوك، وبعدها اضغط RESET؛ كل بيرنر محتاج START جديد.'),
    (('Common', 2), 'Fault', 'Scrubber very high level: reset required', 'حصل إنذار مستوى عالي جدًا من LSHH-103؛ الإنذار يفضل ظاهر لحد RESET حتى لو المستوى رجع طبيعي. اللوحة بتبعت أوامر توقف للبيرنرين وأمر قفل للساكشن؛ أمر الفلير لا يتغير والدرين يفضل تابع للمستوى. اتأكد إن الضغط طبيعي، وLSHH-103 رجع طبيعي، وE-STOP مفكوك، وبعدها اضغط RESET؛ كل بيرنر محتاج START جديد.'),
    (('Common', 3), 'Fault', 'Scrubber waiting for first RESET', 'بعد رجوع الكهرباء، سبب تريب السكرابر محفوظ. أمر فتح للفلير وأمر قفل للساكشن قائم؛ الدرين يفضل يستجيب للمستوى قبل RESET. اتأكد إن الضغط طبيعي، والمستوى العالي جدًا مش موجود، وE-STOP مفكوك، وبعدها اضغط RESET. RESET لا يشغّل البيرنرات؛ كل بيرنر محتاج START بعد رجوع الكهرباء.'),
    (('Common', 4), 'Warning', 'Scrubber high level (LSH-102)', 'إنذار المستوى يختفي لوحده لما دخل LSH-102 يرجع طبيعي، ومش بيوقف البيرنرات. افتراضيًا، LSH-102 أو LSHH-103 يطلب أمر فتح للدرين بعد 3 ثواني، وأمر قفل بعد 5 ثواني من رجوع الحساسين للطبيعي؛ التأخيران قابلان للتعديل. أمر الدرين ممنوع أثناء انتظار RESET للطوارئ أو تريب مهلة الدرين.'),
    (('Common', 5), 'Fault', 'Setting rejected', 'إعداد خرج عن الحدود أو اتغير ولسه فيه سماح START محفوظ لأي بيرنر. اللوحة رجعت آخر قيمة صحيحة، والإنذار يفضل محفوظ لحد RESET. اضغط STOP لكل بيرنر، وراجع حدود الرقم قبل تعديله تاني، واضغط RESET لمسح الإنذار.'),
    (('Common', 6), 'Fault', 'Scrubber drain time limit reached', 'أمر فتح الدرين فضل مطلوب أكتر من المدة المسموحة. اللوحة شالت أمر الفتح، لكن مفيش قياس لموضع الصمام والبيرنرات ما بتقفش بسبب الإنذار ده. افحص سبب استمرار الطلب قبل RESET؛ ممكن RESET يرجع أمر الفتح فورًا.'),
    (('Common', 7), 'Fault', 'Scrubber level switch disagreement', 'لمدة 5 ثواني، LSHH-103 أشار لمستوى عالي جدًا بينما LSH-102 لم يشر لمستوى عالٍ. الإنذار يفضل محفوظ لحد ما الاختلاف يروح وتضغط RESET. LSHH-103 ممكن يشيل أمر فتح الساكشن ويعمل تريب يوقف البيرنرين؛ إشارات المستوى تفضل متحكمة في الدرين. افحص الحساسين وتوصيلاتهم.'),
    (('BR01', 0), 'Fault', 'BR01 E-STOP trip saved', 'حصل تريب طوارئ على BR01، والإنذار ده هيفضل لحد RESET. اللوحة بعتت أمر بإيقاف BR01. فك زرار الطوارئ وصلّح أي مشكلة تانية؛ ولما إشارة تشغيل البيرنر RUN تفصل، اضغط RESET على باب اللوحة، وبعدين START بتاع BR01.'),
    (('BR01', 1), 'Fault', 'BR01 temperature input fault', 'دخل حساس حرارة TK01 كان غير سليم (TE-501 أو TE-502)، والعطل يفضل محفوظ بعد رجوع الدخل سليم. افحص الحساسين والتوصيلات. اللوحة بعتت أمر بإيقاف BR01. صلّح كل المشاكل؛ ولما إشارة تشغيل البيرنر RUN تفصل، اضغط RESET على باب اللوحة، وبعدين START بتاع BR01.'),
    (('BR01', 2), 'Fault', 'BR01 burner lockout', 'علبة التحكم في BR01 أبلغت عن LOCKOUT، والعطل ممكن يفضل محفوظ بعد مسح LOCKOUT محليًا. اللوحة بعتت أمر بإيقاف BR01. صلّح المشكلة واعمل ريسيت للبيرنر نفسه من عنده الأول؛ ولما إشارة تشغيل البيرنر RUN تفصل، اضغط RESET على باب اللوحة، وبعدين START بتاع BR01.'),
    (('BR01', 3), 'Fault', 'BR01 RUN not received in time', 'دخل RUN من علبة BR01 ماوصلش قبل ما وقت الولعة المضبوط يخلص؛ افحص البيرنر. اللوحة بعتت أمر بإيقاف BR01. صلّح كل المشاكل؛ ولما إشارة تشغيل البيرنر RUN تفصل، اضغط RESET على باب اللوحة، وبعدين START بتاع BR01.'),
    (('BR01', 4), 'Fault', 'BR01 RUN input lost', 'دخل RUN من علبة BR01 بقى مفصول؛ افحص البيرنر والسلك. وبعدها اللوحة بعتت أمر بإيقاف BR01. صلّح كل المشاكل؛ ولما إشارة تشغيل البيرنر RUN تفصل، اضغط RESET على باب اللوحة، وبعدين START بتاع BR01.'),
    (('BR01', 5), 'Fault', 'BR01 RUN without request', 'دخل RUN من علبة BR01 فضل شغال 30 ثانية من غير طلب حرارة؛ افحص البيرنر والسلك. اللوحة بعتت أمر بإيقاف BR01. صلّح كل المشاكل؛ ولما إشارة تشغيل البيرنر RUN تفصل، اضغط RESET على باب اللوحة، وبعدين START بتاع BR01.'),
    (('BR01', 6), 'Fault', 'TK01 level too low for BR01', 'التانك TK01 بيقول إن المستوى واطي؛ اللوحة بعتت أمر بإيقاف BR01، والإنذار بيروح لوحده لما المستوى يرجع. في AUTO، الرجوع للتشغيل محتاج سماح START محفوظ، واحتياج للحرارة، وكل شروط البدء سليمة. في MAN، اضغط START بتاع BR01 تاني بعد ما الدورة اتقطعت.'),
    (('BR01', 7), 'Fault', 'BR01 stopped by scrubber trip', 'تريب السكرابر شال طلب تشغيل BR01. صلّح سبب الضغط العالي أو المستوى العالي جدًا واستنى لحد ما إشارة تشغيل البيرنر RUN تفصل. بعد زوال السبب اضغط RESET على باب اللوحة، وبعدين START بتاع BR01.'),
    (('BR02', 0), 'Fault', 'BR02 E-STOP trip saved', 'حصل تريب طوارئ على BR02، والإنذار ده هيفضل لحد RESET. اللوحة بعتت أمر بإيقاف BR02. فك زرار الطوارئ وصلّح أي مشكلة تانية؛ ولما إشارة تشغيل البيرنر RUN تفصل، اضغط RESET على باب اللوحة، وبعدين START بتاع BR02.'),
    (('BR02', 1), 'Fault', 'BR02 temperature input fault', 'دخل حساس حرارة TK02 كان غير سليم (TE-503 أو TE-504)، والعطل يفضل محفوظ بعد رجوع الدخل سليم. افحص الحساسين والتوصيلات. اللوحة بعتت أمر بإيقاف BR02. صلّح كل المشاكل؛ ولما إشارة تشغيل البيرنر RUN تفصل، اضغط RESET على باب اللوحة، وبعدين START بتاع BR02.'),
    (('BR02', 2), 'Fault', 'BR02 burner lockout', 'علبة التحكم في BR02 أبلغت عن LOCKOUT، والعطل ممكن يفضل محفوظ بعد مسح LOCKOUT محليًا. اللوحة بعتت أمر بإيقاف BR02. صلّح المشكلة واعمل ريسيت للبيرنر نفسه من عنده الأول؛ ولما إشارة تشغيل البيرنر RUN تفصل، اضغط RESET على باب اللوحة، وبعدين START بتاع BR02.'),
    (('BR02', 3), 'Fault', 'BR02 RUN not received in time', 'دخل RUN من علبة BR02 ماوصلش قبل ما وقت الولعة المضبوط يخلص؛ افحص البيرنر. اللوحة بعتت أمر بإيقاف BR02. صلّح كل المشاكل؛ ولما إشارة تشغيل البيرنر RUN تفصل، اضغط RESET على باب اللوحة، وبعدين START بتاع BR02.'),
    (('BR02', 4), 'Fault', 'BR02 RUN input lost', 'دخل RUN من علبة BR02 بقى مفصول؛ افحص البيرنر والسلك. وبعدها اللوحة بعتت أمر بإيقاف BR02. صلّح كل المشاكل؛ ولما إشارة تشغيل البيرنر RUN تفصل، اضغط RESET على باب اللوحة، وبعدين START بتاع BR02.'),
    (('BR02', 5), 'Fault', 'BR02 RUN without request', 'دخل RUN من علبة BR02 فضل شغال 30 ثانية من غير طلب حرارة؛ افحص البيرنر والسلك. اللوحة بعتت أمر بإيقاف BR02. صلّح كل المشاكل؛ ولما إشارة تشغيل البيرنر RUN تفصل، اضغط RESET على باب اللوحة، وبعدين START بتاع BR02.'),
    (('BR02', 6), 'Fault', 'TK02 level too low for BR02', 'التانك TK02 بيقول إن المستوى واطي؛ اللوحة بعتت أمر بإيقاف BR02، والإنذار بيروح لوحده لما المستوى يرجع. في AUTO، الرجوع للتشغيل محتاج سماح START محفوظ، واحتياج للحرارة، وكل شروط البدء سليمة. في MAN، اضغط START بتاع BR02 تاني بعد ما الدورة اتقطعت.'),
    (('BR02', 7), 'Fault', 'BR02 stopped by scrubber trip', 'تريب السكرابر شال طلب تشغيل BR02. صلّح سبب الضغط العالي أو المستوى العالي جدًا واستنى لحد ما إشارة تشغيل البيرنر RUN تفصل. بعد زوال السبب اضغط RESET على باب اللوحة، وبعدين START بتاع BR02.'),
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


def alarm_id(word, bit):
    """Keep the original 22 IDs stable; append new scrubber-stop alarms as 23/24."""
    if word == 'Common' and 0 <= bit <= 7:
        return 1 + bit
    if word == 'BR01' and 0 <= bit <= 6:
        return 9 + bit
    if word == 'BR02' and 0 <= bit <= 6:
        return 16 + bit
    return {('BR01', 7): 23, ('BR02', 7): 24}[(word, bit)]


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
