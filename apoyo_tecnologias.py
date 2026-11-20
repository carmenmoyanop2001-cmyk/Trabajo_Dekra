"""Separar el apoyo RF oculto de las tablas visibles que empiezan en fila 1."""
from copy import deepcopy
import re
from lxml import etree as E
from sarlib import _REF, _STR, _sheetname, _fmt_sheet

M='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS={'s':M}


def renombrar_referencias(text, nombres):
    if not text or not nombres:
        return text
    def ref(m):
        nombre=_sheetname(m[1])
        return _fmt_sheet(nombres[nombre])+m[0][len(m[1]):] if nombre in nombres else m[0]
    parts=_STR.split(text)
    for i in range(0,len(parts),2):parts[i]=_REF.sub(ref,parts[i])
    return ''.join(parts)


def actualizar_xml(xml, nombres):
    if not nombres:
        return xml
    root=E.fromstring(xml);changed=False
    for node in root.iter():
        if E.QName(node).localname in ('f','formula','formula1','formula2','definedName') and node.text:
            new=renombrar_referencias(node.text,nombres)
            if new!=node.text:node.text=new;changed=True
    return E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True) if changed else xml


def construir_apoyo(plan):
    """Los calculos internos leen las entradas editables de la tabla visible."""
    from tecnologias_originales import _filas,_celda,_value,_norm,_poner,_col
    from sarlib import col2n
    root=E.fromstring(plan.backend)
    # Usar metadatos de la base, no las etiquetas del formato (Cat M1/LTE etc.).
    rows={new:E.fromstring(raw) for old,new,raw in _filas(plan) if old>2}
    by_record={}
    for index,positions in plan.view_rows.items():
        record=plan.registros[index].record
        key=record.tech,_norm(record.band),_norm(record.channel),_norm(record.frequency)
        by_record.setdefault(key,[]).extend(n for n in positions if n in rows)
    for row in root.findall('s:sheetData/s:row',NS):
        if int(row.get('r'))<=2:continue
        values={c:_value(_celda(row,c),[]) for c in ('J','K','T','U','X')}
        tech=values['J']
        if tech=='Cat M1':tech='LTE CAT M1'
        if tech in ('GPRS','EGPRS') and values['X'] is not None:tech+=f" {int(values['X'])}TX"
        key=tech,_norm(values['K']),_norm(values['T']),_norm(values['U'])
        choices=by_record.get(key,[])
        if not choices:continue
        # Preferir la misma antena/puerto/TX cuando esta descrita en el apoyo.
        def score(number):
            return sum(_value(_celda(row,c),[]) is not None and
                       _norm(_value(_celda(row,c),[]))==_norm(_value(_celda(rows[number],c),[]))
                       for c in ('G','I','L','M','N','Q','R','S'))
        target=max(choices,key=score)
        for cell in row:
            column=_col(cell)
            if not col2n('AC')<=col2n(column)<=col2n('BD') or cell.find('s:f',NS) is not None:continue
            ref=_fmt_sheet(plan.nombre)+column+str(target)
            for child in list(cell):cell.remove(child)
            cell.attrib.pop('t',None)
            E.SubElement(cell,'{'+M+'}f').text=f'IF({ref}="","",{ref})'
    return E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
