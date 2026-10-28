# -*- coding: utf-8 -*-
"""سيناريوهات docs/التشغيل.md §6 على PLCSIM V15.1، أوتوماتيك.

    py tools\\plcsim\\run_scenarios.py              # كلهم
    py tools\\plcsim\\run_scenarios.py T1 T7        # المختار بس

قبلها: البرنامج متنزّل على PLCSIM من TIA (Start simulation + Download)،
وPLCSIM شغال. السكريبت بيكلّمه عن طريق build\\plcsim\\PlcSimCtl.exe.

الاختبار بيشوف المخارج بس (%Q)، لأن واجهة PLCSIM مفيهاش قراية للـ DB.
فالـ FAULT بيتعرف من السلوك: الطلب بيقع، ومش بيرجع غير بـ RESET ثم START.
النتيجة بتتطبع، والسطر الأخير PASS أو FAIL.
"""
from __future__ import print_function
import io, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CTL = os.path.join(ROOT, 'build', 'plcsim', 'PlcSimCtl.exe')

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ---- العناوين (جدول التاجات IO) ---------------------------------------
I = dict(PSH='I0.0', LSH='I0.1', LSHH='I0.2', RR='I0.3', S1='I0.4', Rflt='I0.5', S3='I0.6',
         S0='I1.0', S2='I1.1', LSL1='I1.2', LSL2='I1.3', RR2='I1.4', Rflt2='I1.5',
         Rfuel2='I12.0', S4='I12.1', S5='I12.2', S6='I12.3', S7='I12.4',
         TE501='IW96', TE502='IW98', TE503='IW100', TE504='IW102')
Q = dict(TL1=(0, 0), TR1=(0, 1), XV401=(0, 2), XV402=(0, 3), XV403=(0, 4),
         L2=(0, 5), T2=(0, 6), H5=(0, 7), H6=(1, 0))

HEALTHY = [('PSH', 1), ('LSH', 1), ('LSHH', 1), ('S0', 1), ('S3', 1), ('S7', 1),
           ('LSL1', 1), ('LSL2', 1), ('S4', 1), ('S5', 1), ('RR', 0), ('RR2', 0),
           ('Rflt', 0), ('Rflt2', 0), ('Rfuel2', 0), ('S1', 0), ('S2', 0), ('S6', 0),
           ('TE501', 400), ('TE502', 400), ('TE503', 400), ('TE504', 400)]

SCAN = 0.4      # ثواني بعد كل تغيير، كفاية لكذا scan


class Sim(object):
    def __init__(self):
        self.p = subprocess.Popen([CTL], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  universal_newlines=True, bufsize=1)
        hello = self.p.stdout.readline().strip()
        if not hello.startswith('OK'):
            raise SystemExit('PLCSIM: ' + hello)
        self.log = []
        self.fails = 0

    def cmd(self, line):
        self.p.stdin.write(line + '\n')
        self.p.stdin.flush()
        r = self.p.stdout.readline().strip()
        if not r.startswith('OK'):
            raise RuntimeError('%s -> %s' % (line, r))
        return r[3:]

    def set(self, name, value, wait=SCAN):
        addr = I[name]
        self.cmd(('setw %s %d' if addr.startswith('IW') else 'set %s %d') % (addr, value))
        if wait:
            time.sleep(wait)

    def press(self, name):
        """زرار NO: 1 ثم 0."""
        self.set(name, 1)
        self.set(name, 0)

    def press_nc(self, name):
        """زرار NC (STOP): 0 ثم 1."""
        self.set(name, 0)
        self.set(name, 1)

    def outs(self):
        raw = self.cmd('readq 0 2').split('-')
        b = [int(x, 16) for x in raw]
        return dict((k, (b[byte] >> bit) & 1) for k, (byte, bit) in Q.items())

    def expect(self, label, **want):
        got = self.outs()
        bad = dict((k, got[k]) for k, v in want.items() if got[k] != v)
        line = '  %-4s %s  %s' % ('ok' if not bad else 'FAIL', label,
                                  ' '.join('%s=%d' % (k, got[k]) for k in sorted(want)))
        if bad:
            self.fails += 1
            line += '   expected ' + ' '.join('%s=%d' % (k, want[k]) for k in sorted(bad))
        print(line)

    def wait(self, s):
        time.sleep(s)

    def restart(self):
        """PLC STOP ثم RUN بمداخل سليمة، وبعدها RESET للـ scrubber (S-01)."""
        # المداخل بتتكتب بعد RUN: PLCSIM مش بيقبل SetValues وهو STOP. أول scan
        # بيشوف المداخل القديمة (ممكن E-STOP)، والـ RESET بعدها بيرجّع كله.
        self.cmd('stop')
        time.sleep(1.5)
        self.cmd('run')
        time.sleep(3)
        for n, v in HEALTHY:
            self.set(n, v, wait=0)
        time.sleep(SCAN)
        self.press('S2')

    def close(self):
        try:
            self.cmd('quit')
        except Exception:
            pass


