# -*- coding: utf-8 -*-
"""
بيولّد ملف Excel للإنذارات (discrete alarms) بتاعة الـ KTP400، بنفس شكل Export بتاع TIA V15.1،
عشان يتعمل Import من محرر HMI alarms بدوسة. Openness V15.1 مالوش API لإنذارات Comfort (0007 §6).

- المصدر للربط والمراجع: HMI_ALARMS في build_blocks.py؛ نصوص المشغّل والتصنيف هنا بس.
- الـ trigger: تاج الشاشة Alm_<Word> (UInt) والبت من الجدول.
- الـ class: Fault = "No Acknowledgement"؛ Warning = "Warnings" (مفيش Ack؛ RESET من الباب).
- الأعمدة متاخدة من Export حقيقي (build/alarms_sample.xlsx، 2026-11-02).
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
     'E-STOP was pressed; this alarm stays until RESET. '
     'The panel told both burners to stop, the flare valve to open, and the suction and drain valves to close. '
     'Release E-STOP and press RESET on the panel door; valves may move again, and each burner needs START.'),
    (('Common', 1), 'Fault', 'Scrubber high pressure: RESET needed',
     'PSH-101 reported high pressure. '
     'The panel tells the flare to open and suction to close. '
     'This does not change burner commands or drain control. '
     'When pressure is normal, very high level has cleared and E-STOP is released, press door RESET. '
     'RESET clears this alarm and may move valves.'),
    (('Common', 2), 'Fault', 'Scrubber very high level: RESET needed',
     'LSHH-103 reported very high level. '
     'The panel tells suction to close; flare and burner commands are unchanged. '
     'The level switches still control the drain. '
     'When pressure is normal, very high level has cleared and E-STOP is released, press door RESET. '
     'RESET clears this alarm and may move valves.'),
    (('Common', 3), 'Fault', 'Scrubber waiting after power-up',
     'After power-up, the panel tells the flare to open and suction to close. '
     'The drain can work before RESET. '
     'When pressure is normal, very high level has cleared and E-STOP is released, press door RESET. '
     'RESET clears this alarm and may move valves. '
     'Burners need START after power-up; scrubber RESET does not restart or stop them.'),
    (('Common', 4), 'Warning', 'Scrubber level high (LSH-102)',
     'Check the scrubber level; this alarm clears when LSH-102 returns to normal. '
     'Either level switch can trigger drain opening after a delay. '
     'Usual delays: 3 seconds before opening, 5 before closing after both switches clear. '
     'E-STOP awaiting RESET or a drain time-limit alarm prevents opening. '
     'This alarm does not tell the burners to stop.'),
    (('Common', 5), 'Fault', 'Setting outside allowed range',
     'A number was outside its allowed range. '
     'The panel put back the last valid value. '
     'Check the allowed range before trying again; press RESET on the panel door to clear this alarm.'),
    (('Common', 6), 'Fault', 'Scrubber drain time limit reached',
     'The drain was told to stay open past the set time limit. '
     'The panel told the drain to close and left the burners alone. '
     'Check why the drain was needed so long before pressing door RESET, because RESET can tell it to open again immediately.'),
    (('Common', 7), 'Fault', 'Scrubber level switch problem',
     'For 5 seconds, LSHH-103 reported very high level but LSH-102 did not report high level. '
     'Very high level still tells suction to close; normal drain control continues. '
     'This alarm does not tell burners to stop. '
     'Check both switches and wiring. '
     'Once this mismatch clears, press door RESET.'),
    (('BR01', 0), 'Fault', 'BR01 E-STOP: RESET needed',
     'BR01 had an E-STOP trip; this alarm stays until RESET. '
     'The panel told BR01 to stop. '
     'Release E-STOP and fix other problems; once BR01 no longer reports running, press door RESET, then BR01 START.'),
    (('BR01', 1), 'Fault', 'BR01 temperature sensor problem',
     'A tank temperature sensor gave a bad reading (TE-501 or TE-502); check both sensors and wiring. '
     'The panel told BR01 to stop. '
     'Fix all problems; once BR01 no longer reports running, press door RESET, then BR01 START.'),
    (('BR01', 2), 'Fault', 'BR01 burner lockout',
     'BR01 reported a fault in its own safety control. '
     'The panel told BR01 to stop. '
     'Fix all problems and reset the burner itself first; once it no longer reports running, press door RESET, then BR01 START.'),
    (('BR01', 3), 'Fault', 'BR01 failed to start',
     'BR01 did not report running before the set start time ran out; check the burner. '
     'The panel told BR01 to stop. '
     'Fix all problems; once BR01 no longer reports running, press door RESET, then BR01 START.'),
    (('BR01', 4), 'Fault', 'BR01 no longer reports running',
     'BR01 stopped reporting it was running; check the burner and wiring. '
     'The panel then told BR01 to stop. '
     'Fix all problems; once BR01 no longer reports running, press door RESET, then BR01 START.'),
    (('BR01', 5), 'Fault', 'BR01 reports running while told off',
     'BR01 reported running for 30 seconds without being asked; check the burner and wiring. '
     'The panel is telling BR01 to stay off. '
     'Fix all problems; once BR01 no longer reports running, press door RESET, then BR01 START.'),
    (('BR01', 6), 'Fault', 'TK01 level too low for BR01',
     'TK01 reports low level; the panel told BR01 to stop, and this alarm clears when level returns. '
     'AUTO can restart only if the earlier START still applies, the tank needs heat and all checks pass. '
     'In MAN, press BR01 START again after an interrupted cycle.'),
    (('BR02', 0), 'Fault', 'BR02 E-STOP: RESET needed',
     'BR02 had an E-STOP trip; this alarm stays until RESET. '
     'The panel told BR02 to stop. '
     'Release E-STOP and fix other problems; once BR02 no longer reports running, press door RESET, then BR02 START.'),
    (('BR02', 1), 'Fault', 'BR02 temperature sensor problem',
     'A tank temperature sensor gave a bad reading (TE-503 or TE-504); check both sensors and wiring. '
     'The panel told BR02 to stop. '
     'Fix all problems; once BR02 no longer reports running, press door RESET, then BR02 START.'),
    (('BR02', 2), 'Fault', 'BR02 burner lockout',
     'BR02 reported a fault in its own safety control. '
     'The panel told BR02 to stop. '
     'Fix all problems and reset the burner itself first; once it no longer reports running, press door RESET, then BR02 START.'),
    (('BR02', 3), 'Fault', 'BR02 failed to start',
     'BR02 did not report running before the set start time ran out; check the burner. '
     'The panel told BR02 to stop. '
     'Fix all problems; once BR02 no longer reports running, press door RESET, then BR02 START.'),
    (('BR02', 4), 'Fault', 'BR02 no longer reports running',
     'BR02 stopped reporting it was running; check the burner and wiring. '
     'The panel then told BR02 to stop. '
     'Fix all problems; once BR02 no longer reports running, press door RESET, then BR02 START.'),
    (('BR02', 5), 'Fault', 'BR02 reports running while told off',
     'BR02 reported running for 30 seconds without being asked; check the burner and wiring. '
     'The panel is telling BR02 to stay off. '
     'Fix all problems; once BR02 no longer reports running, press door RESET, then BR02 START.'),
    (('BR02', 6), 'Fault', 'TK02 level too low for BR02',
     'TK02 reports low level; the panel told BR02 to stop, and this alarm clears when level returns. '
     'AUTO can restart only if the earlier START still applies, the tank needs heat and all checks pass. '
     'In MAN, press BR02 START again after an interrupted cycle.'),
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
