# Reparación de WiFi, regiones SAR y desplazamiento de tecnologías

La comparación de los dos Ptoyecto.xlsm recibidos identifica el motivo concreto del aviso «Registros quitados: Fórmula de /xl/worksheets/sheet8.xml»: Excel elimina 1.382 fórmulas de Conducted WiFi. Las otras 8.328 fórmulas permanecen sin cambios después de expandir las fórmulas compartidas que Excel introduce al guardar.

## Causa y corrección

Una fórmula original como `COLUMN(B5)` necesita una referencia. Cuando B5 pertenecía a una fila descartada, el generador sustituía la referencia por el valor de la celda: por ejemplo, `COLUMN("FCC/ISED")` o `COLUMN(1)`. El analizador sintáctico y el SDK Open XML aceptaban ese texto; Excel lo eliminaba por el tipo de argumento.

El generador conserva ahora el número de columna mediante una referencia válida. En la vista completa se reserva COLUMN antes de sustituir referencias de datos. En las plantillas compactas se conserva la referencia reubicada si existe y se utiliza la fila 1 si la fila original ha desaparecido. El número de columna es el mismo, sin depender del contenido de esa celda. Las sustituciones normales de datos RF siguen funcionando fuera de COLUMN.

El validador incorpora esta comprobación de argumentos. Sobre el archivo recibido detecta exactamente las 1.382 celdas que Excel elimina; sobre su copia corregida no detecta errores. Las columnas afectadas son CN, CO, CP, CR, CS y CW. La correspondencia de columnas se recupera de las fórmulas originales guardadas, sin inventar índices.

La regresión conserva una extracción de las fórmulas y los hashes de ambos adjuntos en `tests/fixtures/reparacion_wifi_05_11.json.xz`. No requiere volver a disponer de los libros adjuntos ni ejecutar macros. Verifica tanto las 1.382 eliminadas como las 8.328 que Excel conservó.

## Regiones

Cada hoja SAR recibe exclusivamente registros compatibles con su certificación: EN para SAR EN y FCC/ISED para SAR FCC-ISED. La selección global de varias regiones no hace que todas las bandas se copien a las dos hojas.

En la base proporcionada, WCDMA FDDI y FDDVIII están marcadas EN; FDDII está marcada FCC/ISED. Las pruebas verifican que las primeras aparecen en SAR EN y FDDII en SAR FCC-ISED, manteniendo las tres bandas en la hoja de tecnología. Si una certificación se desconoce («?»), se exige que exista un procedimiento regional para esa tecnología/banda en la plantilla guardada; no se presupone EN/FCC/ISED.

Las filas restantes conservan su procedimiento, posiciones y formato. Las filas eliminadas se compactan mediante el constructor existente. Los archivos de origen, Tune-Up, datos RF y cuestionario siguen guardados en el programa.

## Desplazamiento

En el archivo recibido, 2G-3G inmovilizaba 80 filas; LTE, 848; y 5G, 67. Esos números incluían las filas ocultas de apoyo. Se reconstruye su vista normal, como ya se hacía con WiFi, sin esos paneles inmovilizados. La corrección de vista no cambia celdas, fórmulas, anchos, colores ni imágenes.

Las utilidades `herramientas/corregir_vistas.py` y `herramientas/corregir_formulas_wifi.py` permiten comprobar las correcciones por separado sobre copias, conservando el original. `herramientas/comparar_formulas_excel.py` compara las fórmulas aunque Excel las haya convertido en compartidas o renumerado las partes de las hojas.

## Uso y validación

Extraer la nueva entrega en una carpeta nueva y ejecutar `INICIAR_CUESTIONARIO.bat`. Generar de nuevo con la base y las opciones deseadas para aplicar también el filtro regional. No hace falta aportar el datasheet original ni utilizar la copia reparada por Excel como plantilla.

La copia de diagnóstico corrige únicamente las 1.382 fórmulas identificadas; las 8.328 restantes y todas las demás partes del libro son idénticas. Supera la validación del paquete y el SDK Open XML. También se prueba una generación nueva de WiFi desde el catálogo y el formulario. La apertura de la entrega nueva con Microsoft Excel de Windows queda como comprobación final en ese programa; la causa del aviso ya está respaldada por la comparación con la reparación real, no solo por la validación estructural.

Se superan 34 casos distintos, incluidos generación desde la carpeta extraída, filtro regional, formatos y posiciones aprobados. La comparación de estilos resuelve sus fuentes, rellenos, bordes y formatos, porque los índices se pueden renumerar al quitar bandas; además distingue las distintas ocurrencias de bloques con la misma tecnología/banda/exposición. Los estilos del libro aprobado se conservan junto con su origen y hash. [Resultados](verificacion_wifi_y_regiones.json) · [Pruebas finales](pruebas_wifi_y_regiones.txt).
