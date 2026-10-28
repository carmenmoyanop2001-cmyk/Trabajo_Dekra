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
