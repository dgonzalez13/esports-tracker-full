# Cobertura de las muestras por pareja

Los porcentajes de las tablas operativas siguen siendo exclusivos de cada pareja
y dirección A frente a B. Se conservan los filtros de V% previo, diferencia y
secuencia inicial; no se sustituyen muestras individuales por estadísticas de liga.

## Series con menos de seis resultados

Una sesión cerrada (más de 90 minutos desde el último partido del jugador) con
entre dos y seis encuentros de la pareja puede aportar a los plazos observados:

- V≤4 requiere al menos cuatro resultados.
- V≤5 requiere al menos cinco resultados.
- V≤6 requiere seis resultados.
- V siguiente requiere un resultado posterior al prefijo que se compara.

Cada porcentaje tiene su propio denominador `n`. Los resultados no observados no
cuentan como derrotas. Las sesiones abiertas y las que tienen más de seis
encuentros de la pareja no se usan como series de seis. Se mantienen al menos
20 enfrentamientos anteriores a la sesión, sin usar sus resultados futuros para
calcular los filtros previos.

La columna `n` de «Repetir victoria» corresponde al siguiente partido. Las
estadísticas que expresamente describen series completas de seis conservan su
requisito de seis resultados.

## Recuperación local

`python recover_saved_history.py` revisa las copias HTML guardadas de Eadriatic.
`python recover_saved_history.py --apply` incorpora los resultados consistentes.
Se deduplica por `perspective_id`, se conservan todos los registros existentes y
se descartan nuevas incorporaciones de partidos con discrepancias entre copias.
Cada fila incorporada conserva el nombre del HTML como procedencia.

Los TXT de totales no se convierten en partidos: no contienen las fechas y el
orden por rival necesarios para reconstruir las series. La recuperación local
no completa fechas para las que no se conserva una copia con resultados.

`sample_coverage_comparison.json` documenta el contraste agregado de muestras con
V% previo >40%, antes de la serie (SEC vacía), separado por horizonte. Son casos
por dirección, sumados entre parejas y ligas; no son el `n` de una pareja concreta.
