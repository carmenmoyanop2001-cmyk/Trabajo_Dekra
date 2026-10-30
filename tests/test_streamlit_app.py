"""Pruebas opcionales: instalar requirements_streamlit.txt para ejecutarlas."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

from base_datos import BASE_PREDETERMINADA
from configuracion import WLAN_24
from generador_excel import generar
from web_ensayo import cargar_base, generar_paquete, huella, nombre_seguro
from test_base_datos import database
from test_tecnologias_visibles import workbook
from tablas_helpers import table

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(AppTest is None, 'Instala requirements_streamlit.txt para probar la app web.')
class StreamlitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app_streamlit import cargar_respuestas
        cls.cargar_respuestas = staticmethod(cargar_respuestas)
        cls.base = cargar_base(BASE_PREDETERMINADA.read_bytes(), BASE_PREDETERMINADA.name)
        cls.fixture = (ROOT / 'ejemplos/ejemplo_tecnologias_ordenadas.json').read_bytes()

    def app(self, respuestas=None):
        app = AppTest.from_file(str(ROOT / 'app_streamlit.py'), default_timeout=120).run()
        if respuestas:
            for clave, valor in self.cargar_respuestas(respuestas, self.base).items():
                app.session_state[clave] = valor
            app.run()
        self.assertFalse(app.exception)
        return app

    def test_slots_acumulativos_y_bandas(self):
        app = self.app()
        app.multiselect(key='q:tecnologias').select('2G').select('3G').run()
        app.multiselect(key='q:2g').select('GPRS').select('EGPRS').run()
        for modo in ('GPRS', 'EGPRS'):
            app.checkbox(key=f'q:slot:{modo}:TX3').check().run()
            self.assertEqual([app.checkbox(key=f'q:slot:{modo}:{s}').value for s in ('TX1','TX2','TX3','TX4')],
                             [True, True, True, False])
            app.checkbox(key=f'q:slot:{modo}:TX2').uncheck().run()
            self.assertEqual([app.checkbox(key=f'q:slot:{modo}:{s}').value for s in ('TX1','TX2','TX3','TX4')],
                             [True, False, False, False])
        self.assertFalse(any(x.key == 'q:bandas:2G' for x in app.text_input))
        app.multiselect(key='q:3g').select('HSDPA').run()
        app.text_input(key='q:bandas:HSDPA').set_value('1').run()
        self.assertIn('Seleccionadas: FDDI', [c.value for c in app.caption])
        app.text_input(key='q:bandas:HSDPA').set_value('999').run()
        app.button(key='generar_excel').click().run()
        self.assertTrue(any('999' in e.value for e in app.error))
        self.assertFalse(app.get('download_button'))
        self.assertFalse(app.exception)

    def test_generacion_descargas_y_conservacion(self):
        app = self.app(self.fixture)
        app.button(key='generar_excel').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        result = app.session_state['resultado']
        self.assertEqual(len(app.get('download_button')), 4)
        with zipfile.ZipFile(io.BytesIO(result['zip'])) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(len(z.namelist()), 4)
            self.assertEqual(z.read(self.base.nombre), self.base.contenido)
            datos = json.loads(z.read(result['nombre'] + '.json'))
            self.assertEqual(datos['base_datos'], self.base.nombre)
            self.assertEqual(datos['base_datos_sha256'], self.base.catalogo.sha256)
            self.assertEqual(z.read(result['nombre'] + '.xlsm'), result['excel'])
        with tempfile.TemporaryDirectory() as tmp:
            web, escritorio = Path(tmp)/'web.xlsm', Path(tmp)/'escritorio.xlsm'
            web.write_bytes(result['excel'])
            generar(datos, escritorio, catalogo=self.base.catalogo, log=lambda *_: None)
            names_web, names_desktop = workbook(web), workbook(escritorio)
            with zipfile.ZipFile(web) as a, zipfile.ZipFile(escritorio) as b:
                for nombre in result['resumen']['pestanas_protegidas_identicas']:
                    self.assertEqual(a.read(names_web[nombre][0]), b.read(names_desktop[nombre][0]), nombre)
                self.assertEqual(a.read('xl/vbaProject.bin'), b.read('xl/vbaProject.bin'))
        app.text_input(key='q:proyecto').set_value('Otra selección').run()
        self.assertFalse(app.get('download_button'))
        self.assertTrue(any('Has cambiado' in i.value for i in app.info))

    def test_base_cargada_y_json_portable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'base_editada.xlsx'
            database(path, [['GSM', '900', 12345, 9001.5, 'EN']],
                     headers=['Tecnología','Banda','Canal','Frecuencia (MHz)','Región'])
            base = cargar_base(path.read_bytes(), path.name)
        datos = dict(proyecto='CON', region=['EN'], exposure=['Body'], conducida=True,
                     baterias=[], accesorios=[], spotchecking=[], tecnologias={'2G': {'GSM': True}})
        r = generar_paquete(datos, base)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'web.xlsm'
            path.write_bytes(r['excel'])
            number = Path(workbook(path)['2G'][0]).stem.removeprefix('sheet')
            headers, rows = table(path, number)
            self.assertTrue(any(12345 in row.values() and 9001.5 in row.values() for row in rows))
        restored = self.cargar_respuestas(r['respuestas'], base)
        self.assertEqual(restored['q:proyecto'], 'CON')
        self.assertEqual(r['nombre'], '_CON')
        changed = deepcopy(datos)
        changed['region'] = ['FCC']
        self.assertNotEqual(huella(datos, base), huella(changed, base))
        self.assertEqual(nombre_seguro('../../PRN.xlsx', '.xlsx'), '_PRN.xlsx')
        with self.assertRaises(ValueError):
            cargar_base(b'no es una base XLSX', 'mal.xlsx')

    def test_importacion_no_modifica_original_y_conserva_modos(self):
        datos = json.loads(self.fixture)
        datos['tecnologias']['LTE'] = {'bandas': ['FDD1'], 'modos': ['QPSK']}
        datos['base_datos'] = '/ruta/que/no/debe/leerse.xlsx'
        antes = deepcopy(datos)
        estado = self.cargar_respuestas(json.dumps(datos).encode(), self.base)
        self.assertEqual(estado['q:modos:LTE'], 'QPSK')
        self.assertEqual(estado['q:bandas:HSDPA'], 'FDDI')
        self.assertTrue(estado['q:slot:GPRS:TX1'])
        self.assertTrue(estado['q:slot:GPRS:TX3'])
        self.assertEqual(datos, antes)

    def test_opciones_retiradas_y_respuestas_no_compatibles(self):
        app = self.app(self.fixture)
        app.session_state['q:variantes:n77'] = ['n77 retirada']
        app.run()
        self.assertFalse(app.exception)
        app.button(key='generar_excel').click().run()
        self.assertTrue(any('ya no están disponibles' in e.value for e in app.error))
        self.assertFalse(app.get('download_button'))
        datos = json.loads(self.fixture)
        datos['tecnologias']['WLAN'][WLAN_24] = ['modo inexistente']
        with self.assertRaisesRegex(ValueError, 'no admite este formulario'):
            self.cargar_respuestas(json.dumps(datos).encode(), self.base)


if __name__ == '__main__':
    unittest.main()
