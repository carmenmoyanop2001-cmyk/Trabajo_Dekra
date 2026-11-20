"""COLUMN necesita una referencia, no el contenido de la celda referenciada."""
import re

from sarlib import _REF, _STR, _TOKR, _fmt_sheet

_CALL = re.compile(r'''(?<![A-Za-z0-9_.])(COLUMN|ROW)\s*\(\s*((?:"(?:[^"]|"")*"|'(?:[^']|'')*'|[^"'()])*)\s*\)''', re.I)
_LITERAL = re.compile(r'(?:"(?:[^"]|"")*"|[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?|TRUE|FALSE)$', re.I)


def llamadas_simples(text):
    """Ignorar el texto literal que casualmente contenga COLUMN(...)."""
    strings = [m.span() for m in _STR.finditer(text)]
    for match in _CALL.finditer(text):
        if not any(first <= match.start() < last for first, last in strings):
            yield match


def proteger_columnas(text, referencia_valida=None):
    """Reservar COLUMN(A1) antes de reubicar/incrustar referencias RF.

    El número de columna no depende de la fila ni del valor de la celda.
    Usar la fila 1 conserva ese número incluso si se descarta la fila o la
    hoja original. No se cambia si la columna era relativa o absoluta.
    """
    prefix = '__SAR_GEOMETRIA_COLUMNA_'
    while prefix in text:
        prefix += '_'
    reserved = {}
    changes = []
    for match in llamadas_simples(text):
        if match[1].upper() != 'COLUMN':
            continue
        ref = _REF.fullmatch(match[2].strip())
        if ref is None:
            continue
        if referencia_valida is not None and referencia_valida(ref):
            continue
        argument = f'{ref[2]}{ref[3]}1'
        if ref[7]:
            argument += f':{ref[6]}{ref[7]}1'
        token = prefix + str(len(reserved)) + '__'
        reserved[token] = f'{match[1]}({argument})'
        changes.append((match.start(), match.end(), token))
    for first, last, token in reversed(changes):
        text = text[:first] + token + text[last:]
    return text, reserved


def errores_referencia(text):
    """Casos sintácticamente analizables que Excel elimina por tipo de argumento."""
    return [f'{m[1]}({m[2]}) requiere una referencia de celda'
            for m in llamadas_simples(text) if _LITERAL.fullmatch(m[2].strip())]


def columnas_tokenizadas(pattern, row, resolve, own_sheet, newrow=None):
    """Misma protección en el motor de patrones de las plantillas compactas."""
    changes = []
    for call in llamadas_simples(pattern):
        if call[1].upper() != 'COLUMN':
            continue
        ref = _TOKR.fullmatch(call[2].strip())
        if ref is None:
            continue
        sheet = ref[1] or own_sheet
        def target(kind, delta, role):
            delta = int(delta)
            if newrow is not None and role == 'single' and kind == 'r' and abs(delta) <= 1 and sheet == own_sheet:
                return newrow + delta
            return resolve(sheet, row + delta if kind == 'r' else delta, role)
        a = target(ref[3], ref[4], 'start' if ref[6] else 'single')
        b = target(ref[7], ref[8], 'end') if ref[6] else None
        if a is not None and (not ref[6] or b is not None and b >= a):
            # Si la referencia sobrevive, conservar exactamente la reubicación
            # anterior; no se cambian otras fórmulas SAR que usan COLUMN.
            argument = _fmt_sheet(ref[1]) + ref[2] + ('$' if ref[3] == 'a' else '') + str(a)
            if ref[6]:
                argument += ':' + ref[6] + ('$' if ref[7] == 'a' else '') + str(b)
        else:
            argument = ref[2] + '1'
            if ref[6]:
                argument += ':' + ref[6] + '1'
        changes.append((call.start(), call.end(), f'{call[1]}({argument})'))
    for first, last, replacement in reversed(changes):
        pattern = pattern[:first] + replacement + pattern[last:]
    return pattern
