# Valores conservados y presentación de Mode

## Una celda por tecnología/banda

BY se combina desde la primera hasta la última fila contigua de cada tecnología/banda de SAR EN, abarcando las exposiciones, antenas, baterías y accesorios que correspondan. No se combina por exposure condition.

Si el original contiene varios modos, el resumen muestra todos sus valores distintos en líneas separadas, con el color original, centrado y ajuste de texto. Los valores de cada fila se mantienen en la columna auxiliar CG que ya está oculta. Las referencias de los cálculos pasan de BY a CG; las referencias a BY de otras hojas, como la frecuencia de Conducted 2G-3G, no se alteran.

Mientras Mode contenga el resumen inicial se mantienen los modos originales de cada fila. Si se edita esa celda para escoger un único modo, las fórmulas auxiliares aplican el nuevo valor al bloque. Las filas adicionales conservan su modo N/A. Se respeta la protección de la hoja original.

## Por qué algunos valores se mostraban vacíos

El escritor conservaba `<f>` pero descartaba los resultados `<v>` guardados en el datasheet. Eso permitía que valores dependientes de fórmulas se mostrasen vacíos hasta recalcular. Ahora se guardan ambos: la fórmula sigue activa y el resultado original se conserva para la primera visualización. Los textos, como TBD, se guardan con el tipo de resultado de texto; los canales y frecuencias conservan sus valores numéricos. No se inventan medidas de SAR ni veredictos.

CATM1 contiene tres variantes de fórmula en O: IF(J="Cat M1",0,1), IF(J="Cat M1",0,2) e IF(J="Cat M1",1,2). Su resultado depende solo de J en la misma fila. Se guarda ese resultado sin sustituir la fórmula. La prueba independiente lo compara contra los 35.752 valores de O del Excel original, guardados en `tests/fixtures/catm1_columna_o_original.json.xz` con su nombre y SHA-256 de origen. También se compara la columna O realmente emitida para las 984 filas del caso seleccionado.

El libro pide cálculo automático, cálculo completo al abrir y recálculo al guardar. Los resultados calculados de medidas y los avisos de macros requieren Microsoft Excel; la validación estructural no los ejecuta.

## Filas y fórmulas

Las filas se filtran físicamente por selección y se escriben con números consecutivos. No se deja un bloque vacío donde antes había una tecnología o exposición descartada. Los TBD del original son filas de ensayo y se conservan, con su resultado visible. No se eliminan por falta de un resultado previamente guardado.

Las fórmulas adaptadas de FCC-ISED para las filas adicionales siguen activas. Se mantienen sus rangos sobre el bloque original de EN y sus límites de 10 g. El formato de las filas nuevas y las reglas de formato condicional se conservan al desplazar filas.

Los ejemplos se han validado con el SDK oficial Open XML. La apertura en Microsoft Excel y el aviso de reparación del Proyecto.xlsm concreto del usuario siguen pendientes de comprobar con ese archivo o su informe.
