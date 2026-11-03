"""Comentarios de las tecnologías: relación hoja → VML → celda de la nota."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from lxml import etree as E

from base_datos import Catalogo
from generador_excel import generar, _generar
from herramientas.validar_paquete import validar
from presentacion_tecnologias import PROTEGIDAS
from test_tecnologias_visibles import workbook

ROOT = Path(__file__).resolve().parents[1]
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


class ComentariosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.tmp.name)
        cls.path = cls.folder / 'ensayo.xlsm'
        cls.before = cls.folder / 'antes.xlsm'
        cls.data = json.loads((ROOT / 'ejemplos/ejemplo_tecnologias_ordenadas.json').read_text())
        cls.catalogo = Catalogo()
        _generar(cls.data, str(cls.before), catalogo=cls.catalogo, log=lambda *_: None)
        generar(cls.data, cls.path, catalogo=cls.catalogo, log=lambda *_: None)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def mutar(self, part, transform, nombre):
        target = self.folder / nombre
        with zipfile.ZipFile(self.path) as source, zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as out:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == part:
                    root = E.fromstring(data)
                    transform(root)
                    data = E.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
                out.writestr(deepcopy(info), data)
        return target

    def test_comentarios_y_hojas_protegidas_se_conservan(self):
        self.assertEqual(validar(self.path, verbose=False), [])
        before, after = workbook(self.before), workbook(self.path)
        with zipfile.ZipFile(self.before) as old, zipfile.ZipFile(self.path) as new:
            for nombre in PROTEGIDAS:
                self.assertEqual(old.read(before[nombre][0]), new.read(after[nombre][0]), nombre)
            for part in old.namelist():
                if '/comments' in part or part.endswith('.vml') or part.startswith('xl/media/') or part == 'xl/vbaProject.bin':
                    self.assertEqual(old.read(part), new.read(part), part)
            self.assertEqual(old.read('xl/drawings/drawing2.xml'), new.read('xl/drawings/drawing2.xml'))
            # Renombrar 2G-3G no debe dejar la nota en una copia de apoyo sin relaciones.
            part = after['2G-3G'][0]
            hoja = E.fromstring(new.read(part))
            self.assertEqual(hoja.find('s:legacyDrawing', NS).get('{' + R + '}id'), 'rId3')

    def test_detecta_el_fallo_del_registro_de_excel(self):
        def quitar(root):
            root.remove(root.find('s:legacyDrawing', NS))
        corrupto = self.mutar('xl/worksheets/sheet3.xml', quitar, 'sin_enlace.xlsm')
        errores = validar(corrupto, verbose=False)
        self.assertTrue(any('sheet3.xml: comentarios sin enlace legacyDrawing' in e for e in errores), errores)

    def test_detecta_enlace_a_relacion_incorrecta(self):
        def cambiar(root):
            root.find('s:legacyDrawing', NS).set('{' + R + '}id', 'rId4')  # comentarios, no VML
        corrupto = self.mutar('xl/worksheets/sheet3.xml', cambiar, 'id_incorrecto.xlsm')
        self.assertTrue(any('comentarios sin enlace legacyDrawing' in e for e in validar(corrupto, verbose=False)))

    def test_detecta_formas_desplazadas(self):
        def mover(root):
            root.find('.//{urn:schemas-microsoft-com:office:excel}Row').text = '999'
        corrupto = self.mutar('xl/drawings/vmlDrawing2.vml', mover, 'forma_desplazada.xlsm')
        self.assertTrue(any('celdas de los comentarios y sus formas VML no coinciden' in e
                            for e in validar(corrupto, verbose=False)))


if __name__ == '__main__':
    unittest.main()
