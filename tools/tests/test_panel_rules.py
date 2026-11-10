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


def scan_common(memory):
    for title, expr, outputs in rules(B.common_fc):
        active = expression(expr, memory)
        for op, *args in outputs:
            if op == '=':
                memory[args[0]] = active
            elif active and op == 'S':
                memory[args[0]] = True
            elif active and op == 'R':
                memory[args[0]] = False
            elif active and op == 'MOVE':
                memory[args[1]] = value(args[0], memory)
            elif op not in ('S', 'R', 'MOVE'):
                raise AssertionError('Unsupported rule output: %r' % (op,))


def memory(br1=False, br2=False):
    result = {'"Sys".' + n: False for n, _ in B.SYS}
    result.update({'"S0_EStopStatus"': True, '"S2_FaultReset"': False,
                   '"Sys".EStopOK': True, '"BR01_DB".StartEnabled': br1, '"BR02_DB".StartEnabled': br2})
    for n, typ, default, low, high, comment in B.PARAMS:
        result['"Par".' + n] = value(default, {})
        result['"Par".' + n + '_V'] = value(default, {})
    return result


class SettingsRules(unittest.TestCase):
    def test_all_parameters_accept_only_with_both_start_permissions_off(self):
        for n, typ, default, low, high, comment in B.PARAMS:
            for br1, br2 in [(False, False), (True, False), (False, True), (True, True)]:
                with self.subTest(parameter=n, br1=br1, br2=br2):
                    m = memory(br1, br2)
                    p, v = '"Par".' + n, '"Par".' + n + '_V'
                    previous = m[v]
                    candidate = previous + (1000 if typ == 'Time' else 1)
                    m[p] = candidate
                    scan_common(m)
                    editable = not br1 and not br2
                    self.assertEqual(m[v], candidate if editable else previous)
                    self.assertEqual(m[p], candidate if editable else previous)
                    self.assertEqual(m['"Sys".Alm_ParRejected'], not editable)

    def test_no_false_rejection_for_unchanged_values_while_enabled(self):
        m = memory(True, True)
        scan_common(m)
        self.assertFalse(m['"Sys".Alm_ParRejected'])

    def test_out_of_range_is_restored_for_each_parameter(self):
        for n, typ, default, low, high, comment in B.PARAMS:
            with self.subTest(parameter=n):
                m = memory()
                p, v = '"Par".' + n, '"Par".' + n + '_V'
                previous = m[v]
                m[p] = value(high, {}) + 1
                scan_common(m)
                self.assertEqual(m[p], previous)
                self.assertEqual(m[v], previous)
                self.assertTrue(m['"Sys".Alm_ParRejected'])

    def test_corrupt_retained_values_restore_defaults_on_first_scan(self):
        m = memory()
        m['"Sys".FirstScan'] = True
        for n, typ, default, low, high, comment in B.PARAMS:
            m['"Par".' + n] = m['"Par".' + n + '_V'] = value(high, {}) + 1
        scan_common(m)
        for n, typ, default, low, high, comment in B.PARAMS:
            self.assertEqual(m['"Par".' + n], value(default, {}))
            self.assertEqual(m['"Par".' + n + '_V'], value(default, {}))


class BurnerPermissive(unittest.TestCase):
    def test_scrubber_trip_blocks_ready(self):
        expr = next(expr for title, expr, outs in rules(B.burner_fb) if 'ready to fire' in title)
        m = {'#LevelOK': True, '#TcOk': True, '"Sys".EStopOK': True,
             '#Lockout': False, '#Pause24': False, '"Scrubber_DB".Tripped': True}
        self.assertFalse(expression(expr, m))
        m['"Scrubber_DB".Tripped'] = False
        self.assertTrue(expression(expr, m))


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
        self.assertEqual(len(names), 74)
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
        expected_ids = {('Common', n): 1 + n for n in range(8)}
        expected_ids.update({('BR01', n): 9 + n for n in range(7)})
        expected_ids.update({('BR02', n): 16 + n for n in range(7)})
        expected_ids.update({('BR01', 7): 23, ('BR02', 7): 24})
        self.assertEqual({(w, b): A.alarm_id(w, b) for w, b, *_ in B.HMI_ALARMS}, expected_ids)


if __name__ == '__main__':
    unittest.main()
