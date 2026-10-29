# Revisión del formulario de bandas

- GPRS y EGPRS muestran sus bandas justo debajo de sus slots. GSM dispone de sus propias opciones. Las tres selecciones son independientes.
- Bajo **Bandas** aparecen directamente las casillas de las opciones disponibles en la base, distribuidas en filas según el espacio. La selección se aplica al marcar cada casilla.
- Se conservan las opciones habituales de 3G, variantes 5G y modos WiFi. BT y Custom se agrupan bajo **Mostrar otras tecnologías**.
- Los slots siguen siendo acumulativos. Se admiten los JSON anteriores con bandas 2G compartidas; los nuevos guardan `bandas_por_modo`.

No se han modificado los formatos ni las fórmulas de las hojas Excel en esta revisión.

## Comprobación

En esta revisión se comprueban la selección acumulativa 2G y una exportación con bandas distintas para GSM, GPRS y EGPRS. Las pruebas con widgets Tk reales en una pantalla virtual de Linux comprueban las casillas visibles, su colocación y distribución, variantes 5G, opciones WiFi y carga de respuestas con bandas eliminadas. No se ha probado la apariencia en Windows.

Los resultados están en [pruebas_interfaz_bandas.txt](pruebas_interfaz_bandas.txt) y [pruebas_widgets.txt](pruebas_widgets.txt). La captura [interfaz_bandas.png](interfaz_bandas.png) corresponde a la aplicación ejecutada.
