# Toma de datos SAR – cuestionario + generador de Excel

Programa en Python que hace el cuestionario de la toma de datos y genera:
1. un **archivo de texto** con las respuestas, y
2. un **Excel (.xlsm)** con las pestañas, filas y fórmulas del datasheet FAN22_09 correspondientes a esas respuestas.

**No necesita el datasheet original**: la carpeta `plantilla/` lleva dentro las fórmulas, estilos, macros y estructura de filas.

## Cómo usarlo
```
pip install lxml          # única dependencia fuera de Python (tkinter viene con Python)
python cuestionario_ensayo.py
```
Rellena el cuestionario y pulsa **Generar toma de datos**. Se crean `<nombre>.txt` y `<nombre>.xlsm` en la carpeta que elijas.

## Qué pestañas salen
| Pestaña | Cuándo |
|---|---|
| Overview | siempre (con nombre del proyecto, baterías y accesorios) |
| Test Campaign | siempre |
| SAR EN **o** SAR FCC-ISED | siempre una: EN → SAR EN; FCC e ISED → SAR FCC-ISED |
| Tune-Up | solo si aplican ensayos conducidos |
| Conducted 2G-3G / LTE / LTE CATM1 / LTE NB-IoT / 5G / WiFi | solo si aplican ensayos conducidos **y** se ha marcado esa tecnología (2G y 3G comparten pestaña) |

## Reglas aplicadas
* **Filas**: se generan solo las de las tecnologías/bandas/modos elegidos. En las Conducted se usa el bloque de región coherente con el que referencia la hoja SAR; en la columna B se escribe `EN` o `FCC/ISED` según la región.
* **SAR**: solo las filas de la exposure condition elegida. Tras las filas TBD de cada grupo se añaden, en este orden:
  `TBD - Variability: <nombre>` (spotchecking) → `TBD - Battery check N` (una por batería) → *(solo Body)* `Front of Face` → `Accesorio N: <nombre>`.
  En FCC-ISED se reutilizan las filas de la plantilla; si hay más baterías/accesorios/variantes que las de la plantilla (2 / 7 / 2) se crean copiando la última.
* **Overview**: nombre del proyecto en `E4`, baterías en `J/K` desde la fila 28 y accesorios en `O/P`. Si caben menos de las pedidas (más de 5 baterías) se **insertan filas desplazando el resto** (fórmulas de todas las hojas, formatos condicionales, imagen/botón incluidos); no se borra ni se pisa nada.
* **Fórmulas**: se conservan y se reubican a las nuevas filas. Referencias a filas que no están en la selección: apuntan a una celda vacía (equivale a "sin medir"), o se sustituyen por la celda maestra del límite SAR. Los `INDIRECT` de Tune-Up/Conducted 5G se convierten en referencias directas.
* **Sin ensayos conducidos**: las celdas SAR que enlazaban con Conducted/Tune-Up toman el valor por defecto de la plantilla (banda, canal, frecuencia, modo, BW); **potencia máxima y potencia conducida quedan vacías** para rellenar a mano.

## Cosas que conviene saber
* Es `.xlsm` porque `MyTimestamp` (fechas al introducir un valor) es una macro. Hay que **habilitar macros**; sin ellas las columnas de fecha dan error. Al abrir saldrá el formulario antiguo de "selección de hojas" (viene del proyecto VBA): se puede cerrar.
* La plantilla trae **4 conjuntos de antena** por banda; salen los 4 (la interfaz aún no pregunta por antenas).
* SAR solo tiene filas para GSM, GPRS 4TX, WCDMA, LTE, LTE CATM1, 5G, WLAN, BT y Custom; EGPRS, GPRS 1-3TX, HSDPA/HSPA/DC-HSDPA y NB-IoT solo aparecen en las Conducted. Si una banda no existe en SAR para esa región/exposición, no sale.
* BT y Custom1-8 aún no están en el cuestionario.
* `#N/A` en la columna de peor caso de batería es normal mientras no haya medidas.
* Validado con LibreOffice y con `herramientas/validar_paquete.py` (estructura del paquete). **No se ha podido probar en Excel**: conviene abrir el primer archivo en Excel y comprobarlo.

## Si algún día cambia el datasheet
`python herramientas/extraer_plantilla.py ruta/datasheet.xlsm` regenera `plantilla/` (la hoja de 5G tarda ~10 min).

## Archivos
`cuestionario_ensayo.py` (interfaz) · `generador_excel.py` (genera el .xlsm) · `seleccion.py` (qué filas entran, filas nuevas SAR) · `overview.py` (edición de Overview) · `nucleo.py`/`sarlib.py` (fórmulas, filas XML) · `plantilla/` (datos extraídos) · `herramientas/`
