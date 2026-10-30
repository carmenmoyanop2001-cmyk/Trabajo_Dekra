"""Presentación de tecnologías sin modificar las siete pestañas protegidas."""
from pathlib import Path
import re
import tempfile
import unittest
import zipfile
import openpyxl

from lxml import etree as E

from base_datos import Catalogo
from generador_excel import generar, _generar
from nombres_hojas import renombrar_tecnologias
from presentacion_tecnologias import PROTEGIDAS, columnas_necesarias
from sarlib import col2n
from test_base_datos import database
from tablas_helpers import table, NS


def workbook(path):
    with zipfile.ZipFile(path) as z:
        root = E.fromstring(z.read('xl/workbook.xml'))
        rels = {r.get('Id'): r.get('Target') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        result = {}
        for s in root.findall('s:sheets/s:sheet', NS):
            target = rels[s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            part = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            result[s.get('name')] = (part, s.get('state', 'visible'))
        return result


class TecnologiasVisiblesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.tmp.name)
        cls.db = cls.folder / 'base.xlsx'
        head = ['Tecnología', 'Banda', 'Canal', 'Frecuencia (MHz)', 'Región', 'Bandwidth (MHz)',
                'Modulation', 'UL RB Allocation', 'UL RB Start', 'Narrowband Index', 'SCS (kHz)',
                'Mode', 'Notas', 'Campo adicional', 'Segundo adicional']
        rows = [
            ['GSM', '900', 37, 897.4, 'EN'], ['GSM', '850', 190, 836.6, 'FCC/ISED'],
            ['GPRS 1TX', '900', 37, 897.4, 'EN'], ['GPRS 2TX', '900', 37, 897.4, 'EN'],
            ['EGPRS 1TX', '900', 37, 897.4, 'EN'],
            ['WCDMA', 'FDDI', 9612, 1922.4, 'EN'], ['HSDPA', 'FDDI', 9612, 1922.4, 'EN'],
            ['LTE', 'FDD1', 123456, 9001.25, 'EN', 7.5, 'QAM_NUEVA', 3, 2, None, 12.5, 'Modo A', None, 'Solo de la base', 17],
            ['LTE', 'FDD1', 123456, 9001.25, 'EN', 7.5, 'QAM_NUEVA', 3, 2, None, 12.5, 'Modo A', None, 'Solo de la base', 19],
            ['LTE CAT M1', 'FDD1', 18000, 1920, 'EN', 10, 'QPSK', 1, 0, 0, 15],
            ['LTE NB-IoT', 'FDD1', 18000, 1920, 'EN', 0.2, 'QPSK', 1, 0, 0, 3.75],
            ['5G', 'n77', 630000, 3450, 'EN', None, None, None, None, None, None, None, '=SUM(1,2)'],
            ['WLAN', '2.4 GHz', 1, 2412, 'EN'], ['BT', '2.4 GHz', 0, 2402, 'EU/FCC/ISED'],
        ]
        database(cls.db, rows, headers=head)
        cls.catalogo = Catalogo(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def data(self, technologies, conducted=True):
        return dict(proyecto='Tablas organizadas', region=['EN', 'FCC', 'ISED'], exposure=['Body'],
                    conducida=conducted, baterias=['B1'], accesorios=['Funda'], spotchecking=[],
                    tecnologias=technologies, base_datos=str(self.db))

    def check_protected(self, data, before, after):
        result = _generar(data, str(before), log=lambda *_: None, catalogo=self.catalogo)
        if not data['conducida']:
            names = {s: s.removeprefix('Conducted ') for s in result['hojas'] if s.startswith('Conducted ')}
            renombrar_tecnologias(before, names)
        final = generar(data, after, catalogo=self.catalogo, log=lambda *_: None)
        old_names, new_names = workbook(before), workbook(after)
        with zipfile.ZipFile(before) as old, zipfile.ZipFile(after) as new:
            for name in PROTEGIDAS:
                self.assertEqual(old.read(old_names[name][0]), new.read(new_names[name][0]), name)
            for part in old.namelist():
                if part.startswith('xl/media/') or part in ('xl/vbaProject.bin', 'xl/drawings/drawing2.xml'):
                    self.assertEqual(old.read(part), new.read(part), part)
            old_styles, new_styles = E.fromstring(old.read('xl/styles.xml')), E.fromstring(new.read('xl/styles.xml'))
            for group in old_styles:
                copied = new_styles.find(group.tag)
                self.assertGreaterEqual(len(copied), len(group))
                for a, b in zip(group, copied):
                    self.assertEqual(E.tostring(a, method='c14n', exclusive=True), E.tostring(b, method='c14n', exclusive=True))
            roots = {name: E.fromstring(old.read(part)) for name, (part, _) in old_names.items()}
            techs = {n: None for n in old_names if n not in PROTEGIDAS}
            needed = columnas_necesarias(roots, techs)
            for name, columns in needed.items():
                # El nombre anterior sigue resolviendo las mismas celdas,
                # incluso si es una hoja auxiliar oculta tras renombrar 2G.
                self.assertIn(name, new_names)
                current = E.fromstring(new.read(new_names[name][0]))
                old_cells = {c.get('r'): c for c in roots[name].findall('s:sheetData/s:row/s:c', NS)
                             if col2n(re.sub(r'\d', '', c.get('r'))) in columns}
                current_cells = {c.get('r'): c for c in current.findall('s:sheetData/s:row/s:c', NS)}
                for address, cell in old_cells.items():
                    self.assertEqual(E.tostring(cell, method='c14n', exclusive=True),
                                     E.tostring(current_cells[address], method='c14n', exclusive=True), (name, address))
                from tablas_tecnologias import nombre_visible
                original_name = name if data['conducida'] else 'Conducted ' + name
                display = nombre_visible(original_name, data)
                visible = E.fromstring(new.read(new_names[display][0]))
                self.assertEqual(roots[name].find('s:sheetPr', NS).get('codeName'),
                                 visible.find('s:sheetPr', NS).get('codeName'))
                if display != name:
                    self.assertIsNone(current.find('s:sheetPr', NS).get('codeName'))
        self.assertEqual(set(final['pestanas_protegidas_identicas']), PROTEGIDAS)
        return final

    def test_nombres_2g_3g_y_proteccion_con_y_sin_conducidos(self):
        cases = [({'2G': {'GSM': True, 'GPRS': 'TX2', 'EGPRS': 'TX1'}}, '2G'),
                 ({'3G': {'WCDMA': ['FDDI'], 'HSDPA': ['FDDI']}}, '3G'),
                 ({'2G': {'GSM': True}, '3G': {'WCDMA': ['FDDI']}}, '2G-3G')]
        for n, (technologies, expected) in enumerate(cases):
            for conducted in (True, False):
                with self.subTest(name=expected, conducted=conducted):
                    before = self.folder / f'antes{n}{conducted}.xlsm'
                    after = self.folder / f'despues{n}{conducted}.xlsm'
                    result = self.check_protected(self.data(technologies, conducted), before, after)
                    self.assertIn(expected, result['hojas'])
                    fields, rows = table(after, 3)
                    self.assertEqual(fields, ['Región', 'Tecnología', 'Banda', 'Canal', 'Frecuencia (MHz)'])
                    if '2G' in technologies:
                        self.assertEqual({r['Banda'] for r in rows if r['Tecnología'] == 'GSM'}, {'850', '900'})
                        if technologies['2G'].get('GPRS'):
                            self.assertEqual({r['Tecnología'] for r in rows if r['Tecnología'].startswith('GPRS')}, {'GPRS 1TX', 'GPRS 2TX'})

    def test_lte_y_otras_tablas_solo_informacion_de_base(self):
        technologies = {'LTE': ['FDD1'], 'LTE CAT M1': ['FDD1'], 'LTE NB-IoT': ['FDD1'],
                        '5G': ['n77'], 'WLAN': {'2,4 GHz': ['n20', 'n40']}, 'BT': ['2.4 GHz']}
        before, after = self.folder / 'todos_antes.xlsm', self.folder / 'todos_despues.xlsm'
        result = self.check_protected(self.data(technologies), before, after)
        fields, rows = table(after, 4)
        self.assertEqual(rows[0]['Banda'], 'FDD1')
        self.assertEqual(rows[0]['Canal'], 123456)
        self.assertEqual(rows[0]['Frecuencia (MHz)'], 9001.25)
        self.assertEqual(rows[0]['Bandwidth (MHz)'], 7.5)
        self.assertEqual(rows[0]['Modulation'], 'QAM_NUEVA')
        self.assertEqual(rows[0]['Campo adicional'], 'Solo de la base')
        self.assertEqual(rows[0]['Segundo adicional'], 17)
        self.assertEqual({r['Segundo adicional'] for r in rows}, {17, 19})
        self.assertNotIn('Narrowband Index', fields)
        self.assertFalse(any('Power' in f for f in fields))
        wifi_fields, wifi_rows = table(after, 8)
        self.assertNotIn('Mode', wifi_fields)  # No inventar modos ausentes en el XLSX.
        self.assertEqual(len(wifi_rows), 1)
        fields5g, rows5g = table(after, 7)
        self.assertNotIn('Bandwidth (MHz)', fields5g)
        self.assertEqual(rows5g[0]['Notas'], '=SUM(1,2)')
        self.assertEqual(result['filas']['Conducted WiFi'], 1)
        book = openpyxl.load_workbook(after, read_only=True, data_only=False)
        for row in book['Conducted LTE'].iter_rows(min_row=1, max_row=2, min_col=1, max_col=5):
            for cell in row:
                self.assertEqual(cell.font.color.type, 'rgb')
                self.assertEqual(cell.font.color.rgb, 'FF000000')
        book.close()
