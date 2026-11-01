# -*- coding: utf-8 -*-
"""
بيحط PLCSIM في مواقف جاهزة عشان نتفرّج عليها على محاكي الشاشة (0007 P7).
نفس كلاس Sim بتاع run_scenarios.py. كل أمر بيتنفّذ بالترتيب:

  py tools\plcsim\demo.py healthy                 كله سليم + RESET (40.0 درجة)
  py tools\plcsim\demo.py start1 run1             BR01: START، وبعدين RUN feedback
  py tools\plcsim\demo.py temp1=620               حرارة BR01 (عُشر درجة، القناتين)
  py tools\plcsim\demo.py psh                     ضغط الـ scrubber عالي (يفتح ويرجع)
  py tools\plcsim\demo.py estop reset             طوارئ تتضغط وتتفك، وبعدين RESET
  py tools\plcsim\demo.py lockout1 tcbad2         عطل lockout لـ BR01، وثيرموكابل بايظ لـ BR02
"""
from __future__ import print_function
import sys, time
import run_scenarios as R


def main(args):
    s = R.Sim()
    try:
        for a in args:
            if a == 'healthy':
                s.restart()
            elif a == 'reset':
                s.press('S2')
            elif a in ('start1', 'start2'):
                s.press('S1' if a == 'start1' else 'S6')
            elif a in ('run1', 'run2'):
                time.sleep(1)
                s.set('RR' if a == 'run1' else 'RR2', 1)
            elif a in ('stop1', 'stop2'):
                s.press_nc('S3' if a == 'stop1' else 'S7')
                s.set('RR' if a == 'stop1' else 'RR2', 0)
            elif a.startswith('temp1=') or a.startswith('temp2='):
                v = int(a.split('=')[1])
                pair = ('TE501', 'TE502') if a[4] == '1' else ('TE503', 'TE504')
                s.set(pair[0], v, 0)
                s.set(pair[1], v)
            elif a == 'psh':
                s.set('PSH', 0, 1)
                s.set('PSH', 1)
            elif a == 'lsh':
                s.set('LSH', 0)
            elif a == 'estop':
                s.set('S0', 0, 1)
                s.set('S0', 1)
            elif a in ('lockout1', 'lockout2'):
                s.set('Rflt' if a == 'lockout1' else 'Rflt2', 1)
                s.set('RR' if a == 'lockout1' else 'RR2', 0)
            elif a in ('tcbad1', 'tcbad2'):
                s.set('TE501' if a == 'tcbad1' else 'TE503', 32767)
            else:
                sys.exit('unknown step: ' + a)
            print('done', a)
    finally:
        s.close()


if __name__ == '__main__':
    main(sys.argv[1:])
