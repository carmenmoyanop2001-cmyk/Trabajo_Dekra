# Comprobaciones de fuentes y formatos

La ruta de producción es `generar`, utilizada por el formulario y `generar_desde_json.py`. Siempre carga el catálogo XLSX, por defecto el incluido en datos/. El hash identifica el contenido leído. Las respuestas no conservan un catálogo antiguo oculto como alternativa.

La ruta `generar_heredado` solo permite ejecutar las auditorías y regresiones de las versiones anteriores. Sus pruebas no se presentan como prueba del uso de la base nueva. La suite de producción está identificada en tests/test_base_datos.py.

La prueba principal modifica un XLSX, genera dos libros con distintos valores y comprueba canales, frecuencias, BW, modulación, SCS, RB y datos SAR. Usa FDD101, inexistente en las plantillas antiguas, para detectar una dependencia del antiguo catálogo. Comprueba también que Tune-Up, Validations, Test Campaign y Pretesting-Others conservan el XML guardado.

Otras pruebas verifican que la generación funciona con una carpeta que contiene solamente los formatos reducidos y las hojas guardadas, sin los datos heredados de tecnologías ni el Excel original; que los parámetros ausentes no se recuperan del original; que una banda eliminada se rechaza sin sustituir el archivo previo; que las siete combinaciones de regiones generan las hojas correctas; y que todas las familias incluidas en la base producen sus registros RF.

La interfaz permite elegir o recargar la base, cargar las respuestas JSON y conservar los slots acumulativos. Sus métodos de selección se prueban sin pantalla. La revisión visual y el cálculo de fórmulas en Microsoft Excel no se han ejecutado en este entorno.

Resultados de entrega: 46 pruebas de la suite completa superadas. Tras el ajuste final de validaciones de formato se repitieron las 10 pruebas de producción, también superadas. Los registros están en pruebas_migracion_completa.txt y pruebas_base_datos.txt. El ejemplo XLSM tiene cero errores en el validador Open XML; véase validacion_openxml_base_datos.json.
