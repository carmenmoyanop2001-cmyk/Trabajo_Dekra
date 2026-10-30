"""Tablas visibles de tecnologías, con valores de la base y estilos guardados."""
from copy import deepcopy
import re

from lxml import etree as E

from base_datos import normalizar
from entradas_bandas import _numero
from hojas_base_datos import hoja_tecnologia, PARAM_COL
from sarlib import n2col

M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS = {'s': M}
CORE = [('cert', 'Región', 'B', 20), ('tech', 'Tecnología', 'J', 19),
        ('band', 'Banda', 'K', 16), ('channel', 'Canal', 'T', 17),
        ('frequency', 'Frecuencia (MHz)', 'U', 22)]
LABELS = {'bw': 'Bandwidth (MHz)', 'modulation': 'Modulation', 'rb': 'UL RB Allocation',
          'rb_start': 'UL RB Start', 'nb_index': 'Narrowband Index', 'scs': 'SCS (kHz)',
          'mode': 'Mode', 'data_rate': 'Data Rate', 'duty': 'Duty Cycle', 'mpr': 'MPR',
          'notes': 'Notas'}
ORDER = ['GSM'] + [f'{mode} {n}TX' for mode in ('GPRS', 'EGPRS') for n in range(1, 5)] + [
    'WCDMA', 'HSDPA', 'DC-HSDPA', 'HSPA', 'HSPA+']


class EstilosVisibles:
    """Añade estilos legibles sin cambiar ninguna definición preexistente."""
    def __init__(self, original):
        self.root = E.fromstring(original)
        self.before = deepcopy(self.root)
        self.fonts = self.root.find('s:fonts', NS)
        self.xfs = self.root.find('s:cellXfs', NS)
        self.formats = self.root.find('s:numFmts', NS)
        if self.formats is None:
            self.formats = E.Element('{' + M + '}numFmts', count='0')
            self.root.insert(0, self.formats)
        self.number_format = next((f.get('numFmtId') for f in self.formats if f.get('formatCode') == '0.######'), None)
        if self.number_format is None:
            self.number_format = str(max([163] + [int(f.get('numFmtId')) for f in self.formats]) + 1)
            E.SubElement(self.formats, '{' + M + '}numFmt', numFmtId=self.number_format, formatCode='0.######')
        self.font_cache, self.style_cache = {}, {}

    def style(self, original, kind):
        key = int(original), kind
        if key in self.style_cache:
            return self.style_cache[key]
        xf = deepcopy(self.xfs[int(original)])
        font_id = int(xf.get('fontId', '0'))
        if font_id not in self.font_cache:
            font = deepcopy(self.fonts[font_id])
            color = font.find('s:color', NS)
            if color is None:
                color = E.Element('{' + M + '}color')
                position = next((i for i, child in enumerate(font)
                                 if E.QName(child).localname in ('name', 'family', 'charset', 'scheme')), len(font))
                font.insert(position, color)
            color.attrib.clear()
            color.set('rgb', 'FF000000')
            self.font_cache[font_id] = str(len(self.fonts))
            self.fonts.append(font)
        xf.set('fontId', self.font_cache[font_id])
        xf.set('applyFont', '1')
        xf.set('numFmtId', self.number_format if kind == 'number' else '1' if kind == 'integer' else '0')
        xf.set('applyNumberFormat', '1')
        alignment = xf.find('s:alignment', NS)
        if alignment is None:
            alignment = E.Element('{' + M + '}alignment')
            position = next((i for i, c in enumerate(xf) if E.QName(c).localname in ('protection', 'extLst')), len(xf))
            xf.insert(position, alignment)
        alignment.set('horizontal', 'left' if kind == 'notes' else 'center')
        alignment.set('vertical', 'center')
        alignment.set('textRotation', '0')
        alignment.set('wrapText', '1' if kind in ('header', 'notes') else '0')
        xf.set('applyAlignment', '1')
        value = str(len(self.xfs))
        self.xfs.append(xf)
        self.style_cache[key] = value
        return value

    def xml(self):
        for element in (self.fonts, self.xfs, self.formats):
            element.set('count', str(len(element)))
        check = deepcopy(self.root)
        for tag in ('fonts', 'cellXfs', 'numFmts'):
            old = self.before.find('s:' + tag, NS)
            new = check.find('s:' + tag, NS)
            if old is None:
                check.remove(new)
            else:
                for child in list(new)[len(old):]:
                    new.remove(child)
                new.attrib.clear()
                new.attrib.update(old.attrib)
        assert E.tostring(check, method='c14n') == E.tostring(self.before, method='c14n')
        return E.tostring(self.root, encoding='UTF-8', xml_declaration=True, standalone=True)


