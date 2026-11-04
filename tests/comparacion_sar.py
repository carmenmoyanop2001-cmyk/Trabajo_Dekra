"""Comparar EN autorizando exclusivamente fórmulas/resultados de CC y CD."""
import hashlib
from lxml import etree as E

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def sin_canales(xml):
    root=E.fromstring(xml)
    for cell in root.findall('s:sheetData/s:row/s:c',NS):
        col=''.join(c for c in cell.get('r') if c.isalpha())
        if col in ('CC','CD'):
            for child in list(cell):cell.remove(child)
            cell.attrib.pop('t',None)
    return hashlib.sha256(E.tostring(root,method='c14n',exclusive=True)).hexdigest()
