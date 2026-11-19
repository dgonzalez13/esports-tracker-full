# Importar resultados guardados de BetsAPI/BsportsFan

El recolector oficial sigue funcionando con `python eadriatic_leagues.py`.
La alternativa es una importación ocasional de archivos, sin peticiones a la web.
Acepta HTML, MHTML y MHT de la liga 33440, incluidas capturas del código fuente
guardadas por Chrome. Las instrucciones o scripts de la página no se ejecutan.

## Desde GitHub, sin comandos

Sube los archivos a `eadriatic/manual_imports/` y ejecuta la acción
**Import Eadriatic Manual Results**. Primero puedes previsualizar, y después marcar
**Aplicar importación**. El campo **Días completos** permite reconstruir los TXT de
las fechas para las que has reunido todas las páginas.

Solo se leen archivos directamente dentro de esa carpeta. Tras una ejecución de
aplicación terminada correctamente, puedes borrarlos: los resultados quedan en el
historial y su SHA-256 en `eadriatic/manual_import_log.json`, fuera de la carpeta.
El registro impide procesar de nuevo el mismo contenido, incluso renombrado.
La acción actualiza el análisis, regenera el HTML y guarda los cambios en GitHub.
La carga o eliminación de archivos no ejecuta la importación automáticamente.
Las tres acciones que escriben datos comparten un grupo de concurrencia para no
ejecutarse simultáneamente sobre la misma rama.

## Revisar antes de importar

```powershell
python eadriatic_leagues.py --source betsapi --html "C:\resultados\*.mhtml" --export-dir artifacts/revision_eadriatic
```

Sin `--apply`, el historial y los TXT originales no cambian. La salida indica
partidos únicos, incorporaciones nuevas y primera/última hora en Madrid.
`--export-dir` guarda el HTML extraído, JSONL normalizado y resumen de revisión.
`--source bsportsfan` acepta el mismo formato de página guardada.

## Incorporar partidos al historial detallado

```powershell
python eadriatic_leagues.py --source betsapi --html "C:\resultados\*.mhtml" --apply
```

Se utiliza el mismo `eadriatic/data/match_history.jsonl`. Antes de cambiarlo se
crea una copia `.before_manual_...`. No se borran partidos existentes. Las páginas
solapadas y las reimportaciones no deben aumentar el número de partidos.

Los IDs externos quedan como `eadriatic:betsapi:ID`, con el archivo y la URL de
procedencia. No se inventan los IDs, grupos, rondas o calendarios de LeagueRepublic.
La fecha se obtiene del atributo UTC `data-dt`, nunca del texto abreviado de la
tabla ni de la fecha de guardado del archivo. Se convierten las fechas a Madrid.

Al mezclar con la fuente oficial, se comparan jugador/rival, instante exacto y
marcador desde la perspectiva del jugador, incluso si cambia local/visitante.
Los datos oficiales tienen prioridad: si ya existe el partido oficial, el
resultado manual no lo reemplaza. Si primero se importó manualmente, la llegada
del resultado oficial lo sustituye, incluidos ID, marcador y metadatos de grupo.
Se conserva el registro provisional en `alternate_sources` para auditoría.
El `repair_eadriatic_day.py` aplica esta misma prioridad y permite corregir un
marcador provisional con el oficial; repetir el repair no crea duplicados.

Se coteja partido a partido, no se descartan fechas enteras: un día puede estar
recogido solo parcialmente. Se pueden incluir páginas de fechas ya cubiertas o
solapadas, sin sumar dos veces los resultados oficiales.

Si hay varios candidatos o las horas difieren hasta cinco minutos, se detiene la
importación para revisar el caso. Diferencias mayores no se emparejan automáticamente:
no hay una equivalencia garantizada entre los IDs de ambas webs. No se adivinan
correspondencias cuando han cambiado horarios o nombres de jugadores.


## Reconstruir el TXT cuando esté completo un día

Una página no representa necesariamente un día entero. Deben guardarse todas las
páginas que cubran ese día en horario de Madrid, incluidos sus extremos.
Cuando se hayan reunido los resultados, se puede declarar ese día completo:

```powershell
python eadriatic_leagues.py --source betsapi --html "C:\resultados\*.mhtml" --apply --complete-day 2026-10-19
```

Se reconstruye `20261019_eadriatic_player_stats.txt` con todos los resultados de esa
fecha presentes en el historial combinado y se conserva una copia del TXT anterior.
Se puede repetir `--complete-day` para varias fechas. La declaración es manual:
el programa no puede demostrar que la web haya publicado todos los encuentros.
Sin ella no se reemplazan los totales de un día por los de una muestra parcial.

Después se actualizan los cálculos y la página:

```powershell
python group_analysis.py EADRIATIC
python web_tracker/generate_site.py
```

## Archivo de ejemplo revisado

`test-besapi.mhtml` guarda la página 7: 30 partidos del 19/10/2026 entre las
15:45 y 17:45 de Madrid (13:45–15:45 UTC). Permite la importación, pero no permite
reconstruir el día entero ni los grupos oficiales. La demostración se mantiene en
`artifacts/eadriatic_manual_example`, separada del historial real.


## Candidatos y posibles partidos a partir de resultados importados

