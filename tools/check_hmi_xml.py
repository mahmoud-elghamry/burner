# -*- coding: utf-8 -*-
"""
بيراجع build/hmi/ على exports الحقيقية في build/hmi-ref/، من غير TIA.

    py tools/check_hmi_xml.py

لكل نوع object: أسماء AttributeList وLinkList، وتركيبات ObjectList لازم
تكون ظهرت لنفس النوع في المرجع. كمان IDs ما تتكررش داخل نفس الملف،
وAttributeList تفضل أبجدية. ده فحص توافق مع العيّنات، مش بديل للاستيراد
والكومبايل: مش بيحكم على enum values ولا كل شروط الـ importer.
"""
from __future__ import print_function
import os, sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REF = os.path.join(ROOT, 'build', 'hmi-ref')
OUT = os.path.join(ROOT, 'build', 'hmi')


def xml_files(folder):
    return sorted(os.path.join(base, name)
                  for base, _, names in os.walk(folder)
                  for name in names if name.lower().endswith('.xml'))


def is_object(element):
    return (element.tag.startswith('Hmi.') or
            element.tag in ('MultilingualText', 'MultilingualTextItem'))


def collect_reference(roots):
    """الاتحاد لكل نوع، مش لكل الشاشات مع بعض: خاصية Button مش دليل لـ Rectangle."""
    reference = {}
    for root in roots:
        for obj in root.iter():
            if not is_object(obj):
                continue
            shape = reference.setdefault(obj.tag, {
                'attributes': set(), 'links': set(), 'compositions': set(), 'children': set()})
            shape['attributes'].update(c.tag for c in obj.findall('./AttributeList/*'))
            shape['links'].update(c.tag for c in obj.findall('./LinkList/*'))
            for child in obj.findall('./ObjectList/*'):
                comp = child.get('CompositionName')
                shape['compositions'].add(comp)
                shape['children'].add((child.tag, comp))
    return reference


def check_document(root, reference):
    errors, ids = [], set()
    for obj in root.iter():
        ident = obj.get('ID')
        where = '%s ID=%s' % (obj.tag, ident if ident is not None else '<missing>')
        if ident is not None:
            if ident in ids:
                errors.append('%s: duplicate ID' % where)
            ids.add(ident)
        if not is_object(obj):
            continue
        shape = reference.get(obj.tag)
        if shape is None:
            errors.append('%s: object type never seen in references' % where)
            continue
        for path, key, label in [('./AttributeList/*', 'attributes', 'attribute'),
                                 ('./LinkList/*', 'links', 'link')]:
            for child in obj.findall(path):
                if child.tag not in shape[key]:
                    errors.append('%s: %s %s never seen for this type' %
                                  (where, label, child.tag))
        for alist in obj.findall('./AttributeList'):
            names = [c.tag for c in alist]
            if names != sorted(names):
                errors.append('%s: AttributeList is not alphabetical' % where)
        for child in obj.findall('./ObjectList/*'):
            comp = child.get('CompositionName')
            if comp not in shape['compositions']:
                errors.append('%s: child CompositionName=%r never seen for this type' %
                              (where, comp))
            elif (child.tag, comp) not in shape['children']:
                errors.append('%s: child %s in CompositionName=%r never seen for this type' %
                              (where, child.tag, comp))
    return errors


def read_documents(paths, errors):
    documents = []
    for path in paths:
        try:
            documents.append((path, ET.parse(path).getroot()))
        except (OSError, ET.ParseError) as exc:
            errors.append('%s: %s' % (os.path.relpath(path, ROOT), exc))
    return documents


def main():
    errors = []
    refs, generated = xml_files(REF), xml_files(OUT)
    if not refs:
        errors.append('build/hmi-ref: no reference XML files')
    if not generated:
        errors.append('build/hmi: no generated XML files (run py tools\\build_hmi.py)')
    ref_docs = read_documents(refs, errors)
    reference = collect_reference(root for _, root in ref_docs)
    if refs and not reference:
        errors.append('build/hmi-ref: no reference object types')
    for path, root in read_documents(generated, errors):
        errors.extend('%s: %s' % (os.path.relpath(path, ROOT), error)
                      for error in check_document(root, reference))
    if errors:
        for error in errors:
            print(error)
        print('FAIL - %d finding(s)' % len(errors))
        return 1
    print('OK - %d generated XML files checked against %d reference files (%d object types)' %
          (len(generated), len(refs), len(reference)))
    print('OK - attributes, links, child compositions/types, alphabetical attributes; IDs unique per document')
    return 0


if __name__ == '__main__':
    sys.exit(main())
