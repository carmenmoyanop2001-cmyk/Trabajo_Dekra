"""Desactivar solo la apertura automatica del selector de hojas de la plantilla conocida."""
from hashlib import sha256

# Proyecto original comprobado: Show solo se usa en Workbook_Open para este formulario.
PROYECTO_ORIGINAL = 'f292b73bdf87befb4381f2fadacfdebcadcc7d7b6ee93ab2dbff2e8977d2f077'
PROYECTO_CORREGIDO = '4dd52918db35ed57c477a80cf4295126765074df623875137780f9fbb4eba5be'


def sin_selector_automatico(data):
    firma = sha256(data).hexdigest()
    if firma == PROYECTO_CORREGIDO:
        return data
    if firma != PROYECTO_ORIGINAL:
        raise ValueError('El proyecto VBA de la plantilla no coincide con el revisado. '
                         'Se conserva intacto; hace falta revisar su Workbook_Open.')
    # Cambiar la llamada del formulario y su identificador compilado, ambos de 4 bytes.
    # Conserva contenedor OLE, tamanos de streams y todas las demas macros.
    if data.count(b'Show') != 2:
        raise ValueError('No se reconoce la llamada VBA del selector de hojas.')
    corregido = data.replace(b'Show', b'Hide')
    if sha256(corregido).hexdigest() != PROYECTO_CORREGIDO:
        raise ValueError('No se pudo verificar la correccion del selector de hojas.')
    return corregido
