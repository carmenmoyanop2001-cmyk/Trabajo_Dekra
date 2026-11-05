# Revisión del programa de escritorio — 5 de noviembre de 2026

Se parte de la última versión guardada, `6f1ca2b`, que el usuario confirma que coincide con su ZIP main12. El ZIP adjunto supera el límite de transferencia de 32 MiB. Sí se ha podido examinar el Proyecto.xlsm nuevo (17.376.710 bytes).

Se conserva `cuestionario_ensayo.py` como entrada. Se retiran la aplicación web, su lanzador, dependencias, configuración, pruebas y documentación específica. El cuestionario mantiene sus opciones y la lectura de la base XLSX.

## Canal y frecuencia de SAR

Los cambios de contenido de SAR EN y SAR FCC-ISED se limitan a CC/CD. No cambian posiciones, baterías, accesorios, Mode, exposiciones, combinaciones, colores ni cálculos de las otras columnas.

Para las filas normales se recuperan los enlaces con los auxiliares originales de las tecnologías generadas. Se verifica que cada destino pertenece a la misma tecnología y banda seleccionadas. Así las posiciones normales y los TBD pueden seguir los distintos canales del procedimiento original. Cuando no existe un enlace válido del original para esa combinación, se conserva la fórmula construida desde la base; no se copia un canal de otra banda ni un enlace erróneo a otra tecnología.

Para las filas adicionales de FCC se recuperan sus propias fórmulas originales. En EN se adaptan las fórmulas FCC equivalentes y sus referencias de fila. Por ejemplo:

```excel
FCC: =IF(COUNT(CT3:CT8)=0,"N/A",VLOOKUP(MAX(CT3:CT8),CT3:CY8,5,FALSE))
EN:  =IF(COUNT(CO3:CO8)=0,"N/A",VLOOKUP(MAX(CO3:CO8),CHOOSE({1,2,3,4,5,6},CO3:CO8,CG3:CG8,CH3:CH8,CI3:CI8,CC3:CC8,CD3:CD8),5,FALSE))
```

La tabla FCC CT:CY contiene SAR comunicado, modo, ancho de banda, posición, canal y frecuencia. En EN esos datos están en CO, CG, CH, CI, CC y CD. CHOOSE conserva el orden de esa tabla sin modificar columnas ni insertar auxiliares. Para frecuencia se conserva el índice 6 en vez del 5. EN usa su SAR comunicado de 10 g. Las condiciones originales y los enlaces entre baterías se conservan.

La adaptación distingue antenas y TX, limita las referencias al mismo bloque y deja vacías las referencias a exposiciones descartadas. Una referencia escalar ausente ya no se sustituye por la fila vecina. Las baterías adicionales reutilizan el prototipo original correspondiente.

## Columnas ocultas

`plantilla/columnas_originales.json` guarda la visibilidad original de las 16 pestañas, con la identificación de cada archivo y parte de origen. El generador verifica esa visibilidad al final de cada generación, incluidos los nombres 2G, 3G y las variantes con/sin Conducted. Mantiene anchos y estilos; las columnas nuevas de la base conservan su propia presentación. Esta operación solo modifica el elemento cols del XML, sin reescribir celdas.

## Comprobaciones y límites

Las pruebas de regresión comparan el contenido SAR fuera de CC/CD, las hojas fijas, macros, visibilidad de columnas, fórmulas de baterías/Variability, referencias a auxiliares originales y las correcciones anteriores de CATM1, NB-IoT, WiFi, slots, bandas y temporales. Se superan 40 pruebas distintas; cinco pruebas de widgets se omiten porque requieren pantalla. Los registros conservan la primera pasada y la repetición tras actualizar las expectativas antiguas de visibilidad y fechas.

La carpeta extraída del ZIP importa el cuestionario y genera un ensayo de comprobación. Ese archivo supera el SDK Open XML sin errores. Se analizan además sus 1.600 fórmulas CC/CD (694 distintas), sin referencias rotas ni errores sintácticos. [Resultados](verificacion_escritorio.json) · [Registros](pruebas_revision_escritorio.txt).

El Proyecto.xlsm recibido supera la validación estructural del paquete y el SDK Open XML. Las 4.165 fórmulas distintas de su hoja WiFi se han analizado sin errores sintácticos con un analizador independiente, instalado solo como herramienta de diagnóstico. Esto no reproduce el cálculo ni las reparaciones de Microsoft Excel. No se ha confirmado la causa de los cierres del usuario y queda pendiente la prueba de apertura y edición en Excel de Windows.

Los informes anteriores describen versiones históricas. En esta revisión la comparación contra los SAR aprobados permite los cambios solicitados en CC/CD y en la visibilidad de columnas; sigue comprobando el resto de su contenido.

Para abrir el formulario: extraer la carpeta completa y ejecutar `INICIAR_CUESTIONARIO.bat`, o `python cuestionario_ensayo.py` desde esa carpeta. La primera vez: `python -m pip install -r requirements.txt`.
