# Cierre de Excel al editar AI — archivo recibido el 6 de noviembre

Actualización posterior: el usuario pide incorporar el ajuste al programa. El generador lo incluye ahora en cada libro nuevo y verifica la configuración antes de publicar. La prueba descrita más abajo se conserva como antecedente. Sigue pendiente la confirmación del cierre en Windows; no se considera una causa demostrada ni una resolución confirmada.

El registro de Windows identifica Excel `16.0.5530.1000`, módulo `EXCEL.EXE`, excepción `c0000005` y desplazamiento `00300ee3`. Es una infracción de acceso dentro de Excel. El evento no identifica una celda, fórmula o causa concreta. La clave `Bitness=x86` pertenece a Outlook; no demuestra por sí sola la arquitectura del ejecutable de Excel.

Se ha podido descargar y analizar el `Proyecto.xlsm` que falla (24.704.314 bytes). Conserva el VBA de la entrega anterior y las correcciones de fechas de 2G-3G. La configuración real sigue en cálculo automático, con recálculo al abrir y `forceFullCalc=0`.

El recuento final es de 858.712 fórmulas: 7.250 en 2G-3G, 220.846 en SAR EN y 280.472 en SAR FCC-ISED. Hay 918 fórmulas NOW en 2G-3G, sin MyTimestamp en esa hoja. El paquete ocupa aproximadamente 254,4 MiB descomprimido; ese tamaño no mide la memoria utilizada por Excel en Windows. Se corrige el recuento aproximado anterior indicado en el chat.

El análisis de referencias A1 entre 2G-3G y ambos SAR recorre 508.568 fórmulas, sin encontrar ciclos después de excluir referencias puramente geométricas de COLUMN/ROW. Identifica 1.704 fórmulas locales dependientes de AI. Las validaciones de datos no se aplican a AI y sus dos formatos condicionales comparan potencias con MAX. Este análisis no ejecuta VBA, funciones indirectas ni el motor de cálculo de Excel; no acredita la ausencia de cualquier fallo dinámico.

El archivo original supera el SDK Open XML, como los anteriores. Esto no reproduce el cierre. No se ha ejecutado Excel de Windows en este entorno.

## Prueba acotada de compatibilidad

Se prepara una copia cambiando únicamente `calcPr@concurrentCalc` a `0`: permite probar cálculo en un hilo con cálculo automático, recálculo de apertura y demás opciones intactas. No se presenta como causa confirmada ni como cierre resuelto. La opción no se incorpora todavía al generador predeterminado.

Se comparan los contenidos de todas las partes del archivo real. Solo cambia `xl/workbook.xml`, exactamente en ese atributo. Todas las hojas, sus fórmulas y estilos, ambos SAR, relaciones, imágenes y VBA permanecen idénticos. El original no se sobrescribe. La herramienta verifica los contenidos mediante SHA-256 y rechaza la sobrescritura de archivos existentes.

`Prueba_compatibilidad_Excel.zip` contiene un lanzador, un script Python sin dependencias externas y las instrucciones. No contiene el libro del usuario. La prueba usa seis tests de conservación del contenido, configuración de cálculo y rechazo de sobrescrituras. También se valida la copia del archivo real con el validador del paquete y el SDK Open XML.

**Pendiente:** abrir la copia en el equipo del usuario y editar AI. La causa del cierre y su resolución siguen sin confirmación hasta esa comprobación. Si funciona, se podrá trasladar el ajuste al generador; si no, se mantendrá esta prueba como resultado negativo, sin atribuirle una corrección.
