# -*- coding: utf-8 -*-
"""Output-only PLCSIM V15.1 scenarios for the manager-style Rev B generator.

    py tools\\plcsim\\run_scenarios.py          # default, about 5 minutes
    py tools\\plcsim\\run_scenarios.py T1 T7
    py tools\\plcsim\\run_scenarios.py T7d      # real 10 min drain limit
    py tools\\plcsim\\run_scenarios.py T24      # real 24 h + 60 s
    py tools\\plcsim\\run_scenarios.py --help

Download the CURRENT tools/build_blocks.py program first. Set retained Par values
on the HMI to SP=700, HYST=50, STG=100 (0.1 degC). The bridge cannot read/write
DBs, so settings, alarms and cause bits need separate HMI/watch-table checks.
Only physical inputs are written and %Q outputs read. STOP/RUN exercises OB100;
it does not test physical supply failure or hardwired flame safety.
PASS means only that the selected output assertions passed. Healthy burner trip
recovery needs a new START, never a burner RESET with S2.

C06a: T7 observes valve trip retention, NOT Cause_PSH/Cause_LSHH bits.
C07f/C08f and C07g/C08g: T4/R09 observe no output trip, NOT alarm indication.
Single-scan priorities and alarm bits remain in tools/tests/test_panel_rules.py;
samples after SCAN settling cannot establish single-scan timing.
The final result line is PASS or FAIL (count). --slow is for demonstration;
its extra settling time is excluded from the ~6 min default budget.
"""
from __future__ import print_function
import argparse
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
DRN_MAX = 600.0
STAGE_DELAY = 30.0
TC_DELAY = 10.0


class Sim(object):
    def __init__(self):
        self.p = subprocess.Popen([CTL], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  universal_newlines=True, bufsize=1)
        hello = self.p.stdout.readline().strip()
        if not hello.startswith('OK'):
            self.p.wait(timeout=5)
            raise RuntimeError('PLCSIM: ' + (hello or 'controller exited without a greeting'))
        self.log = []
        self.fails = 0

    def cmd(self, line):
        self.p.stdin.write(line + '\n')
        self.p.stdin.flush()
        r = self.p.stdout.readline().strip()
        # SetInput بيرجّع AddressOutOfRange لبايتات غير 0 مع إن الكتابة بتوصل (اتأكد
        # بالمخارج 2026-10-28)، فالحكم الحقيقي هو expect() على المخارج.
        if line.startswith('set') and r == 'ERR AddressOutOfRange':
            return ''
        if not r.startswith('OK'):
            raise RuntimeError('%s -> %s' % (line, r))
        return r[3:]

    def set(self, name, value, wait=None):
        addr = I[name]
        self.cmd(('setw %s %d' if addr.startswith('IW') else 'set %s %d') % (addr, value))
        if wait is None:
            wait = SCAN             # وقت النداء، عشان --slow يأثّر
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
        """STOP/RUN, healthy inputs, then S2; no drain open/close delay."""
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
        try:
            self.p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.p.kill()
            self.p.wait()


# ---- السيناريوهات -------------------------------------------------------
# Every assertion cites C&E and/or the operating-spec rule.
BURNERS_OFF = dict(TL1=0, TR1=0, L2=0, T2=0, H5=0, H6=0)
ALL_OFF = dict(BURNERS_OFF, XV401=0, XV402=0, XV403=0)


def inputs(s, **values):
    """Batch independent inputs, then settle; never write while PLC is STOP."""
    for name, value in values.items():
        s.set(name, value, wait=0)
    s.wait(SCAN)


def buttons(s, *names):
    inputs(s, **dict((name, 1) for name in names))
    inputs(s, **dict((name, 0) for name in names))


def temperatures(s, a=500, b=None):
    """Same pair on each tank; individual-channel tests use inputs()."""
    inputs(s, TE501=a, TE502=a if b is None else b,
           TE503=a, TE504=a if b is None else b)


def burners(s, label, heat=(1, 1), stage=(0, 0)):
    """Check BR02 lamps against final L/T2 values too (E3/E4)."""
    s.expect(label, TL1=heat[0], TR1=stage[0], L2=heat[1], T2=stage[1],
             H5=heat[1], H6=stage[1])


