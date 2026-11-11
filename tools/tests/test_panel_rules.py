"""Exercise generated LAD expressions; TIA/PLCSIM remains the runtime authority."""
from pathlib import Path
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_blocks as B


def value(token, memory):
    if not isinstance(token, str):
        return token
    if token in memory:
        return memory[token]
    if token.upper() in ('TRUE', 'FALSE'):
        return token.upper() == 'TRUE'
    if token.startswith('T#'):
        scale = {'MS': 1, 'S': 1000, 'M': 60000, 'H': 3600000, 'D': 86400000}
        return sum(int(n) * scale[u] for n, u in re.findall(r'(\d+)(MS|D|H|M|S)', token[2:]))
    return int(token)


def expression(expr, memory):
    if expr is None:
        return True
    if isinstance(expr, str):
        return bool(value(expr, memory))
    op, *args = expr
    if op == '!':
        return not expression(args[0], memory)
    if op in ('&', '|'):
        vals = [expression(a, memory) for a in args]
        return all(vals) if op == '&' else any(vals)
    if op in ('Eq', 'Ne', 'Lt', 'Le', 'Gt', 'Ge'):
        a, b = value(args[1], memory), value(args[2], memory)
        return {'Eq': a == b, 'Ne': a != b, 'Lt': a < b, 'Le': a <= b,
                'Gt': a > b, 'Ge': a >= b}[op]
    raise AssertionError('Unsupported rule expression: %r' % (expr,))


def rules(make):
    with patch.object(B, 'rung', lambda title, expr, *outs: (title, expr, outs)), \
            patch.object(B, 'code_block', lambda tag, name, number, iface, nets, **kw: nets):
        return make()


def val(token, m):
    """Operand value; a symbol that was never written reads FALSE / 0 like a fresh DB."""
    if isinstance(token, str) and (token.startswith('#') or token.startswith('"')):
        return m.get(token, False)
    return value(token, m)


def power(expr, m, src=True):
    """Power flow through a rung expression. A TON passes power when its IN has
    power and the test has marked that timer as elapsed: m['elapsed'] = {'#T_x'}."""
    if expr is None:
        return src
    if isinstance(expr, str):
        return src and bool(val(expr, m))
    op, *args = expr
    if op == '!':
        return src and not bool(val(args[0], m)) if isinstance(args[0], str) \
            else src and not power(args[0], m)
    if op == '&':
        for sub in args:
            src = power(sub, m, src)
        return src
    if op == '|':
        return any(power(sub, m, src) for sub in args)
    if op in ('Eq', 'Ne', 'Lt', 'Le', 'Gt', 'Ge'):
        a, b = val(args[1], m), val(args[2], m)
        return src and {'Eq': a == b, 'Ne': a != b, 'Lt': a < b, 'Le': a <= b,
                        'Gt': a > b, 'Ge': a >= b}[op]
    if op == 'TON':
        return src and args[0] in m.get('elapsed', set())
    raise AssertionError('Unsupported rule expression: %r' % (expr,))


def scan(make, m, prefix=''):
    """One scan of a block. prefix turns '#X' into '"BR01_DB".X' style names."""
    def name(op):
        return prefix + op[1:] if prefix and op.startswith('#') else op

    def ren(e):
        if isinstance(e, str):
            return name(e)
        if isinstance(e, tuple) and e and e[0] == 'TON':
            return ('TON', name(e[1]), e[2])
        if isinstance(e, tuple):
            return (e[0],) + tuple(ren(x) for x in e[1:])
        return e
    for title, expr, outputs in rules(make):
        active = power(ren(expr), m)
        for op, *args in outputs:
            args = [ren(x) for x in args]
            if op == '=':
                m[args[0]] = active
            elif op == 'S' and active:
                m[args[0]] = True
            elif op == 'R' and active:
                m[args[0]] = False
            elif op == 'MOVE' and active:
                m[args[1]] = val(args[0], m)
            elif op in ('SUB', 'ADD') and active:
                a, b = val(args[1], m), val(args[2], m)
                m[args[3]] = a - b if op == 'SUB' else a + b
            elif op not in ('S', 'R', 'MOVE', 'SUB', 'ADD'):
                raise AssertionError('Unsupported rule output: %r' % (op,))


