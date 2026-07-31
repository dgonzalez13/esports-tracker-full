# TASK-001 — Persistencia incremental del historial normalizado

## Alcance implementado

Esta tarea añade la persistencia futura de partidos finalizados como JSONL. No reconstruye datos históricos, no cambia los análisis H2H o Current Streaks y no modifica la web ni el workflow.

Los scrapers mantienen la generación existente de TXT. En cada ejecución también actualizan de forma idempotente:

- `gt/data/match_history.jsonl`;
- `eadriatic/data/match_history.jsonl`.

Los archivos JSONL no se incluyen vacíos en el repositorio: se crean atómicamente en la primera ejecución del scraper, incluso si la lista de candidatos válidos está vacía.

## Archivos creados

- `match_history.py`: validación, normalización de nombres, simetría, carga, merge, deduplicación, orden y escritura atómica.
- `tests/test_match_history.py`: 22 pruebas offline del store y de ambos adaptadores.
- `TASK-001-Match-History-Persistence.md`: este informe.

## Archivos modificados

- `gtleagues_api.py`: convierte partidos válidos de la API en dos perspectivas y actualiza el historial GT antes de generar los agregados existentes.
- `eadriatic_leagues.py`: extrae ID, bloque, fecha, hora, marcador y orden de fuente; actualiza el historial EADRIATIC y conserva el parser agregado anterior.
- `.gitignore`: ignora `tests/.tmp/`, usado por las pruebas en entornos Windows sandboxed.

No se modificaron `group_analysis.py`, `web_tracker/generate_site.py`, `build_opportunity_input.py`, `tracked_players.txt`, `.github/workflows/update.yml`, `docs/index.html` ni `AUDIT-001-Match-History-and-Temporal-Analysis.md`.

## Formato JSONL

Cada línea UTF-8 es una perspectiva de un jugador. Un partido finalizado genera una perspectiva `home` y otra `away`, con el mismo `match_id`, timestamp, marcador y metadatos.

Los campos obligatorios implementados son los indicados por TASK-001. Los opcionales se añaden únicamente cuando la fuente los ofrece. Las claves JSON se escriben alfabéticamente mediante `sort_keys=True`, sin ASCII escaping, y los registros se ordenan por:

1. `timestamp_utc`;
2. `league`;
3. `match_id`;
4. `player_key`.

Los nombres visibles se limpian con `strip()` y Unicode NFKC. Las claves añaden `casefold()` sin eliminar tildes ni caracteres internos.

## Identidad, deduplicación y conflictos

- GT usa `gt:<id_nativo>`.
- EADRIATIC extrae el número de `/match/<id>.html` y usa `eadriatic:<id_nativo>`.
- `perspective_id` es `<match_id>:<player_key>`.
- La idempotencia se aplica globalmente por `perspective_id`, tanto entre candidatos de una ejecución como contra el archivo existente.
- Campos antes ausentes se incorporan al observar información compatible.
- `data_quality` puede mejorar de `partial` a `inferred` o `complete`.
- Un valor incompatible no sustituye al existente y genera `RuntimeWarning` con perspective ID, campo y ambos valores.
- `source_file` y `collected_at` diferentes se consideran observaciones compatibles del mismo evento; se conserva la primera procedencia sin advertencia.
- Una línea JSON inválida o un registro inválido interrumpe la actualización con archivo y número de línea.

La escritura se hace en un temporal UTF-8 dentro de la carpeta destino, se fuerza con `fsync` y se publica con `os.replace`. Un error elimina el temporal cuando el sistema lo permite y deja intacto el archivo definitivo.

## Validación de perspectivas

Antes de persistir cada pareja se comprueba:

- exactamente un registro home y uno away;
- mismo match ID, timestamp, marcador y metadatos;
- jugador y rival invertidos correctamente;
- resultados coherentes con el marcador: V↔D, D↔V o E↔E.

Los fixtures sin marcador final, participantes incompletos, ID inválido o timestamp no interpretable no generan candidatos.

## Política de timestamps GT

Se analiza el `kickoff` original mediante `datetime.fromisoformat`:

- sufijo `Z`: UTC explícito, `timezone="UTC"`, `timezone_inferred=false`;
- offset como `+02:00`: se conserva ese instante y se identifica como `UTC+02:00`, `timezone_inferred=false`;
- sin offset: se aplica `Europe/Madrid` porque el scraper existente define sus rangos diarios en esa zona; se marca `timezone_inferred=true` y `data_quality="inferred"`.

`timestamp_utc` siempre termina en `Z`. La precisión se marca `second` si el valor fuente contiene segundos y `minute` si solo contiene hora y minuto. No se guardan datetimes naive.

No se persisten competición, ronda o grupo de GT porque el código actual no demuestra qué campos reales de la respuesta contienen esos datos. `source_file` usa la referencia lógica `gt_api:YYYY-MM-DD`, ya que no existe un archivo de respuesta cruda.

## Política temporal EADRIATIC

El adaptador combina:

- la fecha terminal de `span.fg-heading`;
- la hora `HH:MM` de `span.time-heading`;
- `Europe/Madrid` como política inicial.

