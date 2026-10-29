"""Producción: el XLSX editable alimenta RF; Tune-Up conserva el original."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import zipfile
from lxml import etree as E

from base_datos import Catalogo
from generador_excel import generar, DIR_PLANTILLA
from nucleo import Hoja

M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS = {'s': M}
ROOT = Path(__file__).resolve().parents[1]
HEAD = ['Tecnología', 'Banda', 'Canal', 'Frecuencia (MHz)', 'Bandwidth (MHz)',
        'Modulation', 'UL RB Allocation', 'UL RB Start', 'Narrowband Index', 'SCS (kHz)', 'Mode']
DATA = dict(proyecto='Prueba de catálogo editable', region=['EN', 'FCC'], exposure=['Close to ear', 'Body'],
            conducida=True, baterias=['B1', 'B2'], accesorios=['Funda'], spotchecking=[],
            tecnologias={'LTE': ['FDD101']})


def database(path, rows, sheet='Datos', headers=HEAD):
    """XLSX mínimo real, sin depender de un escritor de terceros en las pruebas."""
    from sarlib import n2col
    root = E.Element('{' + M + '}worksheet', nsmap={None: M})
    sd = E.SubElement(root, '{' + M + '}sheetData')
    for rn, values in enumerate([headers] + rows, 1):
        row = E.SubElement(sd, '{' + M + '}row', r=str(rn))
        for cn, value in enumerate(values, 1):
            if value is None:
                continue
            c = E.SubElement(row, '{' + M + '}c', r=n2col(cn) + str(rn))
            if isinstance(value, (int, float)):
                E.SubElement(c, '{' + M + '}v').text = str(value)
            else:
                c.set('t', 'inlineStr')
                E.SubElement(E.SubElement(c, '{' + M + '}is'), '{' + M + '}t').text = str(value)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('xl/worksheets/sheet1.xml', E.tostring(root))
        z.writestr('xl/workbook.xml', f'<workbook xmlns="{M}" xmlns:r="{R}"><sheets><sheet name="{sheet}" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="' + R + '/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="' + R + '/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')


def sheet(path, number):
    with zipfile.ZipFile(path) as z:
        return E.fromstring(z.read(f'xl/worksheets/sheet{number}.xml'))


def cells(row):
    return {''.join(x for x in c.get('r') if x.isalpha()): c for c in row}


def value(c):
    return ''.join(c.xpath('.//s:t/text() | s:v/text()', namespaces=NS))


class BaseDatosTests(unittest.TestCase):
    def test_base_recibida_detalles_lte_alias_y_narrowband_scs(self):
        cat = Catalogo()
        self.assertEqual(len(cat.by_tech['WLAN']), 73)  # Wifi no duplica WLAN.
        self.assertEqual(len(cat.by_tech['LTE CAT M1']), 8840)
        self.assertTrue(any(r.channel == 389000 and r.frequency == 1945 for r in cat.by_tech['5G']))
        self.assertEqual(cat.by_tech['LTE CAT M1'][0].params['nb_index'], 0)
        self.assertEqual(cat.by_tech['LTE NB-IoT'][0].params['scs'], 3.75)
        self.assertEqual(cat.by_tech['LTE'][0].params['bw'], 20)

    def test_editar_base_cambia_tecnologias_y_sar_con_tuneup_intacta(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'datos.xlsx'
            outputs = []
            for offset, bw in [(0, 7.5), (1000, 9)]:
                records = [['LTE', 'FDD101', ch, fr + offset, bw, 'QAM_NUEVA', 3, 2, None, 12.5, mode]
                           for ch, fr, mode in [(123456, 9001.25, 'Modo A'), (123457, 9010.5, 'Modo B'), (123458, 9020.75, 'Modo C')]]
                database(db, records)
                output = Path(tmp) / f'generado_{offset}.xlsm'
                result = generar(dict(DATA, base_datos=str(db)), output, log=lambda *_: None)
                self.assertEqual(result['filas']['Conducted LTE'], 3)
                self.assertEqual(result['base_datos']['archivo'], 'datos.xlsx')
                data = sheet(output, 4).findall('s:sheetData/s:row', NS)[2:]
                self.assertEqual({value(cells(r)['T']) for r in data}, {'123456', '123457', '123458'})
                self.assertEqual({float(value(cells(r)['U'])) for r in data}, {9001.25 + offset, 9010.5 + offset, 9020.75 + offset})
                for row in data:
                    c = cells(row)
                    self.assertEqual(value(c['K']), 'FDD101')
                    self.assertEqual(float(value(c['M'])), bw)
                    self.assertEqual(value(c['N']), 'QAM_NUEVA')
                    self.assertEqual(value(c['Q']), '3')
                    self.assertEqual(value(c['L']), '12.5')
                    self.assertEqual(value(c['AH']), '')  # Sin medidas antiguas.
                # Los desplegables no RF siguen formando parte del formato.
                validations = sheet(output, 4).find('s:dataValidations', NS)
                self.assertIsNotNone(validations)
                self.assertTrue(any(v.get('sqref') == 'AG3:AG5' for v in validations))
                for number in (11, 12):
                    sar = sheet(output, number)
                    for row in sar.findall('s:sheetData/s:row', NS)[2:]:
                        c = cells(row)
                        self.assertEqual(value(c['BU']), 'FDD101')
                        self.assertIn(float(value(c['CD'])), {r[3] for r in records})
                        self.assertEqual(float(value(c['BZ'])), bw)
                    if number == 11:
                        mode = sar.find('s:sheetData/s:row/s:c[@r="BY3"]/s:f', NS)
                        self.assertIsNotNone(mode)
                        self.assertIn('INDEX(', mode.text)
                        self.assertIn('$S$', mode.text)
                        positions = {c.get('r'): c for c in sar.findall('s:sheetData/s:row/s:c', NS)
                                     if c.get('r').startswith('CA')}
                        batteries = [c for c in positions.values() if ' - Battery check ' in value(c)]
                        self.assertTrue(batteries)
                        for battery in batteries:
                            import re
                            ref = re.search(r'CONCATENATE\((CA\d+),', battery.find('s:f', NS).text)[1]
                            self.assertEqual(value(positions[ref]), 'TBD')
                            self.assertIsNotNone(positions[ref].find('s:f', NS))
                with zipfile.ZipFile(output) as z, zipfile.ZipFile(Path(DIR_PLANTILLA) / 'plantilla_base.zip') as stored:
                    for number in (2, 10, 13, 14):
                        part = f'xl/worksheets/sheet{number}.xml'
                        self.assertEqual(z.read(part), stored.read(part))
                outputs.append(result['base_datos']['sha256'])
            self.assertNotEqual(outputs[0], outputs[1])

    def test_no_recupera_parametros_ausentes_del_excel_antiguo(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / '5g.xlsx'
            database(db, [['5G', 'n301', 654321, 6789.5]])
            output = Path(tmp) / '5g.xlsm'
            result = generar(dict(DATA, base_datos=str(db), tecnologias={'5G': ['n301']}), output, log=lambda *_: None)
            row = cells(sheet(output, 7).findall('s:sheetData/s:row', NS)[2])
            for col in ('L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'V', 'W'):
                self.assertEqual(value(row[col]), '', col)
                self.assertIsNone(row[col].find('s:f', NS), col)
            self.assertEqual(value(row['K']), 'n301')
            self.assertEqual(value(row['U']), '6789.5')
            self.assertTrue(any('ausentes quedan vacíos' in w for w in result['avisos']))

    def test_banda_eliminada_registro_invalido_y_no_sobrescritura(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, output = Path(tmp) / 'datos.xlsx', Path(tmp) / 'conservar.xlsm'
            output.write_bytes(b'Excel previo')
            for rows in ([['LTE', 'FDD1', 10, 1000]], [['LTE', 'FDD101', 10, 'NaN']], [['LTE', 'FDD101', None, 1000]]):
                database(db, rows)
                with self.assertRaises(ValueError):
                    generar(dict(DATA, base_datos=str(db)), output, log=lambda *_: None)
                self.assertEqual(output.read_bytes(), b'Excel previo')

    def test_funciona_sin_plantillas_de_datos_heredados_ni_excel_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, pack = Path(tmp) / 'base.xlsx', Path(tmp) / 'formatos_programa'
            pack.mkdir()
            shutil.copy(Path(DIR_PLANTILLA) / 'plantilla_base.zip', pack)
            shutil.copytree(Path(DIR_PLANTILLA) / 'formatos', pack / 'formatos')
            database(db, [['LTE', 'FDD101', 42, 4567.5]])
            output = Path(tmp) / 'sin_original.xlsm'
            generar(dict(DATA, base_datos=str(db)), output, dir_plantilla=pack, log=lambda *_: None)
            self.assertTrue(output.is_file())

    def test_cli_base_nueva_y_respuestas_portables(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, source, output = (Path(tmp) / s for s in ('actualizada.xlsx', 'respuestas.json', 'ensayo.xlsm'))
            database(db, [['LTE', 'FDD101', 321, 5678.25]])
            source.write_text(json.dumps(dict(DATA, base_datos='/referencia/antigua.xlsx')), encoding='utf-8')
            result = subprocess.run([sys.executable, str(ROOT / 'generar_desde_json.py'), str(source), str(output),
                                     '--base-datos', str(db)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('actualizada.xlsx', output.with_suffix('.txt').read_text(encoding='utf-8'))
            self.assertEqual(value(cells(sheet(output, 4).findall('s:sheetData/s:row', NS)[2])['U']), '5678.25')

    def test_panel_2g_acumula_slots_y_conserva_bandas_y_carga(self):
        from formulario_bd import Panel2GCatalogo, PanelCatalogo
        class V:
            def __init__(self, value=False): self.v = value
            def get(self): return self.v
            def set(self, v): self.v = v
        class B:
            def __init__(self, bands): self.bands = bands
            def seleccion(self): return self.bands
            def cargar(self, bands): self.bands = bands
            def actualizar(self, available): pass
        p = SimpleNamespace(sel={m: V() for m in ('GSM', 'GPRS', 'EGPRS')},
            slots={m: {f'TX{n}': V() for n in range(1, 5)} for m in ('GPRS', 'EGPRS')},
            bandas_modo={m: B(['900']) for m in ('GSM', 'GPRS', 'EGPRS')},
            _disponibles=lambda mode: ['900', '850'], _mostrar=lambda mode: None)
        p.slots['GPRS']['TX3'].set(True)
        Panel2GCatalogo._cambiar(p, 'GPRS', 'TX3')
        data = Panel2GCatalogo.seleccion(p)
        self.assertEqual(data['GPRS'], ['TX1', 'TX2', 'TX3'])
        self.assertEqual(data['bandas_por_modo'], {'GPRS': ['900']})
        Panel2GCatalogo.cargar(p, dict(data, GSM=True, bandas=['900']))
        self.assertTrue(p.sel['GSM'].get())
        generic = SimpleNamespace(entrada=B([]), modos_guardados=[],
            lbl_modos=SimpleNamespace(configure=lambda **_: None, pack=lambda **_: None))
        PanelCatalogo.cargar(generic, dict(bandas=['FDD101'], modos=['Nuevo modo']))
        self.assertEqual(PanelCatalogo.seleccion(generic), dict(bandas=['FDD101'], modos=['Nuevo modo']))

    def test_todas_las_familias_se_llenan_desde_la_base_recibida(self):
        data = dict(DATA, tecnologias={'2G': {'GSM': True, 'GPRS': 'TX3', 'bandas': ['900']},
            '3G': {'WCDMA': ['FDDI']}, 'LTE': ['FDD1'], 'LTE CAT M1': ['FDD1'],
            'LTE NB-IoT': ['FDD1'], '5G': ['n2'], 'WLAN': ['2.4 GHz'], 'BT': ['2.4 GHz']})
        cat = Catalogo()
        selected = cat.seleccionar(data)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'familias.xlsm'
            result = generar(data, output, log=lambda *_: None)
            self.assertEqual(result['sin_resolver'], {})
            self.assertEqual(set(result['hojas']), {'Overview', 'Tune-Up', 'Validations', 'SAR EN', 'SAR FCC-ISED',
                'Test Campaign', 'Pretesting-Others', 'Conducted 2G-3G', 'Conducted LTE', 'Conducted LTE CATM1',
                'Conducted LTE NB-IoT', 'Conducted 5G', 'Conducted WiFi', 'Conducted BT-Custom'})
            from hojas_base_datos import hoja_tecnologia
            numbers = {'Conducted 2G-3G': 3, 'Conducted LTE': 4, 'Conducted LTE CATM1': 5,
                       'Conducted LTE NB-IoT': 6, 'Conducted 5G': 7, 'Conducted WiFi': 8, 'Conducted BT-Custom': 9}
            for name, number in numbers.items():
                expected = [r for r in selected if hoja_tecnologia(r.tech) == name]
                rows = sheet(output, number).findall('s:sheetData/s:row', NS)[2:]
                self.assertEqual(len(rows), len(expected))
                self.assertEqual({(value(cells(r)['K']), float(value(cells(r)['T'])), float(value(cells(r)['U']))) for r in rows},
                                 {(r.band, r.channel, r.frequency) for r in expected})
            gprs_slots = {value(cells(r)['X']) for r in sheet(output, 3).findall('s:sheetData/s:row', NS)[2:]
                          if value(cells(r)['J']) == 'GPRS'}
            self.assertEqual(gprs_slots, {'1', '2', '3'})
            bt_validations = sheet(output, 9).find('s:dataValidations', NS)
            self.assertIsNotNone(bt_validations)
            self.assertTrue(any('AG' in v.get('sqref', '') for v in bt_validations))
            bt_formats = sheet(output, 9).xpath('//s:conditionalFormatting/@sqref', namespaces=NS)
            self.assertTrue(any('CB' in ref for ref in bt_formats))

    def test_las_regiones_respetan_la_seleccion_con_la_fuente_nueva(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'datos.xlsx'
            database(db, [['GSM', '900', 37, 897.4]])
            cases = [(['EN'], {'SAR EN'}), (['FCC'], {'SAR FCC-ISED'}), (['ISED'], {'SAR FCC-ISED'}),
                     (['EN', 'FCC'], {'SAR EN', 'SAR FCC-ISED'}), (['EN', 'ISED'], {'SAR EN', 'SAR FCC-ISED'}),
                     (['FCC', 'ISED'], {'SAR FCC-ISED'}), (['EN', 'FCC', 'ISED'], {'SAR EN', 'SAR FCC-ISED'})]
            for n, (regions, expected) in enumerate(cases):
                output = Path(tmp) / f'region{n}.xlsm'
                result = generar(dict(DATA, base_datos=str(db), region=regions, conducida=bool(n % 2),
                                      tecnologias={'2G': {'GSM': True, 'bandas': ['900']}}), output, log=lambda *_: None)
                self.assertEqual({s for s in result['hojas'] if s.startswith('SAR ')}, expected)
                with zipfile.ZipFile(output) as z, zipfile.ZipFile(Path(DIR_PLANTILLA) / 'plantilla_base.zip') as source:
                    self.assertEqual(z.read('xl/worksheets/sheet2.xml'), source.read('xl/worksheets/sheet2.xml'))

    def test_seleccion_vacia_no_expande_todas_las_bandas(self):
        cat = Catalogo()
        with self.assertRaises(ValueError):
            cat.seleccionar(dict(DATA, tecnologias={'LTE': {'bandas': []}}))


if __name__ == '__main__':
    unittest.main()
