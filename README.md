# Toma de datos SAR con el original completo guardado en el programa

La actualización actual corrige la causa identificada de la reparación de WiFi, separa las bandas de cada SAR según su certificación y permite desplazarse por 2G-3G, LTE y 5G sin inmovilizar sus filas ocultas. [Detalle de la corrección](docs/correccion_wifi_y_regiones.md). **Extrae esta versión en una carpeta nueva y abre `INICIAR_CUESTIONARIO.bat`.**

El formulario genera un `.xlsm`, un resumen `.txt` y las respuestas `.json` para repetir el ensayo. **La base XLSX determina qué registros existen y sus valores tienen prioridad; el cuestionario selecciona cuáles se incluyen.** Las tecnologías recuperan sus pestañas completas del original: columnas, datos de las filas coincidentes, fórmulas, colores, combinaciones, desplegables, comentarios e imágenes. No hace falta aportar el Excel original al generar otro ensayo.

`plantilla/originales/` conserva las 16 pestañas recibidas, sus formatos, fórmulas y partes auxiliares. Incluye la copia íntegra de 5G y un índice para leer solo las bandas seleccionadas. No necesitas aportar el datasheet original para generar otro ensayo.

La revisión actual conserva el cuestionario de escritorio y elimina la aplicación web. En las filas de SAR EN y SAR FCC-ISED compatibles con la certificación y la selección se corrigen CC/CD: se restauran los enlaces de canal/frecuencia con los auxiliares originales cuando corresponden a la misma tecnología y banda, y las búsquedas originales para las filas adicionales. El resto del contenido de esas filas, sus posiciones y combinaciones se conserva. La visibilidad de las columnas de las 16 hojas originales queda guardada en `plantilla/columnas_originales.json` y se aplica al generar. [Detalle y límites de la revisión](docs/revision_escritorio.md).

## Uso en Windows

Requiere Python 3.11 o posterior, con tkinter.

1. Extrae toda la carpeta del ZIP.
2. Si es la primera instalación, ejecuta `python -m pip install -r requirements.txt`.
3. Abre `INICIAR_CUESTIONARIO.bat` o ejecuta `python cuestionario_ensayo.py`.
4. En **Elegir base de datos…**, selecciona tu XLSX. De inicio se usa la copia incluida en `datos/`.
5. Marca regiones, exposiciones, tecnologías y bandas. Las bandas proceden de la base cargada. GPRS y EGPRS conservan los slots acumulativos.
6. Pulsa **Generar toma de datos**. Guarda los tres archivos que se crean juntos.

En **2G** solo se marcan GSM, GPRS y EGPRS y sus slots TX. Todas sus bandas, canales y frecuencias se toman de la base elegida; no hay entrada de bandas 2G. Los slots siguen siendo acumulativos. En las demás tecnologías se conservan las listas de bandas como texto y la entrada por números separados por comas. BT y Custom quedan en **Mostrar otras tecnologías**.

Si una tecnología solo tiene una banda posible, se utiliza automáticamente. La entrada admite números, pero **Seleccionadas** muestra las etiquetas completas: `FDDI` para la banda 1 de HSDPA, `FDD1` para LTE o `n77` para 5G.

HSPA, HSPA+, HSDPA y DC-HSDPA usan el catálogo de bandas, canales y frecuencias WCDMA de la base cuando no tienen una tabla propia. Se ha contrastado en el Excel original que comparten las 12 bandas de 3G. Si añades registros específicos para una de estas tecnologías a la base, pasan a tener prioridad. Los parámetros propios que falten quedan vacíos.

[Vista de la interfaz](docs/interfaz_bandas.png)

Para repetir un ensayo: elige la base actualizada, pulsa **Cargar respuestas (.json)…** y genera otra salida. **Recargar base** actualiza las opciones si has editado el XLSX mientras el formulario estaba abierto. Las selecciones que ya no existen se rechazan; no se sustituyen por datos antiguos.

## Qué se conserva y de dónde salen los datos

| Elemento | Fuente |
| --- | --- |
| Registros RF que pueden aparecer y campos proporcionados | Base de datos XLSX seleccionada y opciones del formulario, con prioridad sobre los valores originales |
| Columnas completas, datos complementarios, fórmulas, estilos, comentarios e imágenes de tecnologías | Copia completa del original guardada en el programa, filtrada para los registros de la base y la selección |
| Tune-Up completa: datos, fórmulas y presentación | Copia del Excel original guardada en el programa; no se vacía ni se reconstruye desde la base |
| Overview | Copia guardada, con proyecto, baterías y accesorios del formulario |
| Validations, Test Campaign y Pretesting-Others | Hojas originales guardadas en el programa |
| SAR EN y SAR FCC-ISED | Formatos, posiciones y cálculos guardados; datos RF enlazados con las tecnologías generadas desde la base |
| Nombre de pestañas de tecnologías | `Conducted 2G`, `Conducted 3G` o `Conducted 2G-3G` con Conducida; sin esa opción se omite el prefijo, igual que en el resto de tecnologías |

