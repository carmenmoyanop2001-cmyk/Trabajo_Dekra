"""Guarda Validations y Pretesting-Others del original dentro del programa.

Se usa una sola vez al preparar la distribución, no al generar un ensayo.
"""
from copy import deepcopy
import json
from pathlib import Path
import posixpath
import sys
import zipfile
from lxml import etree as E

M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS = {'s': M}
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def incorporar(original, destino):
    with zipfile.ZipFile(destino) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    manifest = json.loads(parts['manifest.json'])
    if '10' in manifest['full'] and '14' in manifest['full']:
        return
    with zipfile.ZipFile(original) as z:
        wb = E.fromstring(z.read('xl/workbook.xml'))
        rels = {r.get('Id'): r.get('Target') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        sheets = {s.get('name'): 'xl/' + rels[s.get('{' + R + '}id')] for s in wb.find('s:sheets', NS)}
        strings = list(E.fromstring(z.read('xl/sharedStrings.xml')))
        old = E.fromstring(parts['xl/styles.xml'])
        source = E.fromstring(z.read('xl/styles.xml'))
        offsets = {}
        formats = {}
        fmt = old.find('s:numFmts', NS)
        if fmt is None:
            fmt = E.Element('{' + M + '}numFmts')
            old.insert(0, fmt)
        next_fmt = max([163] + [int(c.get('numFmtId')) for c in fmt]) + 1
        for element in source.find('s:numFmts', NS):
            copied = deepcopy(element)
            formats[int(element.get('numFmtId'))] = next_fmt
            copied.set('numFmtId', str(next_fmt))
            next_fmt += 1
            fmt.append(copied)
        fmt.set('count', str(len(fmt)))
        for tag in ('fonts', 'fills', 'borders', 'cellStyleXfs', 'cellXfs', 'dxfs'):
            target = old.find('s:' + tag, NS)
            src = source.find('s:' + tag, NS)
            offsets[tag] = len(target)
            for element in src:
                copied = deepcopy(element)
                for node in copied.iter():
                    for attr, table in [('fontId', 'fonts'), ('fillId', 'fills'), ('borderId', 'borders'), ('xfId', 'cellStyleXfs')]:
                        if attr in node.attrib:
                            node.set(attr, str(int(node.get(attr)) + offsets.get(table, 0)))
                    if 'numFmtId' in node.attrib and int(node.get('numFmtId')) in formats:
                        node.set('numFmtId', str(formats[int(node.get('numFmtId'))]))
                target.append(copied)
            target.set('count', str(len(target)))
        parts['xl/styles.xml'] = E.tostring(old, xml_declaration=True, encoding='utf-8', standalone=True)
        ct = E.fromstring(z.read('[Content_Types].xml'))
        src_types = {c.get('PartName').lstrip('/'): c.get('ContentType') for c in ct if c.get('PartName')}
        for c in ct:
            if c.get('Extension'):
                manifest['defaults'].setdefault(c.get('Extension'), c.get('ContentType'))

        def related(src, dest, owned):
            rp = posixpath.join(posixpath.dirname(src), '_rels', posixpath.basename(src) + '.rels')
            if rp not in z.namelist():
                return
            root = E.fromstring(z.read(rp))
            newrp = posixpath.join(posixpath.dirname(dest), '_rels', posixpath.basename(dest) + '.rels')
            owned.append(newrp)
            for rel in root:
                if rel.get('TargetMode') == 'External':
                    continue
                child = posixpath.normpath(posixpath.join(posixpath.dirname(src), rel.get('Target')))
                newchild = 'xl/guardado/' + child
                rel.set('Target', posixpath.relpath(newchild, posixpath.dirname(dest)))
                if newchild not in parts:
                    parts[newchild] = z.read(child)
                    if child in src_types:
                        manifest['overrides']['/' + newchild] = src_types[child]
                    related(child, newchild, owned)
                owned.append(newchild)
            parts[newrp] = E.tostring(root, xml_declaration=True, encoding='utf-8', standalone=True)

        for name, number in [('Validations', 10), ('Pretesting-Others', 14)]:
            src = sheets[name]
            dest = f'xl/worksheets/sheet{number}.xml'
            root = E.fromstring(z.read(src))
            for c in root.findall('s:sheetData/s:row/s:c', NS):
                if c.get('s'):
                    c.set('s', str(int(c.get('s')) + offsets['cellXfs']))
                if c.get('t') == 's':
                    si = strings[int(c.find('s:v', NS).text)]
                    c.remove(c.find('s:v', NS))
                    c.set('t', 'inlineStr')
                    inline = E.SubElement(c, '{' + M + '}is')
                    for node in si:
                        inline.append(deepcopy(node))
            for c in root.iter():
                if c.get('dxfId'):
                    c.set('dxfId', str(int(c.get('dxfId')) + offsets['dxfs']))
            parts[dest] = E.tostring(root, xml_declaration=True, encoding='utf-8', standalone=True)
            owned = []
            related(src, dest, owned)
            manifest['owned'][str(number)] = list(dict.fromkeys(owned))
            manifest['full'][str(number)] = name
        parts['manifest.json'] = json.dumps(manifest, ensure_ascii=False).encode()
    candidate = Path(str(destino) + '.tmp')
    with zipfile.ZipFile(candidate, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)
    candidate.replace(destino)


if __name__ == '__main__':
    incorporar(*sys.argv[1:])