def plant():
    """Healthy panel, both burners stopped, tanks cold (50.0 degC), AUTO."""
    m = {'"S0_EStopStatus"': True, '"Sys".EStopOK': True, 'elapsed': set()}
    for n, typ, default, low, high, comment in B.PARAMS:
        m['"Par".' + n] = value(default, {})
    m.update({'#PSH': True, '#LSH': True, '#LSHH': True})
    for br in ('BR01', 'BR02'):
        p = '"%s_DB".' % br
        m.update({p + 'Auto': True, p + 'StopOK': True, p + 'LevelOK': True,
                  p + 'TeA': 500, p + 'TeB': 500})
    return m


def burner(m, br='BR01', n=1):
    for _ in range(n):
        scan(B.burner_fb, m, '"%s_DB".' % br)


def press_start(m, br='BR01'):
    m['"%s_DB".StartPB' % br] = True
    burner(m, br)
    m['"%s_DB".StartPB' % br] = False
    burner(m, br)


class CommonRules(unittest.TestCase):
    def test_settings_are_kept_inside_their_range(self):
        for n, typ, default, low, high, comment in B.PARAMS:
            for entry, expected in [(int(low) - 1, int(low)), (int(high) + 1, int(high)),
                                    (int(default), int(default))]:
                with self.subTest(parameter=n, entry=entry):
                    m = plant()
                    m['"Par".' + n] = entry
                    scan(B.common_fc, m)
                    self.assertEqual(m['"Par".' + n], expected)

    def test_estop_needs_release_and_reset(self):
        m = plant()
        m['"S0_EStopStatus"'] = False
        scan(B.common_fc, m)
        self.assertFalse(m['"Sys".EStopOK'])
        m['"S0_EStopStatus"'] = True
        scan(B.common_fc, m)
        self.assertFalse(m['"Sys".EStopOK'])
        m['"S2_FaultReset"'] = True
        scan(B.common_fc, m)
        self.assertTrue(m['"Sys".EStopOK'])


class ScrubberRules(unittest.TestCase):
    def test_drain_follows_the_level_without_delay(self):
        m = plant()
        m['#LSH'] = False
        scan(B.scrubber_fb, m)
        self.assertTrue(m['#DrainCmd'])
        m['#LSH'] = True
        scan(B.scrubber_fb, m)
        self.assertFalse(m['#DrainCmd'])

    def test_drain_time_limit_closes_and_reset_reopens(self):
        m = plant()
        m['#LSH'] = False
        scan(B.scrubber_fb, m)
        m['elapsed'] = {'#T_DrnMax'}
        scan(B.scrubber_fb, m)
        m['elapsed'] = set()
        scan(B.scrubber_fb, m)
        self.assertFalse(m['#DrainCmd'])
        m['#Reset'] = True
        scan(B.scrubber_fb, m)
        m['#Reset'] = False
        scan(B.scrubber_fb, m)
        self.assertTrue(m['#DrainCmd'])

    def test_pressure_trip_keeps_its_cause_until_reset(self):
        m = plant()
        m['#PSH'] = False
        scan(B.scrubber_fb, m)
        m['#PSH'] = True
        scan(B.scrubber_fb, m)
        self.assertFalse(m['#FlareCmd'])      # flare open
        self.assertFalse(m['#SuctionCmd'])    # suction closed
        self.assertTrue(m['#Cause_PSH'])
        m['#Reset'] = True
        scan(B.scrubber_fb, m)
        self.assertTrue(m['#FlareCmd'] and m['#SuctionCmd'])
        self.assertFalse(m['#Cause_PSH'])

    def test_very_high_level_trips_suction_not_flare_and_opens_drain(self):
        m = plant()
        m['#LSHH'] = False
        scan(B.scrubber_fb, m)
        self.assertTrue(m['#FlareCmd'])
        self.assertFalse(m['#SuctionCmd'])
        self.assertTrue(m['#DrainCmd'])

    def test_power_up_trips_until_reset(self):
        m = plant()
        m['"Sys".FirstScan'] = True
        scan(B.scrubber_fb, m)
        m['"Sys".FirstScan'] = False
        scan(B.scrubber_fb, m)
        self.assertFalse(m['#SuctionCmd'])
        self.assertFalse(m['#FlareCmd'])


