"""Opciones de la toma de datos compartidas por interfaz y generador."""
REGIONES = ["EN", "FCC", "ISED"]
REGION_AYUDA = {"EN": "Europa", "FCC": "Estados Unidos", "ISED": "Canadá"}
EXPOSICIONES = ["Close to ear", "Close to Head", "Body", "Extremity"]
SI, NO = "Sí", "No"

MIN_N, MAX_N = 1, 10  # límites para baterías, accesorios y variantes
ARCHIVO_POR_DEFECTO = "datos_ensayo.txt"

# --- Bandas válidas, extraídas de la columna K (Band) de cada pestaña del datasheet ---
def _mapa_bandas(fdd, tdd=()):
    mapa = {n: f"FDD{n}" for n in fdd}
    mapa.update({n: f"TDD{n}" for n in tdd})
    return dict(sorted(mapa.items()))


_LTE_FDD = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23, 24,
            25, 26, 27, 28, 30, 66, 71]
_LTE_TDD = [33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44]
BANDAS_LTE = _mapa_bandas(_LTE_FDD, _LTE_TDD)           # pestaña Conducted LTE
BANDAS_CATM1 = _mapa_bandas(_LTE_FDD, _LTE_TDD)         # pestaña Conducted LTE CATM1
BANDAS_NBIOT = _mapa_bandas([1, 2, 3, 4, 5, 7, 8, 9, 12, 13, 14, 17, 20, 22, 23, 24, 25,
                             26, 27, 28, 30, 31, 66, 68, 70, 71, 72, 74, 85])  # Conducted LTE NB-IoT
BANDAS_5G = {n: f"n{n}" for n in [1, 2, 3, 5, 7, 8, 18, 20, 25, 26, 28, 38, 39, 40, 41,
                                  66, 77, 78, 79]}      # pestaña Conducted 5G
# Variantes adicionales que el datasheet tiene para algunas bandas 5G
VARIANTES_5G = {n: [f"n{n}", f"n{n} part O", f"n{n} part Q", f"n{n} RSS-192"] for n in (77, 78)}

OPCIONES_2G = ["GPRS", "EGPRS", "GSM"]
SLOTS_2G = ["TX1", "TX2", "TX3", "TX4"]                 # GSM no lleva slots
OPCIONES_3G = ["DC-HSDPA", "HSDPA", "HSPA", "HSPA+", "WCDMA"]

# WLAN: frecuencias y modos existentes en el datasheet (Conducted WiFi)
WLAN_24 = "2,4 GHz"          # en el datasheet figura como "2.4 GHz"
WLAN_5 = "5 GHz"
WLAN_MODOS_24 = ["b", "g", "n20", "n40", "ac20", "ac40", "ax20", "ax40"]
WLAN_MODO_5 = "a"             # modo "a" de 5 GHz: siempre seleccionado
_N = ["n20", "n40"]
_AC_AX_160 = ["ac20", "ac40", "ac80", "ac160", "ax20", "ax40", "ax80", "ax160"]
_AC_AX_80 = ["ac20", "ac40", "ac80", "ax20", "ax40", "ax80"]
WLAN_MODOS_5 = _N + _AC_AX_160                  # resto de modos de 5 GHz (además de "a")
# Bandas U-NII de 5 GHz, y modos que tienen datos en cada una
WLAN_UNII = {"U-NII-1": _N + _AC_AX_160, "U-NII-2A": _N + _AC_AX_160,
             "U-NII-2C": _N + _AC_AX_160, "U-NII-3": _N + _AC_AX_80,
             "U-NII-4": _N + _AC_AX_80}

# Los tres elementos que siempre aparecen en pantalla
CATEGORIAS = [
    {"clave": "baterias", "pregunta_si": "¿Tiene baterías adicionales?",
     "pregunta": "¿Cuántas baterías adicionales tiene?", "item": "Batería",
     "descripcion": "baterías adicionales", "titulo": "Baterías adicionales",
     "titulo_n": "Número de baterías adicionales"},
    {"clave": "accesorios", "pregunta_si": "¿Tiene accesorios adicionales?",
     "pregunta": "¿Cuántos accesorios adicionales tiene?", "item": "Accesorio",
     "descripcion": "accesorios adicionales", "titulo": "Accesorios adicionales",
     "titulo_n": "Número de accesorios adicionales"},
    {"clave": "spotchecking", "pregunta_si": "¿Lleva Spotchecking?",
     "pregunta": "Número de variantes", "item": "Variante",
     "descripcion": "variantes de spotchecking", "titulo": "Spotchecking",
     "titulo_n": "Número de variantes"},
]


