"""Auxiliares originales SAR: conservar las formulas y enlazar solo sus entradas RF."""
from copy import deepcopy
from collections import defaultdict
import re
from zipfile import ZipFile
from lxml import etree as E
from sarlib import _REF,_STR,_sheetname,col2n,n2col
M='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS={'s':M}


def _sh(name):
    return "'"+name.replace("'","''")+"'!"


def asignar(planes):
    for number,plan in enumerate(planes.values(),1):
        plan.nombre_auxiliar_original='__OriginalRF_'+str(number)
        plan.auxiliares_originales_necesarios=set()


def _indices(plan):
    from tecnologias_originales import _value,_celda,_strings,_norm
    if hasattr(plan,'indice_original_sar'):
        return plan.indice_original_sar
    original=plan.archivo;part=plan.parte
    copia=getattr(plan,'copia_original_sar',None)
    if copia and (original.parent/copia['archivo']).exists():
        original=original.parent/copia['archivo'];part=copia['parte']
    bands={};starts={}
    with ZipFile(original) as z:
        strings=_strings(z)
        with z.open(part) as stream:
            for _,row in E.iterparse(stream,tag='{'+M+'}row'):
                old=int(row.get('r'));band=_norm(_value(_celda(row,'K'),strings))
                if old>2 and band is not None:
                    bands[old]=band;starts.setdefault(band,old)
                row.clear()
                while row.getprevious() is not None:del row.getparent()[0]
    plan.indice_original_sar=(bands,starts)
    return bands,starts


def fila_original(plan,old,banda):
    """Reubicar una referencia de la copia corta 5G en su segmento completo/regional."""
    from tecnologias_originales import _norm
    band=_norm(banda)
    if plan.origen_grupos.get(old,(None,None))[1]==band:
        return old
    bands,starts=_indices(plan)
    source=bands.get(old)
    if source is None:
        return old
    if source==band and not getattr(plan,'copia_original_sar',None):
        return old
    target=next((v['primera'] for b,v in plan.segmentos.items() if _norm(b)==band),None)
    if target is None:
        target=starts.get(band)
    if target is None:
        candidates=[r for r,positions in plan.rows.items()
                    if any(plan.grupos.get(n,(None,None))[1]==band for n in positions)]
        if not candidates:
            raise ValueError('No hay una referencia original RF para la banda '+str(banda))
        target=min(candidates)
    return target+old-starts[source]


def referencia_sar(text,planes,banda,antena=None):
    def one(m):
        family=_sheetname(m[1]);plan=planes.get(family)
        if plan is None:
            return m[0]
        first=(fila_auxiliar_5g(plan,int(m[5]),m[3],banda,antena) if plan.familia=='Conducted 5G' and col2n(m[3])>=col2n('BT') else fila_original(plan,int(m[5]),banda))
        last=fila_original(plan,int(m[9]),banda) if m[7] else first
        if col2n(m[3])<col2n('BT'):
            # Una referencia directa a una entrada se reubica en la tabla visible.
            mapped=plan.mapped(first)
            if mapped is None:
                raise ValueError('La formula SAR original no tiene entrada seleccionada: '+m[0])
            return _sh(plan.nombre)+m[2]+m[3]+m[4]+str(mapped)
        cols=range(col2n(m[3]),col2n(m[7] or m[3])+1) if m[7] else [col2n(m[3])]
        for r in range(first,last+1):
            for c in cols:plan.auxiliares_originales_necesarios.add((r,n2col(c)))
        result=_sh(plan.nombre_auxiliar_original)+m[2]+m[3]+m[4]+str(first)
        if m[7]:result+=':'+m[6]+m[7]+m[8]+str(last)
        return result
    parts=_STR.split(text)
    for i in range(0,len(parts),2):parts[i]=_REF.sub(one,parts[i])
    return ''.join(parts)


