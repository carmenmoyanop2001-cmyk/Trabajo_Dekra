"""Opciones como texto, entrada numérica y bandas 2G independientes."""
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
import zipfile
from lxml import etree as E

from entradas_bandas import resolver_bandas, opciones_bandas
from base_datos import Catalogo
from validacion_datos import validar_datos


class BandasTextoTests(unittest.TestCase):
    def test_numeros_prefijos_romanos_y_bandas_nuevas(self):
        self.assertEqual(resolver_bandas('850, 900, 850', ['850', '900']), ['850', '900'])
        self.assertEqual(resolver_bandas('1, 3, 38, 101', ['FDD1', 'FDD3', 'TDD38', 'FDD101']), ['FDD1', 'FDD3', 'TDD38', 'FDD101'])
        self.assertEqual(resolver_bandas('77, n78', ['n77', 'n78']), ['n77', 'n78'])
        self.assertEqual(resolver_bandas('1, 3, 11', ['FDDI', 'FDDIII', 'FDDXI']), ['FDDI', 'FDDIII', 'FDDXI'])
        self.assertEqual(resolver_bandas('FDD 1, tdd1', ['FDD1', 'TDD1']), ['FDD1', 'TDD1'])

    def test_rechaza_vacio_desconocido_y_numero_ambiguo(self):
        for text, bands in [('', ['FDD1']), ('2', ['FDD1']), ('1', ['FDD1', 'TDD1'])]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                resolver_bandas(text, bands)

    def test_opciones_visibles_se_pueden_escribir_sin_ambiguedad(self):
        for bands in [['FDD1', 'FDD3', 'TDD38'], ['FDDI', 'FDDIII'], ['n77', 'n78'],
                      ['FDD1', 'TDD1'], ['850', '900'], ['2.4 GHz']]:
            displayed = opciones_bandas(bands)
            self.assertEqual(resolver_bandas(', '.join(displayed), bands), bands)
        self.assertEqual(opciones_bandas(['FDD1', 'FDD3', 'TDD38']), ['1', '3', '38'])

    def test_bandas_por_modo_se_reflejan_en_el_excel(self):
        from generador_excel import generar
        data = dict(proyecto='Bandas independientes por modo 2G', region=['EN', 'FCC'], exposure=['Body'],
                    conducida=True, baterias=[], accesorios=[], spotchecking=[],
                    tecnologias={'2G': {'GSM': True, 'GPRS': 'TX3', 'EGPRS': 'TX2',
                        'bandas_por_modo': {'GSM': ['1800'], 'GPRS': ['900'], 'EGPRS': ['850']}}})
        cat = Catalogo()
        validar_datos(data, catalogo=cat)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bandas.xlsm'
            generar(data, path, log=lambda *_: None, catalogo=cat)
            with zipfile.ZipFile(path) as z:
                root = E.fromstring(z.read('xl/worksheets/sheet3.xml'))
        ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        records = []
        for row in root.findall('s:sheetData/s:row', ns)[2:]:
            records.append({''.join(c for c in cell.get('r') if c.isalpha()):
                ''.join(cell.xpath('.//s:t/text() | s:v/text()', namespaces=ns)) for cell in row})
        self.assertEqual({r['K'] for r in records if r['J'] == 'GSM'}, {'1800'})
        self.assertEqual({r['K'] for r in records if r['J'] == 'GPRS'}, {'900'})
        self.assertEqual({r['K'] for r in records if r['J'] == 'EGPRS'}, {'850'})
        self.assertEqual({r['X'] for r in records if r['J'] == 'GPRS'}, {'1', '2', '3'})
        self.assertEqual({r['X'] for r in records if r['J'] == 'EGPRS'}, {'1', '2'})


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Requiere una pantalla X11 para los widgets reales.')
class InterfazRealTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.geometry('800x1000+0+0')
        cls.catalogo = Catalogo()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_subpaneles_2g_colocacion_y_carga_antigua(self):
        from formulario_bd import Panel2GCatalogo
        p = Panel2GCatalogo(self.root, '2G', self.catalogo)
        p.pack(fill='x')
        try:
            self.assertEqual(list(p.sel), ['GPRS', 'EGPRS', 'GSM'])
            for mode, slot, band in [('GPRS', 'TX3', '900'), ('EGPRS', 'TX2', '850')]:
                p.sel[mode].set(True)
                p._mostrar(mode)
                p.slots[mode][slot].set(True)
                p._cambiar(mode, slot)
                p.bandas_modo[mode].texto.set(band)
                self.assertTrue(p.bandas_modo[mode].aceptar())
            self.root.update()
            self.assertFalse(p.detalles['GSM'].winfo_ismapped())
            self.assertTrue(p.detalles['GPRS'].winfo_ismapped())
            self.assertTrue(p.detalles['EGPRS'].winfo_ismapped())
            for mode in ('GPRS', 'EGPRS'):
                frame = p.detalles[mode]
                slots, bands = frame.winfo_children()
                self.assertIs(bands, p.bandas_modo[mode])
                self.assertGreaterEqual(bands.winfo_rooty(), slots.winfo_rooty() + slots.winfo_height())
            selected = p.seleccion()
            self.assertEqual(selected['bandas_por_modo'], {'GPRS': ['900'], 'EGPRS': ['850']})
            self.assertEqual(p.validar(), [])
            p.cargar({'GSM': True, 'GPRS': 'TX2', 'EGPRS': None, 'bandas': ['900']})
            self.assertEqual(p.seleccion()['bandas_por_modo'], {'GSM': ['900'], 'GPRS': ['900']})
            self.assertFalse(p.detalles['EGPRS'].winfo_manager())
        finally:
            p.destroy()

    def test_bandas_lte_variantes_5g_y_opciones_3g(self):
        from formulario_bd import PanelCatalogo, Panel5GCatalogo, Panel3GCatalogo
        from configuracion import OPCIONES_3G
        lte = PanelCatalogo(self.root, 'LTE', self.catalogo)
        five = Panel5GCatalogo(self.root, '5G', self.catalogo)
        three = Panel3GCatalogo(self.root, '3G', self.catalogo)
        try:
            lte.pack(fill='x')
            self.root.update()
            self.assertTrue(lte.entrada.opciones.winfo_ismapped())
            self.assertTrue(lte.entrada.opciones.cget('text').startswith('Bandas disponibles: (1, 2, 3,'))
            self.assertFalse(any(isinstance(w, tk.ttk.Checkbutton) for w in lte.entrada.winfo_children()))
            lte.entrada.texto.set('1, 3, 7')
            self.assertTrue(lte.entrada.aceptar())
            self.assertEqual(lte.seleccion(), ['FDD1', 'FDD3', 'FDD7'])
            self.assertEqual(lte.validar(), [])
            lte.entrada.texto.set('1, 3')
            self.assertTrue(lte.validar())  # Cambios sin confirmar.
            self.assertTrue(lte.entrada.aceptar())
            self.assertEqual(lte.seleccion(), ['FDD1', 'FDD3'])
            five.entrada.texto.set('77')
            self.assertTrue(five.entrada.aceptar())
            self.assertTrue(five.validar())  # Hay que indicar la variante.
            five.variables['n77 part Q'].set(True)
            self.assertEqual(five.seleccion(), ['n77 part Q'])
            self.assertEqual(five.validar(), [])
            five.cargar(['n78 RSS-192'])
            self.assertEqual(five.seleccion(), ['n78 RSS-192'])
            self.assertEqual(list(three.options), OPCIONES_3G)
        finally:
            lte.destroy(); five.destroy(); three.destroy()

    def test_cambio_catalogo_y_respuestas_con_bandas_eliminadas(self):
        from formulario_bd import SelectorBandas
        bands = SelectorBandas(self.root, 'GPRS', ['850', '900', '1800'])
        try:
            self.assertTrue(bands.validar())
            bands.cargar(['900', '1800'])
            self.assertEqual(bands.validar(), [])
            bands.actualizar(['850', '900'])
            self.assertEqual(bands.seleccion(), [])
            self.assertTrue(bands.validar())  # No se descartan silenciosamente.
            bands.texto.set('850, 900')
            self.assertTrue(bands.aceptar())
            self.assertEqual(bands.validar(), [])
            bands.cargar(['1900'])
            self.assertTrue(bands.validar())
            self.assertIn('1900', bands.estado.cget('text'))
        finally:
            bands.destroy()

    def test_app_wlan_opciones_anteriores_y_otros_colapsados(self):
        from cuestionario_ensayo import App
        from configuracion import WLAN_MODOS_24, WLAN_MODOS_5, WLAN_UNII
        self.root.destroy()
        app = App()
        try:
            app.update()
            self.assertEqual(list(app.tecnologias)[:7], ['2G', '3G', 'LTE', 'LTE CAT M1', 'LTE NB-IoT', '5G', 'WLAN'])
            wlan = app.tecnologias['WLAN'].panel
            self.assertEqual(list(wlan.modos_24), WLAN_MODOS_24)
            self.assertEqual(list(wlan.modos_5), WLAN_MODOS_5)
            self.assertEqual(list(wlan.unii), list(WLAN_UNII))
            wlan.cargar({'2,4 GHz': ['n40'], '5 GHz': {'bandas': ['U-NII-1'], 'modos': ['a', 'ac80']}})
            self.assertEqual(wlan.seleccion(), {'2,4 GHz': ['n40'], '5 GHz': {'bandas': ['U-NII-1'], 'modos': ['a', 'ac80']}})
            self.assertEqual(wlan.validar(), [])
            self.assertFalse(app.otros_contenido.winfo_manager())
            app.tecnologias['2G'].var.set(True)
            app.tecnologias['2G']._al_cambiar()
            app.update()
            app.scroll.ver(app.tecnologias['2G'])
            app.update()
            self.assertGreaterEqual(app.tecnologias['2G'].winfo_rooty(), app.scroll.canvas.winfo_rooty())
            self.assertLess(app.tecnologias['2G'].winfo_rooty(), app.scroll.canvas.winfo_rooty() + app.scroll.canvas.winfo_height())
        finally:
            app.destroy()
            type(self).root = tk.Tk()
            self.root.geometry('800x1000+0+0')


if __name__ == '__main__':
    unittest.main()
