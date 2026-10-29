"""Catálogo editable XLSX. No obtiene datos RF del datasheet ni de sus plantillas."""
from dataclasses import dataclass, field, replace
import hashlib
import io
import math
from pathlib import Path
import re
import unicodedata
import zipfile

from lxml import etree as E

BASE_PREDETERMINADA = Path(__file__).parent / 'datos/Base_de_datos_bandas_canales_frecuencias_v2.xlsx'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RNS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def normalizar(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text or '').strip().lower())
                   if not unicodedata.combining(c) and c.isalnum())


def tecnologia(text):
    key = normalizar(text)
    return {'ltecatm1': 'LTE CAT M1', 'ltenbiot': 'LTE NB-IoT', 'wifi': 'WLAN',
            'wlan': 'WLAN', 'bluetooth': 'BT', 'bt': 'BT', 'gsm': 'GSM', 'lte': 'LTE',
            '5g': '5G', 'wcdma': 'WCDMA'}.get(key, str(text).strip())


HEADERS = {
    'tecnologia': 'tech', 'technology': 'tech', 'banda': 'band', 'band': 'band',
    'canal': 'channel', 'channel': 'channel', 'frecuenciamhz': 'frequency',
    'frecuencia': 'frequency', 'frequencymhz': 'frequency',
    'bandwidthmhz': 'bw', 'bandwidth': 'bw', 'bw': 'bw',
    'modulation': 'modulation', 'modulacion': 'modulation',
    'ulrballocation': 'rb', 'ulrbstart': 'rb_start', 'narrowbandindex': 'nb_index',
    'scskhz': 'scs', 'scs': 'scs', 'mpr': 'mpr', 'modo': 'mode', 'mode': 'mode',
    'datarate': 'data_rate', 'dutycycle': 'duty', 'dutycycleporcentaje': 'duty',
    'dutycyclepercent': 'duty', 'cert': 'cert', 'region': 'cert', 'notas': 'notes',
    'notes': 'notes', 'potenciamaximadbm': 'max_power', 'maxpowerdbm': 'max_power',
}
REQUIRED = {'tech', 'band', 'channel', 'frequency'}


def numero(value, where):
    if isinstance(value, bool):
        raise ValueError(f'{where}: se esperaba un número, no un booleano.')
    try:
        number = float(str(value).strip().replace(',', '.'))
    except (ValueError, TypeError):
        raise ValueError(f'{where}: valor numérico no válido: {value!r}.') from None
    if not math.isfinite(number) or number < 0:
        raise ValueError(f'{where}: número no válido: {value!r}.')
    return int(number) if number.is_integer() else number


@dataclass(frozen=True)
class Registro:
    tech: str
    band: str
    channel: int | float
    frequency: int | float
    params: dict = field(default_factory=dict)
    notes: str = ''
    source: str = ''

    def identity(self):
        return self.tech, self.band, self.channel, self.frequency, tuple(sorted(self.params.items()))


