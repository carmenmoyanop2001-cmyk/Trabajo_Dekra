# Filas añadidas a SAR EN

Se conservan las filas originales seleccionadas, con sus valores, fórmulas y estilos. Tras los TBD de cada bloque de tecnología, banda, exposure condition y ancho de banda se añaden `TBD - Battery check 1` hasta `TBD - Battery check N`. En Body se añade también `Front Face` y las filas `Accesorio n: nombre`. No se añaden filas Variability. El siguiente bloque se desplaza; las reglas de formato condicional y validación también se amplían.

Las fórmulas de las filas adicionales usan estas correspondencias de FCC-ISED a EN:

| FCC-ISED | EN | Uso en la fila adicional |
| --- | --- | --- |
| CA | CA | `CONCATENATE(CAref," - Battery check n")` enlaza con la posición TBD original equivalente, que cambia al introducir las medidas. Se mantiene el valor inicial junto con la fórmula. |
| CC, CD | CC, CD | Canal y frecuencia de la fila con máximo SAR comunicado en el bloque original. INDEX/MATCH sustituye a VLOOKUP porque las copias ocultas de FCC no existen en las mismas posiciones en EN. |
| CI, CJ, CK | CG, CH, CI | Copias de modo, ancho de banda y posición. |
| DC | CQ | Veredicto según SAR comunicado y límite. |
| DD | CR | Numeración de plots de las filas adicionales; no presupone solo dos baterías. |
| DE | CS | MyTimestamp del veredicto. |
| DF, DG | CT, CU | Duración del ensayo y preparación. |
| DL | CZ | Deriva de potencia en porcentaje. |
| DN | DB | Potencia conducida de la fila con máximo SAR del bloque original. |
| DO, DP, DQ | DC, DD, DE | Potencias en mW y factor de escala. |

FCC trabaja principalmente con 1 g; EN con 10 g. Para la búsqueda del peor caso se usa CO de EN (SAR comunicado de 10 g), equivalente funcional a CT de FCC para su SAR principal. Se conservan las fórmulas EN de validez e instrucciones de medida (CL:CN), cálculo del SAR comunicado (CO) y límite de 10 g (CP). No se copian umbrales de 1 g ni límites FCC a EN.

Las búsquedas de canal, frecuencia y potencia de cada fila nueva se restringen a las filas originales del mismo bloque, excluyendo las filas añadidas. Si no hay medidas, devuelven N/A mediante fórmula, no como dato fijo. La fila Front Face adicional usa la distancia de 25 mm del caso equivalente FCC; las posiciones y distancias originales permanecen intactas.

SAR FCC-ISED no recibe estas inserciones ni cambios: solo se filtran sus filas originales por la selección.

Para las dos primeras baterías se sigue la posición de referencia de la fórmula FCC equivalente: según el bloque, ambas usan el primer TBD o la segunda usa el segundo TBD. Las baterías 3 a 10 reutilizan la referencia de la primera batería y cambian su número. La referencia se reubica al filtrar o insertar filas; no apunta a otra batería ni concatena el texto fijo «TBD».

En BX de SAR EN se conserva una celda combinada por tecnología, banda y exposición, incluyendo las filas añadidas. Su etiqueta usa fuente negra para que sea legible: el original usa en algunas filas una fuente del color del relleno para ocultar repeticiones. Se conservan los rellenos y el resto del formato.

## Validación

Las pruebas comprueban los cuatro puntos del GSM del original: con dos baterías, se insertan en las filas 9/10, 19/20, 29/30 y 42/43 del primer bloque de antena de la demostración; Front Face y los dos accesorios están en 31/32/33. Se verifica que el siguiente bloque sigue presente y que cada búsqueda apunta a su bloque de medida.

Además de las pruebas Python, se proporciona una comprobación opcional con el SDK oficial Open XML, que requiere .NET 8:

```sh
dotnet run --project herramientas/validar_openxml -- ejemplos/SAR_EN_GSM_2_baterias.xlsm
```

La validación estructural no ejecuta las macros ni sustituye a la comprobación en Microsoft Excel. El aviso de reparación del archivo Proyecto.xlsm del usuario no se ha podido reproducir sin ese archivo o su informe de reparación. El ejemplo incluido no presenta errores en la validación Open XML.
