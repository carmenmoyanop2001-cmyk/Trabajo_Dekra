# Fuente de datos y formatos guardados

El programa usa dos elementos independientes: una base XLSX editable con los datos RF, y un paquete de formatos y hojas originales que viaja con el código. Las respuestas del formulario indican qué registros y condiciones utilizar. No hace falta conservar el Excel original junto al programa.

## Flujo habitual

1. Extrae el ZIP completo e instala `requirements.txt` si es necesario.
2. Ejecuta `INICIAR_CUESTIONARIO.bat` o `python cuestionario_ensayo.py`.
3. Elige la base XLSX con **Elegir base de datos…**. Se incluye una copia de la base recibida en `datos/`.
4. Selecciona las opciones y genera el ensayo. Obtendrás TXT, JSON y XLSM.
5. Para otra versión, elige la base actualizada y carga el JSON de respuestas. Puedes cambiar las opciones antes de generar.

La base se vuelve a leer antes de generar. Si has cambiado un canal o frecuencia, la nueva salida usa el dato nuevo. Si has eliminado una banda seleccionada, la aplicación lo indica y conserva el Excel previo; no busca esa banda en las plantillas antiguas. **Recargar base** reconstruye las opciones del formulario con el contenido actual del archivo.

Las opciones mantienen la organización anterior. Al marcar GPRS o EGPRS aparecen sus slots y justo debajo **Bandas disponibles: (850, 900, 1800, 1900)** con un campo para escribir las elegidas. GSM tiene sus propias opciones y entrada. Las demás tecnologías también muestran sus opciones como texto entre paréntesis: por ejemplo, LTE **(1, 2, 3, …)**. Escribe los números separados por comas y pulsa **Aceptar bandas**. Las variantes 5G aparecen al aceptar sus bandas. WiFi conserva 2,4/5 GHz, modos y U-NII. Las opciones 3G siguen visibles; si una no tiene datos en la base elegida, se avisa en lugar de inventarlos.

Los JSON nuevos usan `tecnologias.2G.bandas_por_modo` para mantener bandas independientes de GSM, GPRS y EGPRS. Se siguen admitiendo las respuestas anteriores con una lista compartida `bandas`, que al cargar se aplica a cada modo activo. Se admiten números y etiquetas completas; si un número corresponde a más de una banda, las opciones muestran las etiquetas para evitar ambigüedades. Si una banda guardada ya no existe en la base cargada, se muestra un aviso. Los cambios escritos se deben confirmar antes de generar.

Las tecnologías con una única banda posible no piden seleccionarla: la usan automáticamente. Esto incluye BT y Custom en la base incluida. Si la base se actualiza para añadirles más bandas, aparece el campo de selección. Las bandas de LTE CAT M1 y tecnologías equivalentes se presentan como números tanto en la entrada como en la confirmación y el resumen de bandas del archivo de texto. Las respuestas JSON conservan los identificadores que utiliza la base.

En el original, WCDMA, HSPA, HSPA+, HSDPA y DC-HSDPA tienen las mismas 12 bandas. Cuando la base solo aporta WCDMA, sus bandas, canales y frecuencias sirven también para las otras opciones 3G, conservando la tecnología elegida. Los parámetros específicos ausentes no se recuperan del Excel original. Una tabla específica en la base tiene prioridad sobre este catálogo común. La comprobación del original está en `docs/bandas_3g_original.json`.

El JSON guarda la ruta y el identificador de la base usada. Al cargarlo desde el formulario se utiliza la base que tengas elegida en ese momento; así puedes repetir una configuración con otra versión. Si mueves archivos a otro ordenador, elige primero su base allí. La CLI permite sustituir la referencia con `--base-datos`.

## Hojas originales conservadas

- **Overview:** presentación original, con proyecto, baterías y accesorios del cuestionario. Si hacen falta filas, se desplaza el contenido posterior.
- **Tune-Up:** se conserva la hoja completa del original, incluidos datos, fórmulas, colores y celdas. La base de datos no la reconstruye ni borra sus potencias.
- **Validations, Test Campaign y Pretesting-Others:** se guardan con el programa y se incluyen en la salida.
- **SAR EN y SAR FCC-ISED:** se guardan los procedimientos, posiciones, formatos y cálculos. Los datos RF se enlazan con las hojas de tecnologías construidas desde la base actual.

Las hojas de tecnologías aparecen con prefijo Conducted cuando se elige Sí y sin él cuando se elige No. EN genera SAR EN; FCC e ISED comparten SAR FCC-ISED sin duplicarla. El archivo terminado se verifica antes de sustituir la salida anterior.

En SAR EN, BY se combina por tecnología/banda y BX por exposición. Las baterías usan fórmulas como `CONCATENATE(CA9," - Battery check 1")`, adaptando la referencia del procedimiento FCC equivalente. Se mantienen sus valores iniciales TBD junto a las fórmulas. En Body se añaden Front Face y accesorios. No se añaden filas Variability. FCC mantiene sus filas de posiciones, baterías y Variability guardadas, sin insertar las opciones adicionales del formulario.

