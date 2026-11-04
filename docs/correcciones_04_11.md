# Cuatro correcciones del 4 de noviembre de 2026

La referencia es la entrega `bc7b062`: tecnologías completas y motor SAR restaurado de Trabajo_Dekra-main11. Esta revisión se limita a los cuatro puntos pedidos. No modifica el formulario, la base XLSX, las plantillas guardadas ni el motor `_generar` aprobado.

- **LTE CATM1:** la etiqueta visible de J es LTE; la familia seleccionada y sus datos siguen siendo CAT M1.
- **NB-IoT:** cuando una fila nativa coincide con un resumen y con su registro detallado, se conserva la coincidencia detallada. No se eliminan las repeticiones que ya forman parte del procedimiento original ni las variantes diferentes. Los resúmenes siguen permitiendo las filas que no tengan detalle equivalente.
- **WiFi:** se reconstruye su vista normal sin paneles inmovilizados ni divisiones heredadas que incluyan las filas ocultas de apoyo. Se regeneran los datos, fórmulas, formatos, comentarios y dibujos desde la copia completa guardada y la selección actual.
- **SAR EN, CC/CD:** solo las filas adicionales toman las fórmulas originales correspondientes de FCC-ISED. Las filas normales ya comparten la búsqueda RF de FCC y se conservan. Se adaptan filas, exposición y antena; las fórmulas de una batería no consultan otra banda o antena. La segunda batería mantiene el alias de FCC a la primera. Si el prototipo usa INDEX/MATCH, se mantiene; si usa VLOOKUP, se mantiene esa función y su condición.

La tabla CT:CY de FCC contiene SAR, modo, BW, posición, canal y frecuencia. En EN son CO, CG, CH, CI, CC y CD. Al no ser contiguas, se usa `CHOOSE({1,2,3,4,5,6},...)` para formar esa misma tabla dentro de la fórmula y conservar los índices 5/6 de VLOOKUP. No se añaden columnas auxiliares ni se modifica ninguna otra columna de EN.

El motor aprobado y sus fuentes siguen comprobándose con el inventario de la revisión anterior. La corrección de CC/CD se aplica después del motor, antes de publicar el archivo. Las pruebas comparan SAR EN conservando estilos y estructura e ignorando únicamente las fórmulas/resultados de CC y CD; FCC-ISED y las otras hojas sin cambios se comparan byte a byte con el ejemplo anterior. El ejemplo actual es `ejemplos/Proyecto_correcciones_04_11.xlsm` y reutiliza `ejemplo_sar_restaurado.json`.

La validación estructural no ejecuta Microsoft Excel ni macros VBA. Los informes anteriores documentan sus respectivas versiones.

## Verificación

Las nueve pruebas específicas han pasado, incluida la comparación de CATM1 fuera de J. También han pasado las tres comprobaciones de integridad del motor aprobado y la generación con el paquete de formatos sin datos heredados ni el Excel original. Los resultados están en `pruebas_correcciones_04_11.txt`.

El informe `verificacion_correcciones_04_11.json` documenta once hojas idénticas byte a byte, estilos y VBA idénticos, y SAR EN idéntico fuera de CC/CD. Se han corregido 992 celdas CC/CD y comprobado 38.616 referencias para verificar que conservan tecnología, banda y antena. La vista WiFi se reconstruye sin cambiar sus datos ni formatos. La validación del paquete y el SDK Open XML dan cero errores.
