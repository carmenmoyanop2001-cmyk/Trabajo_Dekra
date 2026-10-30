"""Ejecutar con: python -m streamlit run app_streamlit.py"""
import hashlib
import json
import logging

import streamlit as st

from base_datos import BASE_PREDETERMINADA
from configuracion import (REGIONES, EXPOSICIONES, CATEGORIAS, OPCIONES_3G,
    SLOTS_2G, WLAN_24, WLAN_5, WLAN_MODOS_24, WLAN_MODOS_5, WLAN_UNII)
from entradas_bandas import resolver_bandas, opciones_bandas, banda_base_5g
from opciones_ensayo import slots_incluidos, seleccion_multiple
from web_ensayo import cargar_base, generar_paquete, huella, validar


TECNOLOGIAS = ['2G', '3G', 'LTE', 'LTE CAT M1', 'LTE NB-IoT', '5G', 'WLAN', 'BT']


def cargar_respuestas(contenido, base):
    """Preparar el estado completo antes de sustituir las respuestas actuales."""
    try:
        datos = json.loads(contenido.decode('utf-8-sig'))
    except (ValueError, UnicodeError) as exc:
        raise ValueError('El archivo de respuestas no es un JSON válido.') from exc
    validar(datos, base.catalogo)
    tecnologias = datos['tecnologias']
    permitidas = TECNOLOGIAS + [t for t in base.catalogo.by_tech if t.startswith('Custom')]
    if set(tecnologias) - set(permitidas):
        raise ValueError('Estas respuestas contienen tecnologías que no admite el formulario web.')
    estado = {'q:proyecto': datos['proyecto'],
              'q:region': seleccion_multiple(datos['region']),
              'q:exposure': seleccion_multiple(datos['exposure']),
              'q:conducida': 'Sí' if datos['conducida'] else 'No',
              'q:tecnologias': list(tecnologias)}
    for categoria in CATEGORIAS:
        clave = categoria['clave']
        nombres = datos[clave]
        estado['q:hay:' + clave] = bool(nombres)
        estado['q:cuantos:' + clave] = max(1, len(nombres))
        for i, nombre in enumerate(nombres):
            estado[f'q:nombre:{clave}:{i}'] = nombre
    for tipo, valor in tecnologias.items():
        if tipo == '2G':
            estado['q:2g'] = [t for t in ('GSM', 'GPRS', 'EGPRS') if valor.get(t)]
            for modo in ('GPRS', 'EGPRS'):
                slots = slots_incluidos(valor.get(modo))
                for slot in SLOTS_2G:
                    estado[f'q:slot:{modo}:{slot}'] = slot in slots
            if valor.get('bandas') or valor.get('bandas_por_modo'):
                # La interfaz actual siempre toma todas las bandas 2G de la base.
                estado['aviso_importacion'] = 'En 2G se usarán todas las bandas de la base, como en el cuestionario actual.'
        elif tipo == '3G':
            selecciones = valor if isinstance(valor, dict) else {t: base.catalogo.bandas(t) for t in valor}
            if set(selecciones) - set(OPCIONES_3G):
                raise ValueError('Las respuestas contienen un modo 3G no admitido.')
            estado['q:3g'] = list(selecciones)
            for subtipo, bandas in selecciones.items():
                _estado_bandas(estado, subtipo, bandas)
        elif tipo == 'WLAN':
            if isinstance(valor, list) or 'bandas' in valor:
                bandas = valor if isinstance(valor, list) else valor['bandas']
                modos = [] if isinstance(valor, list) else valor.get('modos', [])
                valor = {}
                if '2.4 GHz' in bandas:
                    valor[WLAN_24] = [m for m in modos if m in WLAN_MODOS_24]
                unii = [b for b in bandas if b in WLAN_UNII]
                if unii:
                    valor[WLAN_5] = dict(bandas=unii, modos=modos)
            estado['q:wlan:frecuencias'] = list(valor)
            estado['q:wlan:24'] = valor.get(WLAN_24, [])
            cinco = valor.get(WLAN_5, {})
            estado['q:wlan:unii'] = cinco.get('bandas', [])
            estado['q:wlan:5'] = [m for m in cinco.get('modos', []) if m != 'a']
            for elegidas, opciones in ((list(valor), [WLAN_24, WLAN_5]),
                                      (estado['q:wlan:24'], WLAN_MODOS_24),
                                      (estado['q:wlan:unii'], list(WLAN_UNII)),
                                      (estado['q:wlan:5'], WLAN_MODOS_5)):
                if any(e not in opciones for e in elegidas):
                    raise ValueError('WLAN: las respuestas contienen opciones que no admite este formulario.')
        elif tipo == '5G':
            bandas = valor.get('bandas', []) if isinstance(valor, dict) else valor
            bases = list(dict.fromkeys(banda_base_5g(b) for b in bandas))
            estado['q:bandas:5G'] = ', '.join(bases)
            for banda in bases:
                estado['q:variantes:' + banda] = [b for b in bandas if banda_base_5g(b) == banda]
            if isinstance(valor, dict):
                estado['q:modos:5G'] = ', '.join(valor.get('modos', []))
        else:
            _estado_bandas(estado, tipo, valor)
    return estado