# ---- السيناريوهات -------------------------------------------------------
def start_br01(s, temp=400):
    """BR01 لحد RUNNING."""
    s.set('TE501', temp, 0)
    s.set('TE502', temp)
    s.press('S1')
    s.set('RR', 1)


def T1(s):
    """يوم عادي: AUTO، 40 ثم 60 ثم 70 ثم 65"""
    s.expect('after power-up + RESET: burners off, valves normal',
             TL1=0, TR1=0, XV401=1, XV402=1, XV403=1)
    s.press('S1')
    s.expect('START at 40 degC -> STARTING: TL on, no 2nd stage', TL1=1, TR1=0)
    s.set('RR', 1)
    s.expect('RUN -> RUNNING below 60: 2nd stage', TL1=1, TR1=1)
    s.set('TE501', 600, 0); s.set('TE502', 600)
    s.expect('60 degC: 2nd stage stays (2 degC band, F41)', TL1=1, TR1=1)
    s.set('TE501', 620, 0); s.set('TE502', 620)
    s.expect('62 degC: 1st stage only', TL1=1, TR1=0)
    s.set('TE501', 599, 0); s.set('TE502', 599)
    s.expect('59.9 degC: 2nd stage again', TL1=1, TR1=1)
    s.set('TE501', 610, 0); s.set('TE502', 610)
    s.expect('61 degC: still 2nd stage (band)', TL1=1, TR1=1)
    s.set('TE501', 700, 0); s.set('TE502', 700)
    s.expect('70 degC: stop (C07b)', TL1=0, TR1=0)
    s.set('RR', 0)
    s.set('TE501', 680, 0); s.set('TE502', 680)
    s.expect('68 degC: stays off (hysteresis)', TL1=0)
    s.set('TE501', 650, 0); s.set('TE502', 650)
    s.expect('65 degC: restarts by itself in AUTO', TL1=1)


def T1b(s):
    """الحرارة = الأعلى بين الاتنين (C07b)"""
    s.press('S1'); s.set('RR', 1)
    s.set('TE502', 700)
    s.expect('outlet 70, inlet 40: stops on the higher one', TL1=0)


def T2(s):
    """التانك فضي وهو شغال"""
    start_br01(s)
    s.set('LSL1', 0)
    s.expect('LSL lost: stop (C07a)', TL1=0)
    s.set('RR', 0)
    s.set('LSL1', 1)
    s.expect('LSL back: restarts by itself (AUTO)', TL1=1)


def T3(s):
    """اللهب طفى (lockout)"""
    start_br01(s)
    s.set('Rflt', 1, 0); s.set('RR', 0)
    s.expect('lockout: request off (C07e)', TL1=0, TR1=0)
    s.set('Rflt', 0)
    s.press('S1')
    s.expect('lockout cleared at burner, START without RESET: refused', TL1=0)
    s.press('S2')
    s.expect('RESET: still off, needs START (B-02)', TL1=0)
    s.press('S1')
    s.expect('START after RESET: runs', TL1=1)


def T4(s):
    """مولّعش خلال T_START (120 ث)"""
    s.press('S1')
    s.expect('STARTING', TL1=1)
    s.wait(118)
    s.expect('118 s: still waiting', TL1=1)
    s.wait(4)
    s.expect('122 s, no RUN: FAULT (C07f)', TL1=0)
    s.press('S1')
    s.expect('START without RESET: refused', TL1=0)
    s.press('S2'); s.press('S1')
    s.expect('RESET + START: runs', TL1=1)


