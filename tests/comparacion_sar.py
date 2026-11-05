"""Comparar el contenido autorizando CC/CD y visibilidad, según la revisión actual."""
import hashlib
from lxml import etree as E

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def sin_visibilidad(xml):
    root=E.fromstring(xml)
    for cols in root.findall('s:cols', NS):
        canonical=[]
        for col in cols:
            attrs={k:v for k,v in col.attrib.items() if k not in ('min','max','hidden')}
            first,last=int(col.get('min')),int(col.get('max'))
            if canonical and canonical[-1][2]==attrs and canonical[-1][1]+1==first:
                canonical[-1]=(canonical[-1][0],last,attrs)
            else:canonical.append((first,last,attrs))
        cols.clear()
        for first,last,attrs in canonical:
            E.SubElement(cols,'{'+NS['s']+'}col',min=str(first),max=str(last),**attrs)
    return root


def sin_canales(xml):
    root=sin_visibilidad(xml)
    for cell in root.findall('s:sheetData/s:row/s:c',NS):
        col=''.join(c for c in cell.get('r') if c.isalpha())
        if col in ('CC','CD'):
            for child in list(cell):cell.remove(child)
            cell.attrib.pop('t',None)
    return hashlib.sha256(E.tostring(root,method='c14n',exclusive=True)).hexdigest()


def contenido_fijo(xml):
    return E.tostring(sin_visibilidad(xml),method='c14n',exclusive=True)