def _estado_bandas(estado, tipo, valor):
    bandas = valor.get('bandas', []) if isinstance(valor, dict) else valor
    estado['q:bandas:' + tipo] = ', '.join(bandas)
    if isinstance(valor, dict):
        estado['q:modos:' + tipo] = ', '.join(valor.get('modos', []))


def _cambiar_slot(modo, slot):
    numero = int(slot[2:])
    marcado = st.session_state[f'q:slot:{modo}:{slot}']
    for candidato in SLOTS_2G:
        n = int(candidato[2:])
        if (marcado and n < numero) or (not marcado and n > numero):
            st.session_state[f'q:slot:{modo}:{candidato}'] = marcado


def _seleccion_catalogo(etiqueta, opciones, clave, errores):
    """Mantener visibles las selecciones retiradas al cambiar de base, sin sustituirlas."""
    anteriores = st.session_state.get(clave, [])
    retiradas = [v for v in anteriores if v not in opciones]
    elegidas = st.multiselect(etiqueta, opciones + retiradas, key=clave,
        format_func=lambda v: v + ' (no disponible en la base)' if v in retiradas else v)
    if any(v in retiradas for v in elegidas):
        errores.append(etiqueta + ': retira las opciones que ya no están disponibles en la base.')
    return elegidas


def _bandas(tipo, disponibles, errores):
    if not disponibles:
        errores.append(f'{tipo}: la base no contiene bandas disponibles.')
        st.caption('Sin bandas disponibles en esta base.')
        return []
    if len(disponibles) == 1:
        st.caption('Seleccionada automáticamente: ' + disponibles[0])
        return disponibles[:]
    st.caption('Bandas disponibles: ' + ', '.join(opciones_bandas(disponibles)))
    texto = st.text_input(f'Bandas de {tipo}', key='q:bandas:' + tipo,
                         placeholder='Escribe los números separados por comas, por ejemplo: 1, 3, 7')
    try:
        seleccionadas = resolver_bandas(texto, disponibles)
    except ValueError as exc:
        errores.append(f'{tipo}: {exc}')
        if texto.strip():
            st.warning(str(exc))
        return []
    st.caption('Seleccionadas: ' + ', '.join(seleccionadas))
    return seleccionadas


def _con_modos(tipo, bandas):
    with st.expander('Modos opcionales de ' + tipo):
        texto = st.text_input('Modos separados por comas', key='q:modos:' + tipo,
            help='Déjalo vacío para utilizar los datos de la base. Solo indica modos conocidos para este ensayo.')
    modos = list(dict.fromkeys(m.strip() for m in texto.split(',') if m.strip()))
    return dict(bandas=bandas, modos=modos) if modos else bandas


def _panel_2g(errores):
    elegidas = st.multiselect('Tecnologías 2G', ['GSM', 'GPRS', 'EGPRS'], key='q:2g')
    resultado = {'GSM': 'GSM' in elegidas, 'GPRS': None, 'EGPRS': None}
    st.caption('Todas las bandas 2G se toman de la base de datos. Los slots inferiores se incluyen automáticamente.')
    for modo in ('GPRS', 'EGPRS'):
        if modo not in elegidas:
            continue
        st.write('Slots ' + modo)
        for columna, slot in zip(st.columns(4), SLOTS_2G):
            with columna:
                st.checkbox(slot, key=f'q:slot:{modo}:{slot}',
                            on_change=_cambiar_slot, args=(modo, slot))
        slots = [s for s in SLOTS_2G if st.session_state.get(f'q:slot:{modo}:{s}')]
        resultado[modo] = slots_incluidos(slots) or None
        if not slots:
            errores.append(f'{modo}: selecciona al menos un slot.')
    if not elegidas:
        errores.append('2G: selecciona GSM, GPRS o EGPRS.')
    return resultado