EN solicita SAR EN; FCC e ISED comparten SAR FCC-ISED. Antes de guardar se comprueba que las hojas solicitadas existen, están visibles y contienen filas.

También se comprueba que los comentarios de las hojas conservan sus enlaces y formas VML, para detectar el fallo que hacía que Excel eliminara comentarios al abrir el libro. La corrección se aplica al generar un archivo nuevo; consulta [la comprobación de comentarios](docs/correccion_comentarios.md).

SAR EN conserva Mode combinado por tecnología/banda y Exposure Conditions por bloque; añade las baterías mediante fórmulas de concatenación, Front Face y accesorios en Body. FCC conserva las posiciones, baterías y Variability de su procedimiento guardado; no recibe las baterías ni accesorios nuevos del formulario.

## Editar la base

La base inicial es `datos/Base_de_datos_bandas_canales_frecuencias_corregido.xlsx`, una copia sin modificar del último archivo recibido. Puedes elegir otra desde el formulario. Las columnas mínimas son **Tecnología, Banda, Canal y Frecuencia (MHz)**. Sus parámetros y campos adicionales se aplican a las filas seleccionadas, manteniendo las columnas del original. Los campos nuevos que no tienen columna equivalente se añaden al final.

Las tecnologías muestran sus tablas completas del original, incluidas las columnas para introducir medidas. Las filas descartadas se compactan, ajustando fórmulas, combinaciones, comentarios y dibujos. Se conservan columnas, colores y presentación. Las coordenadas que necesitan los cálculos SAR quedan en filas ocultas de apoyo; esas entradas mantienen sus valores y fórmulas de la versión aprobada, sin añadir enlaces nuevos desde la vista completa. Las pestañas auxiliares Liquids-DRAFT y Pendiente también se conservan con su estado de visibilidad original.

Cuando existe una fila coincidente, se conserva su información original y se aplican los campos de la base. Para registros nuevos sin coincidencia exacta se reutiliza el formato de su tecnología y se completan exclusivamente sus valores RF proporcionados: no se copian parámetros ni medidas de otra combinación. **Tune-Up se conserva completa del original.**

Se admiten bandas nuevas de las familias con formato guardado. El procedimiento usa el formato de esa familia; no hace falta actualizar el Excel original. Una banda nueva puede no tener entrada en la Tune-Up guardada: su potencia objetivo queda pendiente hasta completar esa referencia. Las familias sin procedimiento SAR propio no reciben posiciones inventadas. Consulta [USO_AUTOMATICO.md](USO_AUTOMATICO.md) para las limitaciones y el esquema.

## Generación sin pantalla

```sh
python generar_desde_json.py ejemplos/ejemplo_tecnologias_ordenadas.json salidas/ensayo.xlsm
python generar_desde_json.py respuestas.json salidas/repeticion.xlsm --base-datos mi_base_actualizada.xlsx
```

El segundo comando permite reutilizar respuestas con otra versión de la base. La base utilizada se identifica por su nombre y SHA-256 en el resumen de generación. Las rutas relativas de `base_datos` en un JSON se resuelven respecto al propio JSON.

## Ejemplo y comprobaciones

Los ejemplos e informes con fecha anterior documentan versiones históricas. La revisión actual se comprueba en `tests/test_revision_escritorio.py` y se describe en `docs/revision_escritorio.md`.

[Revisión de la presentación completa](docs/original_completo.md) · [Vista de las primeras filas](docs/vista_original_completo.png) · [Conservación de las hojas protegidas](docs/verificacion_correcciones_04_11.json)

```sh
python -m unittest discover -s tests -v
```

Las pruebas de producción están en `tests/test_restauracion_sar.py`, `tests/test_originales_completos.py`, `tests/test_base_datos.py`, `tests/test_tecnologias_visibles.py`, `tests/test_comentarios.py` y `tests/test_interfaz_bandas.py`: archivos originales íntegros, edición de datos, prioridad de la base, conservación de las celdas de apoyo, las hojas fijas y el contenido SAR fuera de CC/CD, nombres 2G/3G, regiones, CLI y widgets. Las auditorías históricas usan `generar_heredado`, que no se utiliza desde el formulario ni la CLI.


El paquete conserva VBA y la macro MyTimestamp. La validación Open XML comprueba estructura, sin ejecutar Microsoft Excel, cálculos ni macros. La interfaz se importa y se comprueban sus métodos de selección; la revisión visual y la apertura en Excel deben hacerse en un ordenador con pantalla. El proyecto VBA original puede mostrar su antiguo formulario de hojas: ciérralo para conservar las hojas ya generadas por el cuestionario.
