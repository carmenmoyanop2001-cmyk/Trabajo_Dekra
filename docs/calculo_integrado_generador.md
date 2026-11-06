# Configuración de cálculo incorporada al generador

El usuario solicita que el ajuste se aplique al crear cada libro, sin ejecutar una reparación posterior. El generador escribe ahora `concurrentCalc="0"` directamente en el `calcPr` de cada salida. Se mantiene `calcMode="auto"`, `forceFullCalc="0"`, el recálculo al abrir y el recálculo al guardar.

Antes de publicar el resultado, `_validar_calculo` verifica la configuración del archivo final, después de reconstruir los SAR y las vistas de tecnologías. Si alguno de esos pasos retira el ajuste o vuelve al cálculo manual o completo forzado, la generación falla antes de sustituir el archivo de destino.

No se modifica código de construcción de ninguna pestaña ni sus datos, fórmulas, formatos, columnas, imágenes, relaciones o macros. Los SAR siguen usando la versión 12 recuperada. El formulario y su lanzador se utilizan como antes. No es necesario ejecutar la herramienta de copias de la entrega anterior.

La comparación entre dos generaciones con la misma selección —2G, 3G, LTE y ambos SAR— verifica que solo cambia `xl/workbook.xml`, exactamente en el atributo añadido. Las pruebas vuelven a generar archivos con y sin conducidos y comprueban el atributo tras todos los pasos del programa. Se mantienen las regresiones de SAR, fechas de AI/AJ, fórmulas WiFi y fuentes originales.

**Límite:** la persistencia del ajuste en nuevos libros está verificada. Su eficacia contra el cierre `c0000005` de Excel de Windows sigue pendiente de confirmación en el equipo del usuario. El evento no identifica una causa concreta y este entorno no ejecuta Microsoft Excel.
