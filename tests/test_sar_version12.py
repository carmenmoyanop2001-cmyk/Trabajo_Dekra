"""Restauración SAR main12 sin alterar el libro de la entrega aprobada."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from lxml import etree as E

from base_datos import Catalogo
from generador_excel import generar
from herramientas.validar_paquete import validar
from restaurar_sar_version12 import aplicar, _pestanas, _crear, NS
from comparacion_sar import estilos_equivalentes, normalizar_estilos

ROOT = Path(__file__).resolve().parents[1]


class FuentesTests(unittest.TestCase):
    def test_procedimiento_version12_copiado_literalmente(self):
        meta = json.loads((ROOT/'docs/fuentes_sar_version12.json').read_text())
        path = ROOT/'sar_version12_motor.py'
        source = path.read_text()
        node = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name == '_sar')
        self.assertEqual(hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest(),
                         meta['fuentes']['sar_version12_motor.py:_sar'])
        self.assertEqual(hashlib.sha256((ROOT/'sar_version12_canales.py').read_bytes()).hexdigest(),
                         meta['fuentes']['sar_version12_canales.py'])


class SustitucionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.tmp.name)
        cls.cat = Catalogo()
        cls.data = dict(proyecto='Restauración SAR 12', region=['EN', 'FCC', 'ISED'],
            exposure=['Close to ear', 'Body'], conducida=True,
            baterias=['B1', 'B2', 'B3'], accesorios=['Funda'], spotchecking=[],
            tecnologias={'2G': {'GSM': True}, '3G': {'WCDMA': ['FDDI', 'FDDII']}})
        cls.before, cls.after = cls.folder/'antes.xlsm', cls.folder/'despues.xlsm'
        with patch('restaurar_sar_version12.aplicar'):
            cls.summary = generar(cls.data, cls.before, catalogo=cls.cat, log=lambda *_: None)
        shutil.copyfile(cls.before, cls.after)
        aplicar(cls.after, cls.data, cls.cat, ROOT/'plantilla', cls.summary)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_todas_las_partes_ajenas_a_sar_son_identicas(self):
        with ZipFile(self.before) as before, ZipFile(self.after) as after:
            names = _pestanas(before)
            permitted = {names['SAR EN'], names['SAR FCC-ISED'],
                         'xl/styles.xml', 'xl/workbook.xml'}
            self.assertEqual(set(before.namelist()), set(after.namelist()))
            for name in before.namelist():
                if name not in permitted:
                    self.assertEqual(before.read(name), after.read(name), name)
            for name in ('SAR EN', 'SAR FCC-ISED'):
                self.assertNotEqual(before.read(names[name]), after.read(names[name]), name)

    def test_estilos_previos_inmutables_y_calculo_aprobado(self):
        with ZipFile(self.before) as before, ZipFile(self.after) as after:
            a, b = (E.fromstring(z.read('xl/styles.xml')) for z in (before, after))
            for group in a:
                actual = b.find(group.tag)
                self.assertGreaterEqual(len(actual), len(group))
                for x, y in zip(group, actual):
                    self.assertEqual(E.tostring(x, method='c14n', exclusive=True),
                                     E.tostring(y, method='c14n', exclusive=True))
            a, b = (E.fromstring(z.read('xl/workbook.xml')) for z in (before, after))
            for root in (a, b):
                for node in root.findall('s:definedNames/s:definedName', NS):
                    if re.match(r"'SAR (EN|FCC-ISED)'!", node.text or ''):
                        node.text = 'FILTRO SAR'
            self.assertEqual(E.tostring(a, method='c14n'), E.tostring(b, method='c14n'))
            self.assertEqual(b.find('s:calcPr', NS).get('forceFullCalc'), '0')

    def test_sar_recupera_contenido_y_estilos_de_su_procedimiento(self):
        donor, styles, counts, _ = _crear(self.data, self.cat, ROOT/'plantilla',
                                          self.folder, ['SAR EN', 'SAR FCC-ISED'])
        old_styles = estilos_equivalentes(styles)
        with ZipFile(self.after) as z:
            new_styles = estilos_equivalentes(z)
            names = _pestanas(z)
            for name in donor:
                old, new = E.fromstring(donor[name]), E.fromstring(z.read(names[name]))
                for root, palette in ((old, old_styles), (new, new_styles)):
                    cols = root.find('s:cols', NS)
                    if cols is not None:
                        root.remove(cols)
                    normalizar_estilos(root, palette)
                self.assertEqual(E.tostring(old, method='c14n', exclusive=True),
                                 E.tostring(new, method='c14n', exclusive=True), name)
                self.assertEqual(self.summary['filas'][name], counts[name])

    def test_paquete_sin_referencias_de_formula_invalidas(self):
        self.assertEqual(validar(self.after, verbose=False), [])
        self.assertTrue(self.summary['sar_version12']['resto_del_paquete_identico'])

    def test_una_region_sin_conducida_y_overview_con_baterias_adicionales(self):
        for region, expected in [('EN', 'SAR EN'), ('FCC', 'SAR FCC-ISED')]:
            with self.subTest(region=region):
                data = deepcopy(self.data)
                data.update(region=[region], conducida=False, baterias=['B']*6,
                            tecnologias={'2G': {'GSM': True}})
                out = self.folder/('individual_' + region + '.xlsm')
                summary = generar(data, out, catalogo=self.cat, log=lambda *_: None)
                with ZipFile(out) as z:
                    names = _pestanas(z)
                    self.assertEqual(set(names) & {'SAR EN', 'SAR FCC-ISED'}, {expected})
                    root = E.fromstring(z.read(names[expected]))
                    formulas = [f.text or '' for f in root.findall('.//s:f', NS)]
                    self.assertFalse(any("'Conducted " in f for f in formulas))
                    self.assertIn('2G', names)
                    self.assertEqual(summary['sar_version12']['pestanas'], [expected])
                self.assertEqual(validar(out, verbose=False), [])


if __name__ == '__main__':
    unittest.main()