def start_both(s):
    buttons(s, 'S1', 'S6')


def feedback(s, value):
    inputs(s, RR=value, RR2=value)


def until(s, started, seconds):
    """Elapsed-time checkpoint: input settling cannot accumulate."""
    s.wait(max(0.0, started + seconds - time.monotonic()))


def cycle(s):
    """Keep prepared inputs across STOP/RUN; no input writes during STOP."""
    s.cmd('stop')
    s.wait(1.5)
    s.expect('[C02] PLC STOP: all nine outputs de-energised', **ALL_OFF)
    s.cmd('run')
    s.wait(3)


def T1(s):
    """Both AUTO burners: RUN delay, stage band and 70/65 hysteresis."""
    temperatures(s)
    start_both(s)
    burners(s, '[C07b/C08b, B-01] START at 50 C: heat, no stage 2')
    s.wait(3)
    burners(s, '[C07c/C08c] request without RUN: stage 2 remains off')
    began = time.monotonic()
    feedback(s, 1)
    burners(s, '[C07c/C08c] RUN just arrived: stage 2 still off')
    until(s, began, 28)
    burners(s, '[C07c/C08c] RUN under 30 s: stage 2 still off')
    temperatures(s, 600)
    until(s, began, STAGE_DELAY + 1)
    burners(s, '[C07c/C08c] RUN over 30 s but exactly 60 C: no stage 2')
    temperatures(s, 599)
    burners(s, '[C07c/C08c] 59.9 C after RUN delay: stage 2 on', stage=(1, 1))
    temperatures(s, 610)
    burners(s, '[C07c/C08c] 61 C: stage 2 held in band', stage=(1, 1))
    temperatures(s, 620)
    burners(s, '[C07c/C08c] exactly 62 C: stage 2 off')
    temperatures(s, 600)
    burners(s, '[C07c/C08c] exactly 60 C cannot re-enable stage 2')
    temperatures(s, 599)
    burners(s, '[C07c/C08c] below 60 C re-enables stage 2', stage=(1, 1))
    feedback(s, 0)
    burners(s, '[C07c/C08c] RUN lost: stage 2 off, heat remains')
    temperatures(s, 700)
    burners(s, '[C07b/C08b] exactly SP 70 C: both requests off', heat=(0, 0))
    temperatures(s, 651)
    burners(s, '[C07b/C08b] 65.1 C: still off', heat=(0, 0))
    temperatures(s, 650)
    burners(s, '[C07b/C08b] exactly 65 C: AUTO resumes without START')


def T1b(s):
    """Each thermocouple can be the higher controlling temperature."""
    start_both(s)
    for a, b in ((400, 700), (700, 400)):
        temperatures(s, a, b)
        burners(s, '[C07b/C08b] max(%s,%s) stops both tanks' % (a, b), heat=(0, 0))
        temperatures(s, 650)
        burners(s, '[C07b/C08b] both channels at 65 C: AUTO resumes')


def T2(s):
    """AUTO low level removes request; recovery needs no START."""
    start_both(s)
    for level, heat in (('LSL1', (0, 1)), ('LSL2', (1, 0))):
        inputs(s, **{level: 0})
        burners(s, '[C07a/C08a] %s lost: only its burner stops' % level, heat=heat)
        inputs(s, **{level: 1})
        burners(s, '[C07a/C08a] %s healthy: AUTO resumes' % level)


def T3(s):
    """Local lockouts are independent and need START, never burner RESET."""
    start_both(s)
    for fault, start, heat in (('Rflt', 'S1', (0, 1)), ('Rflt2', 'S6', (1, 0))):
        inputs(s, **{fault: 1})
        burners(s, '[C07e/C08e] %s: local burner off, peer unaffected' % fault, heat=heat)
        inputs(s, **{start: 1})
        inputs(s, **{fault: 0})
        burners(s, '[C07e/C08e, B-01] lockout cleared, START held: stays off', heat=heat)
        inputs(s, **{start: 0})
        buttons(s, start)
        burners(s, '[C07e/C08e] fresh START after box reset: heat, no S2')


