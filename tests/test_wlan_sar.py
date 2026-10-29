"""SAR WLAN reserva modos TBD; Conducted sí filtra el modo concreto elegido."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from lxml import etree as E
from generador_excel import generar, DIR_PLANTILLA
from nucleo import Hoja
from seleccion import pred_sar, pred_conducted, plan_sar

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
ROOT = Path(__file__).resolve().parents[1]


def text(cell):
    return ''.join(cell.xpath('.//s:t/text() | s:v/text()', namespaces=NS))


class WlanSarTests(unittest.TestCase):
    def test_seleccion_de_la_captura_genera_sar_y_tecnologias(self):
        data = json.loads((ROOT / 'ejemplos/ejemplo_seleccion_wlan_sar.json').read_text(encoding='utf-8'))
        before = json.dumps(data, sort_keys=True)
        source = Hoja(str(Path(DIR_PLANTILLA) / 'sar_en.xz'))
        expected = [i for i, r in enumerate(source.rows) if r[0] > 2 and
                    source.kv(i).get('BT') == 'WLAN' and source.kv(i).get('BU') == '2.4 GHz' and
                    source.kv(i).get('BX', '').lower() == 'close to ear']
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'seleccion.xlsm'
            summary = generar(data, output, log=lambda *_: None)
            self.assertTrue(output.exists())
            for name in ('Conducted 2G-3G', 'Conducted LTE CATM1', 'Conducted LTE NB-IoT', 'Conducted WiFi'):
                self.assertGreater(summary['filas'][name], 0)
            with zipfile.ZipFile(output) as z:
                sar = E.fromstring(z.read('xl/worksheets/sheet11.xml'))
                wifi = E.fromstring(z.read('xl/worksheets/sheet8.xml'))
        self.assertEqual(json.dumps(data, sort_keys=True), before)
        positions = []
        batteries = set()
        for row in sar.findall('s:sheetData/s:row', NS)[2:]:
            cells = {''.join(c for c in cell.get('r') if c.isalpha()): cell for cell in row}
            self.assertEqual(text(cells['BT']), 'WLAN')
            self.assertEqual(text(cells['BU']), '2.4 GHz')
            if text(cells['BX']):
                self.assertEqual(text(cells['BX']).lower(), 'close to ear')
            position = text(cells['CA'])
            if position.startswith('TBD-Battery check '):
                batteries.add(position)
            else:
                positions.append(position)
        self.assertEqual(len(positions), len(expected))
        self.assertGreater(len(expected), 0)
        self.assertEqual(batteries, {'TBD-Battery check 1', 'TBD-Battery check 2'})
        # No aparecen modos ajenos a la selección en Conducted WiFi.
        modes = set()
        from seleccion import token_modo
        for row in wifi.findall('s:sheetData/s:row', NS)[2:]:
            cells = {''.join(c for c in cell.get('r') if c.isalpha()): cell for cell in row}
            self.assertEqual(text(cells['K']), '2.4 GHz')
            modes.add(token_modo(text(cells['S']), text(cells['M'])))
        self.assertEqual(modes, {'n40', 'ac40'})

    def test_plantillas_wlan_solo_banda_y_exposicion_sin_duplicados(self):
        for filename, family in [('sar_en.xz', 'EN'), ('sar_fcc.xz', 'FCC')]:
            h = Hoja(str(Path(DIR_PLANTILLA) / filename))
            for band, selection in [('2.4 GHz', {'2,4 GHz': ['b']}),
                                    ('2.4 GHz', {'2,4 GHz': ['n40', 'ac40']}),
                                    ('U-NII-1', {'5 GHz': {'bandas': ['U-NII-1'], 'modos': ['ac80']}})]:
                with self.subTest(filename=filename, band=band, selection=selection):
                    data = dict(exposure=['Close to ear'], baterias=[], accesorios=[],
                                tecnologias={'WLAN': selection})
                    expected = [i for i, r in enumerate(h.rows) if r[0] > 2 and
                                h.kv(i).get('BT') == 'WLAN' and h.kv(i).get('BU') == band and
                                h.kv(i).get('BX', '').lower() == 'close to ear']
                    plan = plan_sar(h, family, data)
                    self.assertGreater(len(expected), 0)
                    self.assertEqual([it.i for it in plan if not it.clone], expected)
                    self.assertEqual(len(plan), len(expected))

    def test_modos_concretos_son_estrictos_y_tbd_no_se_aplica_a_conducted(self):
        data = dict(exposure='Body', tecnologias={'WLAN': {'2,4 GHz': ['n40']}})
        base = dict(BT='WLAN', BU='2.4 GHz', BX='Body', BY='802.11n', BZ='40')
        self.assertTrue(pred_sar(base, data))
        for change in ({'BZ': '20'}, {'BU': 'U-NII-1'}, {'BX': 'Extremity'}):
            self.assertFalse(pred_sar(dict(base, **change), data))
        for mode in (None, '', 'TBD', 'TBD / NA', 'N/A'):
            self.assertTrue(pred_sar(dict(base, BY=mode, BZ=mode), data))
            self.assertFalse(pred_sar(dict(base, BY=mode), dict(data, tecnologias={})))
            self.assertFalse(pred_conducted('Conducted WiFi', dict(K='2.4 GHz', S=mode, M='40'),
                                            data['tecnologias']))


if __name__ == '__main__':
    unittest.main()
