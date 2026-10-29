"""Valores visibles originales, Mode combinado y ausencia de huecos por filtros."""
from pathlib import Path
import json
import lzma
import tempfile
import unittest
import zipfile
from collections import defaultdict
from lxml import etree as E

from generador_excel import generar_heredado as generar, DIR_PLANTILLA
from nucleo import Hoja
from seleccion import plan_conducted
from sarlib import _REF, _STR, _sheetname

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def cells(root):
    return {c.get('r'): c for c in root.findall('s:sheetData/s:row/s:c', NS)}


def value(cell):
    return ''.join(cell.xpath('.//s:t/text() | s:v/text()', namespaces=NS))


class ValoresModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.data = dict(proyecto='Valores conservados', region='EN',
            exposure=['Close to ear', 'Body', 'Extremity'], conducida=True,
            baterias=['B1', 'B2', 'B3'], accesorios=['Acc1', 'Acc2', 'Acc3'], spotchecking=[],
            tecnologias={'2G': {'GSM': True}, 'LTE CAT M1': ['FDD1'], '5G': ['n1']})
        path = Path(cls.temp.name) / 'caso.xlsm'
        cls.summary = generar(cls.data, path, log=lambda *_: None)
        with zipfile.ZipFile(path) as z:
            cls.en = E.fromstring(z.read('xl/worksheets/sheet11.xml'))
            cls.cat = E.fromstring(z.read('xl/worksheets/sheet5.xml'))
            cls.workbook = E.fromstring(z.read('xl/workbook.xml'))
            cls.styles = E.fromstring(z.read('xl/styles.xml'))
        cls.en_cells = cells(cls.en)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def exposure(self, row):
        for span in self.en.xpath('//s:mergeCell/@ref', namespaces=NS):
            if span.startswith('BX'):
                first, last = (int(ref[2:]) for ref in span.split(':'))
                if first <= int(row) <= last:
                    return value(self.en_cells[f'BX{first}'])
        return value(self.en_cells[f'BX{row}'])

    def test_mode_una_celda_por_tecnologia_banda_y_modos_auxiliares_conservados(self):
        groups = defaultdict(list)
        for row in self.en.findall('s:sheetData/s:row', NS)[2:]:
            r = row.get('r')
            groups[(value(self.en_cells['BT' + r]), value(self.en_cells['BU' + r]))].append(int(r))
        merges = [ref for ref in self.en.xpath('//s:mergeCell/@ref', namespaces=NS) if ref.startswith('BY')]
        self.assertEqual(len(merges), len(groups))
        for (tech, band), rows in groups.items():
            self.assertEqual(rows, list(range(rows[0], rows[-1] + 1)))
            self.assertIn(f'BY{rows[0]}:BY{rows[-1]}', merges)
            style = int(self.en_cells[f'BY{rows[0]}'].get('s', '0'))
            alignment = self.styles.find('s:cellXfs', NS)[style].find('s:alignment', NS)
            self.assertEqual(alignment.get('wrapText'), '1')
            self.assertEqual(alignment.get('vertical'), 'center')
            for r in rows[1:]:
                self.assertEqual(value(self.en_cells[f'BY{r}']), '')
            if tech == '5G':
                self.assertIn('TBD', value(self.en_cells[f'BY{rows[0]}']))
                self.assertIn('100% RB', value(self.en_cells[f'BY{rows[0]}']))
                modes = {value(self.en_cells[f'CG{r}']) for r in rows}
                self.assertTrue({'TBD', '100% RB', 'N/A'}.issubset(modes))
        # Nunca se usa el resumen combinado para buscar los canales por modo.
        for node in self.en.xpath('//s:c/s:f', namespaces=NS):
            formula = node.text or ''
            for part in _STR.split(formula)[::2]:
                for m in _REF.finditer(part):
                    if (_sheetname(m.group(1) or '') or 'SAR EN') == 'SAR EN':
                        if m.group(3) == 'BY':
                            self.assertTrue(node.getparent().get('r').startswith('CG'))
                            self.assertIn('BY' + m.group(5), [ref.split(':')[0] for ref in merges])

    def test_canales_frecuencias_y_tbd_guardan_valor_sin_eliminar_formulas(self):
        h = Hoja(str(Path(DIR_PLANTILLA) / 'sar_en.xz'))
        source = {(h.kv(i).get('BT'), h.kv(i).get('BU'), h.kv(i).get('BX'),
                   h.kv(i).get('CC'), h.kv(i).get('CD')) for i in range(len(h.rows))}
        tbd = 0
        for row in self.en.findall('s:sheetData/s:row', NS)[2:]:
            r = row.get('r')
            pos = value(self.en_cells['CA' + r])
            if pos.startswith(('TBD - Battery check ', 'Accesorio ')) or (
                    pos == 'Front Face' and value(self.en_cells['CB' + r]) == '25'):
                continue
            cc, cd = self.en_cells['CC' + r], self.en_cells['CD' + r]
            self.assertIsNotNone(cc.find('s:f', NS))
            self.assertIsNotNone(cd.find('s:f', NS))
            self.assertNotEqual(value(cc), '')
            self.assertNotEqual(value(cd), '')
            self.assertIn((value(self.en_cells['BT' + r]), value(self.en_cells['BU' + r]),
                           self.exposure(r), value(cc), value(cd)), source)
            if pos == 'TBD':
                tbd += 1
                self.assertIsNotNone(self.en_cells['CA' + r].find('s:f', NS))
                self.assertEqual(self.en_cells['CA' + r].get('t'), 'str')
        self.assertGreater(tbd, 0)

    def test_columna_o_catm1_coincide_con_todos_los_valores_del_original(self):
        fixture = Path(__file__).parent / 'fixtures/catm1_columna_o_original.json.xz'
        with lzma.open(fixture, 'rt') as f:
            original = json.load(f)['values']
        h = Hoja(str(Path(DIR_PLANTILLA) / 'cond_catm1.xz'))
        plan = plan_conducted(h, self.data)
        output = cells(self.cat)
        formulas = 0
        for r, item in enumerate(plan, start=3):
            old = str(h.rows[item.i][0])
            self.assertIn(old, original)
            cell = output[f'O{r}']
            self.assertEqual(value(cell), original[old], f'O{r} (original O{old})')
            if cell.find('s:f', NS) is not None:
                formulas += 1
                self.assertIsNotNone(cell.find('s:v', NS))
        self.assertGreater(formulas, 0)

    def test_cache_de_toda_la_columna_o_contra_los_35752_valores_del_excel_original(self):
        from nucleo import valor_formula_original
        from seleccion import _celda
        fixture = Path(__file__).parent / 'fixtures/catm1_columna_o_original.json.xz'
        with lzma.open(fixture, 'rt') as f:
            original = json.load(f)['values']
        h = Hoja(str(Path(DIR_PLANTILLA) / 'cond_catm1.xz'))
        self.assertEqual(len(original), 35752)
        for row, expected in original.items():
            index = h.by_old[int(row)]
            kind, content = _celda(h, index, 'O')
            actual = valor_formula_original(h, index, 'O', content) if kind == 3 else content
            self.assertEqual(actual, expected, f'O{row} del original')

    def test_sin_huecos_ni_exposiciones_no_seleccionadas_y_recalculo_automatico(self):
        rows = self.en.findall('s:sheetData/s:row', NS)
        numbers = [int(r.get('r')) for r in rows]
        self.assertEqual(numbers, list(range(1, len(rows) + 1)))
        for r in numbers[2:]:
            self.assertIn(self.exposure(r), ['Close to Ear', 'Body', 'Extremity'])
        calc = self.workbook.find('s:calcPr', NS)
        self.assertEqual(calc.get('calcMode'), 'auto')
        self.assertEqual(calc.get('fullCalcOnLoad'), '1')
        self.assertEqual(calc.get('forceFullCalc'), '1')


if __name__ == '__main__':
    unittest.main()
