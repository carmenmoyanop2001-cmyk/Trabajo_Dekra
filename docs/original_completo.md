# Original completo integrado — 3 de noviembre de 2026

Las tecnologías dejaban de mostrar las columnas y los bloques completos del datasheet al publicarse como tablas resumidas. Ahora se recuperan sus pestañas originales completas y se filtran por el catálogo XLSX y el cuestionario. Los campos proporcionados por la base tienen prioridad; se conservan el resto del contenido y la presentación de las filas coincidentes.

## Qué queda guardado en el programa

`plantilla/originales/` conserva todos los archivos internos de los originales divididos recibidos. `inventario.json` identifica las 16 pestañas, su archivo de origen y los SHA-256 de cada parte. La compresión cambia el contenedor, sin modificar el contenido de esas partes.

El adjunto dividido de 5G tenía únicamente n1. Se complementa con la hoja íntegra que ya estaba guardada en `plantilla/cond_5g.xz`: 220.322 filas y 25 bandas/variantes. Su presentación, fórmulas y datos se guardan con un índice por bandas para leer solo las elegidas. La copia del adjunto recibido también se conserva.

Las siete hojas protegidas continúan pasando por el motor anterior. Las tecnologías muestran sus columnas, constantes, fórmulas, colores, combinaciones, validaciones, comentarios, dibujos y capturas. Las filas descartadas se compactan y las referencias se adaptan. Los registros nuevos sin coincidencia usan el formato de la familia y exclusivamente los valores RF proporcionados, sin tomar medidas ni parámetros de otra combinación. Se informa de esos casos al generar.

Las entradas que utilizan los cálculos SAR quedan en filas ocultas de apoyo. Los valores RF se conservan y las entradas de medidas se enlazan a las filas visibles correspondientes, agrupando solo el mismo registro. Así se mantiene intacto el XML de SAR EN y SAR FCC-ISED. Si es necesario cambiar el nombre de la hoja 2G/3G, una hoja de apoyo conserva el nombre que leen esas fórmulas. Los estilos existentes y el VBA no se modifican.

Con Conducida se utiliza **Conducted 2G-3G** cuando se eligen ambas familias, **Conducted 2G** o **Conducted 3G** cuando se elige solo una. Sin Conducida se omite el prefijo. Liquids-DRAFT y Pendiente también se incluyen con su visibilidad original.

## Comprobaciones

- Siete pruebas de la presentación completa aprobadas: archivos originales y hashes, prioridad y campos nuevos de la base, columnas y contenido, seis combinaciones de nombres, medidas visibles, MPR original en CAT M1 y conservación de las hojas protegidas.
- Comprobaciones adicionales de referencias: el rango de una banda original no incluye otra banda nueva por compartir la fila de formato, y no se recuperan frecuencias ajenas a la base seleccionada.
- Once pruebas de la base aprobadas: edición de datos, todas las familias, regiones, CLI, respuestas portables y conservación de la salida anterior ante errores.
- Comprobaciones de tecnologías con y sin conducidos, campos adicionales y comentarios aprobadas. Las expectativas históricas de tablas reducidas se actualizan a la presentación completa del original.
- Cinco casos de Streamlit comprobados, con repetición dirigida de la comprobación del nuevo nombre Conducted 2G. Se conservan slots, importación, generación y descargas.
- El ejemplo incluido supera el SDK Open XML con **cero errores**, además de la validación de comentarios y relaciones del programa.
- Comparación directa del ejemplo con la salida del motor previo para las mismas respuestas: **Overview, Tune-Up, Validations, SAR EN, SAR FCC-ISED, Test Campaign y Pretesting-Others idénticas byte por byte**. Se conservan también el VBA, las imágenes anteriores y todas las definiciones de estilos anteriores. Los hashes están en [conservacion_original_completo.json](conservacion_original_completo.json).
- Prueba de cálculo en una copia temporal con LibreOffice: al introducir `13` en `Conducted 2G-3G!AH87`, la entrada oculta `AH3` recibe `13` y `AH4`, correspondiente a otro canal, sigue vacía. Se revisó también una vista PDF del formato recuperado. No se ha ejecutado Microsoft Excel ni se han verificado los eventos VBA.

[Vista de las primeras filas y columnas](vista_original_completo.png). Es un recorte de una exportación temporal para revisión; el ejemplo XLSM conserva su presentación completa.

El ejemplo está en `ejemplos/Ensayo_original_completo_filtrado.xlsm`; sus respuestas ficticias están en `ejemplo_original_completo.json`. Las selecciones amplias pueden tardar varios minutos.

## Preparación de otra versión del original

La generación de ensayos no necesita estos pasos. Para actualizar las copias guardadas se puede ejecutar `herramientas/guardar_originales_completos.py` con un original completo XLSX/XLSM o con la carpeta de adjuntos divididos. Las herramientas `completar_original_5g.py` e `indexar_original_5g.py` documentan cómo se preparó la copia completa y su índice. No se ejecutan desde el formulario.
