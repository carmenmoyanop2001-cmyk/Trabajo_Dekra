# Revisión del formulario de bandas

- GPRS y EGPRS muestran sus bandas justo debajo de sus slots. GSM dispone de sus propias opciones. Las tres selecciones son independientes.
- Las opciones aparecen como texto **Bandas disponibles: (1, 2, 3, …)**. Debajo se escriben los números elegidos, separados por comas, y se confirman con **Aceptar bandas**. La lista de opciones está siempre visible.
- Se conservan las opciones habituales de 3G, variantes 5G y modos WiFi. BT y Custom se agrupan bajo **Mostrar otras tecnologías**.
- Los slots siguen siendo acumulativos. Se admiten los JSON anteriores con bandas 2G compartidas; los nuevos guardan `bandas_por_modo`.

No se han modificado los formatos ni las fórmulas de las hojas Excel en esta revisión.

## Comprobación

En esta revisión se comprueban la entrada numérica, las etiquetas ambiguas, la selección acumulativa 2G y una exportación con bandas distintas para GSM, GPRS y EGPRS. Las pruebas con widgets Tk reales en una pantalla virtual de Linux comprueban la lista visible como texto y su colocación, variantes 5G, opciones WiFi y carga de respuestas con bandas eliminadas. No se ha probado la apariencia en Windows.

Los resultados están en [pruebas_interfaz_bandas.txt](pruebas_interfaz_bandas.txt) y [pruebas_widgets.txt](pruebas_widgets.txt). La captura [interfaz_bandas.png](interfaz_bandas.png) corresponde a la aplicación ejecutada.
