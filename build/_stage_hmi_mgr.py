"""Preview the Alarms fix on a stale export. NEVER import this preview."""
from pathlib import Path
import difflib
import hashlib
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent.parent
source = root / 'export/xml/HMI_HMI_RT_1/Screens/Alarms.xml'
evidence = root / 'docs/evidence/2026-11-16-manager-style-tia'
evidence.mkdir(exist_ok=True)
before = source.read_bytes()
tree = ET.fromstring(before)
objects = [obj for obj in tree.iter() if obj.findtext('./AttributeList/ObjectName') ==
           'Text_E_STOP_RESET_Sys_Alm_EStop']
assert len(objects) == 1
obj = objects[0]
animations = obj.findall('./ObjectList/Hmi.Dynamic.SingleBitVisibilityAnimation')
assert len(animations) == 1
animation = animations[0]
assert animation.findtext('./AttributeList/Visible') == 'true'
assert animation.findtext('./ObjectList/Hmi.Dynamic.TagElementTrigger/LinkList/Tag/Name') == 'Sys_Alm_EStop'
after = before
for old, new in (
    (b'<ObjectName>Text_E_STOP_RESET_Sys_Alm_EStop</ObjectName>',
     b'<ObjectName>Text_E_STOP_Scrub_EStopOK</ObjectName>'),
    (b'<Name>Sys_Alm_EStop</Name>', b'<Name>Scrub_EStopOK</Name>'),
):
    assert after.count(old) == 1
    after = after.replace(old, new, 1)
# Replace only inside the identified animation, without reserializing the XML.
start = after.index(b'<Hmi.Dynamic.SingleBitVisibilityAnimation ID="C"')
end = after.index(b'</Hmi.Dynamic.SingleBitVisibilityAnimation>', start)
fragment = after[start:end]
assert fragment.count(b'<Visible>true</Visible>') == 1
after = after[:start] + fragment.replace(b'<Visible>true</Visible>', b'<Visible>false</Visible>') + after[end:]
patched = ET.fromstring(after)
new_obj = next(o for o in patched.iter() if o.findtext('./AttributeList/ObjectName') ==
               'Text_E_STOP_Scrub_EStopOK')
new_animation = new_obj.find('./ObjectList/Hmi.Dynamic.SingleBitVisibilityAnimation')
assert new_animation.findtext('./AttributeList/Visible') == 'false'
assert new_animation.findtext('./ObjectList/Hmi.Dynamic.TagElementTrigger/LinkList/Tag/Name') == 'Scrub_EStopOK'
# Reverse exactly the three intended fields, then prove every XML byte matches.
restored = after.replace(b'Text_E_STOP_Scrub_EStopOK', b'Text_E_STOP_RESET_Sys_Alm_EStop', 1)
restored = restored.replace(b'<Name>Scrub_EStopOK</Name>', b'<Name>Sys_Alm_EStop</Name>', 1)
start = restored.index(b'<Hmi.Dynamic.SingleBitVisibilityAnimation ID="C"')
end = restored.index(b'</Hmi.Dynamic.SingleBitVisibilityAnimation>', start)
restored = restored[:start] + restored[start:end].replace(b'<Visible>false</Visible>', b'<Visible>true</Visible>', 1) + restored[end:]
assert restored == before
(evidence / 'Alarms-before.xml').write_bytes(before)
(evidence / 'Alarms-preview.xml').write_bytes(after)
diff = '\n'.join(difflib.unified_diff(before.decode('utf-8-sig').splitlines(),
                                  after.decode('utf-8-sig').splitlines(),
                                  fromfile='existing-export/Alarms.xml',
                                  tofile='DO-NOT-IMPORT/Alarms-preview.xml', lineterm='')) + '\n'
(evidence / 'Alarms-preview.diff').write_text(diff, encoding='utf-8')
print('SOURCE: existing export only; fresh Openness export failed; NOT imported')
print('DO NOT IMPORT: existing Alarms export has NO manual Alarm View; obtain a fresh export first')
print('SHA256 before:', hashlib.sha256(before).hexdigest())
print('SHA256 staged:', hashlib.sha256(after).hexdigest())
print('PASS: exactly ObjectName, visibility tag and Visible changed; all other bytes unchanged')
print('PASS: preview only; build/hmi untouched; no import directory produced')
print(diff)