def construir(plan,planes):
    """Copiar solo los auxiliares alcanzables; no importar resultados RF antiguos."""
    from tecnologias_originales import _fuente,_inline,_col,_norm
    needed=plan.auxiliares_originales_necesarios
    if not needed:return None
    found={};shared={}
    partes=[plan.parte] if not plan.segmentos else list(dict.fromkeys(
        segment['parte'] for band,segment in plan.segmentos.items()
        if any(_norm(view.record.band)==_norm(band) for view in plan.registros)))
    def formula(text):
        from referencias_geometricas import proteger_columnas
        text,reserved=proteger_columnas(text)
        def one(m):
            family=_sheetname(m[1]) or plan.familia
            target=planes.get(family)
            if target is None:return m[0]
            old=int(m[5]);last=int(m[9]) if m[7] else old
            if col2n(m[3])>=col2n('BT'):
                cols=range(col2n(m[3]),col2n(m[7] or m[3])+1)
                for r in range(old,last+1):
                    for c in cols:target.auxiliares_originales_necesarios.add((r,n2col(c)))
                return _sh(target.nombre_auxiliar_original)+m[0][len(m[1] or ''):]
            if m[7]:
                a,b=target.range_rows(old,last,incluir_nuevos=True)
                if a is None:return _sh(target.nombre)+'$A$1:$A$1'
                return _sh(target.nombre)+m[2]+m[3]+m[4]+str(a)+':'+m[6]+m[7]+m[8]+str(b)
            new=old if old<=2 else target.mapped(old)
            return _sh(target.nombre)+m[2]+m[3]+m[4]+str(new) if new is not None else '""'
        parts=_STR.split(text)
        for i in range(0,len(parts),2):parts[i]=_REF.sub(one,parts[i])
        result=''.join(parts)
        for token,value in reserved.items():result=result.replace(token,value)
        return result
    with ZipFile(plan.archivo) as z:
        for attempt in range(8):
            pending=needed-set(found)
            if not pending:break
            by_row=defaultdict(set)
            for row,col in pending:by_row[row].add(col)
            progress=False
            for row in _fuente(z,partes):
                old=int(row.get('r'))
                for cell in row:
                    f=cell.find('s:f',NS)
                    if f is not None and f.get('t')=='shared' and f.text:
                        shared[f.get('si')]=(f.text,old,col2n(_col(cell)))
                if old in by_row:
                    copy=E.Element('{'+M+'}row',r=str(old))
                    for cell in row:
                        if _col(cell) in by_row[old]:copy.append(deepcopy(cell))
                    _inline(copy,plan.strings,shared)
                    for cell in copy:
                        col=_col(cell);f=cell.find('s:f',NS)
                        if f is not None and f.text:
                            f.text=formula(f.text)
                            cached=cell.find('s:v',NS)
                            if cached is not None:cell.remove(cached)
                            cell.attrib.pop('t',None)
                        if cell.get('s') is not None:cell.set('s',str(int(cell.get('s'))+plan.styles['cellXfs']))
                        found[old,col]=deepcopy(cell);progress=True
                row.clear()
                while row.getprevious() is not None:del row.getparent()[0]
            if not progress:
                missing=sorted(needed-set(found))[:5]
                raise ValueError('Faltan auxiliares en el original de '+plan.familia+': '+str(missing))
        else:raise ValueError('Dependencias originales RF demasiado profundas; se conserva el archivo anterior.')
    root=E.Element('{'+M+'}worksheet',nsmap={None:M})
    data=E.SubElement(root,'{'+M+'}sheetData');rows={}
    for (old,col),cell in sorted(found.items(),key=lambda item:(item[0][0],col2n(item[0][1]))):
        if old not in rows:rows[old]=E.SubElement(data,'{'+M+'}row',r=str(old))
        rows[old].append(cell)
    return E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)


def fila_auxiliar_5g(plan,old,column,banda,antena):
    """Buscar el auxiliar por puerto/SCS, no por el tamaño de otra banda.

    Cada banda tiene un número distinto de canales y anchos de banda. Un
    desplazamiento de filas desde n1 puede caer en datos sin auxiliares.
    """
    from tecnologias_originales import _fuente,_celda,_value,_col,_norm,_strings
    if not hasattr(plan,'catalogo_auxiliares_5g'):
        targets=defaultdict(list);source={}
        # La copia corta conserva las coordenadas usadas por las fórmulas SAR.
        copia=getattr(plan,'copia_original_sar',None)
        if copia:
            with ZipFile(plan.archivo.parent/copia['archivo']) as z:
                strings=_strings(z)
                for row in _fuente(z,[copia['parte']]):
                    if int(row.get('r'))>2 and any(_col(c)==column and (c.find('s:f',NS) is not None or c.find('s:v',NS) is not None) for c in row):
                        number=int(row.get('r'))
                        metadata=tuple(_value(_celda(row,c),strings) for c in ('G','L','M'))
                        previous=source.get(number-1)
                        rank=previous[3]+1 if previous and previous[:3]==metadata else 0
                        source[number]=metadata+(rank,)
                    row.clear()
                    while row.getprevious() is not None:del row.getparent()[0]
        bands={_norm(v.record.band) for v in plan.registros}
        with ZipFile(plan.archivo) as z:
            strings=_strings(z)
            for band,segment in plan.segmentos.items():
                if _norm(band) not in bands:continue
                for row in _fuente(z,[segment['parte']]):
                    g=_celda(row,'G');formula=g.findtext('s:f',namespaces=NS) if g is not None else ''
                    match=re.search(r'Overview!\$?E\$?(\d+)',formula or '')
                    port=int(match[1])-27 if match else _value(g,strings)
                    scs=_value(_celda(row,'L'),strings);bw=_value(_celda(row,'M'),strings)
                    for cell in row:
                        if _col(cell) in {'CH','CI','CJ','CK','CQ','CR','CS','CT','CZ','DA','DB','DC'} and (cell.find('s:f',NS) is not None or cell.find('s:v',NS) is not None):
                            targets[_norm(band),_col(cell)].append((int(row.get('r')),port,scs,bw))
                    row.clear()
                    while row.getprevious() is not None:del row.getparent()[0]
        plan.catalogo_auxiliares_5g=(targets,source)
    targets,source=plan.catalogo_auxiliares_5g
    choices=targets.get((_norm(banda),column),[])
    if not choices:raise ValueError('No existe el auxiliar original 5G '+str(banda)+' '+column)
    match=re.search(r'Overview!\$?H\$?(\d+)',str(antena))
    wanted=int(match[1])-27 if match else None
    origin=source.get(old)
    if wanted is None and origin:wanted=origin[0]
    if wanted is not None:
        port_choices=[c for c in choices if _norm(c[1])==_norm(wanted)]
        if not port_choices:raise ValueError('No existe el puerto 5G solicitado: '+str(antena))
        choices=port_choices
    if origin:
        exact=[c for c in choices if (_norm(c[2]),_norm(c[3]))==(_norm(origin[1]),_norm(origin[2]))]
        same_scs=[c for c in choices if _norm(c[2])==_norm(origin[1])]
        choices=exact or same_scs or choices
    return choices[min(origin[3],len(choices)-1) if origin else 0][0]
