from comparacion_sar import sin_canales
from corregir_2g3g import normalizar_fechas
"""Presentación íntegra del original, con catálogo editable y SAR sin cambios."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from lxml import etree as E

from base_datos import Catalogo
from generador_excel import generar, _generar
from herramientas.validar_paquete import validar
from nombres_hojas import renombrar_tecnologias
from presentacion_tecnologias import PROTEGIDAS
from test_base_datos import database
from test_tecnologias_visibles import workbook
from tecnologias_originales import _value, _q, _col, _strings, _norm, PlanOriginal, formula

ROOT = Path(__file__).resolve().parents[1]
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def vista(path, nombre):
    with zipfile.ZipFile(path) as z:
        part = workbook(path)[nombre][0]
        root = E.fromstring(z.read(part))
        strings = _strings(z)
    rows = [r for r in root.findall('s:sheetData/s:row', NS) if r.get('hidden') != '1']
    return root, [{_col(c): _value(c, strings) for c in r} for r in rows], rows


class OriginalesCompletosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.tmp.name)
        cls.db = cls.folder / 'base.xlsx'
        headers = ['Tecnología','Banda','Canal','Frecuencia (MHz)','Región','Module Port',
                   'Bandwidth (MHz)','Modulation','UL RB Allocation','UL RB Start','Dato nuevo']
        database(cls.db, [
            ['GSM','900',37,897.4,'EN',1],
            ['GPRS 1TX','900',37,897.4,'EN',1],
            ['HSDPA','FDDI',9612,1922.4,'EN',1],
            ['WCDMA','FDDI',9612,1922.4,'EN',1],
            ['LTE','FDD1',18100,1930,'EN',1,20,'QPSK',1,0],
            ['LTE CAT M1','FDD1',18100,1930,'EN',1,20,'QPSK',1,0],
            ['LTE NB-IoT','FDD1',18010,1921,'EN',1,None,'BPSK',1,0],
            ['5G','n77',630000,3450,'EN',1,20,'QPSK',1,0],
            ['WLAN','2.4 GHz',1,2412,'EN',1,20],
            ['BT','2.4 GHz',0,2402,'EN',1],
            ['LTE','FDD101',123456,9001.25,'EN',1,7.5,'QAM_NUEVA',3,2,'Desde la base'],
        ], headers=headers)
        cls.cat = Catalogo(cls.db)
        cls.data = dict(proyecto='Original completo filtrado', region=['EN','FCC','ISED'],
            exposure=['Body'], conducida=True, baterias=['B1','B2'], accesorios=['Funda'], spotchecking=[],
            tecnologias={'2G':{'GSM':True,'GPRS':'TX1'},'3G':{'HSDPA':['FDDI']},'LTE':['FDD1','FDD101'],
                'LTE CAT M1':['FDD1'],'LTE NB-IoT':['FDD1'],'5G':['n77'],
                'WLAN':{'2,4 GHz':['n20']},'BT':['2.4 GHz']})
        cls.before, cls.after = cls.folder/'antes.xlsm', cls.folder/'despues.xlsm'
        _generar(cls.data, str(cls.before), catalogo=cls.cat, log=lambda *_: None)
        cls.resumen = generar(cls.data, cls.after, catalogo=cls.cat, log=lambda *_: None)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_sar_y_hojas_fijas_identicas(self):
        old_names, new_names = workbook(self.before), workbook(self.after)
        with zipfile.ZipFile(self.before) as old, zipfile.ZipFile(self.after) as new:
            for name in PROTEGIDAS:
                a,b=old.read(old_names[name][0]),new.read(new_names[name][0])
                self.assertEqual(sin_canales(a),sin_canales(b),name) if name=='SAR EN' else self.assertEqual(a,b,name)
            self.assertEqual(old.read('xl/vbaProject.bin'), new.read('xl/vbaProject.bin'))
            before_styles, after_styles = E.fromstring(old.read('xl/styles.xml')), E.fromstring(new.read('xl/styles.xml'))
            for group in before_styles:
                actual = after_styles.find(group.tag)
                for a,b in zip(group,actual):
                    self.assertEqual(E.tostring(a,method='c14n',exclusive=True), E.tostring(b,method='c14n',exclusive=True))
            # Las fórmulas SAR continúan leyendo las coordenadas anteriores.
            for nombre in self.resumen['presentacion_original']:
                oldroot = E.fromstring(old.read(old_names[nombre][0]))
                if nombre == 'Conducted 2G-3G':
                    normalizar_fechas(oldroot)
                newroot = E.fromstring(new.read(new_names[nombre][0]))
                lookup = {c.get('r'):c for c in newroot.findall('s:sheetData/s:row/s:c',NS)}
                for cell in oldroot.findall('s:sheetData/s:row/s:c',NS):
                    self.assertEqual(E.tostring(cell,method='c14n',exclusive=True),
                                     E.tostring(lookup[cell.get('r')],method='c14n',exclusive=True))

    def test_columnas_contenido_y_seleccion_de_base(self):
        root, values, rows = vista(self.after,'Conducted 2G-3G')
        self.assertEqual(values[1]['G'], 'Module\nport')
        self.assertEqual(values[1]['J'], 'Technology')
        self.assertIn('power',str(values[1]['AH']).lower())
        self.assertTrue(any(v.get('F') is not None for v in values[2:]))
        self.assertTrue(any(c.find('s:f',NS) is not None for r in rows[2:] for c in r))
        allowed = {('GSM','900',37,897.4),('GPRS','900',37,897.4),('HSDPA','FDDI',9612,1922.4)}
        for row in values[2:]:
            self.assertIn((row.get('J'),str(row.get('K')),row.get('T'),row.get('U')),allowed)
            self.assertEqual(row['G'],1)
        self.assertTrue(root.findall('s:cols/s:col',NS))
        self.assertIsNotNone(root.find('s:legacyDrawing',NS))
        self.assertIsNotNone(root.find('s:drawing',NS))
        self.assertTrue(root.findall('s:conditionalFormatting',NS))
        self.assertTrue(root.findall('s:dataValidations/s:dataValidation',NS))

    def test_bandas_nuevas_y_campos_nuevos_prioridad_base(self):
        root, values, rows = vista(self.after,'Conducted LTE')
        selected = [v for v in values[2:] if v.get('K') == 'FDD101']
        self.assertTrue(selected)
        self.assertTrue(all(v.get('T')==123456 and v.get('U')==9001.25 and v.get('M')==7.5 and v.get('N')=='QAM_NUEVA' for v in selected))
        self.assertTrue(any('Desde la base' in v.values() for v in selected))
        self.assertTrue(any('Dato nuevo' in v.values() for v in values[:2]))
        self.assertTrue(any('registros nuevos' in aviso for aviso in self.resumen['avisos']))
        self.assertEqual(validar(self.after,verbose=False), [])

    def test_mpr_catm1_no_pierde_valores_originales(self):
        root, values, rows = vista(self.after,'Conducted LTE CATM1')
        self.assertTrue(values[2:])
        mpr = [c for row in rows[2:] for c in row if _col(c)=='O']
        # En el archivo original recibido estas filas de BW 20 MHz tienen
        # constantes 0 en O, no fórmulas. Deben conservarse tal cual.
        self.assertTrue(mpr)
        self.assertEqual({_value(c,[]) for c in mpr},{0})
        self.assertTrue(all(v['J']=='LTE' for v in values[2:]))

    def test_apoyo_sar_conserva_tambien_las_celdas_de_medidas(self):
        before, after = workbook(self.before), workbook(self.after)
        with zipfile.ZipFile(self.before) as old, zipfile.ZipFile(self.after) as new:
            for name in self.resumen['presentacion_original']:
                a = E.fromstring(old.read(before[name][0]))
                b = E.fromstring(new.read(after[name][0]))
                actual = {c.get('r'): c for c in b.findall('s:sheetData/s:row/s:c', NS)}
                for cell in a.findall('s:sheetData/s:row/s:c', NS):
                    if _col(cell) in ('AH', 'CB', 'CC', 'CD', 'CE'):
                        self.assertEqual(E.tostring(cell, method='c14n', exclusive=True),
                                         E.tostring(actual[cell.get('r')], method='c14n', exclusive=True))

    def test_archivo_original_completo_guardado_y_hashes(self):
        inv=json.loads((ROOT/'plantilla/originales/inventario.json').read_text())
        self.assertTrue({'Overview','Tune-Up','SAR EN','SAR FCC-ISED','Validations','Test Campaign',
            'Pretesting-Others','Liquids-DRAFT','Pendiente'} <= inv['pestanas'].keys())
        for archivo,meta in inv['archivos'].items():
            with zipfile.ZipFile(ROOT/'plantilla/originales'/archivo) as z:
                self.assertEqual(set(z.namelist()),set(meta['partes']))
                for part,sha in meta['partes'].items():
                    h=hashlib.sha256()
                    with z.open(part) as stream:
                        while chunk:=stream.read(1024*1024):h.update(chunk)
                    self.assertEqual(h.hexdigest(),sha,(archivo,part))
        self.assertGreater(inv['pestanas']['Conducted 5G']['filas'],200000)

    def test_conducidos_y_sin_conducidos_nombres_y_sar(self):
        for two,three,conducted,wanted in ((True,False,True,'Conducted 2G'),(False,True,True,'Conducted 3G'),
                  (True,True,True,'Conducted 2G-3G'),(True,False,False,'2G'),(False,True,False,'3G'),(True,True,False,'2G-3G')):
            datos=deepcopy(self.data)
            datos['region']=['EN'];datos['conducida']=conducted
            datos['tecnologias']={}
            if two:datos['tecnologias']['2G']={'GSM':True}
            if three:datos['tecnologias']['3G']={'WCDMA':['FDDI']}
            path=self.folder/(wanted.replace(' ','_')+'.xlsm')
            generar(datos,path,catalogo=self.cat,log=lambda *_:None)
            names=workbook(path)
            self.assertEqual(names[wanted][1],'visible')
            self.assertEqual(names['SAR EN'][1],'visible')
            self.assertEqual(validar(path,verbose=False),[])


class ReferenciasOriginalesTests(unittest.TestCase):
    def test_rangos_no_incluyen_otra_banda_nueva(self):
        p=PlanOriginal('Conducted LTE','Conducted LTE',Path(),'',b'',10,None,Path(),{},[])
        p.rows={1:[11],2:[12],3:[13,20],6:[14],9:[15]}
        p.sorted=sorted(p.rows)
        p.grupos={13:('LTE','fdd1'),14:('LTE','fdd1'),15:('LTE','fdd1'),20:('LTE','fdd101')}
        p.nuevos_grupos={20}
        self.assertEqual(p.range_rows(3,9),(13,15))
        self.assertEqual(p.range_rows(3,9,contexto=20),(20,20))
        self.assertEqual(p.range_rows(1,2,contexto=20),(11,12))
        self.assertEqual(p.range_rows(3,9,incluir_nuevos=True),(13,20))
        self.assertEqual(formula('MAX(AH3:AH9)',p,6,14,{p.familia:p}),'MAX(AH13:AH15)')
        self.assertEqual(formula('MAX(AH3:AH9)',p,3,20,{p.familia:p}),'MAX(AH20:AH20)')
        self.assertEqual(formula('T6',p,3,20,{p.familia:p}),'""')

    def test_no_recupera_frecuencias_fuera_de_la_base(self):
        p=PlanOriginal('Conducted LTE','Conducted LTE',Path(),'',b'',10,None,Path(),{},[])
        p.rows={1:[11],2:[12],3:[13]};p.sorted=sorted(p.rows)
        p.cache={('U',7):1930,('U',9):9001.25}
        p.valores_rf={None:{'T':{123456},'U':{9001.25}}}
        self.assertEqual(formula('U7',p,3,13,{p.familia:p}),'""')
        self.assertEqual(formula('U9',p,3,13,{p.familia:p}),'9001.25')


if __name__=='__main__':
    unittest.main()
