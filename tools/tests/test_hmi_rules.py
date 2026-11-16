"""Check the manager-style PLC/HMI contract without importing into TIA."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_hmi as H
import build_alarms as A
import build_blocks as B


class HmiRules(unittest.TestCase):
    def test_public_tags_and_plc_types(self):
        tags = ET.fromstring(H.tag_table()).findall('.//Hmi.Tag.Tag')
        self.assertEqual(len(tags), 57)
        self.assertEqual(len({t.findtext('AttributeList/Name') for t in tags}), 57)
        links = {t.findtext('AttributeList/Name'): t.findtext('LinkList/ControllerTag/Name')
                 for t in tags}
        self.assertEqual(links['Scrub_EStopOK'], 'Scrubber_DB.EStopOK')
        self.assertFalse(any(name.startswith('Sys_') for name in links))
        for br in ('BR01', 'BR02'):
            for alias, member in H.BR_MEMBERS.items():
                self.assertEqual(links[br + '_' + alias], br + '_DB.' + member)
        for tag in tags:
            db, member = tag.findtext('LinkList/ControllerTag/Name').split('.')
            self.assertIn(db, ('Par', 'Scrubber_DB', 'BR01_DB', 'BR02_DB'))
            self.assertEqual(tag.findtext('LinkList/DataType/Name'), H.MEMBERS[db][member])

    def test_alarm_words_continuous_and_unsigned(self):
        tags = {t.findtext('AttributeList/Name'): t
                for t in ET.fromstring(H.tag_table()).findall('.//Hmi.Tag.Tag')}
        for word, db in H.ALARM_DBS.items():
            tag = tags['Alm_' + word]
            self.assertEqual(tag.findtext('LinkList/ControllerTag/Name'), db + '.Alarms')
            self.assertEqual(tag.findtext('LinkList/DataType/Name'), 'Word')
            self.assertEqual(tag.findtext('LinkList/HmiDataType/Name'), 'UInt')
            self.assertEqual(tag.findtext('AttributeList/AcquisitionTriggerMode'), 'Continuous')
            comment = ''.join(tag.find('ObjectList/MultilingualText').itertext())
            for w, bit, _, title, _, _ in B.HMI_ALARMS:
                if w == word:
                    self.assertIn('x%d %s' % (bit, title), comment)

    def test_all_screen_references_exist_and_estop_banner_uses_zero(self):
        public = {name for name, _, _ in H.TAGS}
        for screen in (H.overview(), H.burner('BR01'), H.burner('BR02'),
                       H.scrubber(), H.settings()):
            root = ET.fromstring(screen.xml())
            references = {n.text for n in root.findall('.//Tag/Name')}
            self.assertLessEqual(references, public, screen.name)
            banners = root.findall('.//Hmi.Dynamic.SingleBitVisibilityAnimation')
            banners = [b for b in banners if b.findtext('.//Tag/Name') == 'Scrub_EStopOK']
            self.assertEqual(len(banners), 1, screen.name)
            self.assertEqual(banners[0].findtext('AttributeList/Visible'), 'false')
            self.assertEqual(banners[0].findtext('AttributeList/BitPosition'), '0')
            if screen.name in ('BR01', 'BR02'):
                lamps = root.findall('.//Hmi.Dynamic.RangeAppearanceAnimation')
                self.assertTrue(any(l.findtext('.//Tag/Name') == 'Scrub_EStopOK' for l in lamps))

    def test_alarm_ids_triggers_and_release_guidance(self):
        operator = A.validate_alarms(B.HMI_ALARMS, A.OPERATOR_ALARMS)
        self.assertEqual([A.alarm_id(w, b) for w, b, *_ in B.HMI_ALARMS], list(range(1, 17)))
        self.assertEqual({'Alm_' + w for w, *_ in B.HMI_ALARMS},
                         {'Alm_Common', 'Alm_BR01', 'Alm_BR02'})
        _, title, info = operator[('Common', 0)]
        self.assertEqual(title, 'E-STOP pressed')
        self.assertIn('الإنذار بيروح أول ما تفك الزرار', info)
        self.assertIn('RESET', info)
        self.assertIn('START', info)


if __name__ == '__main__':
    unittest.main()
