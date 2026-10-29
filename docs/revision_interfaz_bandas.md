# Revisión del formulario de bandas

- GPRS y EGPRS muestran sus bandas justo debajo de sus slots. GSM dispone de sus propias opciones. Las tres selecciones son independientes.
- Las opciones aparecen como texto **Bandas disponibles: (1, 2, 3, …)**. Debajo se escriben los números elegidos, separados por comas, y se confirman con **Aceptar bandas**. La lista de opciones está siempre visible.
- Se conservan las opciones habituales de 3G, variantes 5G y modos WiFi. BT y Custom se agrupan bajo **Mostrar otras tecnologías**.
- Los slots siguen siendo acumulativos. Se admiten los JSON anteriores con bandas 2G compartidas; los nuevos guardan `bandas_por_modo`.
- Una única banda disponible se elige automáticamente y oculta los controles de bandas. Si no hay registros para una tecnología, se oculta la entrada y se informa de la falta de datos.
- LTE CAT M1 y tecnologías equivalentes usan números también al cargar respuestas, confirmar y mostrar el resumen. Los identificadores RF de la base se conservan en JSON y Excel.
- Se ha consultado el XLSM original de 2G-3G: las cinco opciones 3G comparten 12 bandas. HSPA, HSPA+, HSDPA y DC-HSDPA utilizan el catálogo WCDMA de la base si no tienen registros propios. Solo comparten bandas, canales y frecuencias; los parámetros propios ausentes quedan vacíos. El archivo `bandas_3g_original.json` recoge la comprobación. No se han copiado valores RF del original a la base.

No se han modificado los formatos ni las fórmulas de las hojas Excel en esta revisión.

## Comprobación

En esta revisión se comprueban la entrada numérica, las etiquetas ambiguas, la selección acumulativa 2G y una exportación con bandas distintas para GSM, GPRS y EGPRS. Una exportación 3G incluye WCDMA y las cuatro variantes, comprueba cambios de frecuencia en la base y la prioridad de datos específicos. Las pruebas con widgets Tk reales en una pantalla virtual de Linux comprueban la lista visible como texto y su colocación, bandas 3G, variantes 5G, opciones WiFi, tecnologías de banda fija y carga de respuestas con bandas eliminadas. No se ha probado la apariencia en Windows.

Los resultados están en [pruebas_interfaz_bandas.txt](pruebas_interfaz_bandas.txt) y [pruebas_widgets.txt](pruebas_widgets.txt). La captura [interfaz_bandas.png](interfaz_bandas.png) corresponde a la aplicación ejecutada.
