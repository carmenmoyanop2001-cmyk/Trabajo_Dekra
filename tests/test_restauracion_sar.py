"""Regresión contra los dos SAR aprobados en Trabajo_Dekra-main11.zip."""
import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from lxml import etree as E

from base_datos import Catalogo
from generador_excel import generar
from herramientas.validar_paquete import validar, _dibujos
from tecnologias_originales import PlanOriginal, reubicar_dibujo, verificar_apoyo
from test_tecnologias_visibles import workbook

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/sar_main11_aprobado.zip'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
D = 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing'


class FuentesAprobadasTests(unittest.TestCase):
    def test_motor_y_plantillas_del_adjunto(self):
        meta = json.loads((ROOT/'docs/fuentes_sar_main11.json').read_text())
        for path, sha in meta['fuentes'].items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), sha, path)
        source = (ROOT/'generador_excel.py').read_text()
        functions = {n.name: ast.get_source_segment(source, n) for n in ast.parse(source).body
                     if isinstance(n, ast.FunctionDef)}
        for name, sha in meta['funciones_generador'].items():
            self.assertEqual(hashlib.sha256(functions[name].encode()).hexdigest(), sha, name)

    def test_no_permite_reescribir_apoyo_sar(self):
        m=NS['s']
        raw=f'<worksheet xmlns="{m}"><sheetData><row r="3"><c r="AH3"><v>7</v></c></row></sheetData></worksheet>'.encode()
        plan=PlanOriginal('Conducted LTE','Conducted LTE',Path(),'',raw,10,None,Path(),{},[])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'hoja.xml';p.write_bytes(raw)
            verificar_apoyo(plan,p)
            p.write_bytes(raw.replace(b'<v>7</v>',b'<f>MAX(AH20:AH30)</f>'))
            with self.assertRaisesRegex(ValueError,'celdas de apoyo'):
                verificar_apoyo(plan,p)

    def test_dibujo_no_invierte_extremos_al_descartar_filas(self):
        xml = f'<xdr:wsDr xmlns:xdr="{D}"><xdr:twoCellAnchor><xdr:from><xdr:col>78</xdr:col><xdr:colOff>20</xdr:colOff><xdr:row>10</xdr:row><xdr:rowOff>30</xdr:rowOff></xdr:from><xdr:to><xdr:col>83</xdr:col><xdr:colOff>40</xdr:colOff><xdr:row>50</xdr:row><xdr:rowOff>50</xdr:rowOff></xdr:to></xdr:twoCellAnchor></xdr:wsDr>'
        root = E.fromstring(xml)
        plan = PlanOriginal('Conducted 2G-3G', 'Conducted 2G-3G', Path(), '', b'', 100, None, Path(), {}, [])
        plan.rows = {1:[101], 2:[102], 50:[103], 51:[104]}; plan.sorted=sorted(plan.rows)
        reubicar_dibujo(root, plan)
        rows = [int(r.text) for r in root.findall('.//{' + D + '}row')]
        self.assertEqual(rows, [102,142])
        self.assertEqual(rows[1]-rows[0],40)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'dibujos.zip'
            with ZipFile(p,'w') as z:
                z.writestr('xl/drawings/drawing2.xml', E.tostring(root))
            with ZipFile(p) as z:self.assertEqual(_dibujos(z,set(z.namelist())),[])
            root.find('.//{' + D + '}to/{' + D + '}row').text='1'
            with ZipFile(p,'w') as z:
                z.writestr('xl/drawings/drawing2.xml', E.tostring(root))
            with ZipFile(p) as z:self.assertTrue(_dibujos(z,set(z.namelist())))


class SarAdjuntoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.tmp.name)/'mezcla.xlsm'
        with ZipFile(FIXTURE) as z:cls.data=json.loads(z.read('respuestas.json'))
        cls.data['base_datos']=str(ROOT/'datos/Base_de_datos_bandas_canales_frecuencias_corregido.xlsx')
        cls.summary=generar(cls.data,cls.path,catalogo=Catalogo(cls.data['base_datos']),log=lambda *_:None)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_sar_identicos_al_proyecto_aprobado_del_usuario(self):
        names=workbook(self.path)
        with ZipFile(FIXTURE) as approved,ZipFile(self.path) as generated:
            for name in ('SAR EN','SAR FCC-ISED'):
                self.assertEqual(generated.read(names[name][0]),approved.read(name+'.xml'),name)

    def test_tecnologias_completas_y_dibujos_validos(self):
        names=workbook(self.path)
        self.assertIn('Conducted 2G-3G',names)
        with ZipFile(self.path) as z:
            for name,info in self.summary['presentacion_original'].items():
                found = False
                with z.open(names[name][0]) as stream:
                    for _, row in E.iterparse(stream, tag='{' + NS['s'] + '}row'):
                        if int(row.get('r')) == info['cabecera']:
                            self.assertGreater(len(row),20,name)
                            found = True
                            break
                        row.clear()
                        while row.getprevious() is not None:
                            del row.getparent()[0]
                self.assertTrue(found,name)
                self.assertGreater(info['filas_originales'],0,name)
        self.assertEqual(validar(self.path,verbose=False),[])


if __name__=='__main__':unittest.main()
