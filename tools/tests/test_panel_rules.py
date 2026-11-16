"""Exercise generated LAD expressions; TIA/PLCSIM remains the runtime authority."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
from functools import wraps
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
    """Flatten topic networks in rung order; preserve parallel output order."""
    def topic(title, rungs):
        return [(title, expr, tuple(outs)) for expr, *outs in rungs]
    def block_call(title, name, typ, instance=None, params=()):
        return title, ('CALL', name, instance, params), ()
    with patch.object(B, 'network', topic), \
            patch.object(B, 'call', block_call), \
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
        m.setdefault('timer_inputs', {})[args[0]] = src
        return src and args[0] in m.get('elapsed', set())
    raise AssertionError('Unsupported rule expression: %r' % (expr,))


def scan_rules(make, m, prefix=''):
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
        if isinstance(expr, tuple) and expr[0] == 'CALL':
            _, block, instance, params = expr
            prefix_call = '"%s".' % instance
            for n, section, typ, operand in params:
                if section == 'Input':
                    m[prefix_call + n] = val(operand, m)
            scan_rules(B.scrubber_fb if block == 'Scrubber' else B.burner_fb, m, prefix_call)
            for n, section, typ, operand in params:
                if section == 'Output':
                    m[operand] = m[prefix_call + n]
            continue
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
    m = {'"S0_EStopStatus"': True, '#EStopOK': True, 'elapsed': set()}
    for n, typ, default, low, high, comment in B.PARAMS:
        m['"Par".' + n] = value(default, {})
    m.update({'#PSH': True, '#LSH': True, '#LSHH': True})
    for br in ('BR01', 'BR02'):
        p = '"%s_DB".' % br
        m.update({p + 'Auto': True, p + 'StopOK': True, p + 'LevelOK': True,
                  p + 'TeA': 500, p + 'TeB': 500, p + 'EStopOK': True,
                  p + 'SP': 700, p + 'HYST': 50, p + 'STG': 100, p + 'Use24h': br == 'BR01'})
    return m


def burner(m, br='BR01', n=1):
    for _ in range(n):
        p = '"%s_DB".' % br
        m[p + 'EStopOK'] = m['"S0_EStopStatus"']
        m[p + 'ScrubTrip'] = m.get('"Scrubber_DB".Tripped', False)
        scan(B.burner_fb, m, p)


def press_start(m, br='BR01'):
    m['"%s_DB".StartPB' % br] = True
    burner(m, br)
    m['"%s_DB".StartPB' % br] = False
    burner(m, br)


def xml_operand(access, prefix=''):
    """Decode actual Access XML, including a Word slice on its owning member."""
    if access.get('Scope') in ('LiteralConstant', 'TypedConstant'):
        return access.findtext('./{*}Constant/{*}ConstantValue')
    components = access.findall('./{*}Symbol/{*}Component')
    names = [c.get('Name') for c in components]
    if access.get('Scope') == 'LocalVariable':
        result = (prefix or '#') + '.'.join(names)
    else:
        result = '"%s"' % names[0] + ''.join('.' + n for n in names[1:])
    for i, component in enumerate(components):
        if component.get('SliceAccessModifier'):
            if i != len(components) - 1:
                raise AssertionError('slice must be on final member')
            result += '.%' + component.get('SliceAccessModifier').upper()
    return result


def scan_xml(make, m, prefix=''):
    """Execute the emitted graph in Part order, independently of the rung DSL.

    This is a local test model, not a substitute for TIA import or PLCSIM.
    Timer expiry is injected; timer IN is still evaluated from actual wiring.
    """
    root = ET.fromstring(make())
    for net in root.findall('.//{*}FlgNet'):
        accesses = {a.get('UId'): xml_operand(a, prefix)
                    for a in net.findall('./{*}Parts/{*}Access')}
        sources, destinations = {}, {}
        for wire in net.findall('./{*}Wires/{*}Wire'):
            source, *sinks = list(wire)
            for sink in sinks:
                sources[(sink.tag.split('}')[-1], sink.get('UId'), sink.get('Name'))] = source
            if source.tag.endswith('NameCon'):
                destinations[(source.get('UId'), source.get('Name'))] = sinks
        signals = {}

        def read(source):
            if source.tag.endswith('Powerrail'):
                return True
            if source.tag.endswith('IdentCon'):
                return val(accesses[source.get('UId')], m)
            return signals[(source.get('UId'), source.get('Name'))]

        def pin(uid, name):
            return read(sources[('NameCon', uid, name)])

        def write(uid, name, result, enabled=True):
            signals[(uid, name)] = result
            if enabled:
                for sink in destinations.get((uid, name), []):
                    if sink.tag.endswith('IdentCon'):
                        m[accesses[sink.get('UId')]] = result

        for part in net.find('{*}Parts'):
            kind, uid = part.get('Name'), part.get('UId')
            if part.tag.endswith('Access'):
                continue
            if part.tag.endswith('Call'):
                info = part.find('{*}CallInfo')
                instance = info.find('./{*}Instance/{*}Component').get('Name')
                local = '"%s".' % instance
                for param in info.findall('{*}Parameter'):
                    if param.get('Section') == 'Input':
                        m[local + param.get('Name')] = pin(uid, param.get('Name'))
                scan_xml(B.scrubber_fb if info.get('Name') == 'Scrubber' else B.burner_fb, m, local)
                for param in info.findall('{*}Parameter'):
                    if param.get('Section') == 'Output':
                        write(uid, param.get('Name'), m[local + param.get('Name')])
            elif kind == 'Contact':
                operand = bool(pin(uid, 'operand'))
                if part.find('{*}Negated') is not None:
                    operand = not operand
                signals[(uid, 'out')] = bool(pin(uid, 'in')) and operand
            elif kind == 'O':
                card = int(part.findtext('{*}TemplateValue'))
                signals[(uid, 'out')] = any(pin(uid, 'in%d' % i) for i in range(1, card + 1))
            elif kind in ('Coil', 'SCoil', 'RCoil'):
                active = bool(pin(uid, 'in'))
                write(uid, 'operand', active if kind == 'Coil' else kind == 'SCoil',
                      kind == 'Coil' or active)
            elif kind in B.CMPS:
                a, b = pin(uid, 'in1'), pin(uid, 'in2')
                signals[(uid, 'out')] = bool(pin(uid, 'pre')) and {
                    'Eq': a == b, 'Ne': a != b, 'Lt': a < b, 'Le': a <= b,
                    'Gt': a > b, 'Ge': a >= b}[kind]
            elif kind == 'TON':
                timer = (prefix or '#') + part.find('./{*}Instance/{*}Component').get('Name')
                m.setdefault('timer_inputs', {})[timer] = bool(pin(uid, 'IN'))
                signals[(uid, 'Q')] = bool(pin(uid, 'IN')) and timer in m.get('elapsed', set())
            elif kind == 'Move':
                write(uid, 'out1', pin(uid, 'in'), bool(pin(uid, 'en')))
            elif kind in ('Sub', 'Add'):
                a, b = pin(uid, 'in1'), pin(uid, 'in2')
                write(uid, 'out', a - b if kind == 'Sub' else a + b, bool(pin(uid, 'en')))
            else:
                raise AssertionError('Unmodelled XML instruction: ' + str(kind))


def physical_plant():
    m = plant()
    # Main's real physical inputs, obtained from the instance-test defaults.
    for n, _ in B.SCRUB_IN:
        if n in ('PSH', 'LSH', 'LSHH'):
            m['"%s_%s"' % (n, {'PSH': '101', 'LSH': '102', 'LSHH': '103'}[n])] = True
    for br in ('BR01', 'BR02'):
        for n, section, typ, operand in B.burner_params(br):
            if section == 'Input' and re.fullmatch(r'"[^"]+"', operand):
                m[operand] = m.get('"%s_DB".%s' % (br, n), False)
    return m


def scan(make, m, prefix=''):
    """Check each behavior scan against both the DSL and emitted XML graph."""
    expected = deepcopy(m)
    scan_rules(make, expected, prefix)
    scan_xml(make, m, prefix)
    if m != expected:
        diff = {k: (expected.get(k), m.get(k)) for k in expected.keys() | m.keys()
                if expected.get(k) != m.get(k)}
        raise AssertionError('Generated XML differs from ordered rungs: %r' % diff)


class CommonRules(unittest.TestCase):
    def test_settings_are_kept_inside_their_range(self):
        for n, typ, default, low, high, comment in B.PARAMS:
            for entry, expected in [(int(low) - 1, int(low)), (int(high) + 1, int(high)),
                                    (int(default), int(default))]:
                with self.subTest(parameter=n, entry=entry):
                    m = plant()
                    m['"Par".' + n] = entry
                    scan(B.main_ob, m)
                    self.assertEqual(m['"Par".' + n], expected)



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
        m['#ResetPB'] = True
        scan(B.scrubber_fb, m)
        m['#ResetPB'] = False
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
        m['#ResetPB'] = True
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
        scan(B.startup_ob, m)
        for member in ('Tripped', 'FlareTrip', 'ResetMem'):
            m['#' + member] = m['"Scrubber_DB".' + member]
        scan(B.scrubber_fb, m)
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
                 'estop': ('"S0_EStopStatus"', False),
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


class ManagerRules(unittest.TestCase):
    S = '"Scrubber_DB".'
    P = '"BR01_DB".'

    def test_estop_drain_closes_only_while_pressed_and_trip_stays_after_release(self):
        m = physical_plant()
        m['"LSH_102"'] = False
        scan(B.main_ob, m)
        self.assertTrue(m['"XV_402_Cmd"'])
        m['"S0_EStopStatus"'] = False
        scan(B.main_ob, m)
        self.assertFalse(m['"XV_402_Cmd"'])
        self.assertTrue(m[self.S + 'Alarms.%X0'])
        m['"S0_EStopStatus"'] = True
        scan(B.main_ob, m)
        self.assertTrue(m['"XV_402_Cmd"'])
        self.assertFalse(m[self.S + 'Alarms.%X0'])
        self.assertTrue(m[self.S + 'Tripped'])
        self.assertFalse(m['"XV_401_Cmd"'])
        self.assertFalse(m['"XV_403_Cmd"'])

    def test_startup_and_stop_to_run_ignore_held_buttons(self):
        for warm in (False, True):
            with self.subTest(stop_to_run=warm):
                m = physical_plant()
                if warm:
                    for start in ('"S1_BR01_Start"', '"S6_BR02_Start"'):
                        m[start] = True
                    scan(B.main_ob, m)
                    self.assertTrue(m['"BR01_TL_Cmd"'] and m['"BR02_L_Cmd"'])
                m['"S2_FaultReset"'] = True
                m['"S1_BR01_Start"'] = m['"S6_BR02_Start"'] = True
                scan(B.startup_ob, m)
                for key in (self.S + 'Tripped', self.S + 'FlareTrip', self.S + 'ResetMem',
                            '"BR01_DB".StartMem', '"BR02_DB".StartMem'):
                    self.assertTrue(m[key])
                scan(B.main_ob, m)
                self.assertFalse(m[self.S + 'ResetPulse'])
                self.assertTrue(m[self.S + 'Tripped'])
                self.assertFalse(m['"BR01_TL_Cmd"'] or m['"BR02_L_Cmd"'])
                # Release and re-press RESET. Held START must still be ignored.
                m['"S2_FaultReset"'] = False
                scan(B.main_ob, m)
                m['"S2_FaultReset"'] = True
                scan(B.main_ob, m)
                self.assertFalse(m[self.S + 'Tripped'])
                self.assertFalse(m['"BR01_TL_Cmd"'] or m['"BR02_L_Cmd"'])
                m['"S1_BR01_Start"'] = m['"S6_BR02_Start"'] = False
                scan(B.main_ob, m)
                m['"S1_BR01_Start"'] = m['"S6_BR02_Start"'] = True
                scan(B.main_ob, m)
                self.assertTrue(m['"BR01_TL_Cmd"'] and m['"BR02_L_Cmd"'])

    def test_br02_power_up_in_diesel_keeps_one_scan_fuel_change(self):
        m = physical_plant()
        m['"Rfuel2_BR02_DieselMode"'] = True
        scan(B.startup_ob, m)
        self.assertFalse(m.get('"BR02_DB".FuelMem', False))
        scan(B.main_ob, m)
        self.assertTrue(m['"BR02_DB".FuelChg'])
        self.assertTrue(m['"BR02_DB".Trip'])
        self.assertTrue(m['"BR02_DB".FuelMem'])
        scan(B.main_ob, m)
        self.assertFalse(m['"BR02_DB".FuelChg'])

    def test_reset_with_present_trip_cause_cannot_clear_or_queue_reset(self):
        for cause in ('#PSH', '#LSHH', '#EStopOK'):
            with self.subTest(cause=cause):
                m = plant()
                m[cause] = False
                m['#ResetPB'] = True
                scan(B.scrubber_fb, m)
                self.assertTrue(m['#Tripped'])
                m[cause] = True
                scan(B.scrubber_fb, m)
                self.assertTrue(m['#Tripped'], 'held RESET must not queue recovery')
                m['#ResetPB'] = False
                scan(B.scrubber_fb, m)
                m['#ResetPB'] = True
                scan(B.scrubber_fb, m)
                self.assertFalse(m['#Tripped'])

    def test_start_while_trip_present_is_not_queued(self):
        for member, bad in [('Lockout', True), ('EStopOK', False), ('ScrubTrip', True)]:
            with self.subTest(cause=member):
                m = plant()
                p = self.P
                m[p + member] = bad
                m[p + 'StartPB'] = True
                scan(B.burner_fb, m, p)
                self.assertFalse(m[p + 'HeatReq'])
                self.assertFalse(m[p + 'StartEnabled'])
                m[p + member] = not bad
                scan(B.burner_fb, m, p)
                self.assertFalse(m[p + 'StartEnabled'])
                m[p + 'StartPB'] = False
                scan(B.burner_fb, m, p)
                m[p + 'StartPB'] = True
                scan(B.burner_fb, m, p)
                self.assertTrue(m[p + 'HeatReq'])

    def test_trip_removes_all_burner_requests_and_lamps_in_same_scan(self):
        for cause, bad in [('"S0_EStopStatus"', False), ('"PSH_101"', False)]:
            with self.subTest(cause=cause):
                m = physical_plant()
                m['"S1_BR01_Start"'] = m['"S6_BR02_Start"'] = True
                m['"BR01_Run"'] = m['"BR02_Run"'] = True
                m['elapsed'] = {'"BR01_DB".T_Stage2', '"BR02_DB".T_Stage2'}
                scan(B.main_ob, m)
                outputs = ['BR01_TL_Cmd', 'BR01_TR_Cmd', 'BR02_L_Cmd', 'BR02_T2_Cmd',
                           'BR02_Stage1Lamp_Cmd', 'BR02_Stage2Lamp_Cmd']
                self.assertTrue(all(m['"%s"' % n] for n in outputs))
                m[cause] = bad
                scan(B.main_ob, m)
                self.assertTrue(all(not m['"%s"' % n] for n in outputs))
                self.assertFalse(m['"BR01_DB".StartEnabled'] or m['"BR02_DB".StartEnabled'])

    def test_br02_lamps_follow_final_l_and_t2(self):
        m = physical_plant()
        changes = [ {'"S6_BR02_Start"': True}, {'"BR02_Run"': True},
                    {'elapsed': {'"BR02_DB".T_Stage2'}}, {'"TE_503_Raw"': 620},
                    {'"TE_503_Raw"': 700}, {'"S7_BR02_Stop"': False} ]
        states = []
        for change in changes:
            m.update(change)
            scan(B.main_ob, m)
            self.assertEqual(m['"BR02_L_Cmd"'], m['"BR02_Stage1Lamp_Cmd"'])
            self.assertEqual(m['"BR02_T2_Cmd"'], m['"BR02_Stage2Lamp_Cmd"'])
            states.append((m['"BR02_L_Cmd"'], m['"BR02_T2_Cmd"']))
        self.assertEqual(states, [(True, False), (True, False), (True, True),
                                  (True, False), (False, False), (False, False)])

    def test_drain_timeout_scan_delay_and_reset_priority(self):
        m = plant()
        m['#LSH'] = False
        m['elapsed'] = {'#T_DrnMax'}
        scan(B.scrubber_fb, m)
        self.assertTrue(m['#F_DrainTO'])
        self.assertTrue(m['#DrainCmd'], 'timeout closes drain on the next scan')
        m['#ResetPB'] = True
        scan(B.scrubber_fb, m)
        self.assertFalse(m['#F_DrainTO'])
        self.assertFalse(m['#DrainCmd'], 'RESET reopens drain on the next scan')
        m['elapsed'] = set()
        scan(B.scrubber_fb, m)
        self.assertTrue(m['#DrainCmd'])
        # Simultaneous timer expiry and RESET: RESET is the later rung.
        m['#ResetPB'] = False
        scan(B.scrubber_fb, m)
        m['#ResetPB'] = True
        m['elapsed'] = {'#T_DrnMax'}
        scan(B.scrubber_fb, m)
        self.assertFalse(m['#F_DrainTO'])

    def test_daily_stop_reads_previous_request_and_reset_wins(self):
        m = plant()
        m[self.P + 'StartPB'] = True
        m['elapsed'] = {self.P + 'T_24h'}
        burner(m)
        self.assertFalse(m['timer_inputs'][self.P + 'T_24h'])
        self.assertTrue(m[self.P + 'HeatReq'])
        burner(m)
        self.assertTrue(m['timer_inputs'][self.P + 'T_24h'])
        self.assertTrue(m[self.P + 'Pause24'])
        self.assertFalse(m[self.P + 'HeatReq'])
        m['elapsed'] = {self.P + 'T_Pause'}
        burner(m)
        self.assertFalse(m[self.P + 'Pause24'])
        self.assertTrue(m[self.P + 'HeatReq'])
        m['elapsed'] = {self.P + 'T_24h', self.P + 'T_Pause'}
        burner(m)
        self.assertFalse(m[self.P + 'Pause24'], '60 s RESET wins over 24 h SET')
        other = physical_plant()
        other['"S6_BR02_Start"'] = True
        other['elapsed'] = {'"BR02_DB".T_24h'}
        scan(B.main_ob, other)
        scan(B.main_ob, other)
        self.assertFalse(other.get('"BR02_DB".Pause24', False))
        self.assertTrue(other['"BR02_L_Cmd"'])

    def test_run_without_request_is_alarm_only_and_clears(self):
        m = plant()
        m[self.P + 'RunFb'] = True
        m['elapsed'] = {self.P + 'T_RunWrong'}
        burner(m)
        self.assertTrue(m[self.P + 'RunWrong'])
        self.assertFalse(m[self.P + 'Trip'])
        press_start(m)
        self.assertTrue(m[self.P + 'HeatReq'])
        self.assertFalse(m[self.P + 'RunWrong'])


class XmlContracts(unittest.TestCase):
    def test_block_set_counts_single_flgnet_and_one_shared_rail(self):
        expected = {'Par': 0, 'Burner': 9, 'Scrubber': 5, 'BR01_DB': 0,
                    'BR02_DB': 0, 'Scrubber_DB': 0, 'Startup': 1, 'Main': 4}
        if not B.MULTI_RUNG:
            expected.update(Burner=32, Scrubber=18, Main=9)
        self.assertEqual({Path(n).stem for n, _ in B.BLOCKS}, set(expected))
        total = 0
        for filename, make in B.BLOCKS:
            root = ET.fromstring(make())
            units = root.findall('.//SW.Blocks.CompileUnit')
            self.assertEqual(len(units), expected[Path(filename).stem], filename)
            total += len(units)
            ids = [n.get('ID') for n in root.iter() if n.get('ID') is not None]
            self.assertEqual(len(ids), len(set(ids)), filename)
            for unit in units:
                nets = unit.findall('./AttributeList/NetworkSource/{*}FlgNet')
                self.assertEqual(len(nets), 1)
                net = nets[0]
                self.assertEqual(len(net.findall('.//{*}Powerrail')), 1)
                uids = [n.get('UId') for n in net.iter()
                        if n.tag.split('}')[-1] in ('Access', 'Part', 'Call', 'Instance', 'Wire', 'OpenCon')]
                self.assertEqual(len(uids), len(set(uids)))
                parts = list(net.find('{*}Parts'))
                kinds = [p.tag.split('}')[-1] for p in parts]
                if 'Access' in kinds:
                    self.assertTrue(all(k == 'Access' for k in kinds[:kinds.count('Access')]))
                sources = [ET.tostring(list(w)[0]) for w in net.findall('./{*}Wires/{*}Wire')]
                self.assertEqual(len(sources), len(set(sources)))
                texts = {t.get('CompositionName'): t.findtext('.//Text')
                         for t in unit.findall('./ObjectList/MultilingualText')}
                self.assertTrue(texts['Comment'])
                if not B.MULTI_RUNG and Path(filename).stem != 'Main':
                    self.assertRegex(texts['Title'], r' \(\d+/\d+\)$')
        self.assertEqual(total, 19 if B.MULTI_RUNG else 60)

    def test_physical_outputs_written_once_only_by_main_call_pins(self):
        io = ET.parse(Path(B.ROOT) / 'build/tags/IO.xml')
        physical_q = {t.findtext('./AttributeList/Name') for t in io.findall('.//SW.Tags.PlcTag')
                      if t.findtext('./AttributeList/LogicalAddress', '').startswith('%Q')}
        writes = []
        for filename, make in B.BLOCKS:
            root = ET.fromstring(make())
            for net in root.findall('.//{*}FlgNet'):
                accesses = {a.get('UId'): xml_operand(a) for a in net.findall('./{*}Parts/{*}Access')}
                calls = {c.get('UId'): c for c in net.findall('./{*}Parts/{*}Call')}
                for wire in net.findall('./{*}Wires/{*}Wire'):
                    source, *sinks = list(wire)
                    for sink in sinks:
                        operand = accesses.get(sink.get('UId'), '') if sink.tag.endswith('IdentCon') else ''
                        if operand.strip('"') not in physical_q:
                            continue
                        writes.append(operand.strip('"'))
                        self.assertEqual(filename, 'Main.xml')
                        call = calls[source.get('UId')]
                        param = call.find('./{*}CallInfo/{*}Parameter[@Name="%s"]' % source.get('Name'))
                        self.assertEqual(param.get('Section'), 'Output')
        self.assertEqual(len(physical_q), 9, 'Q inventory must come from the actual IO table')
        self.assertEqual(Counter(writes), Counter({q: 1 for q in physical_q}))

    def test_every_physical_input_is_visible_on_main_calls(self):
        io = ET.parse(Path(B.ROOT) / 'build/tags/IO.xml')
        physical_i = {t.findtext('./AttributeList/Name') for t in io.findall('.//SW.Tags.PlcTag')
                      if t.findtext('./AttributeList/LogicalAddress', '').startswith('%I')}
        root = ET.fromstring(B.main_ob())
        connected = set()
        for net in root.findall('.//{*}FlgNet'):
            accesses = {a.get('UId'): xml_operand(a).strip('"') for a in net.findall('./{*}Parts/{*}Access')}
            calls = {c.get('UId'): c for c in net.findall('./{*}Parts/{*}Call')}
            for wire in net.findall('./{*}Wires/{*}Wire'):
                source, *sinks = list(wire)
                if source.tag.endswith('IdentCon'):
                    for sink in sinks:
                        if sink.get('UId') in calls:
                            connected.add(accesses[source.get('UId')])
        self.assertEqual(connected & physical_i, physical_i)
        self.assertEqual(len(physical_i), 22)

    def test_fb_instance_sections_types_and_defaults_match(self):
        for fb, instances in [(B.burner_fb, [lambda: B.burner_db('BR01_DB', 3), lambda: B.burner_db('BR02_DB', 4)]),
                              (B.scrubber_fb, [B.scrubber_db])]:
            def sections(make):
                root = ET.fromstring(make())
                return {sec.get('Name'): [(m.get('Name'), m.get('Datatype'), m.get('Remanence'), m.findtext('{*}StartValue'))
                                          for m in sec.findall('{*}Member')]
                        for sec in root.findall('.//Interface/{*}Sections/{*}Section')
                        if sec.get('Name') in ('Input', 'Output', 'InOut', 'Static')}
            expected = sections(fb)
            for instance in instances:
                self.assertEqual(sections(instance), expected)
            for sec in expected.values():
                self.assertTrue(all(remanence == 'NonRetain' for _, _, remanence, _ in sec))
            if fb == B.burner_fb:
                self.assertIn(('Use24h', 'Bool', 'NonRetain', None), expected['Input'])
                self.assertIn(('FuelMem', 'Bool', 'NonRetain', None), expected['Static'])
                self.assertNotIn('Use24h', [n for n, *_ in expected['Static']])
            else:
                self.assertIn(('Tripped', 'Bool', 'NonRetain', None), expected['Output'])
                self.assertIn(('Alarms', 'Word', 'NonRetain', None), expected['Output'])

    def test_alarm_table_ids_and_local_word_slices(self):
        import build_alarms as A
        expected_ids = {('Common', n): 1 + n for n in range(6)}
        expected_ids.update({('BR01', n): 7 + n for n in range(5)})
        expected_ids.update({('BR02', n): 12 + n for n in range(5)})
        self.assertEqual({(w, b): A.alarm_id(w, b) for w, b, *_ in B.HMI_ALARMS}, expected_ids)
        self.assertTrue(all(len(row) == 6 and row[2].lstrip('!').startswith('#') for row in B.HMI_ALARMS))
        self.assertEqual(B.alarm_rungs('BR01'), B.alarm_rungs('BR02'))
        for make, word in [(B.scrubber_fb, 'Common'), (B.burner_fb, 'BR01')]:
            alarms = [r for r in rules(make) if r[0].split(' :: ')[0] == 'Alarms']
            self.assertEqual([(expr, *outs) for _, expr, outs in alarms][-len(B.alarm_rungs(word)):], B.alarm_rungs(word))
            root = ET.fromstring(make())
            slices = root.findall('.//{*}Component[@SliceAccessModifier]')
            self.assertEqual([c.get('Name') for c in slices], ['Alarms'] * len(B.alarm_rungs(word)))
            self.assertEqual([c.get('SliceAccessModifier') for c in slices], ['x%d' % n for n in range(len(slices))])
        self.assertEqual(B.HMI_ALARMS[0][3:5], ('E-STOP pressed', 'Release E-STOP; then RESET the scrubber and START the burners'))
        for bit in range(16):
            n = B.Net()
            n.operand('#Alarms.%%X%d' % bit)
            self.assertEqual(ET.fromstring(n.render()).find('.//{*}Component').get('SliceAccessModifier'), 'x%d' % bit)
        for bad in ('#Alarms.%X16', '#Alarms.%X-1'):
            with self.assertRaises(ValueError):
                B.Net().operand(bad)
        changed = [row[:2] + ('#TcBad',) + row[3:] if row[:2] == ('BR02', 0) else row
                   for row in B.HMI_ALARMS]
        with patch.object(B, 'HMI_ALARMS', changed), self.assertRaisesRegex(ValueError, 'shared Burner FB'):
            B.burner_fb()

    def test_panel_text_covers_current_blocks_and_topics(self):
        names = {Path(n).stem for n, _ in B.BLOCKS}
        self.assertEqual(set(B.P.BLOCK_COMMENTS), names)
        self.assertEqual(set(B.P.NETWORK_TEXT), {'Burner', 'Scrubber', 'Startup', 'Main'})
        with patch.object(B, 'MULTI_RUNG', True):
            for name, make in [('Burner', B.burner_fb), ('Scrubber', B.scrubber_fb), ('Startup', B.startup_ob), ('Main', B.main_ob)]:
                root = ET.fromstring(make())
                descriptions = {}
                for unit in root.findall('.//SW.Blocks.CompileUnit'):
                    texts = {t.get('CompositionName'): t.findtext('.//Text')
                             for t in unit.findall('./ObjectList/MultilingualText')}
                    descriptions[texts['Title']] = (texts['Title'], texts['Comment'])
                self.assertEqual(descriptions, B.P.NETWORK_TEXT[name])
        for group, aliases in B.P.SYMBOL_RENAMES.items():
            members = B.P.MEMBER_TEXT[group]
            self.assertTrue(set(aliases.values()) <= set(members))


class HmiContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Retain the HMI checks for Task 2. Only the explicitly expected removed
        # SYS dependency defers this class; unrelated import errors still fail.
        try:
            import build_hmi
        except AttributeError as exc:
            if exc.name == 'SYS' and exc.obj is B:
                raise unittest.SkipTest('Task 2 pending: build_hmi still imports removed B.SYS')
            raise

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
        self.assertEqual(len(names), 57)
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


def both_xml_modes(test):
    @wraps(test)
    def run(self):
        for multi in (True, False):
            with self.subTest(MULTI_RUNG=multi), patch.object(B, 'MULTI_RUNG', multi):
                test(self)
    return run


# Every PLC behavior and structure check executes against both serializers.
for test_class in (CommonRules, ScrubberRules, BurnerRules, ManagerRules, XmlContracts):
    for test_name, test_method in list(vars(test_class).items()):
        if test_name.startswith('test_'):
            setattr(test_class, test_name, both_xml_modes(test_method))
del test_class, test_name, test_method


if __name__ == '__main__':
    unittest.main()