def _panel_wlan(cat, errores):
    frecuencias = st.multiselect('Frecuencias WLAN', [WLAN_24, WLAN_5], key='q:wlan:frecuencias')
    salida = {}
    if WLAN_24 in frecuencias:
        modos = st.multiselect('Modos WLAN 2,4 GHz', WLAN_MODOS_24, key='q:wlan:24')
        salida[WLAN_24] = modos
        if not modos:
            errores.append('WLAN 2,4 GHz: selecciona al menos un modo.')
    if WLAN_5 in frecuencias:
        disponibles = [b for b in WLAN_UNII if b in cat.bandas('WLAN')]
        bandas = _seleccion_catalogo('Bandas WLAN 5 GHz', disponibles, 'q:wlan:unii', errores)
        modos = st.multiselect('Modos WLAN 5 GHz', WLAN_MODOS_5, key='q:wlan:5')
        st.caption('El modo a se incluye automáticamente en 5 GHz.')
        salida[WLAN_5] = dict(bandas=bandas, modos=['a'] + modos)
        if not bandas:
            errores.append('WLAN 5 GHz: selecciona al menos una banda U-NII.')
        for modo in modos:
            if bandas and not any(modo in WLAN_UNII[b] for b in bandas):
                errores.append(f'WLAN: el modo {modo} no es compatible con las bandas elegidas.')
    if not frecuencias:
        errores.append('WLAN: selecciona al menos una frecuencia.')
    return salida


def _panel_5g(cat, errores):
    grupos = {}
    for banda in cat.bandas('5G'):
        grupos.setdefault(banda_base_5g(banda), []).append(banda)
    seleccionadas = _bandas('5G', list(grupos), errores)
    resultado = []
    for banda in seleccionadas:
        variantes = grupos[banda]
        if len(variantes) == 1:
            resultado.extend(variantes)
        else:
            elegidas = _seleccion_catalogo('Variantes de ' + banda, variantes, 'q:variantes:' + banda, errores)
            resultado.extend(elegidas)
            if not elegidas:
                errores.append(f'5G: selecciona al menos una variante de {banda}.')
    return _con_modos('5G', resultado)


def _formulario(base):
    errores = []
    st.subheader('Datos del ensayo')
    proyecto = st.text_input('Nombre del proyecto', key='q:proyecto', placeholder='Nombre del ensayo')
    izquierda, derecha = st.columns(2)
    with izquierda:
        regiones = st.multiselect('Regiones', REGIONES, key='q:region')
    with derecha:
        exposiciones = st.multiselect('Exposure conditions', EXPOSICIONES, key='q:exposure')
    conducida = st.radio('¿Se realizarán ensayos conducidos?', ['Sí', 'No'], key='q:conducida', horizontal=True)
    adicionales = {}
    for columna, categoria in zip(st.columns(3), CATEGORIAS):
        with columna:
            clave = categoria['clave']
            adicionales[clave] = []
            if st.checkbox(categoria['titulo'], key='q:hay:' + clave):
                cantidad = st.number_input(categoria['titulo_n'], min_value=1, max_value=10,
                                           step=1, key='q:cuantos:' + clave)
                for i in range(cantidad):
                    adicionales[clave].append(st.text_input(f'{categoria["item"]} {i + 1}',
                        key=f'q:nombre:{clave}:{i}').strip())
    st.divider()
    st.subheader('Tecnologías y bandas')
    opciones = TECNOLOGIAS + [t for t in base.catalogo.by_tech if t.startswith('Custom')]
    seleccion = _seleccion_catalogo('Tecnologías del ensayo', opciones, 'q:tecnologias', errores)
    tecnologias = {}
    for tipo in seleccion:
        with st.container(border=True):
            st.markdown('**' + tipo + '**')
            if tipo == '2G':
                tecnologias[tipo] = _panel_2g(errores)
            elif tipo == '3G':
                subtipos = st.multiselect('Tecnologías 3G', OPCIONES_3G, key='q:3g')
                tecnologias[tipo] = {}
                if not subtipos:
                    errores.append('3G: selecciona al menos una tecnología.')
                for subtipo in subtipos:
                    bandas = _bandas(subtipo, base.catalogo.bandas(subtipo), errores)
                    tecnologias[tipo][subtipo] = _con_modos(subtipo, bandas)
            elif tipo == 'WLAN':
                tecnologias[tipo] = _panel_wlan(base.catalogo, errores)
            elif tipo == '5G':
                tecnologias[tipo] = _panel_5g(base.catalogo, errores)
            else:
                bandas = _bandas(tipo, base.catalogo.bandas(tipo), errores)
                tecnologias[tipo] = _con_modos(tipo, bandas)
    datos = dict(proyecto=proyecto.strip(), region=regiones, exposure=exposiciones,
                 conducida=conducida == 'Sí', tecnologias=tecnologias, **adicionales)
    return datos, errores


