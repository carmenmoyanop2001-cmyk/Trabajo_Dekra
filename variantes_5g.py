"""Variantes n77/n78 seleccionadas por la region del cuestionario."""
import re


def variantes_por_region(bandas, regiones, disponibles):
    if isinstance(regiones, str):
        regiones = [regiones]
    regiones = {'EN' if str(r).upper() in ('EN', 'CE') else str(r).upper() for r in regiones}
    disponibles = list(disponibles)
    etiquetas = {re.sub(r'\s+', '', b).casefold(): b for b in disponibles}
    elegidas = []
    for banda in bandas:
        match = re.match(r'^(?:n)?(77|78)(?:\b|$)', str(banda), re.I)
        if not match:
            destinos = [banda]
        else:
            n = match[1]
            destinos = []
            if 'EN' in regiones:
                destinos.append('n' + n)
            if 'FCC' in regiones:
                destinos.extend(['n' + n + ' part O', 'n' + n + ' part Q'])
            if 'ISED' in regiones:
                destinos.append('n77 RSS-192')
            if not destinos:
                raise ValueError('Selecciona una region para resolver las variantes n77/n78.')
        for destino in destinos:
            key = re.sub(r'\s+', '', destino).casefold()
            if key not in etiquetas:
                raise ValueError('La base no contiene la variante 5G requerida: ' + destino)
            etiqueta = etiquetas[key]
            if etiqueta not in elegidas:
                elegidas.append(etiqueta)
    return elegidas
