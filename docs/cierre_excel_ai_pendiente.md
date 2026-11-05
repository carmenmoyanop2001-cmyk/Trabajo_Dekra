# Cierre de Excel al editar AI: investigación pendiente

El usuario confirma que el proceso de Excel se cierra al escribir en AI de un libro recién generado con la entrega 75c28e5. El fallo sigue pendiente de confirmación en Windows; las validaciones XML y de fórmulas no demuestran que ese cierre esté resuelto.

La hoja 2G-3G del ensayo disponible tiene 3.526 fórmulas y ninguna llamada MyTimestamp: la corrección anterior de fechas sigue activa. Su módulo de hoja no contiene un Worksheet_Change activo. El VBA compartido conserva MyTimestamp para las otras tecnologías. No se detecta discrepancia fuente/p-code con la herramienta de inspección; esto no prueba que Excel no tenga un fallo al ejecutar el proyecto.

Se identifica y corrige un ajuste de cálculo innecesariamente costoso: forceFullCalc=1 obligaba a recalcular todo el libro tras cada edición. El ensayo amplio conservado contiene cerca de medio millón de fórmulas y más de 45.000 llamadas MyTimestamp. Ahora se mantiene calcMode=auto, fullCalcOnLoad=1 y calcOnSave=1, con forceFullCalc=0. Se recalculan las cachés al abrir y posteriormente las dependencias de las entradas modificadas. No se cambian AI, AJ, conversiones de potencia, fórmulas SAR, datos ni formatos.

Ocho pruebas dirigidas verifican fechas 2G-3G, referencias de potencia, fórmulas compartidas, instalador anterior y fuentes, incluyendo la configuración real del libro generado. Esta mejora de cálculo no se presenta como causa confirmada del cierre.

Falta revisar el Excel concreto recién generado que falla y el registro de Windows que identifica el módulo y la excepción del cierre. El archivo de antes de la entrega 75c28e5 sirve como referencia, pero no acredita la selección y configuración del nuevo archivo que falla.

`DIAGNOSTICO_CIERRE_EXCEL.bat` lee los eventos Application Error/Windows Error Reporting de Excel de los últimos siete días y datos de versión/plataforma de Office. Escribe Diagnostico_Excel.txt junto al BAT y lo abre en el Bloc de notas. Recoge como máximo tres eventos de Excel, con fecha, versión, módulo y excepción, evitando rutas y nombres de documentos. No instala herramientas, cambia políticas ni inicia Excel. Si la consulta no está disponible, conserva el error en el informe.

El BAT está preparado para ejecutarse en Windows; no se ha ejecutado en este entorno Linux. La entrega Diagnostico_cierre_Excel.zip contiene el BAT y sus instrucciones. Se solicita el TXT y el libro recién generado para continuar con la causa concreta, en vez de considerar suficientes las comprobaciones estructurales.
