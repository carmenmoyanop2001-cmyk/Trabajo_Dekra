"""Generación sin interfaz: python generar_desde_json.py respuestas.json salida.xlsm."""
import argparse
import json
import os
from pathlib import Path
import tempfile

from generador_excel import generar
from validacion_datos import validar_datos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('respuestas', type=Path)
    parser.add_argument('salida', type=Path)
    args = parser.parse_args()
    if args.salida.suffix.lower() != '.xlsm':
        parser.error('La salida debe tener extensión .xlsm.')
    if args.salida.exists() or args.salida.with_suffix('.txt').exists():
        parser.error('La salida ya existe; elige otro nombre para conservar tus archivos.')
    try:
        datos = json.loads(args.respuestas.read_text(encoding='utf-8'))
        validar_datos(datos)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    # Validar antes de publicar el archivo final; no dejar un Excel parcial.
    with tempfile.TemporaryDirectory(dir=args.salida.parent) as tmp:
        candidate = Path(tmp) / 'datos.xlsm'
        resumen = generar(datos, str(candidate))
        os.replace(candidate, args.salida)
    avisos = '\n'.join(resumen.get('avisos', []))
    args.salida.with_suffix('.txt').write_text(
        'DATOS DEL ENSAYO\n' + json.dumps(datos, ensure_ascii=False, indent=2) + '\n\nAVISOS\n' + avisos + '\n',
        encoding='utf-8')
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