def nombre_visible(original, datos):
    if original == 'Conducted 2G-3G':
        two, three = bool(datos['tecnologias'].get('2G')), bool(datos['tecnologias'].get('3G'))
        return '2G-3G' if two and three else '2G' if two else '3G'
    return original if datos['conducida'] else original.removeprefix('Conducted ')


def valor(record, key, raw):
    if key == 'cert':
        return record.params.get('cert')
    if key == 'tech':
        return record.tech
    if key == 'band':
        return record.band
    if key == 'channel':
        return record.channel
    if key == 'frequency':
        return record.frequency
    return raw.get(key)


def tabla(catalogo, records, original):
    """No crea modos, medidas ni parámetros que no existan en la base."""
    records = [r for r in records if hoja_tecnologia(r.tech) == original]
    fields = list(CORE)
    raw_values = []
    extra_fields = {}
    for record in records:
        for source_key in getattr(catalogo, 'variantes_fuente', {}).get(record.source, [record.source]):
            source = getattr(catalogo, 'campos_fuente', {}).get(source_key, [])
            raw = {}
            for key, label, value in source:
                key = key or 'extra:' + normalizar(label)
                raw[key] = value
                if key in {c[0] for c in CORE} or value is None or str(value).strip() in ('', '-', 'N/A'):
                    continue
                extra_fields.setdefault(key, (key, LABELS.get(key, label), PARAM_COL.get(key, 'BO'),
                                              58 if key == 'notes' else max(17, min(26, len(label) + 2))))
            # El catálogo normalizado ofrece soporte a integraciones que creen
            # registros sin campos de procedencia; la interfaz usa campos_fuente.
            if not source:
                raw = dict(record.params, notes=record.notes or None)
                for key, value in raw.items():
                    if key != 'cert' and value is not None:
                        extra_fields.setdefault(key, (key, LABELS.get(key, key), PARAM_COL.get(key, 'BO'), 20))
            raw_values.append((record, raw))
    if original != 'Conducted 2G-3G':
        fields.extend(extra_fields.values())
    keys = [f[0] for f in fields]
    projected = {}
    for record, raw in raw_values:
        values = tuple(valor(record, key, raw) for key in keys)
        projected.setdefault(values, record)

    def sort_key(pair):
        values, record = pair
        tech = ORDER.index(record.tech) if record.tech in ORDER else len(ORDER)
        band = _numero(record.band)
        def ordered(value):
            if value is None:
                return (0, '')
            return (1, float(value)) if isinstance(value, (int, float)) else (2, str(value).casefold())
        extras = tuple(ordered(value) for value, field in zip(values[5:], fields[5:]) if field[0] != 'notes')
        return tech, record.tech, band if band is not None else 10**8, record.band, extras, record.channel, record.frequency

    return fields, sorted(projected.items(), key=sort_key)


def _text(cell):
    return ''.join(cell.xpath('.//s:t/text() | s:v/text()', namespaces=NS))


