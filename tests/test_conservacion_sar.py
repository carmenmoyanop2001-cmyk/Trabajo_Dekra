"""Regresiones: conservar FCC y ampliar EN sin borrar ni sobrescribir originales."""
from pathlib import Path
import tempfile
import unittest
import zipfile
from lxml import etree as E

from generador_excel import generar, DIR_PLANTILLA
from nucleo import Hoja
from sarlib import n2col

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
DATA = dict(proyecto='Conservación SAR', region=['EN', 'FCC'], exposure='Body',
            conducida=False, baterias=[], accesorios=[], spotchecking=[],
            tecnologias={'LTE': ['FDD5'], 'LTE CAT M1': ['FDD5']})


def cell_map(row):
    return {''.join(ch for ch in c.get('r') if ch.isalpha()): c for c in row}


def value(cell):
    return ''.join(cell.xpath('.//s:t/text() | s:v/text()', namespaces=NS))


class ConservacionTests(unittest.TestCase):
    def test_reglas_de_formato_y_validacion_incluyen_filas_insertadas(self):
        from nucleo import _remap_range_rows
        # La antigua fila 11 aparece en la salida en 4 y se copia en 5 y 6.
        # La antigua fila 12 se desplaza a 7, sin ser sobrescrita.
        rows = {10: 3, 11: 4, 12: 7}
        clones = [(11, 5), (11, 6)]
        self.assertEqual(_remap_range_rows('CA10:CD12', sorted(rows), rows, clones), ['CA3:CD7'])
        self.assertEqual(_remap_range_rows('CA11', sorted(rows), rows, clones), ['CA4:CA6'])
        self.assertEqual(_remap_range_rows('CA12', sorted(rows), rows, clones), ['CA7'])

    def test_fcc_solo_filtra_y_conserva_posiciones_formulas_y_estilos(self):
        h = Hoja(str(Path(DIR_PLANTILLA) / 'sar_fcc.xz'))
        # Filtro independiente del plan del generador, sobre las filas de origen.
        original = [i for i, r in enumerate(h.rows) if r[0] > 2 and
                    h.kv(i).get('BT') in ('LTE', 'LTE CATM1') and
                    h.kv(i).get('BU') == 'FDD5' and h.kv(i).get('BX') == 'Body']
        with tempfile.TemporaryDirectory() as tmp:
            sheet_versions = []
            for extra in (False, True):
                data = dict(DATA, baterias=['Batería A', 'Batería B'] if extra else [],
                            accesorios=['Funda'] if extra else [],
                            spotchecking=['No añadir Variability'] if extra else [])
                path = Path(tmp) / f'{extra}.xlsm'
                generar(data, path, log=lambda *_: None)
                with zipfile.ZipFile(path) as z:
                    sheet_versions.append(z.read('xl/worksheets/sheet12.xml'))
                    with zipfile.ZipFile(Path(DIR_PLANTILLA) / 'plantilla_base.zip') as base:
                        old_styles = E.fromstring(base.read('xl/styles.xml'))
                        new_styles = E.fromstring(z.read('xl/styles.xml'))
                        for tag in ('fonts', 'fills', 'borders', 'numFmts'):
                            self.assertEqual(E.tostring(old_styles.find('s:' + tag, NS)),
                                             E.tostring(new_styles.find('s:' + tag, NS)))
                        old_xfs, new_xfs = old_styles.find('s:cellXfs', NS), new_styles.find('s:cellXfs', NS)
                        for old, new in zip(old_xfs, new_xfs):
                            self.assertEqual(E.tostring(old), E.tostring(new))
            self.assertEqual(sheet_versions[0], sheet_versions[1])
            rows = E.fromstring(sheet_versions[0]).findall('s:sheetData/s:row', NS)[2:]
            self.assertEqual(len(rows), len(original))
            for row, index in zip(rows, original):
                src = h.rows[index]
                actual = cell_map(row)
                self.assertEqual(set(actual), {n2col(c[0]) for c in h.templates[src[1]]})
                const_index = 0
                for ci, style, kind, payload in h.templates[src[1]]:
                    col = n2col(ci)
                    cell = actual[col]
                    self.assertEqual(int(cell.get('s', '0')), style)
                    if kind in (1, 2, 9, 10):
                        self.assertEqual(value(cell), h.cpool[src[2][const_index]][1])
                        const_index += 1
                    if kind == 3 and col == 'CA':
                        self.assertIsNotNone(cell.find('s:f', NS))

    def test_en_inserta_debajo_sin_variability_y_con_formato_superior(self):
        h = Hoja(str(Path(DIR_PLANTILLA) / 'sar_en.xz'))
        original = [i for i, r in enumerate(h.rows) if r[0] > 2 and
                    h.kv(i).get('BT') in ('LTE', 'LTE CATM1') and
                    h.kv(i).get('BU') == 'FDD5' and h.kv(i).get('BX') == 'Body']
        data = dict(DATA, baterias=[f'Batería {n}' for n in range(1, 8)],
                    accesorios=[f'Funda {n}' for n in range(1, 9)],
                    spotchecking=['No debe crear Variability'])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'en.xlsm'
            generar(data, path, log=lambda *_: None)
            with zipfile.ZipFile(path) as z:
                rows = E.fromstring(z.read('xl/worksheets/sheet11.xml')).findall('s:sheetData/s:row', NS)[2:]
        unchanged = []
        batteries = accessories = 0
        for i, row in enumerate(rows):
            cells = cell_map(row)
            pos = value(cells['CA'])
            self.assertNotIn('Variability', pos)
            added = pos.startswith(('TBD-Battery check ', 'Accesorio ')) or (pos == 'Front Face' and value(cells['CB']) == '25')
            if added:
                previous = cell_map(rows[i - 1])
                self.assertEqual({c: e.get('s') for c, e in cells.items()},
                                 {c: e.get('s') for c, e in previous.items()})
                for col in ('CC', 'CD', 'DB'):
                    self.assertIsNotNone(cells[col].find('s:f', NS))
                if pos.startswith('TBD-Battery check '): batteries += 1
                if pos.startswith('Accesorio '): accessories += 1
            else:
                unchanged.append(row)
        self.assertEqual(len(unchanged), len(original))
        # Todos los originales permanecen en orden; las inserciones desplazan
        # las filas siguientes y se conservan las posiciones y fórmulas previas.
        from seleccion import _celda
        for row, index in zip(unchanged, original):
            kind, src_pos = _celda(h, index, 'CA')
            cell = cell_map(row)['CA']
            if kind == 2:
                self.assertEqual(value(cell), src_pos)
            elif kind == 3:
                self.assertIsNotNone(cell.find('s:f', NS))
        self.assertGreater(batteries, 7)
        self.assertEqual(batteries // 7, accessories // 8)
        self.assertEqual(len({row.get('r') for row in rows}), len(rows))

    def test_hojas_de_todas_las_tecnologias_incluso_sin_conducidos(self):
        data = dict(DATA, tecnologias={'2G': {'GSM': True}, '3G': ['WCDMA'],
                    'LTE': ['FDD5'], 'LTE CAT M1': ['FDD5'], 'LTE NB-IoT': ['FDD5'],
                    '5G': ['n78'], 'WLAN': {'2,4 GHz': ['b']}})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'todas.xlsm'
            summary = generar(data, path, log=lambda *_: None)
        for name in ('2G-3G', 'LTE', 'LTE CATM1', 'LTE NB-IoT', '5G', 'WiFi'):
            self.assertIn(name, summary['hojas'])
            self.assertGreater(summary['filas'][name], 0)


if __name__ == '__main__':
    unittest.main()
