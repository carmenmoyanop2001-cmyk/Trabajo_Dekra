"""Una celda Mode por tecnología/banda, sin perder los modos usados en cálculos."""
from sarlib import col2n
from copy import deepcopy
from lxml import etree


def _text_formula(value):
    parts = ['"' + part.replace('"', '""') + '"' for part in str(value).split('\n')]
    return '(' + '&CHAR(10)&'.join(parts) + ')' if len(parts) > 1 else parts[0]


def _centrar_estilo(xfs, style_map, old_style, font_id=None):
    key = (old_style, font_id)
    if key not in style_map:
        xf = deepcopy(xfs[old_style])
        if font_id is not None:
            xf.set('fontId', str(font_id))
            xf.set('applyFont', '1')
        alignment = xf.find('{*}alignment')
        if alignment is None:
            alignment = etree.Element('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}alignment')
            xf.insert(0, alignment)
        alignment.set('horizontal', 'center')
        alignment.set('vertical', 'center')
        alignment.set('wrapText', '1')
        xf.set('applyAlignment', '1')
        style_map[key] = len(xfs)
        xfs.append(xf)
    return style_map[key]


def _combinar_exposiciones(en, plan, ctx, xfs, style_map, fonts):
    bx = col2n('BX')
    visible_fonts = {}
    groups = []
    previous = None
    for row, item in enumerate(plan, start=3):
        kv = en.kv(item.i)
        key = (kv.get('BT'), kv.get('BU'), kv.get('BX'))
        if key != previous:
            groups.append([])
        groups[-1].append((row, item))
        previous = key
    for group in groups:
        first, first_item = group[0]
        last = group[-1][0]
        anchor = en.rows[first_item.i][0]
        for _, item in group:
            item.ovr[bx] = None
            ctx.cell_anchors[('SAR EN', 'BX', en.rows[item.i][0])] = anchor
        first_item.ovr[bx] = en.kv(first_item.i)['BX']
        if first != last:
            ctx.display_merges['SAR EN'].append(f'BX{first}:BX{last}')
        old_style = next(c[1] for c in en.templates[en.rows[first_item.i][1]] if c[0] == bx)
        # El original oculta etiquetas repetidas con la fuente del color del
        # relleno. La única etiqueta del bloque combinado debe ser legible.
        old_font = int(xfs[old_style].get('fontId', '0'))
        if old_font not in visible_fonts:
            font = deepcopy(fonts[old_font])
            color = font.find('{*}color')
            if color is None:
                color = etree.SubElement(font, '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}color')
            color.attrib.clear()
            color.set('rgb', 'FF000000')
            visible_fonts[old_font] = len(fonts)
            fonts.append(font)
        ctx.style_overrides[('SAR EN', first, bx)] = _centrar_estilo(
            xfs, style_map, old_style, visible_fonts[old_font])
    fonts.set('count', str(len(fonts)))


def combinar_mode(en, plan, ctx, styles_xml):
    # CG ya existe y está oculta en la plantilla: conserva el modo por fila.
    # Los cálculos pasan a leer CG; BY solo resume visualmente cada bloque.
    ctx.column_aliases[('SAR EN', 'BY')] = 'CG'
    by, cg = col2n('BY'), col2n('CG')
    styles = etree.fromstring(styles_xml)
    xfs = styles.find('{*}cellXfs')
    style_map = {}
    groups = []
    previous = None
    for output_row, item in enumerate(plan, start=3):
        kv = en.kv(item.i)
        key = (kv.get('BT'), kv.get('BU'))
        if key != previous:
            groups.append([])
        groups[-1].append((output_row, item))
        previous = key
    merges = []
    for group in groups:
        modes = []
        for _, item in group:
            if item.ovr is None:
                item.ovr = {}
            mode = item.ovr.get(by, en.kv(item.i).get('BY'))
            item.ovr[cg] = mode
            if not item.extra and mode and mode not in modes:
                modes.append(mode)
            item.ovr[by] = None
        first, last = group[0][0], group[-1][0]
        summary = '\n'.join(modes)
        group[0][1].ovr[by] = summary if summary else None
        for _, item in group:
            mode = item.ovr[cg]
            if not item.extra:
                # El resumen inicial no cambia los modos originales por fila.
                # Si el usuario elige un único modo en la celda combinada,
                # ese modo se aplica al bloque completo, sin referencias rotas.
                anchor = f'$BY${first}'
                formula = f'IF(OR({anchor}={_text_formula(summary)},{anchor}=""),{_text_formula(mode or "")},{anchor})'
                item.ovr[cg] = ('f', formula, mode or '')
        if first != last:
            merges.append(f'BY{first}:BY{last}')
        first_item = group[0][1]
        old_style = next(c[1] for c in en.templates[en.rows[first_item.i][1]] if c[0] == by)
        ctx.style_overrides[('SAR EN', first, by)] = _centrar_estilo(xfs, style_map, old_style)
    ctx.display_merges['SAR EN'] = merges
    _combinar_exposiciones(en, plan, ctx, xfs, style_map, styles.find('{*}fonts'))
    xfs.set('count', str(len(xfs)))
    return etree.tostring(styles, encoding='UTF-8', xml_declaration=True, standalone=True)
