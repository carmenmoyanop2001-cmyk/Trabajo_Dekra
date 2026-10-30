# Tablas de tecnologías desde la base elegida

El formulario ya no pide bandas en GSM, GPRS ni EGPRS. Solo pide los slots de GPRS/EGPRS y mantiene su selección acumulativa. Se leen todas las bandas de los modos 2G elegidos. La pestaña se llama `2G`, `3G` o `2G-3G`, independientemente de la opción de conducidos.

2G/3G muestra Región, Tecnología, Banda, Canal y Frecuencia (MHz). El resto de familias muestra las columnas de la base que tienen información, incluidas columnas adicionales. Las columnas compuestas solo por vacíos, guiones o N/A se omiten. Los modos del formulario sirven para seleccionar, pero no crean valores ni filas técnicas que no existan en la base.

Las filas se ordenan por tecnología, banda y parámetros. Los formatos conservan los colores de las celdas originales, con estilos nuevos de texto negro para que los valores sean legibles. Se mantienen intactas todas las definiciones de estilos anteriores. Las cabeceras tienen filtro y quedan inmovilizadas. En el formulario, `Seleccionadas` muestra FDDI, FDDIII, FDD1 o n77 según corresponda.

## Conservación de hojas protegidas

La reorganización se aplica después de generar el libro con el motor anterior. En cada generación se comprueba que Overview, Tune-Up, Validations, SAR EN, SAR FCC-ISED, Test Campaign y Pretesting-Others conserven exactamente sus XML. No se reescriben sus fórmulas.

Las coordenadas que necesitan esas fórmulas se mantienen ocultas en las pestañas de tecnologías. Si la pestaña 2G-3G cambia de nombre, una copia de apoyo oculta mantiene el nombre anterior para que los enlaces sigan resolviéndose. Las tablas visibles son una presentación de la base; para cambiar datos RF se edita la base y se vuelve a generar.

Los archivos de las cuatro capturas de 2G-3G, sus relaciones y sus anclajes se copian sin cambios. La base `Base_de_datos_bandas_canales_frecuencias_corregido.xlsx` incluida es idéntica al archivo que se recibió.

Las pestañas visibles conservan sus identificadores internos `codeName`, asociados a los módulos de hoja del VBA original. La copia de apoyo no duplica ese identificador. El proyecto VBA se conserva sin ejecutarlo ni modificarlo.

## Verificación

- Las pruebas de nombres cubren 2G, 3G y ambas familias, con y sin conducidos. Comparan las siete hojas protegidas y las celdas que utilizan sus fórmulas.
- Las pruebas de datos cubren edición de frecuencias, bandas nuevas, regiones, CLI y todas las familias. Incluyen campos adicionales y filas que solo se distinguen en esos campos.
- Las pruebas Tk comprueban los slots sin entradas de bandas 2G y la confirmación con etiquetas completas.
- El ejemplo pasa el SDK oficial Open XML con cero errores.
- Se ha revisado una vista parcial de LTE con LibreOffice y el formulario con Tk en Linux. No se ha ejecutado Excel de Windows ni VBA.

Resultados: [conservacion_tablas_tecnologias.json](conservacion_tablas_tecnologias.json), [validacion_openxml_tecnologias.json](validacion_openxml_tecnologias.json), [pruebas_tablas_base.txt](pruebas_tablas_base.txt), [pruebas_tecnologias_protegidas.txt](pruebas_tecnologias_protegidas.txt) y [pruebas_widgets.txt](pruebas_widgets.txt).

Vista parcial: [vista_tabla_lte.png](vista_tabla_lte.png). Ejemplo completo: `ejemplos/Ensayo_tecnologias_ordenadas.xlsm`, con las respuestas en `ejemplos/ejemplo_tecnologias_ordenadas.json`.