def _barra_lateral():
    with st.sidebar:
        st.header('Base de datos')
        archivo = st.file_uploader('Cargar base XLSX', type=['xlsx'], key='base_upload',
            help='Sin cargar un archivo se usa la base incluida en el programa.')
        try:
            contenido = archivo.getvalue() if archivo else BASE_PREDETERMINADA.read_bytes()
            nombre = archivo.name if archivo else BASE_PREDETERMINADA.name
            firma = (nombre, hashlib.sha256(contenido).hexdigest())
            if st.session_state.get('base_firma') != firma:
                nueva = cargar_base(contenido, nombre)
                st.session_state['base_activa'] = nueva
                st.session_state['base_firma'] = firma
                st.session_state.pop('resultado', None)
            base = st.session_state['base_activa']
        except (OSError, ValueError) as exc:
            st.error('No se pudo cargar la base: ' + str(exc))
            st.stop()
        st.caption('Base activa: ' + base.nombre)
        st.caption(f'{len(base.catalogo.records):,} registros · SHA-256 {base.catalogo.sha256[:12]}…')
        st.divider()
        st.subheader('Repetir un ensayo')
        respuestas = st.file_uploader('Respuestas guardadas', type=['json'], key='json_upload')
        if st.button('Cargar respuestas', key='cargar_json', disabled=respuestas is None):
            try:
                estado = cargar_respuestas(respuestas.getvalue(), base)
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                st.error('No se pudieron cargar las respuestas: ' + str(exc))
            else:
                for clave in list(st.session_state):
                    if clave.startswith('q:') or clave in ('resultado', 'aviso_importacion'):
                        del st.session_state[clave]
                st.session_state.update(estado)
                st.success('Respuestas cargadas con la base activa.')
        st.divider()
        st.caption('No hace falta cargar el datasheet original. El programa conserva las plantillas y usa el generador existente.')
    return base


def main():
    st.set_page_config(page_title='Toma de datos SAR', page_icon='📋', layout='wide')
    st.title('Toma de datos SAR')
    st.write('Configura el ensayo y descarga el Excel en una sola aplicación.')
    base = _barra_lateral()
    if st.session_state.get('aviso_importacion'):
        st.info(st.session_state['aviso_importacion'])
    datos, errores = _formulario(base)
    st.divider()
    if st.button('Generar Excel', key='generar_excel', type='primary', width='stretch'):
        st.session_state.pop('resultado', None)
        try:
            if errores:
                raise ValueError('\n'.join(errores))
            validar(datos, base.catalogo)
            with st.spinner('Generando el Excel y comprobando sus hojas…'):
                st.session_state['resultado'] = generar_paquete(datos, base)
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            logging.exception('No se ha podido generar el ensayo desde Streamlit')
            st.error('No se ha podido generar el Excel. Consulta el detalle en la terminal donde abriste la aplicación.')
    resultado = st.session_state.get('resultado')
    if resultado:
        if errores or resultado['huella'] != huella(datos, base):
            st.info('Has cambiado las opciones. Pulsa Generar Excel para actualizar los archivos.')
        else:
            st.success('Excel generado. Ya puedes descargar los archivos.')
            st.caption('Hojas: ' + ', '.join(resultado['resumen']['hojas']))
            nombre = resultado['nombre']
            descargas = [('Descargar Excel', 'excel', '.xlsm', 'application/vnd.ms-excel.sheet.macroEnabled.12'),
                         ('Descargar todo en ZIP', 'zip', '.zip', 'application/zip'),
                         ('Guardar respuestas JSON', 'respuestas', '.json', 'application/json'),
                         ('Descargar resumen TXT', 'texto', '.txt', 'text/plain')]
            for columna, (etiqueta, clave, extension, mime) in zip(st.columns(4), descargas):
                with columna:
                    st.download_button(etiqueta, resultado[clave], nombre + extension, mime=mime,
                                       on_click='ignore', width='stretch')
            st.caption('El ZIP contiene el Excel, las respuestas, el resumen y la base utilizada.')
            avisos = resultado['resumen'].get('avisos', [])
            if avisos:
                with st.expander(f'Avisos del generador ({len(avisos)})'):
                    for aviso in avisos:
                        st.write(aviso)


if __name__ == '__main__':
    main()
