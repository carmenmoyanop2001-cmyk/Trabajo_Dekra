"""Comparar el contenido autorizando CC/CD y visibilidad, según la revisión actual."""
import hashlib
from copy import deepcopy
from functools import lru_cache
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


def estilos_equivalentes(z):
    """Comparar estilos efectivos aunque al filtrar bandas cambien sus índices."""
    root=E.fromstring(z if isinstance(z,bytes) else z.read('xl/styles.xml'))
    groups={E.QName(g).localname:list(g) for g in root}
    formats={f.get('numFmtId'):f.get('formatCode') for f in groups.get('numFmts',[])}
    @lru_cache(maxsize=None)
    def definition(group,index):
        node=deepcopy(groups[group][index])
        for attr,target in [('fontId','fonts'),('fillId','fills'),('borderId','borders')]:
            if node.get(attr) is not None:
                node.set(attr,definition(target,int(node.get(attr))))
        if node.get('numFmtId') is not None:
            value=node.get('numFmtId')
            node.set('numFmtId',formats.get(value,'builtin:'+value))
        if group=='cellXfs' and node.get('xfId') is not None:
            node.set('xfId',definition('cellStyleXfs',int(node.get('xfId'))))
        return hashlib.sha256(E.tostring(node,method='c14n',exclusive=True)).hexdigest()
    return {str(i):definition('cellXfs',i) for i in range(len(groups['cellXfs']))}


def normalizar_estilos(root,styles):
    for node in root.iter():
        tag=E.QName(node).localname
        attr='s' if tag in ('c','row') else 'style' if tag=='col' else None
        if attr and node.get(attr) is not None:
            node.set(attr,styles[node.get(attr)])
    return root


def contenido_fijo(xml,styles=None):
    root=sin_visibilidad(xml)
    if styles is not None:normalizar_estilos(root,styles)
    return E.tostring(root,method='c14n',exclusive=True)