Como el HTML no declara la zona, todos estos registros usan:

- `timestamp_precision="minute"`;
- `timezone="Europe/Madrid"`;
- `timezone_inferred=true`;
- `data_quality="inferred"`.

El timestamp UTC se calcula explícitamente respetando CET/CEST. El archivo se ordena posteriormente por timestamp; el orden global del DOM no se interpreta como cronológico.

Del encabezado real se extraen, cuando encaja con el formato observado, `round` y `competition`. `group_key` se deriva de la etiqueta completa normalizada y la fecha. También se guardan `source_block_order` y `source_row_order`. No se inventa `group_players`.

El scraper guarda primero el HTML y usa su nombre real como `source_file`. `collected_at` se obtiene con offset de `Europe/Madrid`.

## Campos no disponibles

- GT: no se añaden grupo, conjunto de jugadores, competición o ronda porque no están demostrados por los campos consumidos actualmente.
- EADRIATIC: no se añaden segundos ni conjunto completo de jugadores; la zona horaria es inferida.
- Ningún scraper reconstruye datos anteriores a la ejecución que crea el historial.
- No se guarda una respuesta cruda GT porque no existe en el flujo actual.

## Compatibilidad con TXT

La lógica existente `process()` → `build_df()` → `save_txt()` se conserva. Los nombres, argumentos CLI, columnas, W/D/L, `played`, `stk`, `seq` y `VS RIVALES` no se cambian.

Como comprobación adicional, se ejecutaron el parser heredado y el adaptador nuevo sobre los siete HTML reales disponibles. Ambos identificaron exactamente el mismo número de partidos válidos en cada archivo:

| HTML | Parser TXT | Historial |
|---|---:|---:|
| 20260610 | 292 | 292 |
| 20260611 | 266 | 266 |
| 20260612 | 174 | 174 |
| 20260613 | 246 | 246 |
| 20260617 | 244 | 244 |
| 20260709 | 224 | 224 |
| 20260714 | 94 | 94 |

Esta comprobación fue solo en memoria; no creó ni reconstruyó `match_history.jsonl`.

## Ejemplos de fixtures

Ejemplo GT generado desde el fixture mínimo con ID `123`, kickoff UTC y marcador 2–1:

```json
{"away_score":1,"data_quality":"complete","home_away":"home","home_score":2,"league":"GT","match_id":"gt:123","native_match_id":"123","perspective_id":"gt:123:álex","player":"Álex","player_key":"álex","result":"V","rival":"João","rival_key":"joão","schema_version":1,"source_file":"gt_api:test","source_type":"gt_api","timestamp":"2026-07-14T10:00:15+00:00","timestamp_precision":"second","timestamp_utc":"2026-07-14T10:00:15Z","timezone":"UTC","timezone_inferred":false}
```

Ejemplo EADRIATIC generado desde una estructura mínima derivada del HTML real `/match/44413067.html`:

```json
{"away_score":0,"competition":"INTERNATIONAL","data_quality":"inferred","group_key":"eadriatic:fc26-r475-international:2026-07-13","home_away":"home","home_score":2,"league":"EADRIATIC","match_id":"eadriatic:44413067","native_match_id":"44413067","perspective_id":"eadriatic:44413067:dexter","player":"Dexter","player_key":"dexter","result":"V","rival":"Eric","rival_key":"eric","round":"FC26 R475","schema_version":1,"source_block_order":0,"source_file":"fixture.html","source_row_order":0,"source_type":"eadriatic_html","timestamp":"2026-07-13T23:55+02:00","timestamp_precision":"minute","timestamp_utc":"2026-07-13T21:55Z","timezone":"Europe/Madrid","timezone_inferred":true}
```

## Pruebas ejecutadas

Comando específico:

```text
python -m unittest discover -s tests -p 'test_match_history.py' -v
```

Resultado: 22 pruebas, todas correctas.

Comando de descubrimiento completo:

```text
python -m unittest discover -s tests -v
```

Resultado: 22 pruebas, todas correctas. No existían otras pruebas en `tests/`.

Validación sintáctica:

```text
python -m py_compile match_history.py gtleagues_api.py eadriatic_leagues.py tests\test_match_history.py
```

Resultado: correcto, sin salida ni errores.

## Limitaciones pendientes

- No se ha consultado internet para confirmar campos adicionales o retención histórica de GT.
- No se ha reconstruido el histórico existente.
- La zona EADRIATIC continúa siendo una inferencia que debe confirmarse.
- La precisión al minuto puede dejar empates temporales sin orden real en EADRIATIC; se conservan los órdenes de fuente como desempate futuro.
- El store conserva la primera procedencia de un evento; no mantiene una lista de todas las capturas donde reapareció.
- La estrategia JSONL reescribe el archivo completo de forma atómica. Es adecuada al volumen inicial, pero deberá vigilarse su crecimiento.
- Current Streaks, H2H Last 20, sesiones, asteriscos y coincidencias quedan expresamente fuera de TASK-001.