def T4(s):
    """LONG: no RUN for 120 s is alarm-only; alarm bit is not observable."""
    start_both(s)
    began = time.monotonic()
    burners(s, '[C07f/C08f] no RUN: heat request active')
    until(s, began, 118)
    burners(s, '[C07f/C08f] before 120 s: request remains')
    until(s, began, 122)
    burners(s, '[C07f/C08f] after 120 s: NO output trip (alarm unobserved)')
    feedback(s, 1)
    burners(s, '[C07f/C08f] RUN arrives: request remains, stage timer starts')
    inputs(s, S3=0, S7=0)
    burners(s, '[C07f/C08f, B-01] STOP removes requests', heat=(0, 0))


def T5(s):
    """RUN dropout alone is not a trip in Rev B."""
    start_both(s)
    feedback(s, 1)
    feedback(s, 0)
    burners(s, '[C07c/C08c; Rev B] RUN lost without lockout: heat stays, stage off')


def T6(s):
    """Both channels, both burners: short bad input vs >10 s trip."""
    start_both(s)
    for channel1, channel2 in (('TE501', 'TE503'), ('TE502', 'TE504')):
        # A failed-low reading must not hide behind a healthy, higher channel.
        began = time.monotonic()
        inputs(s, **{channel1: -201, channel2: -201})
        burners(s, '[C07d/C08d] %s/%s below -20 C: immediate inhibit' %
                (channel1, channel2), heat=(0, 0))
        until(s, began, 8)
        temperatures(s)
        burners(s, '[C07d/C08d] repaired at 8 s (<10 s): AUTO resumes')
        inputs(s, **{channel1: 32767, channel2: 32767})
        burners(s, '[C07d/C08d] %s/%s broken: immediate inhibit' %
                (channel1, channel2), heat=(0, 0))
        s.wait(TC_DELAY + 1)
        temperatures(s)
        burners(s, '[C07d/C08d] good after >10 s fault: stays off until START', heat=(0, 0))
        start_both(s)
        burners(s, '[C07d/C08d] fresh START after repair: no S2 needed')


def T6p(s):
    """TC invalid during OB100 startup; <10 s calibration then fresh START."""
    inputs(s, TE501=32767, TE503=32767)
    cycle(s)
    s.press('S2')
    burners(s, '[C02/C07d/C08d] startup invalid TC: no heat', heat=(0, 0))
    temperatures(s)
    start_both(s)
    burners(s, '[C07d/C08d, B-01] valid after calibration then START: heat')


def T6b(s):
    """STOP wins; holding START through STOP release never starts."""
    inputs(s, S3=0, S7=0, S1=1, S6=1)
    burners(s, '[B-01/C02] START + STOP: both off', heat=(0, 0))
    inputs(s, S3=1, S7=1)
    burners(s, '[B-01/C02] STOP released with START held: still off', heat=(0, 0))
    inputs(s, S1=0, S6=0)
    start_both(s)
    burners(s, '[B-01] release then fresh START: both on')
    inputs(s, S3=0, S7=0)
    burners(s, '[B-01] NC STOP open removes both requests and lamps', heat=(0, 0))
    inputs(s, S3=1, S7=1)
    burners(s, '[B-01] STOP released: no automatic restart', heat=(0, 0))


