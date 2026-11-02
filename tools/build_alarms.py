# -*- coding: utf-8 -*-
"""
بيولّد ملف Excel للإنذارات (discrete alarms) بتاعة الـ KTP400، بنفس شكل Export بتاع TIA V15.1،
عشان يتعمل Import من محرر HMI alarms بدوسة. Openness V15.1 مالوش API لإنذارات Comfort (0007 §6).

- المصدر: HMI_ALARMS في build_blocks.py، نفس الجدول اللي بيولّد HmiMap والجدول في التشغيل.md §5.
- الـ trigger: تاج الشاشة Alm_<Word> (UInt) والبت من الجدول.
- الـ class: "No Acknowledgement" (D4: مفيش Ack على الشاشة، والـ RESET من الباب).
- الأعمدة متاخدة من Export حقيقي (build/alarms_sample.xlsx، 2026-11-02).
"""
from __future__ import print_function
import os, sys
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


def main():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'DiscreteAlarms'
    ws.append(HEADER)
    for i, (word, bit, _src, text, clears, ref) in enumerate(B.HMI_ALARMS, 1):
        ws.append((i, 'Alm_%s_x%d' % (word, bit), text, '', 'No Acknowledgement',
                   'Alm_' + word, bit, NONE, 0, NONE, 0, NONE, 'False',
                   'Clears: %s. Source: %s' % (clears, ref)))
    if not os.path.isdir(os.path.dirname(OUT)):
        os.makedirs(os.path.dirname(OUT))
    wb.save(OUT)
    print('wrote %s (%d alarms)' % (os.path.relpath(OUT, ROOT), len(B.HMI_ALARMS)))


if __name__ == '__main__':
    main()
