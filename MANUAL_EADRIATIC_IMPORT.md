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
