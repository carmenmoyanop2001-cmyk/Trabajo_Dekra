# Comprobación de la app Streamlit — 30 de octubre de 2026

Se usa `app_streamlit.py` con Python 3.12 y Streamlit 1.66.1. La app requiere Python 3.11 o posterior. El generador y las plantillas existentes no se modifican.

## Pruebas automatizadas

```sh
python -m unittest discover -s tests -p test_streamlit_app.py -v
```

Las cuatro pruebas iniciales pasaron. Después de añadir el tratamiento de opciones retiradas al cambiar de base, pasaron las dos comprobaciones dirigidas de opciones y slots. Son cinco casos distintos:

- Slots acumulativos GPRS/EGPRS, desmarcado de slots superiores, ausencia de bandas 2G, confirmación `FDDI` y rechazo de bandas inexistentes.
- Generación desde el formulario, cuatro descargas, integridad del ZIP, base y SHA-256 correctos en las respuestas; igualdad de las siete hojas protegidas y del VBA frente al generador de escritorio. Una edición posterior oculta las descargas antiguas.
- Base temporal editada: el Excel muestra canal `12345` y frecuencia `9001.5`, procedentes exclusivamente de ese archivo. Reimportación del JSON y tratamiento de nombres de archivo reservados de Windows. Rechazo de una base dañada.
- Importación sin seguir rutas de otro ordenador ni modificar el documento recibido; conservación de modos guardados y slots acumulativos.
- Opciones retiradas: siguen visibles con aviso y bloquean la generación. Las respuestas WLAN incompatibles se rechazan antes de sustituir el formulario.

## Navegador y archivo final

Se abrió la app local en Chromium mediante Playwright. Se cargaron el XLSX incluido y `ejemplos/ejemplo_tecnologias_ordenadas.json`, se generó el ensayo y se descargó el ZIP mediante el botón del navegador. Contenía los cuatro archivos esperados y `ZipFile.testzip()` no detectó errores. El hash de la base descargada coincidía con el guardado en el JSON. Una segunda sesión del navegador no compartía las respuestas ni las descargas de la primera.

El validador Open XML devolvió `Count: 0` para el Excel producido desde Streamlit. Esto comprueba su estructura; no ejecuta Microsoft Excel ni sus macros.

Capturas reales: [formulario](streamlit_cuestionario.png) y [descargas](streamlit_descargas.png).
