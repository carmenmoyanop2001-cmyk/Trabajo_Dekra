# SAR de main12 sobre la última entrega

Se mantiene como base la entrega `823dca2`. Se sustituyen únicamente SAR EN y SAR FCC-ISED por el procedimiento de `6f1ca2b`, identificado como la base de main12 en la confirmación del usuario registrada en `verificacion_escritorio.json`. El ZIP adjunto no se ha podido descargar por su tamaño; se recupera esa copia del historial, sin atribuirle una lectura del adjunto.

`sar_version12_motor.py` conserva literalmente la función SAR de esa base. `sar_version12_canales.py` conserva su adaptación de canales EN. La integración se añade al final del generador actual: crea los dos SAR por separado y reemplaza exclusivamente sus partes XML, filtros y estilos necesarios. Los índices y definiciones de los estilos existentes permanecen intactos.

No se modifica el código de Overview, Tune-Up, tecnologías, Validations, Test Campaign ni Pretesting-Others. También permanecen intactas las correcciones de fórmulas WiFi, desplazamiento de tecnologías, columna AI y cálculo automático de la última entrega. No se incorpora Streamlit.

La comparación con el libro de la última entrega usa una selección que incluye las siete familias de tecnologías, ambas hojas SAR, baterías y accesorios. Todas las partes ajenas a SAR se conservan byte por byte, incluidas las hojas, imágenes, relaciones y VBA. Solo cambian las dos partes SAR, sus filtros en workbook.xml y los estilos añadidos/reutilizados en styles.xml. Los dos SAR coinciden con una generación independiente de la referencia histórica antes del ajuste de índices de estilos y visibilidad aprobada.

Pruebas: `PYTHONPATH=tests:. python -m unittest -v test_sar_version12`. La validación del paquete y el SDK Open XML no detectan errores en el libro de comprobación. No se ha ejecutado Microsoft Excel de Windows en este entorno.

El formulario se inicia como antes: `INICIAR_CUESTIONARIO.bat` o `python cuestionario_ensayo.py` dentro de la carpeta extraída.
