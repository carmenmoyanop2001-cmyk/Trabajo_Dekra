"""Servicios de la app web; utilizan el mismo generador que el cuestionario local."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
import zipfile

from base_datos import Catalogo
from generador_excel import generar
from validacion_datos import validar_datos


def nombre_seguro(nombre, extension=None):
    nombre = re.split(r'[/\\]', str(nombre))[-1]
    nombre = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', nombre).strip(' .')[:120]
    nombre = nombre or 'Ensayo'
    if re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', nombre, re.I):
        nombre = '_' + nombre
    if extension:
        nombre = Path(nombre).stem + extension
    return nombre


@dataclass
class BaseWeb:
    nombre: str
    contenido: bytes
    catalogo: Catalogo


def cargar_base(contenido, nombre):
    nombre = nombre_seguro(nombre, '.xlsx')
    with tempfile.TemporaryDirectory(prefix='sar_base_') as tmp:
        path = Path(tmp) / nombre
        path.write_bytes(contenido)
        catalogo = Catalogo(path)
    # Catalogo guarda todos los datos en memoria. No necesita conservar la ruta temporal.
    return BaseWeb(nombre, contenido, catalogo)


def respuestas_portables(datos, base):
    salida = deepcopy(datos)
    salida['base_datos'] = base.nombre
    salida['base_datos_sha256'] = base.catalogo.sha256
    return salida


def huella(datos, base):
    contenido = json.dumps(respuestas_portables(datos, base), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(contenido.encode('utf-8')).hexdigest()


def validar(datos, catalogo):
    validar_datos(datos, catalogo=catalogo)
    for clave in ('baterias', 'accesorios', 'spotchecking'):
        nombres = [n.strip().casefold() for n in datos[clave]]
        if len(nombres) != len(set(nombres)):
            raise ValueError(f'{clave}: no repitas nombres.')


def generar_paquete(datos, base):
    """No publica archivos parciales ni comparte carpetas entre sesiones."""
    datos = respuestas_portables(datos, base)
    validar(datos, base.catalogo)
    nombre = nombre_seguro(datos['proyecto'])
    with tempfile.TemporaryDirectory(prefix='sar_excel_') as tmp:
        path = Path(tmp) / (nombre + '.xlsm')
        resumen = generar(datos, path, catalogo=base.catalogo, log=lambda *_: None)
        excel = path.read_bytes()
    respuestas = json.dumps(datos, ensure_ascii=False, indent=2).encode('utf-8')
    texto = ('DATOS DEL ENSAYO\n' + respuestas.decode('utf-8') + '\n\nAVISOS\n' +
             '\n'.join(resumen.get('avisos', [])) + '\n').encode('utf-8')
    archivos = {nombre + '.xlsm': excel, nombre + '.json': respuestas, nombre + '.txt': texto}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        for archivo, contenido in archivos.items():
            z.writestr(archivo, contenido)
        z.writestr(base.nombre, base.contenido)
    return dict(nombre=nombre, excel=excel, respuestas=respuestas, texto=texto,
                zip=buffer.getvalue(), resumen=resumen, huella=huella(datos, base))
