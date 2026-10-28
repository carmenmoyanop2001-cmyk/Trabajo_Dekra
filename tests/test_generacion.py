import copy
from pathlib import Path
import tempfile
import unittest
import zipfile
import json
import subprocess
import sys
from lxml import etree as E

from generador_excel import generar
from validacion_datos import validar_datos
from opciones_ensayo import slots_incluidos

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
BASE = dict(proyecto='Prueba SAR', region='EN', exposure='Body', conducida=False,
            baterias=['Batería principal'], accesorios=['Funda'],
            spotchecking=['Variante A'], tecnologias={'LTE': ['FDD1']})


class GeneracionTests(unittest.TestCase):
    def test_bloques_conducidos_de_cada_region_y_filas_comunes(self):
        from seleccion import plan_conducted
        from sarlib import col2n
        class Sheet:
            name = 'Conducted LTE'
            rows = [(3,), (4,), (5,), (6,), (7,)]
            def kv(self, i):
                return {'J': 'LTE', 'K': 'FDD5' if i < 4 else 'FDD7',
                        'B': ['EN', 'EN', 'FCC/ISED', 'FCC/ISED', 'EN/FCC/ISED'][i]}
        data = dict(BASE, region=['EN', 'FCC', 'ISED'], tecnologias={'LTE': ['FDD5', 'FDD7']})
        items = plan_conducted(Sheet(), data, {'EN': {3}, 'FCC': set()})
        self.assertEqual([item.i for item in items], [0, 1, 2, 3, 4])
        self.assertEqual([item.ovr[col2n('B')] for item in items],
                         ['EN', 'EN', 'FCC/ISED', 'FCC/ISED', 'EN/FCC/ISED'])
        one = plan_conducted(Sheet(), dict(data, region='FCC'))
        both = plan_conducted(Sheet(), dict(data, region=['FCC', 'ISED']))
        self.assertEqual([i.i for i in one], [i.i for i in both])

    def test_enlaces_heredados_sin_hoja_disponible_se_notifican(self):
        # La plantilla FCC LTE FDD5 enlaza DN con CATM1 en algunas filas.
        # Si CATM1 no se selecciona, se debe informar, también con multiselección.
        data = dict(BASE, region=['EN', 'FCC'], exposure=['Close to ear', 'Body'],
                    conducida=True, tecnologias={'LTE': ['FDD5']})
        with tempfile.TemporaryDirectory() as tmp:
            summary = generar(data, Path(tmp) / 'avisos.xlsm', log=lambda *_: None)
        self.assertTrue(summary['sin_resolver'])
        self.assertTrue(any('sin enlace disponible' in w for w in summary['avisos']))

    def test_respuestas_e_informe_interfaz_con_varias_opciones(self):
        from cuestionario_ensayo import App
        from types import SimpleNamespace
        class Var:
            def __init__(self, value): self.value = value
            def get(self): return self.value
        app = SimpleNamespace(
            _nombre_proyecto=lambda: 'Prueba SAR', _marcadas=App._marcadas,
            var_region={r: Var(True) for r in ('EN', 'FCC', 'ISED')},
            var_expo={'Body': Var(True), 'Extremity': Var(True), 'Close to ear': Var(False)},
            var_conducida=Var('Sí'),
            elementos={key: SimpleNamespace(var=Var('No')) for key in ('baterias', 'accesorios', 'spotchecking')},
            tecnologias={'LTE': SimpleNamespace(activa=lambda: True, seleccion=lambda: ['FDD5'],
                                               lineas=lambda: ['- LTE FDD5'])})
        data = App.datos_para_excel(app)
        self.assertEqual(data['region'], ['EN', 'FCC', 'ISED'])
        self.assertEqual(data['exposure'], ['Body', 'Extremity'])
        validar_datos(data)
        text = App._construir_informe(app)
        self.assertIn('Regiones: EN, FCC, ISED', text)
        self.assertIn('Exposure conditions: Body, Extremity', text)
        self.assertEqual(App._validar_general(app), [])
        app.var_region = {}
        app.var_expo = {}
        self.assertEqual(len(App._validar_general(app)), 2)

    def test_slots_interfaz_acumulativos_e_independientes(self):
        from cuestionario_ensayo import Panel2G
        class Var:
            def __init__(self, value): self.value = value
            def get(self): return self.value
            def set(self, value): self.value = value
        class Panel:
            sel = {mode: Var(True) for mode in ('GSM', 'GPRS', 'EGPRS')}
            slot = {mode: Var('') for mode in ('GPRS', 'EGPRS')}
            slot_checks = {mode: {f'TX{n}': Var(False) for n in range(1, 5)}
                           for mode in ('GPRS', 'EGPRS')}
        panel = Panel()
        for mode, maximum in [('GPRS', 3), ('EGPRS', 4)]:
            panel.slot_checks[mode][f'TX{maximum}'].set(True)
            Panel2G._cambiar_slot(panel, mode, f'TX{maximum}')
            self.assertEqual([s for s, v in panel.slot_checks[mode].items() if v.get()],
                             [f'TX{n}' for n in range(1, maximum + 1)])
        selection = Panel2G.seleccion(panel)
        self.assertEqual(selection['GPRS'], ['TX1', 'TX2', 'TX3'])
        self.assertEqual(selection['EGPRS'], ['TX1', 'TX2', 'TX3', 'TX4'])
        self.assertIn('- GPRS TX1', Panel2G.lineas(panel))
        panel.slot_checks['GPRS']['TX2'].set(False)
        Panel2G._cambiar_slot(panel, 'GPRS', 'TX2')
        self.assertEqual(Panel2G.seleccion(panel)['GPRS'], ['TX1'])
        self.assertEqual(Panel2G.seleccion(panel)['EGPRS'], selection['EGPRS'])
        panel.slot_checks['GPRS']['TX1'].set(False)
        Panel2G._cambiar_slot(panel, 'GPRS', 'TX1')
        self.assertEqual(Panel2G.seleccion(panel)['GPRS'], [])
        self.assertTrue(Panel2G.validar(panel))

    def test_validacion_multiseleccion_y_slots_anteriores(self):
        for field in ('region', 'exposure'):
            for invalid in ([], None, ['desconocida'], ['EN', 'EN']):
                with self.subTest(field=field, value=invalid):
                    with self.assertRaises(ValueError):
                        validar_datos(dict(BASE, **{field: invalid}))
        data = dict(BASE, region=['EN', 'FCC', 'ISED'], exposure=['Body', 'Extremity'],
                    tecnologias={'2G': {'GPRS': ['TX1', 'TX2', 'TX3'], 'EGPRS': 'TX2'}})
        validar_datos(data)
        self.assertEqual(slots_incluidos('TX3'), ['TX1', 'TX2', 'TX3'])

    def test_excel_multirregion_exposiciones_y_slots(self):
        data = dict(BASE, region=['EN', 'FCC', 'ISED'],
                    exposure=['Body', 'Close to ear', 'Close to Head', 'Extremity'],
                    conducida=True, tecnologias={'LTE': ['FDD5'], 'LTE CAT M1': ['FDD5'],
                        '2G': {'GPRS': ['TX1', 'TX2', 'TX3'], 'EGPRS': 'TX2'}})
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'multiple.xlsm'
            summary = generar(data, output, log=lambda *_: None)
            self.assertEqual(summary['hojas'].count('SAR FCC-ISED'), 1)
            self.assertIn('SAR EN', summary['hojas'])
            self.assertGreater(summary['filas']['SAR EN'], 0)
            self.assertGreater(summary['filas']['SAR FCC-ISED'], 0)
            self.assertEqual(summary['sin_resolver'], {})
            with zipfile.ZipFile(output) as z:
                wb = E.fromstring(z.read('xl/workbook.xml'))
                rels = {r.get('Id'): r.get('Target') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
                for sheet in wb.findall('s:sheets/s:sheet', NS):
                    name = sheet.get('name')
                    if name not in ('SAR EN', 'SAR FCC-ISED', 'Conducted 2G-3G'):
                        continue
                    rel = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                    root = E.fromstring(z.read('xl/' + rels[rel]))
                    exposures = {}
                    for span in root.xpath('//s:mergeCell/@ref', namespaces=NS):
                        if span.startswith('BX'):
                            first, last = (int(ref[2:]) for ref in span.split(':'))
                            text = ''.join(root.xpath(f'//s:c[@r="BX{first}"]//s:t/text()', namespaces=NS))
                            exposures.update({r: text for r in range(first, last + 1)})
                    records = []
                    for row in root.findall('s:sheetData/s:row', NS)[2:]:
                        records.append({''.join(c for c in cell.get('r') if c.isalpha()):
                            ''.join(cell.xpath('.//s:t/text() | s:v/text()', namespaces=NS)) for cell in row})
                        if not records[-1].get('BX') and int(row.get('r')) in exposures:
                            records[-1]['BX'] = exposures[int(row.get('r'))]
                    if name == 'Conducted 2G-3G':
                        for mode, expected in [('GPRS', {'1', '2', '3'}), ('EGPRS', {'1', '2'})]:
                            self.assertEqual({r.get('X') for r in records if r.get('J') == mode}, expected)
                    else:
                        exposures = {r.get('BX') for r in records}
                        self.assertGreater(len(exposures), 1)
                        self.assertTrue({e.lower() for e in exposures}.issubset({e.lower() for e in data['exposure']}))
                        self.assertTrue(any(r.get('CA', '').startswith('Accesorio') for r in records))
                        for row in records:
                            if row.get('CA', '').startswith('Accesorio') or row.get('CA') == 'Front of Face':
                                self.assertEqual(row.get('BX'), 'Body')

    def test_cli_genera_respuestas_y_no_sobrescribe(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'respuestas.json'
            source.write_text(json.dumps(BASE), encoding='utf-8')
            output = Path(tmp) / 'ensayo.xlsm'
            cmd = [sys.executable, str(Path(__file__).resolve().parents[1] / 'generar_desde_json.py'),
                   str(source), str(output)]
            first = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn('pestañas de tecnologías', output.with_suffix('.txt').read_text(encoding='utf-8'))
            content = output.read_bytes()
            second = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(output.read_bytes(), content)

    def test_rechaza_selecciones_invalidas_sin_tocar_salida(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'datos.xlsm'
            output.write_bytes(b'archivo existente')
            for value in ({'LTE': ['BANDA_INEXISTENTE']}, {'Bluetooth': []},
                          {'LTE': []}, {'2G': {'GSM': False, 'GPRS': None}},
                          {'WLAN': {'5 GHz': {'bandas': ['U-NII-3'], 'modos': ['ax160']}}}):
                with self.subTest(value=value):
                    datos = dict(BASE, tecnologias=value)
                    with self.assertRaises(ValueError):
                        generar(datos, output, log=lambda *_: None)
                    self.assertEqual(output.read_bytes(), b'archivo existente')

    def test_2g_formato_real_interfaz(self):
        from cuestionario_ensayo import Panel2G
        class Var:
            def __init__(self, value): self.value = value
            def get(self): return self.value
        class Panel:
            sel = {'GSM': Var(True), 'GPRS': Var(False), 'EGPRS': Var(False)}
            slot = {'GPRS': Var(''), 'EGPRS': Var('')}
        selection = Panel2G.seleccion(Panel())
        validar_datos(dict(BASE, tecnologias={'2G': selection}))

    def test_fallo_de_plantilla_conserva_excel_previo(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'datos.xlsm'
            output.write_bytes(b'conservar')
            with self.assertRaises(FileNotFoundError):
                generar(BASE, output, dir_plantilla=tmp, log=lambda *_: None)
            self.assertEqual(output.read_bytes(), b'conservar')

    def test_generacion_regiones_y_extras(self):
        with tempfile.TemporaryDirectory() as tmp:
            for region, conducted, exposure in [('EN', False, 'Body'),
                                                ('FCC', True, 'Body'),
                                                ('ISED', True, 'Close to ear')]:
                with self.subTest(region=region):
                    data = copy.deepcopy(BASE)
                    data.update(region=region, conducida=conducted, exposure=exposure,
                                baterias=[f'Batería {i}' for i in range(1, 7)],
                                accesorios=[f'Accesorio {i}' for i in range(1, 9)],
                                spotchecking=['Variante A', 'Variante B', 'Variante C'])
                    if conducted:
                        data['tecnologias'].update({'2G': {'GSM': True}, '3G': ['WCDMA'],
                            'LTE CAT M1': ['FDD1'], 'LTE NB-IoT': ['FDD1'], '5G': ['n78'],
                            'WLAN': {'2,4 GHz': ['b', 'n20']}})
                    output = Path(tmp) / (region + '.xlsm')
                    summary = generar(data, output, log=lambda *_: None)
                    sar = 'SAR EN' if region == 'EN' else 'SAR FCC-ISED'
                    self.assertGreater(summary['filas'][sar], 0)
                    with zipfile.ZipFile(output) as z:
                        workbook = E.fromstring(z.read('xl/workbook.xml'))
                        sheets = workbook.xpath('//s:sheet/@name', namespaces=NS)
                        self.assertIn(sar, sheets)
                        self.assertIn('Overview', sheets)
                        self.assertIn('Test Campaign', sheets)
                        self.assertIn('Tune-Up', sheets)
                        self.assertIn('Conducted LTE' if conducted else 'LTE', sheets)
                        self.assertEqual('Conducted 5G' in sheets, conducted)
                        self.assertIn('xl/vbaProject.bin', z.namelist())
                        ov = E.fromstring(z.read('xl/worksheets/sheet1.xml'))
                        self.assertEqual(ov.xpath('//s:c[@r="E4"]//s:t/text()', namespaces=NS), ['Prueba SAR'])
                        self.assertIn('Batería 6', ov.xpath('//s:t/text()', namespaces=NS))
                        self.assertIn('Accesorio 8', ov.xpath('//s:t/text()', namespaces=NS))
                    if conducted:
                        self.assertEqual(summary['sin_resolver'], {})
                        self.assertTrue(summary['referencias_rotas_plantilla'])
                        self.assertTrue(any('#REF!' in w for w in summary['avisos']))
                    else:
                        self.assertTrue(any('pestañas de tecnologías' in w for w in summary['avisos']))


if __name__ == '__main__':
    unittest.main()