## Estructura de la base XLSX

Cada tabla de datos tiene una fila de cabecera y estas columnas mínimas:

| Columna | Contenido |
| --- | --- |
| Tecnología | Familia, por ejemplo GSM, GPRS 2TX, LTE, LTE-CAT M1, LTE NB-IoT, 5G o WLAN |
| Banda | Etiqueta que aparecerá en el formulario y la salida |
| Canal | Número, incluido 0 cuando el registro lo requiera |
| Frecuencia (MHz) | Número, con punto o coma decimal |

Columnas opcionales: Bandwidth (MHz), Modulation, UL RB Allocation, UL RB Start, Narrowband Index, SCS (kHz), MPR, Mode, Data Rate, Duty Cycle, Cert y Notas. Un guion o N/A en los parámetros opcionales significa no informado. Los campos ausentes quedan vacíos y no recuperan valores RF del datasheet. Tune-Up es una referencia fija independiente y se conserva del original.

LTE, CAT M1 y NB-IoT pueden convivir en la hoja LTE: se distinguen por la columna Tecnología. Narrowband Index se escribe en P y SCS en L. Se conservan todas las combinaciones distintas de parámetros de las bandas elegidas, sin añadir las combinaciones que existían únicamente en el Excel antiguo.

La entrega trae WLAN y Wifi duplicadas: se utiliza WLAN cuando está presente; si difieren, se informa. Si no existe WLAN se admite Wifi como alias. Los resúmenes sin parámetros no duplican combinaciones ya presentes en las tablas detalladas. Las hojas Notas se consideran documentación y no se ejecuta su contenido. Las notas de registros se conservan en Comment y se incluyen en los avisos de generación.

Las fórmulas del XLSX de datos deben tener su resultado guardado: si lo calculas con Excel, guarda el archivo antes de cargarlo. El programa no ejecuta macros ni calcula fórmulas de la base.

## Bandas nuevas y datos incompletos

Las familias con formato guardado admiten bandas nuevas desde la base, sin consultar el Excel original. La presentación usa un bloque de esa familia, pero los valores RF proceden de los registros nuevos. Una familia de tecnología completamente nueva necesita definir su formato y procedimiento; no basta con inventarle posiciones SAR.

La base recibida no informa todos los modos, anchos de banda y otros parámetros de 5G, WiFi y BT. Se dejan vacíos o se usa el modo indicado explícitamente en el formulario. No se deducen parámetros técnicos a partir de valores antiguos.

GPRS/EGPRS conservan la selección acumulativa TX1–TXn. SAR no tiene procedimientos propios guardados para EGPRS, GPRS TX1–TX3, HSPA/HSDPA/DC-HSDPA o NB-IoT; estas selecciones tienen su hoja de tecnología. Si toda la selección carece de procedimiento SAR para una región solicitada, se avisa y no se guarda una hoja SAR vacía. CAT M1 EN reutiliza la presentación de posiciones LTE, con los datos RF de CAT M1.

La Tune-Up guardada no se amplía ni modifica por añadir bandas en la base. Si una banda no tiene una referencia de potencia en esa hoja, la potencia objetivo queda pendiente; el programa no la toma de otra banda. Las medidas, potencias y resultados de ensayo no se inventan ni se rellenan con resultados antiguos.

## Ejecución y pruebas

```sh
python generar_desde_json.py ejemplos/ejemplo_base_datos.json salidas/ensayo.xlsm
python generar_desde_json.py respuestas.json salidas/ensayo_actualizado.xlsm --base-datos base_actualizada.xlsx
python -m unittest discover -s tests -v
```

La CLI rechaza sobrescribir salidas existentes. El formulario permite sustituirlas con su confirmación habitual. La escritura de XLSM es atómica y valida el paquete antes de publicarlo.

`tests/test_base_datos.py` comprueba la ruta de producción: cambios de canales/frecuencias/parámetros, bandas nuevas, datos incompletos, tablas exactas de tecnologías, fuente independiente del Excel original, Tune-Up intacta, regiones, carga de respuestas y CLI. Las auditorías históricas usan explícitamente `generar_heredado`, que no está conectada a la interfaz ni a la CLI de producción.

Los formatos reducidos de `plantilla/formatos/` evitan cargar los millones de filas antiguas para construir una tabla desde la base. Los scripts de `herramientas/` permiten preparar esos formatos y conservar las hojas estáticas; no se ejecutan al generar un ensayo.

La validación estructural se complementa con el SDK oficial Open XML. No ejecuta Microsoft Excel, VBA ni cálculos. Se conserva MyTimestamp. La revisión visual de la interfaz y de los libros queda pendiente en un equipo con Excel. Los informes de originales de versiones anteriores están en docs/ como auditoría histórica, no como fuente RF de la generación actual.
