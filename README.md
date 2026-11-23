# Trabajo Dekra — programa completo corregido

Esta carpeta incluye el programa, la base de datos, las plantillas originales,
los formatos y las correcciones entregadas de 5G, tablas y enlaces SAR.
Conserva las correcciones de WiFi y del formato numérico de AI en 2G-3G.

## Cómo empezar en Windows

1. Extrae **todo** el ZIP en una carpeta nueva. No lo ejecutes dentro del ZIP.
2. Si ya tienes Python y las dependencias instaladas, abre
   **INICIAR_CUESTIONARIO.bat**.
3. Si falta `lxml`, ejecuta una vez **INSTALAR_DEPENDENCIAS.bat** y después
   vuelve a abrir **INICIAR_CUESTIONARIO.bat**.

Necesitas Python 3 con tkinter. Este paquete contiene el programa Python;
no incluye un intérprete Python ni es un ejecutable EXE independiente.

También puedes abrir una terminal en esta carpeta y ejecutar:

```
py -3 -m pip install -r requirements.txt
py -3 cuestionario_ensayo.py
```

## Contenido

- Archivos `.py`: programa completo y correcciones.
- `datos/`: base de datos de bandas, canales y frecuencias utilizada en las pruebas.
- `plantilla/`: plantilla base, formatos y copias originales requeridas.
- `herramientas/`: comprobación de los Excel generados.
- `CAMBIOS_Y_VALIDACION/`: explicación y verificaciones de las correcciones.

Mantén juntas estas carpetas. No necesitas copiar las de una versión anterior.
Tus Excel de proyectos anteriores no se modifican; genera uno nuevo con esta versión.

Las plantillas grandes pueden hacer que la generación tarde varios minutos.
No se ha ejecutado Microsoft Excel en Windows en las pruebas: el recálculo y
las macros deben comprobarse en tu equipo.

La corrección vigente de 5G y SAR EN se describe en CORRECCION_5G_SAR_EN.txt.
La carpeta datos/ incluye la base ampliada con Module Port y SCS.
