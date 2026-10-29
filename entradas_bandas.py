"""Números de banda del formulario, resueltos contra el catálogo cargado."""
import re


def _clave(value):
    return re.sub(r'\s+', '', str(value)).casefold()


def _numero(value):
    text = _clave(value)
    match = re.fullmatch(r'(?:fdd|tdd|n)?(\d+)', text)
    if match:
        return int(match[1])
    match = re.fullmatch(r'fdd([ivxlcdm]+)', text)
    if match:
        digits = {'i': 1, 'v': 5, 'x': 10, 'l': 50, 'c': 100, 'd': 500, 'm': 1000}
        total, previous = 0, 0
        for letter in reversed(match[1]):
            number = digits[letter]
            total += -number if number < previous else number
            previous = max(previous, number)
        return total
    return None


def resolver_bandas(texto, disponibles):
    """Acepta 850, 1/FDD1, 38/TDD38 o 77/n77; no adivina ambigüedades."""
    tokens = [t.strip() for t in texto.split(',') if t.strip()]
    if not tokens:
        raise ValueError('Introduce al menos una banda, separando los números con comas.')
    result = []
    for token in tokens:
        exact = [b for b in disponibles if _clave(b) == _clave(token)]
        matches = exact or [b for b in disponibles if token.isdigit() and _numero(b) == int(token)]
        if not matches:
            raise ValueError(f'La banda «{token}» no está disponible en la base cargada.')
        if len(matches) > 1:
            raise ValueError(f'«{token}» corresponde a varias bandas: {", ".join(matches)}. Escribe la etiqueta completa.')
        if matches[0] not in result:
            result.append(matches[0])
    return result


def opciones_bandas(disponibles):
    """Muestra números que se pueden escribir; conserva etiquetas ambiguas."""
    numbers = [_numero(b) for b in disponibles]
    return [str(n) if n is not None and numbers.count(n) == 1 else b
            for b, n in zip(disponibles, numbers)]


def banda_base_5g(value):
    match = re.match(r'^n(\d+)(?:\b|$)', value, re.I)
    return 'n' + match[1] if match else value
