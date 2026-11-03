# Fuente de datos y formatos guardados

El programa usa una base XLSX editable para delimitar los registros RF y aplicar sus valores, y una copia completa del original que viaja con el código en `plantilla/originales/`. Las respuestas del formulario indican qué registros y condiciones utilizar. No hace falta aportar el Excel original junto al ensayo. Se guardan las 16 pestañas recibidas, todos sus archivos relacionados y la 5G completa conservada previamente en el proyecto.

## Flujo habitual

1. Extrae el ZIP completo e instala `requirements.txt` si es necesario.
2. Ejecuta `INICIAR_CUESTIONARIO.bat` o `python cuestionario_ensayo.py`.
3. Elige la base XLSX con **Elegir base de datos…**. Se incluye una copia de la base recibida en `datos/`.
4. Selecciona las opciones y genera el ensayo. Obtendrás TXT, JSON y XLSM.
5. Para otra versión, elige la base actualizada y carga el JSON de respuestas. Puedes cambiar las opciones antes de generar.

La base se vuelve a leer antes de generar. Si has cambiado un canal o frecuencia, la nueva salida usa el dato nuevo. Si has eliminado una banda seleccionada, la aplicación lo indica y conserva el Excel previo; no busca esa banda en las plantillas antiguas. **Recargar base** reconstruye las opciones del formulario con el contenido actual del archivo.

En 2G se marcan GSM, GPRS y EGPRS y solo se piden sus slots TX. Sus bandas se toman completas de la base seleccionada. El resto conserva las listas de bandas como texto y la entrada por números. Al pulsar **Aceptar bandas**, **Seleccionadas** muestra las etiquetas completas: por ejemplo, **FDDI, FDDIII** en HSDPA. Las variantes 5G y las opciones WiFi se conservan.

Los JSON nuevos guardan únicamente modos y slots en `tecnologias.2G`. El formulario admite cargar respuestas anteriores, pero sus antiguas restricciones de bandas 2G se sustituyen por todas las bandas de la base actual. La CLI sigue admitiendo las respuestas antiguas. En las demás familias se admiten números y etiquetas completas y se comprueba que las bandas sigan en la base.

Las tecnologías con una única banda posible la usan automáticamente. Esto incluye BT y Custom en la base incluida. Si se añaden más bandas, aparece la entrada. En ella se pueden escribir números; la confirmación y las respuestas JSON conservan las etiquetas de la base.

En el original, WCDMA, HSPA, HSPA+, HSDPA y DC-HSDPA tienen las mismas 12 bandas. Cuando la base solo aporta WCDMA, sus bandas, canales y frecuencias sirven también para las otras opciones 3G, conservando la tecnología elegida. Una tabla específica en la base tiene prioridad sobre este catálogo común. La presentación completa filtra las filas originales correspondientes y conserva su información complementaria. La comprobación de bandas está en `docs/bandas_3g_original.json`.

El JSON guarda la ruta y el identificador de la base usada. Al cargarlo desde el formulario se utiliza la base que tengas elegida en ese momento; así puedes repetir una configuración con otra versión. Si mueves archivos a otro ordenador, elige primero su base allí. La CLI permite sustituir la referencia con `--base-datos`.

## Hojas originales conservadas

- **Overview:** presentación original, con proyecto, baterías y accesorios del cuestionario. Si hacen falta filas, se desplaza el contenido posterior.
- **Tune-Up:** se conserva la hoja completa del original, incluidos datos, fórmulas, colores y celdas. La base de datos no la reconstruye ni borra sus potencias.
- **Validations, Test Campaign y Pretesting-Others:** se guardan con el programa y se incluyen en la salida.
- **SAR EN y SAR FCC-ISED:** se guardan los procedimientos, posiciones, formatos y cálculos. Los datos RF se enlazan con las hojas de tecnologías construidas desde la base actual.

La pestaña compartida se llama **Conducted 2G**, **Conducted 3G** o **Conducted 2G-3G** según las familias marcadas cuando se elige Conducida. Al elegir No se omite el prefijo, igual que en el resto de tecnologías. EN genera SAR EN; FCC e ISED comparten SAR FCC-ISED sin duplicarla. El archivo terminado se verifica antes de sustituir la salida anterior.

La presentación de tecnologías se aplica después del motor aprobado. Se comprueba que las siete hojas protegidas y sus definiciones de estilos existentes permanecen idénticas. Los estilos de las vistas completas se incorporan sin modificar los anteriores. Las coordenadas de apoyo se conservan en filas ocultas y se enlazan a las medidas visibles. Si cambia el nombre de 2G-3G, una copia de apoyo oculta conserva el nombre anterior para que las fórmulas SAR no se reescriban.

Las tablas visibles recuperan las columnas, datos complementarios, medidas, fórmulas, celdas combinadas, filtros, colores, validaciones, comentarios y dibujos del original. Se compactan las filas descartadas y se ajustan las referencias. Los valores de la base tienen prioridad; los campos nuevos sin columna equivalente se añaden al final. Las capturas se conservan y sus anclajes se ajustan a la selección. Liquids-DRAFT y Pendiente también se guardan e incluyen con la visibilidad original.