class Catalogo:
    def __init__(self, path=BASE_PREDETERMINADA):
        self.path = Path(path).expanduser().resolve()
        snapshot = self.path.read_bytes()
        self.sha256 = hashlib.sha256(snapshot).hexdigest()
        self.avisos = []
        try:
            raw = self._leer(snapshot)
        except (KeyError, E.XMLSyntaxError, zipfile.BadZipFile) as exc:
            raise ValueError('La base no es un archivo XLSX válido con tablas de tecnologías: ' + str(exc)) from exc
        # La entrega tiene WLAN y Wifi duplicadas. WLAN es la tabla principal.
        if any(r.source.startswith('WLAN!') for r in raw):
            wifi = [r for r in raw if r.source.startswith('Wifi!')]
            main = {r.identity() for r in raw if r.source.startswith('WLAN!')}
            if wifi and main != {r.identity() for r in wifi}:
                self.avisos.append('WLAN y Wifi difieren: se utiliza la tabla WLAN. Edita WLAN para actualizar WiFi.')
            raw = [r for r in raw if not r.source.startswith('Wifi!')]
        # Las tablas resumen no duplican combinaciones que ya están detalladas.
        detailed = {(r.tech, r.band, r.channel, r.frequency) for r in raw if r.params}
        unique = {}
        for r in raw:
            if not r.params and (r.tech, r.band, r.channel, r.frequency) in detailed:
                continue
            unique.setdefault(r.identity(), r)
        self.records = list(unique.values())
        if not self.records:
            raise ValueError('La base no contiene registros de tecnologías, bandas, canales y frecuencias.')
        self.by_tech = {}
        for r in self.records:
            self.by_tech.setdefault(r.tech, []).append(r)

    def _leer(self, snapshot):
        records = []
        try:
            z = zipfile.ZipFile(io.BytesIO(snapshot))
        except (OSError, zipfile.BadZipFile) as exc:
            raise ValueError(f'No se puede leer la base XLSX: {exc}') from exc
        with z:
            workbook = E.fromstring(z.read('xl/workbook.xml'))
            rels = {r.get('Id'): r.get('Target') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
            strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                with z.open('xl/sharedStrings.xml') as f:
                    for _, si in E.iterparse(f, tag='{' + NS['s'] + '}si'):
                        strings.append(''.join(si.xpath('.//s:t/text()', namespaces=NS)))
                        si.clear()
            for sheet in workbook.findall('s:sheets/s:sheet', NS):
                name = sheet.get('name')
                if normalizar(name) in ('notas', 'notes'):
                    continue
                target = rels[sheet.get('{' + RNS + '}id')]
                part = target.lstrip('/') if target.startswith('/') else 'xl/' + target
                columns = None
                with z.open(part) as f:
                    for _, row in E.iterparse(f, tag='{' + NS['s'] + '}row'):
                        values = {}
                        for c in row:
                            col = re.sub(r'\d+', '', c.get('r'))
                            v = c.findtext('s:v', namespaces=NS)
                            if c.get('t') == 's' and v is not None:
                                v = strings[int(v)]
                            elif c.get('t') == 'inlineStr':
                                v = ''.join(c.xpath('.//s:t/text()', namespaces=NS))
                            if c.find('s:f', NS) is not None and v is None:
                                raise ValueError(f'{name}!{c.get("r")}: fórmula sin resultado guardado. Calcula y guarda la base en Excel.')
                            if v is not None:
                                values[col] = v
                        if columns is None:
                            columns = {col: HEADERS[normalizar(v)] for col, v in values.items()
                                       if normalizar(v) in HEADERS}
                            if not REQUIRED <= set(columns.values()):
                                raise ValueError(f'Hoja {name}: faltan las columnas Tecnología, Banda, Canal o Frecuencia (MHz).')
                        elif values:
                            data = {key: values.get(col) for col, key in columns.items()}
                            if not any(data.get(k) for k in REQUIRED):
                                continue
                            where = f'{name}!fila {row.get("r")}'
                            if not all(data.get(k) is not None and str(data[k]).strip() for k in REQUIRED):
                                raise ValueError(f'{where}: registro incompleto.')
                            params = {k: v for k, v in data.items() if k not in REQUIRED | {'notes'} and
                                      v is not None and str(v).strip() not in ('', '-', 'N/A')}
                            for key in ('bw', 'scs', 'rb', 'rb_start', 'nb_index', 'duty', 'data_rate', 'mpr'):
                                if key in params:
                                    params[key] = numero(params[key], where + '/' + key)
                            band = str(data['band']).strip()
                            if re.fullmatch(r'\d+\.0+', band):
                                band = band.split('.')[0]
                            records.append(Registro(tecnologia(data['tech']), band,
                                numero(data['channel'], where + '/Canal'), numero(data['frequency'], where + '/Frecuencia'),
                                params, str(data.get('notes') or ''), f'{name}!{row.get("r")}'))
                        row.clear()
                        while row.getprevious() is not None:
                            del row.getparent()[0]
        return records

    def registros(self, tech):
        """Catálogo 3G común; una tabla específica tiene prioridad."""
        if tech in self.by_tech:
            return self.by_tech[tech]
        if tech in ('HSPA', 'HSPA+', 'HSDPA', 'DC-HSDPA'):
            return [replace(r, tech=tech, params={}) for r in self.by_tech.get('WCDMA', [])]
        return []

    def bandas(self, tech):
        return list(dict.fromkeys(r.band for r in self.registros(tech)))

    def seleccionar(self, datos):
        from opciones_ensayo import slots_incluidos
        wanted = []
        for name, value in datos['tecnologias'].items():
            if name == '2G':
                bands = value.get('bandas')
                per_mode = value.get('bandas_por_modo', {})
                if value.get('GSM'):
                    wanted.append(('GSM', per_mode.get('GSM', bands), None))
                for mode in ('GPRS', 'EGPRS'):
                    wanted.extend((f'{mode} {slot[2:]}TX', per_mode.get(mode, bands), None)
                                  for slot in slots_incluidos(value.get(mode)))
            elif name == '3G':
                if isinstance(value, dict):
                    wanted.extend((t, b.get('bandas'), b.get('modos')) if isinstance(b, dict) else (t, b, None)
                                  for t, b in value.items())
                else:
                    wanted.extend((t, None, None) for t in value)
            elif name == 'WLAN' and isinstance(value, dict) and 'bandas' not in value:
                if value.get('2,4 GHz'):
                    wanted.append(('WLAN', ['2.4 GHz'], value['2,4 GHz']))
                if value.get('5 GHz'):
                    wanted.append(('WLAN', value['5 GHz']['bandas'], value['5 GHz']['modos']))
            elif isinstance(value, dict):
                wanted.append((name, value.get('bandas'), value.get('modos')))
            else:
                wanted.append((name, value, None))
        selected = []
        for tech, bands, modes in wanted:
            records = self.registros(tech)
            if not records:
                raise ValueError(f'La base no contiene registros para {tech}.')
            if tech not in self.by_tech:
                note = f'{tech}: bandas, canales y frecuencias de la tabla WCDMA de la base; los parámetros específicos ausentes quedan vacíos.'
                if note not in self.avisos:
                    self.avisos.append(note)
            available = self.bandas(tech)
            bands = available if bands is None else bands
            if not isinstance(bands, list) or not bands or any(not isinstance(b, str) for b in bands):
                raise ValueError(f'{tech}: las bandas deben ser una lista de nombres de la base.')
            if len(bands) != len(set(bands)):
                raise ValueError(f'{tech}: hay bandas duplicadas en la selección.')
            if modes is not None and (not isinstance(modes, list) or any(not isinstance(m, str) or not m.strip() for m in modes)):
                raise ValueError(f'{tech}: selección de modos no válida.')
            missing = set(bands) - set(available)
            if missing:
                raise ValueError(f'{tech}: bandas no disponibles en la base: {", ".join(sorted(missing))}.')
            rows = [r for r in records if r.band in bands and
                    (not modes or not r.params.get('mode') or r.params['mode'] in modes)]
            if not rows:
                raise ValueError(f'La base no contiene combinaciones para la selección de {tech}.')
            # Un modo elegido por el usuario es un dato del formulario, no una
            # excusa para recuperar parámetros de la plantilla antigua.
            if modes and not any(r.params.get('mode') for r in rows):
                rows = [replace(r, params=dict(r.params, mode=m)) for m in modes for r in rows]
            selected.extend(rows)
        return selected


def cargar(datos):
    if not isinstance(datos, dict):
        raise ValueError('Las respuestas deben ser un objeto.')
    if datos.get('base_datos') and not isinstance(datos['base_datos'], (str, Path)):
        raise ValueError('base_datos debe ser la ruta de un archivo XLSX.')
    return Catalogo(datos.get('base_datos') or BASE_PREDETERMINADA)