def T5(s):
    """وقف لوحده وهو شغال"""
    start_br01(s)
    s.set('RR', 0)
    s.expect('RUN lost, no lockout: FAULT (C07g)', TL1=0)
    s.press('S1')
    s.expect('START without RESET: refused', TL1=0)
    s.press('S2'); s.press('S1')
    s.expect('RESET + START: runs', TL1=1)


def T6(s):
    """ثيرموكابل بايظ: 32767، و-32768، و2500 — على قناة واحدة"""
    s.wait(11)      # بعد مهلة رجوع الكهربا (R-10)
    for bad in (32767, -32768, 2500):
        start_br01(s)
        s.set('TE501', bad)
        s.set('RR', 0)
        s.expect('TE-501 = %d: request off at once' % bad, TL1=0)
        s.set('TE501', 400)
        s.press('S1')
        s.expect('TE-501 good again, START without RESET: refused (C07d FAULT)', TL1=0)
        s.press('S2'); s.press('S1')
        s.expect('RESET + START: runs', TL1=1)
        s.set('RR', 1); s.press_nc('S3'); s.set('RR', 0)


def T6p(s):
    """R-10: بعد رجوع الكهربا الكارت بيدّي 32767 لثواني — مش عطل لو رجع قبل 10 ث"""
    s.set('TE501', 32767)
    s.cmd('stop'); time.sleep(1.5)
    s.cmd('run'); time.sleep(3); s.press('S2')
    s.press('S1')
    s.expect('TC still calibrating: START refused, no heat', TL1=0)
    s.set('TE501', 400)
    s.press('S1')
    s.expect('TC valid within 10 s: START accepted', TL1=1)


def T6b(s):
    """STOP وSTART مع بعض، وSTART محشور"""
    s.set('S3', 0, 0); s.set('S1', 1)
    s.expect('STOP + START together: off (STOP wins)', TL1=0)
    s.set('S3', 1)
    s.expect('STOP released, START still held: off', TL1=0)
    s.set('S1', 0)
    s.set('S1', 1)
    s.cmd('stop'); time.sleep(1.5); s.cmd('run'); time.sleep(3); s.press('S2')
    s.expect('START held through PLC STOP/RUN: off (R-05)', TL1=0)
    s.set('S1', 0)
    s.press('S1')
    s.expect('released and pressed again: runs', TL1=1)


def T7(s):
    """ضغط الـ scrubber عالي — البيرنرات تكمّل"""
    start_br01(s)
    s.set('PSH', 0)
    s.expect('PSH-101: valves safe, BR01 keeps running (C03)', XV401=0, XV402=0, XV403=0, TL1=1)
    s.set('PSH', 1)
    s.expect('PSH back: valves stay safe until RESET', XV401=0, XV402=0, XV403=0)
    s.press('S2')
    s.expect('RESET: valves normal, BR01 untouched (R-07)', XV401=1, XV402=1, XV403=1, TL1=1)
    s.set('LSHH', 0)
    s.expect('LSHH-103: valves safe (C05)', XV401=0, XV402=0, XV403=0, TL1=1)
    s.press('S2')
    s.expect('RESET while LSHH still open: stays tripped', XV401=0, XV402=0, XV403=0)
    s.set('LSHH', 1); s.press('S2')
    s.set('LSH', 0)
    s.expect('LSH-102: alarm only, valves stay (C04)', XV401=1, XV402=1, XV403=1)


def T8(s):
    """E-STOP"""
    start_br01(s)
    s.set('TE503', 400, 0); s.set('TE504', 400); s.press('S6'); s.set('RR2', 1)
    s.expect('both burners running', TL1=1, L2=1)
    s.set('S0', 0); s.set('RR', 0, 0); s.set('RR2', 0)
    s.expect('E-STOP: everything off, valves safe (C01)',
             TL1=0, TR1=0, L2=0, T2=0, XV401=0, XV402=0, XV403=0)
    s.set('S0', 1)
    s.expect('E-STOP released: still off', TL1=0, L2=0, XV403=0)
    s.press('S2')
    s.expect('RESET: scrubber back, burners stay off (B-02)', XV401=1, XV403=1, TL1=0, L2=0)
    s.press('S1'); s.press('S6')
    s.expect('START each: both run', TL1=1, L2=1)


