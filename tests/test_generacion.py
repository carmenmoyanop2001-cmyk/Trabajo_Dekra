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

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
BASE = dict(proyecto='Prueba SAR', region='EN', exposure='Body', conducida=False,
            baterias=['Batería principal'], accesorios=['Funda'],
            spotchecking=['Variante A'], tecnologias={'LTE': ['FDD1']})


class GeneracionTests(unittest.TestCase):
    def test_cli_genera_respuestas_y_no_sobrescribe(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'respuestas.json'
            source.write_text(json.dumps(BASE), encoding='utf-8')
            output = Path(tmp) / 'ensayo.xlsm'
            cmd = [sys.executable, str(Path(__file__).resolve().parents[1] / 'generar_desde_json.py'),
                   str(source), str(output)]
            first = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn('potencias', output.with_suffix('.txt').read_text(encoding='utf-8'))
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
                        self.assertEqual('Tune-Up' in sheets, conducted)
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
                        self.assertTrue(any('potencias' in w for w in summary['avisos']))


if __name__ == '__main__':
    unittest.main()
