# Revisión del formulario de bandas

- GPRS y EGPRS muestran sus bandas justo debajo de sus slots. GSM dispone de su propio campo. Las tres selecciones son independientes.
- Las bandas se introducen mediante números separados por comas. Se comprueban contra la base cargada al pulsar **Aceptar bandas**. La lista completa solo se muestra al pulsar **Ver disponibles**.
- Se conservan las opciones habituales de 3G, variantes 5G y modos WiFi. BT y Custom se agrupan bajo **Mostrar otras tecnologías**.
- Los slots siguen siendo acumulativos. Se admiten los JSON anteriores con bandas 2G compartidas; los nuevos guardan `bandas_por_modo`.

No se han modificado los formatos ni las fórmulas de las hojas Excel en esta revisión.

## Comprobación

Se han superado 14 pruebas de selección, compatibilidad y generación desde la base de datos, incluida una exportación con bandas distintas para GSM, GPRS y EGPRS. También se han superado 3 pruebas con los widgets Tk reales en una pantalla virtual de Linux: posición de los campos, opciones anteriores y carga de respuestas. No se ha probado la apariencia en Windows.

Los resultados están en [pruebas_interfaz_bandas.txt](pruebas_interfaz_bandas.txt) y [pruebas_widgets.txt](pruebas_widgets.txt). La captura [interfaz_bandas.png](interfaz_bandas.png) corresponde a la aplicación ejecutada.
