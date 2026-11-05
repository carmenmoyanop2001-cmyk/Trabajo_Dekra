# SAR de la versión aprobada y tecnologías completas

Informe de la entrega del 3 de noviembre. La solicitud posterior del 4 de noviembre autoriza únicamente la adaptación de CC/CD en SAR EN; el resto se conserva. Véase [correcciones_04_11.md](correcciones_04_11.md).

Se toma `Trabajo_Dekra-main11.zip`, adjuntado por el usuario, como referencia de SAR EN y SAR FCC-ISED. El motor `_generar`, sus utilidades y todas las dependencias y plantillas SAR enumeradas en `fuentes_sar_main11.json` coinciden con ese adjunto. Las tecnologías siguen utilizando las copias completas del original incorporadas en la versión anterior, con el filtrado de la base y del formulario.

La integración anterior añadía fórmulas COUNT/MAX a las celdas ocultas de medidas que utilizan los cálculos SAR. Aunque no cambiaba el XML de las hojas SAR, cambiaba sus dependencias. Se retira esa transformación. Todas las celdas de apoyo, incluidas sus fórmulas, constantes y valores guardados, se conservan ahora exactamente. Antes de publicar, el programa comprueba que la presentación nueva no haya modificado ninguna de ellas. Las hojas SAR conservan el comportamiento de la versión aprobada; no se añade una conexión automática nueva entre medidas de la vista completa y esas celdas.

Se incluye una referencia de regresión en `tests/fixtures/sar_main11_aprobado.zip`, extraída de los dos SAR del `Proyecto.xlsm` recibido y de sus respuestas. Las rutas del equipo del usuario se sustituyen por la base incluida al ejecutar las pruebas. La comparación es directamente contra el proyecto aprobado, sin utilizar una salida del motor nuevo como única referencia.

También se reproduce un anclaje invertido de una captura de 2G-3G en la última versión: su extremo inferior quedaba por encima del superior al compactar filas. La captura se traslada ahora entera, manteniendo su altura y sus desplazamientos internos. La validación detecta anclajes invertidos o de tamaño nulo, que el esquema XML no señalaba.

Las opciones de los formularios y los datos de la base no se modifican. La corrección se aplica al cuestionario de escritorio.

## Verificación de esta entrega

- Cinco pruebas aprobadas, incluyendo la comparación byte a byte de SAR EN y SAR FCC-ISED contra el `Proyecto.xlsm` recibido, la presencia de las columnas completas de tecnologías, los anclajes de dibujos y el bloqueo de cambios en las entradas de apoyo.
- Dos pruebas adicionales de referencias aprobadas: los rangos no incluyen otra banda nueva y no recuperan frecuencias ajenas a la base seleccionada.
- El ejemplo supera el SDK oficial Open XML con **cero errores**, además de la validación de comentarios, relaciones y anclajes del programa.
- Las siete hojas protegidas se contrastan también con ese proyecto aprobado; el detalle y los SHA-256 están en `verificacion_sar_restaurado.json`.
- Se conserva el ejemplo generado con las respuestas recibidas en `ejemplos/Proyecto_SAR_restaurados.xlsm`, junto con `ejemplo_sar_restaurado.json`.

Las pruebas de esta revisión están registradas en `pruebas_restauracion_sar.txt`. La validación estructural no ejecuta Microsoft Excel ni VBA.