def T7(s):
    """Each scrubber trip alone, retained trip and healthy RESET gating."""
    for cause in ('PSH', 'LSHH'):
        row = 'C03' if cause == 'PSH' else 'C05'
        flare = 0 if cause == 'PSH' else 1
        start_both(s)
        burners(s, '[%s] both requesting before %s trip' % (row, cause))
        inputs(s, **{cause: 0})
        s.expect('[%s] cause active: valve actions, all burner requests/lamps off' % row,
                 XV401=flare, XV402=int(cause == 'LSHH'), XV403=0, **BURNERS_OFF)
        s.press('S2')
        s.expect('[%s] RESET with cause active: trip wins' % row,
                 XV401=flare, XV403=0, **BURNERS_OFF)
        inputs(s, **{cause: 1})
        s.expect('[%s/C06a] cause healthy: valve trip retained (cause bits unobserved)' % row,
                 XV401=flare, XV402=0, XV403=0, **BURNERS_OFF)
        inputs(s, **{cause: 0})
        inputs(s, S2=1, S1=1, S6=1)
        inputs(s, **{cause: 1})
        s.expect('[%s/C06a] cause clears while RESET/START held: still tripped' % row,
                 XV401=flare, XV403=0, **BURNERS_OFF)
        inputs(s, S2=0)
        s.press('S2')
        s.expect('[%s] healthy fresh S2: normal valves, held START cannot run' % row,
                 XV401=1, XV402=0, XV403=1, **BURNERS_OFF)
        inputs(s, S1=0, S6=0)
        start_both(s)
        burners(s, '[%s] fresh START after S2 restores both requests' % row)
        inputs(s, S3=0, S7=0)
        inputs(s, S3=1, S7=1)


def T7b(s):
    """Drain immediate level control, E-STOP release and high-level startup."""
    start_both(s)
    for level in (0, 1, 0, 1, 0):
        inputs(s, LSH=level)
        s.expect('[C04] LSH=%d: drain follows within settling interval; no trip' % level,
                 XV401=1, XV402=1-level, XV403=1, TL1=1, L2=1, H5=1)
    inputs(s, S0=0)
    s.expect('[C01/C04] E-STOP while high: all outputs off', **ALL_OFF)
    s.press('S2')
    s.expect('[C01] S2 while E-STOP pressed cannot reset', **ALL_OFF)
    inputs(s, S0=1)
    s.expect('[C01/C04] release WITHOUT S2: drain open, scrubber still tripped',
             XV401=0, XV402=1, XV403=0, **BURNERS_OFF)
    inputs(s, LSH=1)
    s.expect('[C04] level healthy WITHOUT S2: drain closes', XV402=0, XV403=0)
    inputs(s, LSH=0)
    cycle(s)
    s.expect('[C02/C04] high level after RUN, no S2: drain opens during trip',
             XV401=0, XV402=1, XV403=0, **BURNERS_OFF)
    inputs(s, LSH=1)
    s.press('S2')
    s.expect('[C02/C04] healthy S2 restores scrubber only',
             XV401=1, XV402=0, XV403=1, **BURNERS_OFF)


def T7c(s):
    """Trip cancels AUTO permission even when idle at SP; diesel also trips."""
    temperatures(s, 700)
    start_both(s)
    burners(s, '[C07b/C08b, B-01] START at SP: enabled but no heat', heat=(0, 0))
    inputs(s, PSH=0)
    inputs(s, PSH=1)
    s.press('S2')
    temperatures(s)
    burners(s, '[C03] scrubber trip while AUTO idle cancelled START', heat=(0, 0))
    start_both(s)
    inputs(s, Rfuel2=1)
    buttons(s, 'S6')
    burners(s, '[C08h] fresh START in diesel: both requesting')
    inputs(s, PSH=0)
    s.expect('[C03/C08h] scrubber trip also stops BR02 diesel', XV401=0, XV403=0,
             **BURNERS_OFF)


def T7d(s):
    """LONG: real 10 min drain limit and RESET, not a DB timer override."""
    inputs(s, LSH=0)
    began = time.monotonic()
    s.expect('[C04/C04a] high level opens drain immediately', XV402=1)
    until(s, began, DRN_MAX - 30)
    s.expect('[C04a] at 9.5 min: drain still open', XV401=1, XV402=1, XV403=1)
    until(s, began, DRN_MAX + 1)
    s.expect('[C04a] after 10 min: drain forced closed', XV401=1, XV402=0, XV403=1)
    inputs(s, LSH=1)
    inputs(s, LSH=0)
    s.expect('[C04a] level cycle cannot clear timeout', XV402=0)
    s.press('S2')
    s.expect('[C04a] fresh S2: drain follows high level again', XV402=1)
    inputs(s, LSH=1)
    s.expect('[C04] healthy level: drain closes immediately', XV402=0)


