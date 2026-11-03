"""Separar la copia 5G por bandas, conservando íntegros cabecera, filas y cola.

Es una preparación interna: la app puede leer solo las bandas elegidas sin
descomprimir los cientos de MB de las otras bandas. No consulta la base RF.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

from lxml import etree as E

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tecnologias_originales import _estructura, _q, _col, _value, _strings, _xml
from base_datos import normalizar
from herramientas.completar_original_5g import CompresorPreparacion


def indexar(root):
    folder=root/'plantilla/originales'
    invpath=folder/'inventario.json'
    inventory=json.loads(invpath.read_text(encoding='utf-8'))
    info=inventory['pestanas']['Conducted 5G']
    if info.get('segmentos'):
        print('5G ya está indexada.')
        return
    source=folder/info['archivo']
    candidate=folder/'5g_indexada.tmp'
    parts={}
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(source) as z:
        meta=_estructura(z,info['parte'])
        sd=meta.find('s:sheetData',{'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'})
        strings=_strings(z)
        handles, files, ranges, counts={},{},{},{}
        with z.open(info['parte']) as stream:
            for i,(_,row) in enumerate(E.iterparse(stream,tag=_q('row'))):
                number=int(row.get('r'))
                if number<=2:
                    sd.append(deepcopy(row))
                else:
                    key=_value(next((c for c in row if _col(c)=='K'),None),strings)
                    band=str(key) if key is not None else 'sin_banda'
                    if band not in handles:
                        file=Path(tmp)/(normalizar(band)+'.xml')
                        files[band]=file
                        handles[band]=file.open('wb')
                        handles[band].write(b'<sheetData xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">')
                        ranges[band]=[number,number]
                        counts[band]=0
                    handles[band].write(E.tostring(row))
                    ranges[band][1]=number
                    counts[band]+=1
                row.clear()
                while row.getprevious() is not None:del row.getparent()[0]
                if i and i%40000==0:print(i,'filas indexadas',flush=True)
        for h in handles.values():
            h.write(b'</sheetData>');h.close()
        with zipfile.ZipFile(candidate,'w',zipfile.ZIP_LZMA) as out:
            for name in z.namelist():
                if name==info['parte']:
                    data=_xml(meta)
                    out.writestr(name,data)
                    parts[name]=hashlib.sha256(data).hexdigest()
                else:
                    data=z.read(name)
                    out.writestr(name,data)
                    parts[name]=hashlib.sha256(data).hexdigest()
            segments={}
            for band,file in files.items():
                name='filas/'+file.name
                out.write(file,name)
                h=hashlib.sha256()
                with file.open('rb') as stream:
                    while chunk:=stream.read(1024*1024):h.update(chunk)
                parts[name]=h.hexdigest()
                segments[band]=dict(parte=name,primera=ranges[band][0],ultima=ranges[band][1],filas=counts[band])
    candidate.replace(source)
    info['segmentos']=segments
    inventory['archivos'][info['archivo']]['partes']=parts
    invpath.write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Índice completo:',len(segments),'bandas/variantes;',sum(counts.values()),'filas de datos;',source.stat().st_size,'bytes',flush=True)


if __name__=='__main__':
    zipfile.LZMACompressor=CompresorPreparacion
    indexar(Path(__file__).resolve().parents[1])
