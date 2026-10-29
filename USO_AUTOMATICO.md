# Toma de datos SAR

## Interfaz de escritorio

Instala Python 3 con tkinter. Desde esta carpeta:

```sh
python -m pip install -r requirements.txt
python cuestionario_ensayo.py
```

Rellena el cuestionario y pulsa **Generar toma de datos**. Se guarda el texto con las respuestas y un `.xlsm` en la carpeta elegida. El Excel se valida antes de sustituir la salida: si falla la generación, se conserva el Excel anterior. La aplicación avisa de fórmulas con `#REF!` heredadas de la plantilla y de selecciones sin filas SAR. Las pestañas de tecnologías aparecen siempre: `Conducted LTE`, etc., si se eligen conducidos, y `LTE`, etc., si no; sus enlaces se actualizan.

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

El archivo 5G recibido tiene 8.182 filas, frente a 220.322 de la plantilla incluida. Se conserva la plantilla completa. Los ejemplos conducidos seleccionados heredan 18 fórmulas con `#REF!` de NB-IoT; se notifican expresamente sin inventar referencias. Sin conducidos se conservan las pestañas de tecnologías y sus enlaces, con sus nombres sin el prefijo Conducted. No se introducen medidas nuevas.

La validación XML comprueba estructura, relaciones y orden de filas/celdas; no calcula fórmulas ni ejecuta macros. Queda pendiente la comprobación funcional en Microsoft Excel y la resolución de referencias rotas de origen. Las fechas dependen de la macro MyTimestamp incluida.

No se han añadido preguntas de antenas, BT ni Custom; se mantiene el alcance del cuestionario recibido.

Se han contrastado también las fórmulas de las filas 3 a 10 de las nueve hojas específicas: 2107 fórmulas coincidentes y 42 diferencias, todas con #REF! en los archivos SAR recibidos. Es una muestra, no una comparación exhaustiva. Detalle en `docs/contraste_muestra_formulas.json`.

## Selección múltiple y slots acumulativos

Se pueden marcar varias regiones y varias exposure conditions. El Excel reúne las condiciones seleccionadas en cada hoja SAR. EN añade SAR EN; FCC e ISED comparten SAR FCC-ISED y no duplican sus filas. Las hojas Conducted conservan los bloques necesarios para ambas familias de región. Los accesorios y Front Face de SAR EN se añaden únicamente a sus grupos Body. FCC conserva las posiciones y baterías que ya contiene la plantilla original.

En GPRS y EGPRS, marcar TX3 activa TX1, TX2 y TX3. Marcar TX4 activa los cuatro. Al desmarcar TX2, por ejemplo, solo queda TX1. GPRS y EGPRS se configuran de forma independiente. La selección se refleja en el resumen de texto y en las filas Conducted. La plantilla SAR solo tiene GPRS 4TX, por lo que elegir TX1-TX3 no crea modos SAR inexistentes.

Para JSON, `region` y `exposure` admiten listas; se mantiene la compatibilidad con los archivos antiguos que contienen una sola cadena. GPRS y EGPRS admiten una lista de slots o la cadena antigua del máximo: `"TX3"` incluye también TX1 y TX2. Consulta `ejemplos/ejemplo_multiple.json`.

Algunas fórmulas FCC de LTE FDD5 apuntan a CATM1 en la plantilla original. Si CATM1 no se selecciona, los enlaces no disponibles quedan vacíos y se muestra un aviso; no se ha sustituido la referencia de origen.

## Conservación de las hojas SAR

SAR FCC-ISED conserva sus filas originales que cumplen el filtro de tecnologías, bandas, exposure conditions y modos. No se renombran posiciones ni baterías; tampoco se sustituyen sus filas Variability originales por variantes del cuestionario.

En SAR EN se conservan todas las filas originales seleccionadas y se insertan debajo de cada grupo las baterías elegidas y, para Body, Front Face y accesorios. Se copian los estilos de la fila superior y se adaptan las fórmulas equivalentes de FCC-ISED a EN; no se sustituyen esas fórmulas por constantes N/A; también se amplían las reglas de formato condicional y las validaciones que afectaban a esa fila. Las filas posteriores se desplazan. No se añaden filas Variability. Spotchecking se registra en el resumen de respuestas, pero no añade filas SAR.

