# Revisión de selección y conservación de FCC-ISED

Base de contraste: versión `ae00f85`, anterior al cambio de etiquetas de exposición y fórmulas de batería. Se mantiene su adaptación de las columnas calculadas de las filas nuevas EN; únicamente CA elige el prototipo FCC con el número de batería correspondiente.

No se dispone de las respuestas que produjeron la captura del usuario. La ausencia concreta de SAR EN en ese archivo no se ha reproducido. Se han probado las siete combinaciones nuevas de EN, FCC e ISED con tecnologías y bandas seleccionadas, incluyendo LTE FDD2/FDD5 y GSM. EN produce SAR EN; FCC e ISED comparten SAR FCC-ISED. FCC/ISED sin EN no solicitan una hoja EN. Si una selección EN no existe en la plantilla original se conserva el error explícito, sin inventar filas ni guardar un Excel parcial.

La comprobación final lee el workbook emitido y verifica las hojas solicitadas, su visibilidad y sus filas. Las pruebas inyectan tanto una hoja ausente como una oculta y comprueban que se conserva el archivo previo.

En las capturas se muestran tecnologías diferentes: LTE FDD2 y GSM 850. Sus colores y fórmulas de posiciones pueden diferir ya en el datasheet. La comparación de conservación se realiza por la misma fila de origen, no igualando LTE con GSM.

Se ha verificado que la plantilla FCC mantiene idénticos todos los campos de `ae00f85`: filas, fórmulas, constantes, estilos, cabecera y cola. Solo se añade un campo con resultados guardados del original FCC recibido, contrastando la fórmula expandida de cada celda con la plantilla. Se descartan fórmulas con referencias rotas o diferentes. Estos resultados se guardan junto a las fórmulas activas para evitar celdas inicialmente vacías, como los límites SAR con valor 0. No se añaden baterías ni accesorios a FCC.

El script reproducible es `herramientas/completar_cache_fcc.py`; su informe incluye el hash del original y los recuentos en `docs/cache_fcc_original.json`. Los metadatos ya conservados, como Channel y Freq, tienen prioridad sobre este complemento. El recálculo y las macros necesitan Microsoft Excel; la validación Open XML es estructural.
