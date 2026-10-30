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
from tablas_helpers import table


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
        self.assertEqual(opciones_bandas(['FDD1'], ['FDD1', 'TDD1']), ['FDD1'])

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
            _, records = table(path, 3)
        self.assertEqual({r['Banda'] for r in records if r['Tecnología'] == 'GSM'}, {'1800'})
        self.assertEqual({r['Banda'] for r in records if r['Tecnología'].startswith('GPRS ')}, {'900'})
        self.assertEqual({r['Banda'] for r in records if r['Tecnología'].startswith('EGPRS ')}, {'850'})
        self.assertEqual({r['Tecnología'] for r in records if r['Tecnología'].startswith('GPRS ')}, {'GPRS 1TX', 'GPRS 2TX', 'GPRS 3TX'})
        self.assertEqual({r['Tecnología'] for r in records if r['Tecnología'].startswith('EGPRS ')}, {'EGPRS 1TX', 'EGPRS 2TX'})


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
            for mode, slot in [('GPRS', 'TX3'), ('EGPRS', 'TX2')]:
                p.sel[mode].set(True)
                p._mostrar(mode)
                p.slots[mode][slot].set(True)
                p._cambiar(mode, slot)
            self.root.update()
            self.assertFalse(p.detalles['GSM'].winfo_ismapped())
            self.assertTrue(p.detalles['GPRS'].winfo_ismapped())
            self.assertTrue(p.detalles['EGPRS'].winfo_ismapped())
            self.assertFalse(hasattr(p, 'bandas_modo'))
            for frame in p.detalles.values():
                self.assertTrue(all(isinstance(w, tk.ttk.Checkbutton) for w in frame.winfo_children()))
            selected = p.seleccion()
            self.assertEqual(selected, {'GSM': False, 'GPRS': ['TX1', 'TX2', 'TX3'], 'EGPRS': ['TX1', 'TX2']})
            self.assertEqual(p.validar(), [])
            p.cargar({'GSM': True, 'GPRS': 'TX2', 'EGPRS': None, 'bandas': ['900']})
            self.assertEqual(p.seleccion(), {'GSM': True, 'GPRS': ['TX1', 'TX2'], 'EGPRS': None})
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
            for tech, (_, panel) in three.options.items():
                self.assertEqual(panel.entrada.disponibles, self.catalogo.bandas('WCDMA'))
                panel.entrada.texto.set('1, 3')
                self.assertTrue(panel.entrada.aceptar(), tech)
                self.assertEqual(panel.entrada.estado.cget('text'), 'Seleccionadas: FDDI, FDDIII')
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

    def test_catm1_numeros_y_tecnologias_con_banda_fija(self):
        from formulario_bd import PanelCatalogo
        panels = [PanelCatalogo(self.root, tech, self.catalogo) for tech in ('LTE CAT M1', 'BT', 'Custom1')]
        try:
            catm, bt, custom = panels
            for panel in panels:
                panel.pack(fill='x')
            catm.cargar(['FDD1', 'FDD3'])
            self.root.update()
            self.assertEqual(catm.entrada.texto.get(), '1, 3')
            self.assertEqual(catm.entrada.estado.cget('text'), 'Seleccionadas: FDD1, FDD3')
            self.assertEqual(catm.lineas(), ['Bandas: 1, 3'])
            self.assertEqual(catm.seleccion(), ['FDD1', 'FDD3'])
            for panel, bands in [(bt, ['2.4 GHz']), (custom, ['?'])]:
                self.assertFalse(panel.entrada.controles.winfo_ismapped())
                self.assertFalse(panel.entrada.estado.winfo_ismapped())
                self.assertEqual(panel.validar(), [])
                self.assertEqual(panel.seleccion(), bands)
                panel.cargar(bands)
                self.assertEqual(panel.validar(), [])
            bt.entrada.actualizar(['2.4 GHz', '5 GHz'])
            self.root.update()
            self.assertTrue(bt.entrada.controles.winfo_ismapped())
            self.assertEqual(bt.seleccion(), ['2.4 GHz'])
        finally:
            for panel in panels:
                panel.destroy()

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
