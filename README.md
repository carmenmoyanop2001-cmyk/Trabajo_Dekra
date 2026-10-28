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
Puedes marcar varias regiones y varias exposure conditions. En GPRS y EGPRS, marcar TXn incluye automáticamente TX1 hasta TXn.

Rellena el cuestionario y pulsa **Generar toma de datos**. Se crean `<nombre>.txt` y `<nombre>.xlsm` en la carpeta que elijas.

## Qué pestañas salen
| Pestaña | Cuándo |
|---|---|
| Overview | siempre (con nombre del proyecto, baterías y accesorios) |
| Test Campaign | siempre |
| SAR EN y/o SAR FCC-ISED | EN → SAR EN; FCC e ISED → SAR FCC-ISED (una sola hoja compartida) |
| Tune-Up | soporte de los enlaces y límites de las hojas de tecnologías |
| 2G-3G / LTE / LTE CATM1 / LTE NB-IoT / 5G / WiFi | siempre que se seleccione la tecnología; con prefijo `Conducted ` si aplican ensayos conducidos. 2G y 3G comparten pestaña |

## Reglas aplicadas
* **Filas**: se generan solo las de las tecnologías/bandas/modos elegidos. En las Conducted se usa el bloque de región coherente con el que referencia la hoja SAR; en la columna B se escribe `EN`, `FCC/ISED` o `EN/FCC/ISED` para las filas compartidas, según las regiones elegidas.
* **SAR FCC-ISED**: solo se filtran las filas originales por tecnología, banda, exposición y modos seleccionados. Se conservan sus posiciones, baterías y Variability originales; no se añaden ni se renombran filas por las respuestas sobre baterías, accesorios o spotchecking.
* **SAR EN**: se conservan las filas originales filtradas. Debajo de cada grupo se insertan `TBD - Battery check N` y, solo en Body, `Front of Face` y `Accesorio N: nombre`. Las filas nuevas copian el formato y las fórmulas de la fila superior; el contenido siguiente se desplaza, no se sobrescribe. No se generan filas Variability ni se sustituyen las fórmulas de las filas nuevas por N/A.
* **Overview**: nombre del proyecto en `E4`, baterías en `J/K` desde la fila 28 y accesorios en `O/P`. Si caben menos de las pedidas (más de 5 baterías) se **insertan filas desplazando el resto** (fórmulas de todas las hojas, formatos condicionales, imagen/botón incluidos); no se borra ni se pisa nada.
* **Fórmulas**: se conservan y se reubican a las nuevas filas. Referencias a filas que no están en la selección: apuntan a una celda vacía (equivale a "sin medir"), o se sustituyen por la celda maestra del límite SAR. Los `INDIRECT` de Tune-Up/Conducted 5G se convierten en referencias directas.
* **Nombres de tecnologías**: con conducidos se usan `Conducted LTE`, etc.; sin conducidos se usan `LTE`, etc. Los enlaces de las fórmulas se actualizan al nombre de cada pestaña. Tune-Up se mantiene para conservar sus referencias. Las fórmulas se reubican al filtrar o insertar filas; no se cambian los datos originales de FCC por las respuestas de baterías/accesorios.

## Cosas que conviene saber
* Es `.xlsm` porque `MyTimestamp` (fechas al introducir un valor) es una macro. Hay que **habilitar macros**; sin ellas las columnas de fecha dan error. Al abrir saldrá el formulario antiguo de "selección de hojas" (viene del proyecto VBA): se puede cerrar.
* La plantilla trae **4 conjuntos de antena** por banda; salen los 4 (la interfaz aún no pregunta por antenas).
* SAR solo tiene filas para GSM, GPRS 4TX, WCDMA, LTE, LTE CATM1, 5G, WLAN, BT y Custom; EGPRS, GPRS 1-3TX, HSDPA/HSPA/DC-HSDPA y NB-IoT solo aparecen en las Conducted. Si una banda no existe en SAR para esa región/exposición, no sale.
* BT y Custom1-8 aún no están en el cuestionario.
* `#N/A` en la columna de peor caso de batería es normal mientras no haya medidas.
* Comprobado con pruebas automatizadas y con `herramientas/validar_paquete.py` (estructura del paquete). **No se ha podido probar en Excel**: conviene abrir el primer archivo en Excel y comprobarlo.

## Si algún día cambia el datasheet
`python herramientas/extraer_plantilla.py ruta/datasheet.xlsm` regenera `plantilla/` (la hoja de 5G tarda ~10 min).

## Archivos
`cuestionario_ensayo.py` (interfaz) · `generador_excel.py` (genera el .xlsm) · `seleccion.py` (qué filas entran, filas nuevas SAR) · `overview.py` (edición de Overview) · `nucleo.py`/`sarlib.py` (fórmulas, filas XML) · `plantilla/` (datos extraídos) · `herramientas/`
