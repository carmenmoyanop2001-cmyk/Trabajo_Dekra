# Comentarios eliminados por Excel — 3 de noviembre de 2026

El registro recibido indica que Excel quitó comentarios de `/xl/comments1.xml`. En la salida anterior se reprodujo una incoherencia: las hojas de tecnologías conservaban las relaciones a los comentarios y sus formas VML, pero la presentación nueva omitía `legacyDrawing` en el XML de la propia hoja. El comprobador anterior verificaba que los archivos existieran, sin detectar que ese enlace faltaba.

Se conserva ahora `legacyDrawing` al reconstruir cada hoja de tecnología. Se mantienen los comentarios y los dibujos originales completos. No se modifica la plantilla guardada, las fórmulas, las imágenes, los estilos ni las macros.

El validador comprueba también que cada hoja con comentarios enlaza al dibujo VML correspondiente y que sus formas Note coinciden con las celdas de los comentarios. Una incoherencia bloquea la publicación del archivo.

Comprobaciones realizadas:

- Cuatro pruebas nuevas aprobadas: conservación de comentarios y hojas protegidas; detección de enlace ausente; detección de enlace a una relación incorrecta; detección de formas desplazadas.
- Dos pruebas existentes de tablas de tecnologías aprobadas, incluyendo nombres 2G/3G, selección con y sin conducidos, regiones y conservación de las siete hojas protegidas.
- Ejemplo regenerado desde las mismas respuestas: solo cambian `xl/worksheets/sheet3.xml`, `sheet7.xml`, `sheet8.xml` y `sheet9.xml`, incorporando el enlace perdido. Todos los demás archivos internos coinciden byte por byte con el ejemplo anterior.
- SDK Open XML: `Count: 0`, sin errores estructurales. No se ha ejecutado Microsoft Excel en este entorno.

Para aplicar la corrección a un ensayo anterior, vuelve a generarlo con la versión actual del programa. El cambio se aplica al cuestionario de escritorio.