En SAR EN, BY se combina por tecnología/banda y BX por exposición. Las baterías usan fórmulas como `CONCATENATE(CA9," - Battery check 1")`, adaptando la referencia del procedimiento FCC equivalente. Se mantienen sus valores iniciales TBD junto a las fórmulas. En Body se añaden Front Face y accesorios. No se añaden filas Variability. FCC mantiene sus filas de posiciones, baterías y Variability guardadas, sin insertar las opciones adicionales del formulario.

## Estructura de la base XLSX

Cada tabla de datos tiene una fila de cabecera y estas columnas mínimas:

| Columna | Contenido |
| --- | --- |
| Tecnología | Familia, por ejemplo GSM, GPRS 2TX, LTE, LTE-CAT M1, LTE NB-IoT, 5G o WLAN |
| Banda | Etiqueta que aparecerá en el formulario y la salida |
| Canal | Número, incluido 0 cuando el registro lo requiera |
| Frecuencia (MHz) | Número, con punto o coma decimal |

Columnas opcionales: Bandwidth (MHz), Modulation, UL RB Allocation, UL RB Start, Narrowband Index, SCS (kHz), MPR, Mode, Data Rate, Duty Cycle, Cert y Notas. Un guion o N/A en los parámetros opcionales significa no informado. Las filas que coinciden conservan el resto de su información original; en registros nuevos sin coincidencia no se toman parámetros RF ni medidas de otras combinaciones. Tune-Up es una referencia fija independiente y se conserva del original.

LTE, CAT M1 y NB-IoT pueden convivir en la base: se distinguen por Tecnología. Se incluyen únicamente las combinaciones RF permitidas por esa base y por el formulario, conservando las filas y detalles originales que correspondan a ellas.

La entrega trae WLAN y Wifi duplicadas: se utiliza WLAN cuando está presente; si difieren, se informa. Si no existe WLAN se admite Wifi como alias. Los resúmenes sin parámetros no duplican combinaciones detalladas. Las hojas Notas se consideran documentación y no se ejecuta su contenido. Las notas proporcionadas se conservan en la columna de comentarios y en los avisos de generación.

Las fórmulas del XLSX de datos deben tener su resultado guardado: si lo calculas con Excel, guarda el archivo antes de cargarlo. El programa no ejecuta macros ni calcula fórmulas de la base.

## Bandas nuevas y datos incompletos

Las familias con formato guardado admiten bandas nuevas desde la base, sin consultar el Excel original. La presentación usa un bloque de esa familia, pero los valores RF proceden de los registros nuevos. Una familia de tecnología completamente nueva necesita definir su formato y procedimiento; no basta con inventarle posiciones SAR.

Si la base no restringe modos o anchos de banda, la vista completa conserva las variantes originales que coincidan con sus registros y la selección. Para una combinación nueva sin coincidencia, solo se completan sus campos RF proporcionados; el resto queda pendiente. Se informa de esas filas al generar.

GPRS/EGPRS conservan la selección acumulativa TX1–TXn. SAR no tiene procedimientos propios guardados para EGPRS, GPRS TX1–TX3, HSPA/HSDPA/DC-HSDPA o NB-IoT; estas selecciones tienen su hoja de tecnología. Si toda la selección carece de procedimiento SAR para una región solicitada, se avisa y no se guarda una hoja SAR vacía. CAT M1 EN reutiliza la presentación de posiciones LTE, con los datos RF de CAT M1.

La Tune-Up guardada no se amplía ni modifica por añadir bandas en la base. Si una banda no tiene una referencia de potencia en esa hoja, la potencia objetivo queda pendiente; el programa no la toma de otra banda. Las medidas, potencias y resultados de ensayo no se inventan ni se rellenan con resultados antiguos.

## Ejecución y pruebas

```sh
python generar_desde_json.py ejemplos/ejemplo_tecnologias_ordenadas.json salidas/ensayo.xlsm
python generar_desde_json.py respuestas.json salidas/ensayo_actualizado.xlsm --base-datos base_actualizada.xlsx
python -m unittest discover -s tests -v
```

La CLI rechaza sobrescribir salidas existentes. El formulario permite sustituirlas con su confirmación habitual. La escritura de XLSM es atómica y valida el paquete antes de publicarlo.

`tests/test_base_datos.py` comprueba la ruta de producción: cambios de canales/frecuencias/parámetros, bandas nuevas, datos incompletos, tablas exactas de tecnologías, fuente independiente del Excel original, Tune-Up intacta, regiones, carga de respuestas y CLI. Las auditorías históricas usan explícitamente `generar_heredado`, que no está conectada a la interfaz ni a la CLI de producción.

Los formatos reducidos de `plantilla/formatos/` mantienen estable el motor SAR. La vista de tecnologías se obtiene de las copias completas de `plantilla/originales/`; 5G está indexada por bandas para evitar leerlas todas al generar. Los scripts de preparación de `herramientas/` no se ejecutan durante un ensayo. `guardar_originales_completos.py` admite tanto los adjuntos divididos como un original completo XLSX/XLSM para una actualización futura del formato.

La validación estructural se complementa con el SDK oficial Open XML. No ejecuta Microsoft Excel, VBA ni cálculos. Se conserva MyTimestamp. La revisión visual de la interfaz y de los libros queda pendiente en un equipo con Excel. Los informes de originales de versiones anteriores están en docs/ como auditoría histórica, no como fuente RF de la generación actual.
