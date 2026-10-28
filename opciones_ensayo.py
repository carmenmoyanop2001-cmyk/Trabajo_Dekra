"""Selecciones múltiples y expansión de los slots acumulativos de 2G."""


def seleccion_multiple(value):
    """Admite también las respuestas antiguas con una sola cadena."""
    return [value] if isinstance(value, str) else value


def slots_incluidos(value):
    if not value:
        return []
    selected = seleccion_multiple(value)
    maximum = max(int(slot[2:]) for slot in selected)
    return [f'TX{n}' for n in range(1, maximum + 1)]
