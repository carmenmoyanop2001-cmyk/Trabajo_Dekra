"""Crear una entrega completa sin cachés, entornos ni ejemplos Excel antiguos."""
from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def empaquetar(output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    files = list(ROOT.glob('*.py'))
    files += [ROOT / name for name in ('INICIAR_CUESTIONARIO.bat', 'LEEME_PRIMERO.txt',
                                      'requirements.txt', 'README.md', 'USO_AUTOMATICO.md',
                                      'DIAGNOSTICO_CIERRE_EXCEL.bat')]
    for folder in ('plantilla', 'datos', 'docs'):
        files += [p for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += list((ROOT / 'ejemplos').glob('*.json'))
    files += list((ROOT / 'herramientas').glob('*.py'))
    with ZipFile(output, 'w', ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(set(files)):
            z.write(p, Path('Trabajo_Dekra_escritorio') / p.relative_to(ROOT))
    return output


if __name__ == '__main__':
    path = empaquetar(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'entregas/Trabajo_Dekra_escritorio.zip')
    print(f'{path}: {path.stat().st_size / 2**20:.1f} MiB')