def crear_hoja(original_xml, fields, rows, original, estilos=None):
    """Estilos de las celdas originales; la tabla no hereda datos ni fórmulas."""
    old = E.fromstring(original_xml)
    header = old.find('s:sheetData/s:row[@r="2"]', NS)
    header_styles = {re.sub(r'\d', '', c.get('r')): c.get('s', '0') for c in header}
    styles = {}
    first = None
    for row in old.findall('s:sheetData/s:row', NS)[2:]:
        values = {re.sub(r'\d', '', c.get('r')): c for c in row}
        tech = _text(values['J']) if 'J' in values else ''
        if tech == 'Cat M1':
            tech = 'LTE CAT M1'
        if tech in ('GPRS', 'EGPRS') and 'X' in values:
            tech += ' ' + _text(values['X']) + 'TX'
        band = _text(values['K']) if 'K' in values else ''
        row_styles = {col: c.get('s', '0') for col, c in values.items()}
        styles.setdefault((tech, band), row_styles)
        styles.setdefault((tech, None), row_styles)
        if first is None:
            first = row_styles
    first = first or header_styles
    sheet = E.Element('{' + M + '}worksheet', nsmap={None: M, 'r': R})
    pr = E.SubElement(sheet, '{' + M + '}sheetPr')
    original_pr = old.find('s:sheetPr', NS)
    if original_pr is not None:
        if original_pr.get('codeName'):
            pr.set('codeName', original_pr.get('codeName'))
        tab = original_pr.find('s:tabColor', NS)
        if tab is not None:
            pr.append(deepcopy(tab))
    E.SubElement(pr, '{' + M + '}pageSetUpPr', fitToPage='1')
    last = n2col(len(fields))
    E.SubElement(sheet, '{' + M + '}dimension', ref=f'A1:{last}{len(rows) + 1}')
    views = E.SubElement(sheet, '{' + M + '}sheetViews')
    view = E.SubElement(views, '{' + M + '}sheetView', workbookViewId='0', showGridLines='0', zoomScale='90')
    E.SubElement(view, '{' + M + '}pane', ySplit='1', topLeftCell='A2', activePane='bottomLeft', state='frozen')
    E.SubElement(view, '{' + M + '}selection', pane='bottomLeft', activeCell='A2', sqref='A2')
    E.SubElement(sheet, '{' + M + '}sheetFormatPr', defaultRowHeight='18')
    cols = E.SubElement(sheet, '{' + M + '}cols')
    for index, (_, _, _, width) in enumerate(fields, 1):
        E.SubElement(cols, '{' + M + '}col', min=str(index), max=str(index), width=str(width), customWidth='1')
    if original == 'Conducted 2G-3G':
        # Mantener las capturas y sus anclajes originales. Las columnas vacías
        # intermedias se ocultan para situarlas junto a la tabla visible.
        E.SubElement(cols, '{' + M + '}col', min=str(len(fields) + 1), max='78', hidden='1', width='0', customWidth='1')
        old_cols = old.find('s:cols', NS)
        for col in old_cols if old_cols is not None else []:
            start, end = max(79, int(col.get('min'))), min(104, int(col.get('max')))
            if start <= end:
                copy = deepcopy(col)
                copy.set('min', str(start))
                copy.set('max', str(end))
                copy.attrib.pop('hidden', None)
                cols.append(copy)
    sd = E.SubElement(sheet, '{' + M + '}sheetData')
    row = E.SubElement(sd, '{' + M + '}row', r='1', ht='34', customHeight='1')
    for index, (_, label, source_col, _) in enumerate(fields, 1):
        style = header_styles.get('J', '0')
        if estilos is not None:
            style = estilos.style(style, 'header')
        cell = E.SubElement(row, '{' + M + '}c', r=n2col(index) + '1', s=style, t='inlineStr')
        E.SubElement(E.SubElement(cell, '{' + M + '}is'), '{' + M + '}t').text = label
    for rn, (values, record) in enumerate(rows, 2):
        row = E.SubElement(sd, '{' + M + '}row', r=str(rn))
        row_styles = styles.get((record.tech, record.band), styles.get((record.tech, None), first))
        for cn, (value, (key, _, source_col, _)) in enumerate(zip(values, fields), 1):
            style = row_styles.get(source_col, row_styles.get('J', '0'))
            if estilos is not None:
                kind = 'notes' if key == 'notes' else 'integer' if isinstance(value, int) or isinstance(value, float) and value.is_integer() else 'number' if isinstance(value, float) else 'text'
                style = estilos.style(style, kind)
            cell = E.SubElement(row, '{' + M + '}c', r=n2col(cn) + str(rn), s=style)
            if value is None:
                continue
            if isinstance(value, bool):
                cell.set('t', 'b')
                E.SubElement(cell, '{' + M + '}v').text = '1' if value else '0'
            elif isinstance(value, (int, float)):
                E.SubElement(cell, '{' + M + '}v').text = str(value)
            else:
                cell.set('t', 'inlineStr')
                E.SubElement(E.SubElement(cell, '{' + M + '}is'), '{' + M + '}t').text = str(value)
    E.SubElement(sheet, '{' + M + '}autoFilter', ref=f'A1:{last}{len(rows) + 1}')
    E.SubElement(sheet, '{' + M + '}pageMargins', left='0.3', right='0.3', top='0.5', bottom='0.5', header='0.2', footer='0.2')
    E.SubElement(sheet, '{' + M + '}pageSetup', orientation='landscape', paperSize='9', fitToWidth='1', fitToHeight='0')
    drawing = old.find('s:drawing', NS)
    if drawing is not None and original == 'Conducted 2G-3G':
        sheet.append(deepcopy(drawing))
    return E.tostring(sheet, encoding='UTF-8', xml_declaration=True, standalone=True)