La posición de cada batería en CA es una fórmula, como `CONCATENATE(CA9," - Battery check 1")`, adaptada a su fila de referencia en EN. Inicialmente muestra «TBD - Battery check n» y se actualiza con la posición del ensayo de referencia. El nombre de la exposure condition se muestra en negro en BX, conservando la celda combinada y su fondo original.

La reubicación de referencias sigue siendo necesaria cuando se filtran filas, se insertan otras o se cambia el nombre de las hojas. Se conservan las fórmulas de origen; los enlaces que no pueden resolverse siguen notificándose en los avisos. Las macros se conservan y requieren comprobación en Excel.

SAR EN inserta las baterías al final de cada bloque de exposición original, justo tras sus TBD. En Body añade además Front Face y los accesorios. Se mantienen los límites y medidas EN de 10 g. Consulta `docs/formulas_sar_en.md`.

Se incluye `ejemplos/SAR_EN_GSM_2_baterias.xlsm`, generado con dos baterías y dos accesorios para los cuatro puntos del ejemplo GSM. Es una demostración con datos ficticios. Si una selección no existe en la hoja SAR original, la aplicación avisa y conserva el Excel anterior en lugar de guardar una hoja SAR vacía.

## Mode combinado y valores originales

En SAR EN, Mode (BY) es una única celda combinada por tecnología y banda, incluyendo todas sus exposiciones y las filas adicionales. Cuando hay varios modos originales, se muestran juntos. Los modos por fila se conservan en CG, que ya estaba oculta; los cálculos leen esa columna. Las celdas conservan el color original y el resumen de Mode se centra y ajusta a varias líneas.

Se guardan los valores originales de Channel (CC), Freq (CD) y las posiciones TBD junto con sus fórmulas. También se conservan los resultados de las fórmulas de la columna O de CATM1. El libro solicita recálculo automático al abrirlo. No se eliminan filas de ensayo por tener una fórmula pendiente de calcular: solo se omiten las filas que no cumplen la selección y las restantes se escriben consecutivamente, sin filas espaciadoras.

El ejemplo `ejemplos/SAR_EN_5G_CATM1_3_baterias.xlsm` permite comprobar 5G n1, CATM1 FDD1 y GSM, con tres baterías y tres accesorios. Los datos de sus respuestas son ficticios. Véase `docs/valores_y_mode.md` para las comprobaciones.

Corrección puntual: Cert. (B) en todas las tecnologías conserva los valores originales por fila para cualquier región, sin asignar EN/FCC/ISED a una fila por el hecho de compartirla entre regiones. En SAR EN, BX se combina por tecnología, banda y exposure condition, incluyendo las filas adicionales; FCC-ISED permanece igual.

La auditoría de Cert. está en `docs/auditoria_cert_originales.json`: se contrastaron 80.612 filas identificables en los siete originales recibidos. El archivo 5G recibido es parcial y tiene referencias rotas en sus últimas filas. Los marcadores ? y #REF! de origen se conservan y se avisan; no se deducen certificaciones nuevas. El ejemplo `ejemplos/Cert_regiones_multiples.xlsm` muestra todas las tecnologías disponibles con EN, FCC e ISED seleccionadas.

## WLAN en SAR

Las hojas SAR originales reservan las filas WLAN con Mode/BW `TBD`, `TBD / NA` o sin modo concreto. Se conservan las filas de la banda y exposure condition elegidas, incluidas las filas adicionales originales de FCC. Elegir varios modos, como n40 y ac40, no duplica esas filas SAR. En Conducted WiFi sí se filtran los modos concretos seleccionados. No se sustituyen los marcadores originales por medidas o modos inventados.

`ejemplos/ejemplo_seleccion_wlan_sar.json` reproduce la selección que provocaba el error de SAR EN vacío. Su Excel de ejemplo es `ejemplos/SAR_EN_seleccion_WLAN.xlsm`, con baterías ficticias. Las tecnologías sin filas en la plantilla SAR original siguen teniendo su pestaña de tecnología; no se crean filas SAR para ellas.