def T9(s):
    """الكهربا قطعت ورجعت"""
    start_br01(s)
    s.cmd('stop'); time.sleep(1.5)
    s.expect('PLC STOP: all outputs off (C02)', TL1=0, XV401=0, XV403=0)
    s.set('RR', 0)
    s.cmd('run'); time.sleep(3)
    s.expect('RUN again: scrubber tripped, burner off (S-01, B-02)', TL1=0, XV401=0, XV403=0)
    s.press('S2')
    s.expect('RESET: scrubber normal, burner still off', XV401=1, XV403=1, TL1=0)


def T10(s):
    """MAN: دورة واحدة"""
    s.set('S4', 0)
    s.press('S1')
    s.expect('MAN + START: runs', TL1=1)
    s.set('RR', 1)
    s.set('TE501', 700, 0); s.set('TE502', 700)
    s.expect('70 degC: stops', TL1=0)
    s.set('RR', 0)
    s.set('TE501', 600, 0); s.set('TE502', 600)
    s.expect('60 degC: does NOT restart (MAN)', TL1=0)
    s.press('S1')
    s.expect('new START: runs', TL1=1)


def R02(s):
    """تغيير AUTO/MAN وهو شغال"""
    start_br01(s)
    s.set('S4', 0)
    s.expect('AUTO -> MAN while running: off (R-02)', TL1=0)
    s.set('RR', 0); s.set('S4', 1)
    s.expect('back to AUTO: stays off, needs START', TL1=0)


def R01(s):
    """START والمستوى واطي بيترفض"""
    s.set('LSL1', 0)
    s.press('S1')
    s.set('LSL1', 1)
    s.expect('START with LSL low was refused: off (R-01)', TL1=0)


def R09(s):
    """RUN شغال من غير طلب 30 ث"""
    s.set('RR', 1)
    s.wait(32)
    s.set('RR', 0)
    s.press('S1')
    s.expect('RUN without request 30 s: FAULT, START refused (R-09)', TL1=0)
    s.press('S2'); s.press('S1')
    s.expect('RESET + START: runs', TL1=1)


def BR02(s):
    """BR02: نفس المنطق، واللمبات، والديزل، والاستقلال عن BR01"""
    s.press('S6')
    s.expect('BR02 START: L and lamp H5', L2=1, H5=1, T2=0, H6=0)
    s.set('RR2', 1)
    s.expect('BR02 RUN below 60: T2 and lamp H6', L2=1, H5=1, T2=1, H6=1)
    start_br01(s)
    s.set('Rflt', 1, 0); s.set('RR', 0)
    s.expect('BR01 lockout: BR02 keeps running', TL1=0, L2=1)
    s.set('Rflt', 0)
    s.press('S2')
    s.expect('RESET for BR01: BR02 untouched (R-07)', L2=1, T2=1)
    s.set('Rfuel2', 1)
    s.expect('fuel changed while running: BR02 off (R-12)', L2=0, H5=0)
    s.set('RR2', 0)
    s.press('S6')
    s.expect('new START: BR02 runs', L2=1)
    s.set('RR2', 1)
    s.press_nc('S7')
    s.expect('S7 STOP: BR02 off', L2=0)


ALL = [T1, T1b, T2, T3, T4, T5, T6, T6p, T6b, T7, T8, T9, T10, R01, R02, R09, BR02]


def main(names):
    tests = [t for t in ALL if not names or t.__name__ in names]
    s = Sim()
    try:
        for t in tests:
            print('%s — %s' % (t.__name__, t.__doc__.strip()))
            s.restart()
            try:
                t(s)
            except Exception as e:
                s.fails += 1
                print('  FAIL exception: %s' % e)
    finally:
        s.close()
    print('PASS' if s.fails == 0 else 'FAIL (%d)' % s.fails)
    return 0 if s.fails == 0 else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
