"""Validación compartida por la interfaz y la generación automática."""
from opciones_ensayo import seleccion_multiple


def validar_datos(datos):
    if not isinstance(datos, dict):
        raise ValueError('Las respuestas deben ser un objeto.')
    required = {'proyecto', 'region', 'exposure', 'conducida', 'baterias',
                'accesorios', 'spotchecking', 'tecnologias'}
    missing = required - datos.keys()
    if missing:
        raise ValueError('Faltan campos: ' + ', '.join(sorted(missing)))
    if not isinstance(datos['proyecto'], str) or not datos['proyecto'].strip():
        raise ValueError('Escribe el nombre del proyecto.')
    for field, allowed in (('region', ('EN', 'FCC', 'ISED')),
                           ('exposure', ('Close to ear', 'Close to Head', 'Body', 'Extremity'))):
        values = seleccion_multiple(datos[field])
        if not isinstance(values, list) or not values or any(
                not isinstance(v, str) or v not in allowed for v in values):
            raise ValueError(f'Selecciona al menos una opción válida para {field}.')
        if len(values) != len(set(values)):
            raise ValueError(f'Selección duplicada para {field}.')
    if type(datos['conducida']) is not bool:
        raise ValueError('conducida debe ser true o false.')
    for field in ('baterias', 'accesorios', 'spotchecking'):
        value = datos[field]
        if not isinstance(value, list) or len(value) > 10 or any(
                not isinstance(v, str) or not v.strip() for v in value):
            raise ValueError(f'{field}: se admiten hasta diez nombres no vacíos.')
    technologies = datos['tecnologias']
    if not isinstance(technologies, dict) or not technologies:
        raise ValueError('Selecciona al menos una tecnología.')
    # Comparte los identificadores del cuestionario sin crear ventanas.
    from configuracion import (BANDAS_LTE, BANDAS_CATM1, BANDAS_NBIOT,
        BANDAS_5G, VARIANTES_5G, OPCIONES_3G, WLAN_MODOS_24, WLAN_UNII)
    bands = {'LTE': set(BANDAS_LTE.values()), 'LTE CAT M1': set(BANDAS_CATM1.values()),
             'LTE NB-IoT': set(BANDAS_NBIOT.values()),
             '5G': set(BANDAS_5G.values()) | {v for vs in VARIANTES_5G.values() for v in vs},
             '3G': set(OPCIONES_3G)}

    def check_list(value, allowed, label):
        if not isinstance(value, list) or not value or any(
                not isinstance(v, str) or v not in allowed for v in value):
            raise ValueError(f'Selección no válida para {label}.')
        if len(value) != len(set(value)):
            raise ValueError(f'Selección duplicada para {label}.')

    for name, value in technologies.items():
        if name in bands:
            check_list(value, bands[name], name)
        elif name == '2G':
            if not isinstance(value, dict) or not value or set(value) - {'GSM', 'GPRS', 'EGPRS'}:
                raise ValueError('Selección 2G no válida.')
            if not any(value.values()):
                raise ValueError('Selecciona al menos un modo 2G.')
            for mode, selection in value.items():
                if mode == 'GSM' and type(selection) is not bool:
                    raise ValueError('GSM debe ser true o false.')
                if mode != 'GSM' and selection is not None:
                    check_list(seleccion_multiple(selection), {'TX1', 'TX2', 'TX3', 'TX4'}, mode)
        elif name == 'WLAN':
            if not isinstance(value, dict) or not value or set(value) - {'2,4 GHz', '5 GHz'}:
                raise ValueError('Selección WLAN no válida.')
            if '2,4 GHz' in value:
                check_list(value['2,4 GHz'], set(WLAN_MODOS_24), 'WLAN 2,4 GHz')
            if '5 GHz' in value:
                five = value['5 GHz']
                if not isinstance(five, dict) or set(five) != {'bandas', 'modos'}:
                    raise ValueError('WLAN 5 GHz necesita bandas y modos.')
                check_list(five['bandas'], set(WLAN_UNII), 'bandas WLAN 5 GHz')
                allowed = {'a'} | {m for b in five['bandas'] for m in WLAN_UNII[b]}
                check_list(five['modos'], allowed, 'modos WLAN 5 GHz')
        else:
            raise ValueError(f'Tecnología no admitida: {name}.')