Al aplicar una importacion con cambios se regenera la web. El bloque
**Eadriatic: posibles partidos pendientes** detecta parejas con resultados
importados en las ultimas 8 horas y sin encuentros publicados en el calendario.
Muestra los partidos registrados, los posibles pendientes hasta seis y la hora
del ultimo resultado (Madrid). Los horarios calculados se identifican como estimados, sin confirmar que haya otro
partido: se presupone una serie de seis y que la muestra reciente este completa.

Las parejas detectadas se evaluan en los candidatos de 4, 5 y 6 partidos y en la
nueva lista de repetir victoria, incluso si no pertenecen a los grupos configurados.
Los grupos guardados no se modifican. Se conservan los filtros, las exclusiones,
los minimos de muestra y los checks. Registrar una pareja no basta para que sea
candidata: debe tener estadisticas suficientes y cumplir los requisitos.

Importa resultados recientes durante la jornada. Las parejas sin nuevos
resultados dejan de inferirse al salir de la ventana de ocho horas en la siguiente
generacion de la web. Los partidos con hora publicada mantienen su calendario
normal; no se sustituyen por una prediccion. En las lineas sin calendario se indica
el numero registrado y el posible resto, siempre para comprobacion manual.
Una pagina incompleta puede omitir partidos ya disputados; no se puede demostrar
que los encuentros estimados esten realmente pendientes.


## Horarios estimados por pareja

La pauta configurada es: primer partido, +75, +165, +240, +315 y +390 minutos.
Por ejemplo: 07:00, 08:15, 09:45, 11:00, 12:15 y 13:30 (Madrid).

Se calcula automaticamente el inicio solo si las horas observadas encajan de forma
unica y se dispone de todos los resultados desde el primer partido. Una sola
observacion no permite saber si corresponde al primero, segundo u otro encuentro.
Si faltan resultados intermedios o la pauta no coincide, no se inventa un horario.

En **Import Eadriatic Manual Results** puedes rellenar **first_games** con:

```
David|Fox|2026-11-19 07:00
```

Son los nombres exactos de la pareja y la fecha/hora del primer partido en Madrid.
Para varias parejas, separalas por punto y coma. Marca **Aplicar importacion** para
guardar el inicio y regenerar la pagina. Puedes introducirlo aunque los HTML ya se
hayan procesado; no hace falta cambiar de nombre ni volver a importar los archivos.
Si dejas el campo vacio, se conservan los inicios guardados para sus fechas.
Quedan en `eadriatic/estimated_starts.json`. Las fechas anteriores no se reutilizan
para extrapolar rondas nuevas.

Las estimaciones aparecen en **Eadriatic: posibles partidos pendientes** y en los
candidatos que cumplan los filtros, con la etiqueta **Horario estimado**. No se
mezclan con el calendario publicado ni se guardan como partidos oficiales.
El calendario oficial tiene prioridad. Pasar una hora prevista no cuenta como
resultado ni adelanta la progresion: solo un resultado importado puede hacerlo.
Si una hora prevista ya ha pasado, la linea avisa de que falta el resultado.


### Pauta compartida y alerta de forma

Si una pareja tiene al menos dos resultados pero su inicio es ambiguo, se pueden
usar como referencia parejas que compartan jugador y tengan un inicio ya resuelto
independientemente, a menos de 75 minutos del primer resultado observado. Solo
se genera horario si queda una unica alineacion compatible y no faltan resultados
desde el inicio. Se identifica como **pauta compartida (comprobar)**. No se encadenan
estimaciones de unas parejas a otras ni se extrapolan grupos nuevos por un solo
resultado. El inicio manual y las horas oficiales mantienen prioridad.

Los candidatos de 4, 5 y 6 partidos muestran una alerta si su indicador operativo
es rojo y el del rival verde, usando los mismos criterios de colores de las ultimas
8 horas. El aviso incluye derrotas/partidos del candidato y victorias/partidos del
rival. No elimina al candidato ni modifica la muestra historica o la progresion.
El rojo del indicador actual incluye el 50% de derrotas, salvo que corresponda
verde por el criterio de victorias. La alerta sigue esos mismos colores.


Los avisos de forma distinguen tres combinaciones desfavorables para el candidato:
**rojo-verde**, alerta grave en rojo, y **rojo-blanco** / **blanco-verde**, avisos
de precaucion en naranja. Blanco equivale al indicador neutro NONE; no se asigna
un aviso por ausencia de resultados. Ambos jugadores deben tener datos recientes.
Se muestran victorias y derrotas de ambos con sus muestras de partidos. La alerta
no supone una nueva probabilidad de victoria ni cambia los filtros del candidato.


### Recuperacion del calendario oficial

El modo sin calendario solo se activa si no hay un calendario Eadriatic utilizable:
la ultima actualizacion debe tener como maximo ocho horas, no tener un error de
captura y contener proximos partidos publicados. Cuando se recupera, se usan
solo sus horarios: se retiran estimaciones y candidatos de parejas sin partido
publicado. No se renombra a un jugador ni se sustituye automaticamente en los
grupos guardados si cambia la composicion del calendario.

Los workflows de importacion manual, reparacion y actualizacion de jugadores
refrescan tambien el calendario antes de regenerar la web. Si falla la captura,
se conserva el calendario anterior con el error y se permite de nuevo el modo
alternativo. Este refresco no modifica por si solo los jugadores configurados.