class BurnerRules(unittest.TestCase):
    P = '"BR01_DB".'

    def test_start_gives_heat_request_and_stop_removes_it(self):
        m = plant()
        burner(m)
        self.assertFalse(m[self.P + 'HeatReq'])
        press_start(m)
        self.assertTrue(m[self.P + 'HeatReq'])
        m[self.P + 'StopOK'] = False
        burner(m)
        self.assertFalse(m[self.P + 'HeatReq'])

    def test_every_trip_needs_a_new_start(self):
        trips = {'lockout': (self.P + 'Lockout', True),
                 'scrubber': ('"Scrubber_DB".Tripped', True),
                 'estop': ('"Sys".EStopOK', False),
                 'fuel': (self.P + 'Fuel', True)}
        for label, (key, bad) in trips.items():
            with self.subTest(trip=label):
                m = plant()
                press_start(m)
                good = m.get(key, False)
                m[key] = bad
                burner(m)
                self.assertFalse(m[self.P + 'HeatReq'])
                if label != 'fuel':
                    m[key] = good
                burner(m, n=2)
                self.assertFalse(m[self.P + 'HeatReq'], 'restarted without START')
                press_start(m)
                self.assertTrue(m[self.P + 'HeatReq'])

    def test_thermocouple_fault_after_10_s(self):
        m = plant()
        press_start(m)
        m[self.P + 'TeA'] = 32767
        burner(m)
        self.assertFalse(m[self.P + 'HeatReq'])       # no valid temperature: no heat
        self.assertFalse(m[self.P + 'TcBad'])
        m['elapsed'] = {self.P + 'T_TcBad'}
        burner(m)
        self.assertTrue(m[self.P + 'TcBad'])
        self.assertFalse(m[self.P + 'StartEnabled'])

    def test_stage2_waits_for_run_and_its_timer_and_stops_at_62(self):
        m = plant()
        press_start(m)
        m[self.P + 'RunFb'] = True
        burner(m)
        self.assertFalse(m[self.P + 'Stage2'])
        m['elapsed'] = {self.P + 'T_Stage2'}
        burner(m)
        self.assertTrue(m[self.P + 'Stage2'])
        m[self.P + 'TeA'] = 610
        burner(m)
        self.assertTrue(m[self.P + 'Stage2'])
        m[self.P + 'TeA'] = 620
        burner(m)
        self.assertFalse(m[self.P + 'Stage2'])

    def test_auto_hysteresis_stops_at_sp_and_restarts_at_sp_minus_hyst(self):
        m = plant()
        press_start(m)
        m[self.P + 'TeA'] = m[self.P + 'TeB'] = 700
        burner(m)
        self.assertFalse(m[self.P + 'HeatReq'])
        self.assertTrue(m[self.P + 'StartEnabled'])
        m[self.P + 'TeA'] = m[self.P + 'TeB'] = 660
        burner(m)
        self.assertFalse(m[self.P + 'HeatReq'])
        m[self.P + 'TeA'] = m[self.P + 'TeB'] = 650
        burner(m)
        self.assertTrue(m[self.P + 'HeatReq'])

    def test_man_runs_one_cycle(self):
        m = plant()
        m[self.P + 'Auto'] = False
        press_start(m)
        self.assertTrue(m[self.P + 'HeatReq'])
        m[self.P + 'TeA'] = m[self.P + 'TeB'] = 700
        burner(m)
        self.assertFalse(m[self.P + 'StartEnabled'])
        m[self.P + 'TeA'] = m[self.P + 'TeB'] = 500
        burner(m, n=2)
        self.assertFalse(m[self.P + 'HeatReq'])

    def test_low_tank_level_waits_in_auto(self):
        m = plant()
        press_start(m)
        m[self.P + 'LevelOK'] = False
        burner(m)
        self.assertFalse(m[self.P + 'HeatReq'])
        m[self.P + 'LevelOK'] = True
        burner(m)
        self.assertTrue(m[self.P + 'HeatReq'])

    def test_run_alarms_are_alarms_only(self):
        m = plant()
        press_start(m)
        m['elapsed'] = {self.P + 'T_NoRun'}
        burner(m)
        self.assertTrue(m[self.P + 'NoRun'])
        self.assertTrue(m[self.P + 'HeatReq'])


