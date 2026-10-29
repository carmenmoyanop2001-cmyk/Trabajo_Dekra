# Toma de datos SAR desde una base editable

El formulario genera un `.xlsm`, un resumen `.txt` y las respuestas `.json` para repetir el ensayo. **Los datos RF se leen de la base XLSX elegida; no se recuperan del datasheet antiguo.** El programa ya lleva guardados los formatos y las hojas de referencia. No hace falta aportar el Excel original para generar otro ensayo.

## Uso en Windows

Requiere Python 3.10 o posterior, con tkinter.

1. Extrae toda la carpeta del ZIP.
2. Si es la primera instalación, ejecuta `python -m pip install -r requirements.txt`.
3. Abre `INICIAR_CUESTIONARIO.bat` o ejecuta `python cuestionario_ensayo.py`.
4. En **Elegir base de datos…**, selecciona tu XLSX. De inicio se usa la copia incluida en `datos/`.
5. Marca regiones, exposiciones, tecnologías y bandas. Las bandas proceden de la base cargada. GPRS y EGPRS conservan los slots acumulativos.
6. Pulsa **Generar toma de datos**. Guarda los tres archivos que se crean juntos.

Cada tecnología muestra sus opciones como texto: **Bandas disponibles: (1, 2, 3, …)**. Debajo puedes escribir los números que elijas, separados por comas, y pulsar **Aceptar bandas**. En 2G, las opciones y el campo de GPRS y EGPRS aparecen justo debajo de sus respectivos slots; GSM tiene los suyos. Los slots siguen siendo acumulativos. Las opciones habituales de 3G, variantes 5G y modos WiFi se conservan. BT y Custom quedan en **Mostrar otras tecnologías**.

Si una tecnología solo tiene una banda posible en la base, se utiliza automáticamente y no muestra opciones ni campo de bandas. En LTE, LTE CAT M1 y LTE NB-IoT se muestran los números también al cargar respuestas y confirmar la selección: `1, 2, 3` en lugar de `FDD1, FDD2, FDD3`. Los identificadores completos se conservan internamente para generar el Excel.

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
| Nombre de pestañas de tecnologías | `Conducted …` si hay conducidos; nombre sin prefijo si no |

EN solicita SAR EN; FCC e ISED comparten SAR FCC-ISED. Antes de guardar se comprueba que las hojas solicitadas existen, están visibles y contienen filas.

SAR EN conserva Mode combinado por tecnología/banda y Exposure Conditions por bloque; añade las baterías mediante fórmulas de concatenación, Front Face y accesorios en Body. FCC conserva las posiciones, baterías y Variability de su procedimiento guardado; no recibe las baterías ni accesorios nuevos del formulario.

## Editar la base

La entrega incluye `datos/Base_de_datos_bandas_canales_frecuencias_v2.xlsx`. Puedes modificar esa copia o elegir otra desde el formulario. Sus columnas mínimas son **Tecnología, Banda, Canal y Frecuencia (MHz)**. Las columnas opcionales incluyen Bandwidth (MHz), Modulation, UL RB Allocation, UL RB Start, Narrowband Index, SCS (kHz), Mode, MPR y Notas.

Los parámetros que no estén informados quedan vacíos. **La excepción es Tune-Up, que se conserva completa del original.** No se inventan parámetros 5G, MPR, modos ni certificados. Si conoces un modo para el ensayo, puedes indicarlo en el formulario o añadir la columna Mode a la base.

Se admiten bandas nuevas de las familias con formato guardado. El procedimiento usa el formato de esa familia; no hace falta actualizar el Excel original. Una banda nueva puede no tener entrada en la Tune-Up guardada: su potencia objetivo queda pendiente hasta completar esa referencia. Las familias sin procedimiento SAR propio no reciben posiciones inventadas. Consulta [USO_AUTOMATICO.md](USO_AUTOMATICO.md) para las limitaciones y el esquema.

## Generación sin pantalla

```sh
python generar_desde_json.py ejemplos/ejemplo_base_datos.json salidas/ensayo.xlsm
python generar_desde_json.py respuestas.json salidas/repeticion.xlsm --base-datos mi_base_actualizada.xlsx
```

El segundo comando permite reutilizar respuestas con otra versión de la base. La base utilizada se identifica por su nombre y SHA-256 en el resumen de generación. Las rutas relativas de `base_datos` en un JSON se resuelven respecto al propio JSON.

## Ejemplo y comprobaciones

`ejemplos/Ensayo_desde_base_datos.xlsm` demuestra todas las familias disponibles, EN/FCC/ISED, dos baterías y un accesorio; sus respuestas son ficticias y están en `ejemplo_base_datos.json`. Los demás Excel de ejemplos y los informes anteriores documentan versiones históricas.

```sh
python -m unittest discover -s tests -v
```

Las pruebas de producción están en `tests/test_base_datos.py`: edición de datos, bandas nuevas, falta de parámetros, conservación de Tune-Up, todas las familias, regiones y CLI. Las otras pruebas conservan la auditoría histórica de formatos mediante `generar_heredado`; esa ruta no se utiliza desde el formulario ni la CLI actuales.

El paquete conserva VBA y la macro MyTimestamp. La validación Open XML comprueba estructura, sin ejecutar Microsoft Excel, cálculos ni macros. La interfaz se importa y se comprueban sus métodos de selección; la revisión visual y la apertura en Excel deben hacerse en un ordenador con pantalla. El proyecto VBA original puede mostrar su antiguo formulario de hojas: ciérralo para conservar las hojas ya generadas por el cuestionario.