def T8(s):
    """E-STOP removes energised stage outputs too; recovery S2 then START."""
    start_both(s)
    feedback(s, 1)
    s.wait(STAGE_DELAY + 1)
    burners(s, '[C07c/C08c] both stage outputs and BR02 lamps on before E-STOP', stage=(1, 1))
    inputs(s, S0=0)
    s.expect('[C01] E-STOP removes all nine outputs', **ALL_OFF)
    feedback(s, 0)
    inputs(s, S1=1, S6=1)
    inputs(s, S0=1)
    s.expect('[C01] release without S2: scrubber tripped, burners off', **ALL_OFF)
    s.press('S2')
    s.expect('[C01] S2 restores scrubber; held START ignored',
             XV401=1, XV402=0, XV403=1, **BURNERS_OFF)
    inputs(s, S1=0, S6=0)
    start_both(s)
    burners(s, '[C01/B-01] new START each: heat restored, no stage yet')


def T9(s):
    """OB100 on STOP/RUN: held START/RESET ignored, gas and diesel startup."""
    for diesel in (0, 1):
        inputs(s, Rfuel2=diesel)
        inputs(s, S1=0, S6=0, S2=0)
        start_both(s)
        burners(s, '[C02/C08h] both requesting before restart; diesel=%d' % diesel)
        inputs(s, S1=1, S6=1, S2=1)
        cycle(s)
        s.expect('[C02/S-01/B-01] held START and S2 at startup: tripped and off', **ALL_OFF)
        inputs(s, S2=0)
        s.press('S2')
        s.expect('[C02/S-01] new S2 restores valves; held START still ignored',
                 XV401=1, XV402=0, XV403=1, **BURNERS_OFF)
        inputs(s, S1=0, S6=0)
        start_both(s)
        burners(s, '[C02/B-01/C08h] fresh START after RUN: heat in gas/diesel')


def T10(s):
    """MAN one cycle at SP and after low level, for both burners."""
    inputs(s, S4=0, S5=0)
    start_both(s)
    burners(s, '[B-01/C07b/C08b] MAN START below SP: heat')
    temperatures(s, 700)
    burners(s, '[C07b/C08b, B-01] MAN reaches SP: off', heat=(0, 0))
    buttons(s, 'S1', 'S6')
    temperatures(s, 650)
    burners(s, '[B-01] MAN START at SP refused; cooling cannot restart', heat=(0, 0))
    start_both(s)
    burners(s, '[B-01] MAN fresh START below SP: heat')
    inputs(s, LSL1=0, LSL2=0)
    burners(s, '[C07a/C08a, B-01] MAN low level: requests off', heat=(0, 0))
    inputs(s, LSL1=1, LSL2=1)
    burners(s, '[C07a/C08a, B-01] MAN level recovers: needs START', heat=(0, 0))
    start_both(s)
    burners(s, '[B-01] MAN fresh START after level recovery: heat')


def R01(s):
    """START at low tank level must not create latent permission."""
    inputs(s, LSL1=0, LSL2=0)
    start_both(s)
    inputs(s, LSL1=1, LSL2=1)
    burners(s, '[C07a/C08a, B-01] START with low level refused; recovery stays off', heat=(0, 0))
    start_both(s)
    burners(s, '[C07a/C08a, B-01] new START with healthy level: heat')


def R02(s):
    """AUTO/MAN selector changes apply new rules without stopping heat."""
    start_both(s)
    inputs(s, S4=0, S5=0)
    burners(s, '[B-01; operation section 2] AUTO -> MAN while heating: continues')
    inputs(s, S4=1, S5=1)
    burners(s, '[B-01; operation section 2] MAN -> AUTO while heating: continues')


def R09(s):
    """RUN without request for >30 s is an alarm, not a START inhibit."""
    feedback(s, 1)
    s.wait(32)
    burners(s, '[C07g/C08g] RUN without request >30 s: outputs remain off', heat=(0, 0))
    start_both(s)
    burners(s, '[C07g/C08g] START accepted with unexpected RUN still high (no S2)')
    feedback(s, 0)
    burners(s, '[C07g/C08g] RUN clears: no latched trip (alarm unobserved)')


