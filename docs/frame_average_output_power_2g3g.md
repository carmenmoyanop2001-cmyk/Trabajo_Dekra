# Revisión de AI — Frame Average Output Power, 2G-3G

Actualización: el usuario confirma que el cierre persiste con la entrega reciente. Se corrige el recálculo completo forzado y se solicita el fallo registrado por Windows. El estado vigente está en [cierre_excel_ai_pendiente.md](cierre_excel_ai_pendiente.md); las validaciones descritas abajo no constituyen una confirmación de estabilidad en Excel.

El usuario confirma que Excel se bloquea y también llega a cerrarse al introducir valores en AI. Se revisa el Proyecto_2G_3G.xlsm adjuntado. Tiene cinco hojas: Overview, Tune-Up, Conducted 2G-3G, Validations y Test Campaign. Se conserva esa misma lista, sin generar otras tecnologías ni hojas SAR.

AI es una entrada manual. AJ aplica el factor de slots original, por ejemplo `AI75+$CL$74`. No se han encontrado referencias circulares ni un evento Worksheet_Change activo en la hoja Hoja17. La función MyTimestamp ejecutada desde BE es una UDF VBA de fecha. No contiene un bucle ni escribe celdas; no se ha confirmado que sea la causa del bloqueo de Excel.

La corrección propuesta retira la llamada a VBA de las fechas de esta hoja y la sustituye por una fórmula nativa de Excel, conservando la misma celda de entrada y la presentación yyyy-mm-dd hh:mm:ss. El identificador regional [$-409] mantiene ese formato en Excel en español. Con forceFullCalc ya activo en el archivo recibido, ambas versiones recalculan las fechas cuando se recalcula el libro. No se añade una fecha fija ni se altera la conversión de potencia.

Solo cambia xl/worksheets/sheet3.xml del archivo adjunto. Las otras cuatro hojas, estilos, macros, imágenes, comentarios, nombres definidos y demás partes se mantienen byte a byte. En esa hoja solo cambian los textos de 12 maestros de fórmula, equivalentes a 510 fechas después de expandir sus grupos compartidos. AI, AJ, slots, canales, frecuencias y estilos permanecen intactos. No se modifica el VBA compartido con otras tecnologías.

El generador aplica la misma corrección únicamente a la familia 2G-3G, incluidas sus filas ocultas y las vistas con nombre 2G o 3G. El instalador pequeño modifica solo esos puntos en generador_excel.py y tecnologias_originales.py, incorpora corregir_2g3g.py y guarda copias previas. Se ha comprobado sobre las versiones 9bb8aa0, bc7b062 y 2ba272b; se detiene si no reconoce el código, sin reemplazar el resto del programa. No fue posible descargar Trabajo_Dekra-main12.zip porque supera el límite de transferencia de 32 MiB de la herramienta.

Cinco pruebas superadas: referencias de potencia, fórmulas compartidas, instalador compatible e idempotente, rechazo de versiones desconocidas y generación 2G/3G. El Excel corregido supera el SDK Open XML sin errores. La comparación y los hashes están en verificacion_frame_2g3g.json.

No se ha ejecutado Microsoft Excel de Windows. La reproducción del bloqueo y la prueba de entrada en AI75 siguen pendientes en ese equipo. El archivo corregido se entrega para realizar esa comprobación antes de aplicar el parche al programa.

## Actualización: permiso denegado en temporales de red

El siguiente error recibido se produce al generar, antes de abrir Excel: WinError 5 al sustituir wifi.zip.ordenadas por wifi.zip.filas dentro de la carpeta de red. Se cambia únicamente la gestión de archivos: el trabajo de las tecnologías usa el directorio temporal del sistema y el ordenador de filas conserva el archivo ordenado con su nombre, actualizando la referencia interna en vez de reemplazar el anterior. Las tablas no cambian.

Se ha simulado la denegación de renombrado, contrastado los bytes y las asignaciones de filas con el ordenador anterior y comparado todas las partes de un Excel generado con 2G y WiFi. El resultado es idéntico. El instalador reconoce también el parche anterior y puede repetirse. No se ha probado contra el servidor de red del usuario; la prueba de bloqueo se simula en el entorno de desarrollo.
