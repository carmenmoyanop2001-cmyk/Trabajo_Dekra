# Toma de datos SAR

## Interfaz de escritorio

Instala Python 3 con tkinter. Desde esta carpeta:

```sh
python -m pip install -r requirements.txt
python cuestionario_ensayo.py
```

Rellena el cuestionario y pulsa **Generar toma de datos**. Se guarda el texto con las respuestas y un `.xlsm` en la carpeta elegida. El Excel se valida antes de sustituir la salida: si falla la generación, se conserva el Excel anterior. La aplicación avisa de fórmulas con `#REF!` heredadas de la plantilla y de selecciones sin filas SAR.

## Generación sin pantalla

```sh
python generar_desde_json.py ejemplos/ejemplo_EN.json salidas/mi_ensayo.xlsm
```

Cambia las respuestas del JSON para tu ensayo; los ejemplos son ficticios. Esta opción genera `.txt` y `.xlsm`, y rechaza sobrescribir archivos existentes. No necesita tkinter ni el datasheet original. Los identificadores de bandas y modos se comparten con el cuestionario. No se admiten tecnologías desconocidas ni bandas inexistentes.

## Comprobaciones

```sh
python -m unittest discover -s tests -v
```

Se prueban las tres regiones, selección de hojas, seis baterías, ocho accesorios, tres variantes, conservación del proyecto VBA, entradas inválidas y preservación de archivos ante errores. La interfaz se importa y se comprueba su formato de respuestas 2G, pero no se ha probado visualmente en este entorno sin pantalla.

## Contraste con los archivos originales

Se han inspeccionado las nueve hojas específicas de los diez libros recibidos. Los libros SAR EN y FCC, CATM1, NB-IoT y 5G contienen fórmulas con `#REF!`. El informe `docs/comparacion_originales.json` indica los recuentos y ejemplos; no demuestra cuándo ni por qué se rompieron. No se han usado estos libros para sobrescribir las plantillas completas: podrían perderse referencias, formatos o bandas.

El archivo 5G recibido tiene 8.182 filas, frente a 220.322 de la plantilla incluida. Se conserva la plantilla completa. Los ejemplos conducidos seleccionados heredan 18 fórmulas con `#REF!` de NB-IoT; se notifican expresamente sin inventar referencias. Las potencias de los ensayos sin conducidos quedan vacías para introducirlas manualmente.

La validación XML comprueba estructura, relaciones y orden de filas/celdas; no calcula fórmulas ni ejecuta macros. Queda pendiente la comprobación funcional en Microsoft Excel y la resolución de referencias rotas de origen. Las fechas dependen de la macro MyTimestamp incluida.

No se han añadido preguntas de antenas, BT ni Custom; se mantiene el alcance del cuestionario recibido.

Se han contrastado también las fórmulas de las filas 3 a 10 de las nueve hojas específicas: 2107 fórmulas coincidentes y 42 diferencias, todas con #REF! en los archivos SAR recibidos. Es una muestra, no una comparación exhaustiva. Detalle en `docs/contraste_muestra_formulas.json`.

## Selección múltiple y slots acumulativos

Se pueden marcar varias regiones y varias exposure conditions. El Excel reúne las condiciones seleccionadas en cada hoja SAR. EN añade SAR EN; FCC e ISED comparten SAR FCC-ISED y no duplican sus filas. Las hojas Conducted conservan los bloques necesarios para ambas familias de región. Los accesorios y Front of Face se añaden únicamente a los grupos Body.

En GPRS y EGPRS, marcar TX3 activa TX1, TX2 y TX3. Marcar TX4 activa los cuatro. Al desmarcar TX2, por ejemplo, solo queda TX1. GPRS y EGPRS se configuran de forma independiente. La selección se refleja en el resumen de texto y en las filas Conducted. La plantilla SAR solo tiene GPRS 4TX, por lo que elegir TX1-TX3 no crea modos SAR inexistentes.

Para JSON, `region` y `exposure` admiten listas; se mantiene la compatibilidad con los archivos antiguos que contienen una sola cadena. GPRS y EGPRS admiten una lista de slots o la cadena antigua del máximo: `"TX3"` incluye también TX1 y TX2. Consulta `ejemplos/ejemplo_multiple.json`.

Algunas fórmulas FCC de LTE FDD5 apuntan a CATM1 en la plantilla original. Si CATM1 no se selecciona, los enlaces no disponibles quedan vacíos y se muestra un aviso; no se ha sustituido la referencia de origen.
