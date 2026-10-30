# Toma de datos SAR desde una base editable

El formulario genera un `.xlsm`, un resumen `.txt` y las respuestas `.json` para repetir el ensayo. **Los datos RF se leen de la base XLSX elegida; no se recuperan del datasheet antiguo.** El programa ya lleva guardados los formatos y las hojas de referencia. No hace falta aportar el Excel original para generar otro ensayo.

## App Streamlit: todo desde el navegador

Requiere **Python 3.11 o posterior**. Extrae la carpeta completa del proyecto y abre una terminal en esa carpeta. La primera vez instala las dependencias de la app:

```sh
python -m pip install -r requirements_streamlit.txt
```

Para abrirla:

```sh
python -m streamlit run app_streamlit.py
```

En Windows también puedes hacer doble clic en **INICIAR_STREAMLIT.bat** después de instalar las dependencias. Se abrirá el navegador en `http://localhost:8501`. Mantén la terminal abierta mientras uses la app; `Ctrl+C` la detiene.

1. Carga la base XLSX desde la barra lateral, o utiliza la base incluida.
2. Completa proyecto, regiones, exposure conditions, baterías, accesorios y tecnologías. Las bandas se escriben por números; debajo aparecen las etiquetas completas. En 2G solo se eligen las tecnologías y los slots acumulativos.
3. Pulsa **Generar Excel** y después **Descargar Excel** o **Descargar todo en ZIP**.

El ZIP del ensayo incluye `.xlsm`, `.json`, `.txt` y la base utilizada. Para repetirlo, carga esa base y el JSON en la barra lateral y pulsa **Cargar respuestas**. La app siempre utiliza la base que esté activa en pantalla, sin seguir rutas de archivos guardadas en un JSON de otro ordenador. Si cambias las opciones después de generar, las descargas anteriores se ocultan hasta regenerar el Excel.

Esta versión funciona en tu ordenador y reutiliza el generador del cuestionario. No cambia las plantillas ni la lógica de SAR EN, SAR FCC-ISED, Overview, Tune-Up, Validations, Test Campaign y Pretesting-Others. El cuestionario de escritorio sigue disponible. Para compartir la app mediante una dirección web permanente se necesitaría alojarla en un servidor; ejecutar este comando no publica el proyecto en Internet.

[Vista del cuestionario web](docs/streamlit_cuestionario.png) · [Vista de las descargas](docs/streamlit_descargas.png)

## Uso en Windows

Requiere Python 3.10 o posterior, con tkinter.

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
| Bandas, canales, frecuencias y parámetros RF de tecnologías | Base de datos XLSX seleccionada y opciones explícitas del formulario |
| Tune-Up completa: datos, fórmulas y presentación | Copia del Excel original guardada en el programa; no se vacía ni se reconstruye desde la base |
| Overview | Copia guardada, con proyecto, baterías y accesorios del formulario |
| Validations, Test Campaign y Pretesting-Others | Hojas originales guardadas en el programa |
| SAR EN y SAR FCC-ISED | Formatos, posiciones y cálculos guardados; datos RF enlazados con las tecnologías generadas desde la base |
| Nombre de pestañas de tecnologías | `2G`, `3G` o `2G-3G` según la selección; el resto conserva `Conducted …` cuando se eligen conducidos |

EN solicita SAR EN; FCC e ISED comparten SAR FCC-ISED. Antes de guardar se comprueba que las hojas solicitadas existen, están visibles y contienen filas.

SAR EN conserva Mode combinado por tecnología/banda y Exposure Conditions por bloque; añade las baterías mediante fórmulas de concatenación, Front Face y accesorios en Body. FCC conserva las posiciones, baterías y Variability de su procedimiento guardado; no recibe las baterías ni accesorios nuevos del formulario.

## Editar la base

La base inicial es `datos/Base_de_datos_bandas_canales_frecuencias_corregido.xlsx`, una copia sin modificar del último archivo recibido. Puedes elegir otra desde el formulario. Las columnas mínimas son **Tecnología, Banda, Canal y Frecuencia (MHz)**. Los demás campos de la base se muestran cuando contienen datos; Región ocupa la primera columna.

Las tablas de 2G/3G muestran solo **Región, Tecnología, Banda, Canal y Frecuencia (MHz)**. Las demás familias muestran los campos con datos en la base elegida, sin añadir columnas de medidas ni columnas compuestas solo por guiones. Se conservan colores y capturas del original y se añaden estilos legibles con texto negro. La presentación verifica que las siete hojas protegidas, sus fórmulas y las definiciones originales de sus estilos permanecen idénticas, manteniendo ocultas las coordenadas de apoyo que necesitan.

Los parámetros que no estén informados quedan vacíos. **La excepción es Tune-Up, que se conserva completa del original.** No se inventan parámetros 5G, MPR, modos ni certificados. Si conoces un modo para el ensayo, puedes indicarlo en el formulario o añadir la columna Mode a la base.

Se admiten bandas nuevas de las familias con formato guardado. El procedimiento usa el formato de esa familia; no hace falta actualizar el Excel original. Una banda nueva puede no tener entrada en la Tune-Up guardada: su potencia objetivo queda pendiente hasta completar esa referencia. Las familias sin procedimiento SAR propio no reciben posiciones inventadas. Consulta [USO_AUTOMATICO.md](USO_AUTOMATICO.md) para las limitaciones y el esquema.

## Generación sin pantalla

```sh
python generar_desde_json.py ejemplos/ejemplo_tecnologias_ordenadas.json salidas/ensayo.xlsm
python generar_desde_json.py respuestas.json salidas/repeticion.xlsm --base-datos mi_base_actualizada.xlsx
```

El segundo comando permite reutilizar respuestas con otra versión de la base. La base utilizada se identifica por su nombre y SHA-256 en el resumen de generación. Las rutas relativas de `base_datos` en un JSON se resuelven respecto al propio JSON.

## Ejemplo y comprobaciones

`ejemplos/Ensayo_tecnologias_ordenadas.xlsm` muestra las tablas actuales con todas las familias, EN/FCC/ISED, dos baterías y un accesorio. Sus respuestas ficticias están en `ejemplo_tecnologias_ordenadas.json`. Los demás Excel de ejemplos y los informes anteriores documentan versiones históricas.

```sh
python -m unittest discover -s tests -v
```

Las pruebas de producción están en `tests/test_base_datos.py`, `tests/test_tecnologias_visibles.py` y `tests/test_interfaz_bandas.py`: tablas visibles, edición de datos, conservación de las siete hojas protegidas, nombres 2G/3G, regiones, CLI y widgets reales. Las auditorías históricas usan `generar_heredado`, que no se utiliza desde el formulario ni la CLI.

Con las dependencias de Streamlit instaladas, `python -m unittest discover -s tests -p test_streamlit_app.py -v` comprueba el formulario web, los slots, la importación de respuestas, las descargas, la lectura de una base editada y la igualdad de las siete hojas protegidas frente al generador de escritorio.

El paquete conserva VBA y la macro MyTimestamp. La validación Open XML comprueba estructura, sin ejecutar Microsoft Excel, cálculos ni macros. La interfaz se importa y se comprueban sus métodos de selección; la revisión visual y la apertura en Excel deben hacerse en un ordenador con pantalla. El proyecto VBA original puede mostrar su antiguo formulario de hojas: ciérralo para conservar las hojas ya generadas por el cuestionario.