def BR02(s):
    """BR02 fuel change in both directions and STOP; BR01 unaffected."""
    start_both(s)
    for diesel in (1, 0):
        inputs(s, Rfuel2=diesel)
        burners(s, '[C08h/E3/E4] fuel change: BR02 L/T2/H5/H6 off, BR01 on', heat=(1, 0))
        s.wait(SCAN)
        burners(s, '[C08h] selector stable: BR02 still needs START', heat=(1, 0))
        buttons(s, 'S6')
        burners(s, '[C08h/E3/E4] fresh START on selected fuel: BR02 L/H5 on')
    inputs(s, S7=0)
    burners(s, '[B-01/E3/E4] BR02 NC STOP: all its commands and lamps off', heat=(1, 0))
    inputs(s, S7=1)
    burners(s, '[B-01] BR02 STOP release: remains off', heat=(1, 0))


def T24(s):
    """LONG: real 24 h BR01 daily stop, 60 s RUN-off pause, BR02 exempt."""
    start_both(s)
    feedback(s, 1)
    began = time.monotonic()
    # Check throughout: an early stop cannot hide behind a later restart.
    while time.monotonic() - began < 86400 - 30:
        remaining = 86400 - 30 - (time.monotonic() - began)
        s.wait(min(30, remaining))
        burners(s, '[C07h/C08c] before 24 h: both continuously heating', stage=(1, 1))
    until(s, began, 86402)
    burners(s, '[C07h] after 24 h: BR01 paused, BR02 exempt', heat=(0, 1), stage=(0, 1))
    s.wait(3)
    burners(s, '[C07h] RUN still high: daily pause held', heat=(0, 1), stage=(0, 1))
    paused = time.monotonic()
    inputs(s, RR=0)
    until(s, paused, 58)
    burners(s, '[C07h] RUN off under 60 s: BR01 still paused', heat=(0, 1), stage=(0, 1))
    until(s, paused, 62)
    burners(s, '[C07h] RUN off over 60 s: BR01 AUTO resumes without START', stage=(0, 1))


ALL = [T1, T1b, T2, T3, T5, T6, T6p, T6b, T7, T7b, T7c, T8, T9, T10, R01, R02, R09, BR02]
LONG = [T4, T7d, T24]  # by name only; never shorten timers via DB writes
EN = dict((t.__name__, t.__doc__) for t in ALL + LONG)


def main(args):
    global SCAN
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('scenarios', nargs='*', metavar='NAME',
                        help='selected scenario names; default excludes T4, T7d, T24')
    parser.add_argument('--slow', action='store_true', help='2 s input settling for demonstration')
    parser.add_argument('--list', action='store_true', help='list names without connecting to PLCSIM')
    options = parser.parse_args(args)
    known = dict((t.__name__, t) for t in ALL + LONG)
    unknown = [n for n in options.scenarios if n not in known]
    if unknown:
        parser.error('unknown scenario(s): ' + ', '.join(unknown))
    if options.list:
        for t in ALL + LONG:
            print('%s%s - %s' % (t.__name__, ' [long, by name only]' if t in LONG else '', EN[t.__name__]))
        return 0
    SCAN = 2.0 if options.slow else 0.4
    tests = [known[n] for n in options.scenarios] if options.scenarios else ALL
    print('Precondition: retained Par SP=700, HYST=50, STG=100; CURRENT manager-style download.')
    print('Only %Q is checked; alarm/cause bits and physical safety circuits are not observed.')
    s = None
    failures = 0
    try:
        s = Sim()
        for t in tests:
            print('%s - %s' % (t.__name__, EN[t.__name__]))
            try:
                s.restart()
                t(s)
            except Exception as e:
                s.fails += 1
                print('  FAIL [%s] exception: %s' % (t.__name__, e))
        failures = s.fails
    except (OSError, RuntimeError) as e:
        failures += 1
        print('  FAIL PLCSIM connection: %s' % e)
    except KeyboardInterrupt:
        failures = (s.fails if s else 0) + 1
        print('  FAIL interrupted')
    finally:
        if s is not None:
            s.close()
    print('PASS' if failures == 0 else 'FAIL (%d)' % failures)
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
