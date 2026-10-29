"""Reduce las plantillas a filas de formato reutilizables sin el catálogo RF.

Se ejecuta al preparar el programa, no al cargar una base del usuario.
Cada archivo se procesa en un proceso aislado para limitar la memoria.
"""
import lzma
from pathlib import Path
import pickle
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nucleo import Hoja


def guardar(source, target):
    h = Hoja(str(source))
    rows, seen = [], set()
    for row in h.rows:
        keep = row[0] <= 2 or h.name.startswith('SAR ')
        if not keep:
            metadata = {k: h.cpool[v][1] for k, v in row[4] if k in ('J', 'K', 'B', 'BT')}
            key = tuple(metadata.get(k) for k in ('J', 'K', 'B', 'BT'))
            keep = key not in seen
            seen.add(key)
        if keep:
            rows.append(row)
    template_ids = {r[1] for r in rows}
    templates, tmap, patterns, pmap, pool, cmap = [], {}, [], {}, [], {}
    def constant(old):
        if old not in cmap:
            cmap[old] = len(pool)
            pool.append(h.cpool[old])
        return cmap[old]
    for tid in sorted(template_ids):
        tmap[tid] = len(templates)
        cells = []
        for col, style, kind, payload in h.templates[tid]:
            if kind == 3:
                if payload not in pmap:
                    pmap[payload] = len(patterns)
                    patterns.append(h.patterns[payload])
                payload = pmap[payload]
            cells.append((col, style, kind, payload))
        templates.append(tuple(cells))
    compact = []
    from array import array
    for old, tid, values, aid, metadata in rows:
        compact.append((old, tmap[tid], array('I', (constant(c) for c in values)), aid,
                        tuple((k, constant(v)) for k, v in metadata)))
    sd = dict(h.sd, rows=compact, templates=templates, patterns=patterns, cpool=pool, formula_cache={})
    target.parent.mkdir(parents=True, exist_ok=True)
    with lzma.open(target, 'wb') as f:
        pickle.dump(sd, f, protocol=4)
    print(h.name, len(h.rows), '→', len(rows), flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 3:
        guardar(Path(sys.argv[1]), Path(sys.argv[2]))
    else:
        root = Path(__file__).resolve().parents[1] / 'plantilla'
        for file in sorted(root.glob('*.xz')):
            subprocess.run([sys.executable, __file__, str(file), str(root / 'formatos' / file.name)], check=True)