class HmiContracts(unittest.TestCase):
    def test_v15_fields_do_not_create_duplicate_info_text_entries(self):
        # Seven generated nonempty IOField HelpTexts produced six V15.1
        # duplicate-entry-order compile errors. Keep source descriptions on
        # the tags and the visible ranges, outside this unsupported import path.
        import build_hmi as H
        for screen in [H.burner('BR01'), H.burner('BR02'), H.settings()]:
            for field in ET.fromstring(screen.xml()).iter('Hmi.Screen.IOField'):
                for text in field.findall('./ObjectList/MultilingualText'):
                    if text.get('CompositionName') == 'HelpText':
                        value = text.find('.//AttributeList/Text')
                        self.assertFalse(''.join(value.itertext()).strip())

    def test_bindings_and_object_names_are_complete(self):
        import build_hmi as H
        names = {name for name, db, member in H.TAGS}
        self.assertEqual(len(names), 58)
        for screen in [H.overview(), H.burner('BR01'), H.burner('BR02'), H.scrubber(), H.settings(), H.alarms()]:
            root = ET.fromstring(screen.xml())
            objects = root.findall('.//ObjectName')
            object_names = [n.text for n in objects]
            self.assertEqual(len(object_names), len(set(object_names)), screen.name)
            self.assertFalse(any(re.match(r'^(Text|IOField|Circle|Rectangle|Button)_\d+$', n) for n in object_names))
            for name in root.findall('.//LinkList/Tag/Name'):
                self.assertIn(name.text, names, screen.name)
        self.assertEqual(H.WRITABLE, {'Par_' + p[0] for p in B.PARAMS})

    def test_operator_lamps_distinguish_healthy_inputs_from_commands(self):
        import build_hmi as H
        def lamps(screen):
            result = {}
            for obj in ET.fromstring(screen.xml()).iter('Hmi.Screen.Circle'):
                animation = obj.find('./ObjectList/Hmi.Dynamic.RangeAppearanceAnimation')
                if animation is None:
                    continue  # A drawing circle is not an input/output indicator.
                tag = animation.findtext('.//LinkList/Tag/Name')
                result[tag] = {int(r.findtext('./AttributeList/LowerLimit')):
                               r.findtext('./AttributeList/BackColor')
                               for r in animation.findall('./ObjectList/Hmi.Dynamic.Range')}
            return result
        for br in ['BR01', 'BR02']:
            colors = lamps(H.burner(br))
            for suffix in ['_LevelOK', '_TcOkA', '_TcOkB']:
                self.assertEqual(colors[br + suffix], {0: H.RED, 1: H.GREEN})
            for suffix in ['_RunFb', '_HeatReq', '_Stage2']:
                self.assertEqual(colors[br + suffix], {0: H.GREY, 1: H.GREEN})
            self.assertEqual(colors[br + '_Lockout'], {0: H.GREY, 1: H.RED})
        colors = lamps(H.scrubber())
        for tag in ['Scrub_PSH', 'Scrub_LSHH']:
            self.assertEqual(colors[tag], {0: H.RED, 1: H.GREEN})
        self.assertEqual(colors['Scrub_LSH'], {0: H.AMBER, 1: H.GREEN})
        for tag in ['Scrub_FlareCmd', 'Scrub_DrainCmd', 'Scrub_SuctionCmd']:
            self.assertEqual(colors[tag], {0: H.GREY, 1: H.GREEN})

    def test_alarm_words_are_continuous_and_ids_are_stable(self):
        import build_hmi as H
        import build_alarms as A
        root = ET.fromstring(H.tag_table())
        for item in root.findall('.//Hmi.Tag.Tag'):
            name = item.findtext('./AttributeList/Name')
            expected = 'Continuous' if name.startswith('Alm_') else 'Visible'
            self.assertEqual(item.findtext('./AttributeList/AcquisitionTriggerMode'), expected)
        expected_ids = {('Common', n): 1 + n for n in range(6)}
        expected_ids.update({('BR01', n): 7 + n for n in range(5)})
        expected_ids.update({('BR02', n): 12 + n for n in range(5)})
        self.assertEqual({(w, b): A.alarm_id(w, b) for w, b, *_ in B.HMI_ALARMS}, expected_ids)


if __name__ == '__main__':
    unittest.main()
