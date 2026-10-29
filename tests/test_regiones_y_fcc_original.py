"""Selecciones nuevas: presencia real de SAR y conservación de FCC-ISED."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from lxml import etree as E
import generador_excel as gen
from nucleo import Hoja
from sarlib import n2col

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
DATA = dict(proyecto='Regiones SAR', region=['EN', 'FCC'], exposure=['Body', 'Close to ear'],
            conducida=True, baterias=['B1', 'B2'], accesorios=['Funda'], spotchecking=[],
            tecnologias={'2G': {'GSM': True}, 'LTE': ['FDD2', 'FDD5']})


def value(cell):
    return ''.join(cell.xpath('.//s:t/text() | s:v/text()', namespaces=NS))


class RegionesFccTests(unittest.TestCase):
    def test_las_siete_combinaciones_de_regiones_generan_las_hojas_solicitadas(self):
        cases = [(['EN'], {'SAR EN'}), (['FCC'], {'SAR FCC-ISED'}),
                 (['ISED'], {'SAR FCC-ISED'}), (['EN', 'FCC'], {'SAR EN', 'SAR FCC-ISED'}),
                 (['EN', 'ISED'], {'SAR EN', 'SAR FCC-ISED'}),
                 (['FCC', 'ISED'], {'SAR FCC-ISED'}),
                 (['EN', 'FCC', 'ISED'], {'SAR EN', 'SAR FCC-ISED'})]
        with tempfile.TemporaryDirectory() as tmp:
            for n, (regions, expected) in enumerate(cases):
                with self.subTest(regions=regions):
                    output = Path(tmp) / 'regiones.xlsm'
                    summary = gen.generar(dict(DATA, region=regions, conducida=bool(n % 2)),
                                          output, log=lambda *_: None)
                    with zipfile.ZipFile(output) as z:
                        wb = E.fromstring(z.read('xl/workbook.xml'))
                        sheets = {s.get('name'): s for s in wb.findall('s:sheets/s:sheet', NS)}
                    self.assertEqual(set(sheets) & {'SAR EN', 'SAR FCC-ISED'}, expected)
                    for name in expected:
                        self.assertGreater(summary['filas'][name], 0)
                        self.assertEqual(sheets[name].get('state', 'visible'), 'visible')

    def test_no_publica_excel_si_una_hoja_solicitada_falta_o_esta_oculta(self):
        original = gen._generar
        for problem in ('missing', 'hidden'):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / 'anterior.xlsm'
                output.write_bytes(b'Excel anterior intacto')

                def damaged(data, path, *args):
                    summary = original(data, path, *args)
                    with zipfile.ZipFile(path) as z:
                        parts = {name: z.read(name) for name in z.namelist()}
                    wb = E.fromstring(parts['xl/workbook.xml'])
                    sheet = wb.xpath('//s:sheet[@name="SAR EN"]', namespaces=NS)[0]
                    if problem == 'missing':
                        sheet.getparent().remove(sheet)
                        for name in wb.findall('s:definedNames/s:definedName', NS):
                            if (name.text or '').startswith("'SAR EN'!"):
                                name.getparent().remove(name)
                    else:
                        sheet.set('state', 'hidden')
                    parts['xl/workbook.xml'] = E.tostring(wb)
                    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
                        for name, data in parts.items():
                            z.writestr(name, data)
                    return summary

                with patch.object(gen, '_generar', side_effect=damaged):
                    with self.assertRaisesRegex(ValueError, 'hojas SAR|oculta'):
                        gen.generar(dict(DATA, region='EN'), output, log=lambda *_: None)
                self.assertEqual(output.read_bytes(), b'Excel anterior intacto')

    def test_fcc_conserva_ceros_formulas_estilos_y_filas_sin_anadir_baterias(self):
        data = dict(DATA, region='FCC', exposure=['Body', 'Close to ear'])
        source = Hoja(str(Path(gen.DIR_PLANTILLA) / 'sar_fcc.xz'))
        original = [i for i, row in enumerate(source.rows) if row[0] > 2 and
                    source.kv(i).get('BT') in ('GSM', 'LTE') and
                    (source.kv(i).get('BT') == 'GSM' or source.kv(i).get('BU') in ('FDD2', 'FDD5')) and
                    source.kv(i).get('BX') in ('Body', 'Close to Ear')]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'fcc.xlsm'
            gen.generar(data, output, log=lambda *_: None)
            with zipfile.ZipFile(output) as z:
                root = E.fromstring(z.read('xl/worksheets/sheet12.xml'))
        rows = root.findall('s:sheetData/s:row', NS)[2:]
        self.assertEqual(len(rows), len(original))
        self.assertTrue(any('Variability' in value(c) for row in rows for c in row if c.get('r').startswith('CA')))
        self.assertEqual(root.xpath('//s:mergeCell/@ref', namespaces=NS), [])
        for row, index in zip(rows, original):
            cells = {''.join(x for x in c.get('r') if x.isalpha()): c for c in row}
            old = source.rows[index][0]
            # El límite 1 g de origen tiene resultado guardado 0, conservando
            # su fórmula, en lugar de mostrarse vacío hasta recalcular.
            self.assertEqual(value(cells['CZ']), '0')
            self.assertIsNotNone(cells['CZ'].find('s:f', NS))
            for colnum, style, kind, payload in source.templates[source.rows[index][1]]:
                cell = cells[n2col(colnum)]
                self.assertEqual(int(cell.get('s', '0')), style)
                if kind == 3 and cell.find('s:f', NS) is not None and n2col(colnum) in source.sd['formula_cache'].get(old, {}):
                    self.assertEqual(value(cell), source.sd['formula_cache'][old][n2col(colnum)])


if __name__ == '__main__':
    unittest.main()
