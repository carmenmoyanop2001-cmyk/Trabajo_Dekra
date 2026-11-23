"""Copiar las fórmulas de SAR EN; adaptar exclusivamente sus referencias."""
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile
import re
from lxml import etree as E
from nucleo import Hoja
from seleccion import _celda, _tipo_extra
from sarlib import expand, _REF, _STR, _sheetname, n2col

M='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS={'s':M}


def estructura(xml):
    """Permitir cambios de contenido conservando celdas, estilos y diseño."""
    root=E.fromstring(xml)
    for cell in root.findall('s:sheetData/s:row/s:c',NS):
        for child in list(cell):cell.remove(child)
        cell.attrib.pop('t',None)
    return E.tostring(root,method='c14n',exclusive=True)


def restaurar(xml,planes,plantilla,overview=None):
    from tecnologias_originales import _norm
    from sar_en_canales import _groups,_source_value,adaptar_formula
    from auxiliares_originales import referencia_sar
    from hojas_base_datos import indice_tune_up
    folder=Path(plantilla)
    path=folder/'formatos/sar_en.xz'
    if not path.exists():path=folder/'sar_en.xz'
    source=Hoja(str(path));root=E.fromstring(xml)
    by_key=defaultdict(list);prototypes={}
    for i in range(2,len(source.rows)):
        v=source.kv(i)
        key=(v.get('BT'),_norm(v.get('BU')),str(v.get('BX')).casefold())
        by_key[key].append(i)
    for (tech,band,exposure),indices in by_key.items():
        if len({source.kv(i).get('CA') for i in indices}-{None,'','TBD'})>1:
            prototypes.setdefault((tech,exposure),indices)
    tune={}
    if (folder/'plantilla_base.zip').exists():
        with ZipFile(folder/'plantilla_base.zip') as z:tune=indice_tune_up(z)
    blocks=[];maps=defaultdict(dict)
    for key,block in _groups(root):
        tech,band,ant,tx,exposure=key
        indices=by_key.get((tech,_norm(band),str(exposure).casefold())) or prototypes.get((tech,str(exposure).casefold()))
        if not indices:raise ValueError('El original SAR EN no contiene procedimiento para '+str(key))
        own=[i for i in indices if _source_value(source,i,'BV')==ant]
        if not own:raise ValueError('El original SAR EN no contiene la antena '+str(ant))
        positions=defaultdict(list)
        for i in own:
            if not _tipo_extra(source,i):positions[str(source.kv(i).get('CA')or'')].append(i)
        counts=defaultdict(int);assign=[]
        for number,position,kind,cells in block:
            if kind:
                # Las filas adicionales mantienen la posición indicada por el
                # cuestionario y usan el procedimiento TBD del propio EN.
                matches=positions.get('TBD')or own[-1:]
                i=matches[-1]
            else:
                matches=positions.get(position,[])
                if not matches:raise ValueError('No hay posición original SAR EN: '+str(position))
                ordinal=counts[position];counts[position]+=1
                if ordinal>=len(matches):raise ValueError('Posición SAR EN repetida sin un modelo original: '+str(position))
                i=matches[ordinal]
                maps[tech,_norm(band)][source.rows[i][0]]=number
            assign.append((i,number,kind,cells))
        blocks.append((key,own,indices,assign))
    report=[]
    def expanded(i,col):
        kind,pattern=_celda(source,i,col)
        return (kind,expand(pattern,source.rows[i][0],lambda s,r,role:r,source.name)) if kind==3 else (kind,pattern)
    for key,own,indices,assign in blocks:
        tech,band,ant,tx,exposure=key
        mapping=maps[tech,_norm(band)]
        for i,number,kind,cells in assign:
            old=source.rows[i][0]
            for ci,style,cell_kind,payload in source.templates[source.rows[i][1]]:
                col=n2col(ci);cell=cells.get(col)
                if cell is None or col in ('BT','BU','BX'):continue
                if kind and col in ('CA','CB'):continue
                k,text=expanded(i,col);formula_source_row=old
                formula_mapping=mapping
                if k==3 and (not text or '#REF!'in text):
                    # Recuperar un enlace perdido de la misma posición de EN;
                    # no utilizar fórmulas de FCC ni construir otros cálculos.
                    position=source.kv(i).get('CA')
                    position_rows=[a for a in own if source.kv(a).get('CA')==position]
                    ordinal=position_rows.index(i)
                    peer_ports={_source_value(source,a,'BV') for a in indices}
                    peers=[]
                    for port in sorted(peer_ports,key=str):
                        candidates=[a for a in indices if _source_value(source,a,'BV')==port and source.kv(a).get('CA')==position]
                        if ordinal<len(candidates):peers.append(candidates[ordinal])
                    for j in peers:
                        peer_kind,candidate=expanded(j,col)
                        if peer_kind==3 and candidate and '#REF!'not in candidate:
                            text=candidate;formula_source_row=source.rows[j][0]
                            other=[a for a in indices if _source_value(source,a,'BV')==_source_value(source,j,'BV')]
                            formula_mapping=dict(mapping)
                            for a,b in zip(other,own):
                                if source.rows[b][0]in mapping:formula_mapping[source.rows[a][0]]=mapping[source.rows[b][0]]
                            break
                    else:raise ValueError('La fórmula original SAR EN está rota: '+col+str(old))
                if k==3:
                    def masters(m):
                        if _sheetname(m[1]) not in ('',source.name):return m[0]
                        if not m[7] and m[3]=='CP'and int(m[5])==3 and 3 not in formula_mapping:
                            master_kind,master=expanded(source.by_old[3],'CP')
                            if master_kind!=3:raise ValueError('Falta la fórmula maestra CP3 de SAR EN.')
                            return '('+master+')' if col=='CP' and number==3 else '__SAR_ORIGINAL_MAESTRO_CP__'
                        if m[7] and m[3]==m[7]=='CR'and int(m[5])==3 and int(m[9])==formula_source_row-1:
                            return '__SAR_ORIGINAL_PREFIJO_CR__'
                        return m[0]
                    pieces=_STR.split(text)
                    for part in range(0,len(pieces),2):pieces[part]=_REF.sub(masters,pieces[part])
                    text=''.join(pieces)
                    text=referencia_sar(text,planes,band,ant)
                    text=adaptar_formula(text,formula_mapping,formula_source_row,number,'SAR EN',origen='SAR EN')
                    text=text.replace('__SAR_ORIGINAL_MAESTRO_CP__','$CP$3')
                    text=text.replace('__SAR_ORIGINAL_PREFIJO_CR__',f'$CR$3:CR{number-1}'if number>3 else '$CR$1:CR1')
                    target_tune=tune.get((tech,str(band)))
                    def foreign(m):
                        sheet=_sheetname(m[1])
                        if sheet=='Tune-Up'and target_tune is not None:
                            return m[1]+m[2]+m[3]+m[4]+str(target_tune)
                        if sheet=='Overview'and overview is not None:
                            out=m[1]+m[2]+m[3]+m[4]+str(overview(int(m[5])))
                            if m[7]:out+=':'+m[6]+m[7]+m[8]+str(overview(int(m[9])))
                            return out
                        return m[0]
                    pieces=_STR.split(text)
                    for part in range(0,len(pieces),2):pieces[part]=_REF.sub(foreign,pieces[part])
                    text=''.join(pieces)
                for child in list(cell):cell.remove(child)
                cell.attrib.pop('t',None)
                if k==3:
                    E.SubElement(cell,'{'+M+'}f').text=text
                    E.SubElement(cell,'{'+M+'}v')
                    report.append((col+str(number),col+str(formula_source_row)))
                elif k==1 and text is not None:E.SubElement(cell,'{'+M+'}v').text=str(text)
                elif k==2 and text is not None:
                    cell.set('t','inlineStr');E.SubElement(E.SubElement(cell,'{'+M+'}is'),'{'+M+'}t').text=str(text)
                elif k not in (0,1,2):raise ValueError('Tipo original SAR EN no soportado: '+str(k))
    result=E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
    if estructura(xml)!=estructura(result):raise ValueError('La restauración de fórmulas ha cambiado el formato SAR EN.')
    return result,len(report)
