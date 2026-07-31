# AUDIT-001 — Historial de partidos y análisis temporal

## 1. Resumen ejecutivo

Esta auditoría se basa exclusivamente en el código y los archivos presentes en el repositorio a 31 de julio de 2026. No se ha consultado la API ni las webs externas y no se ha ejecutado ningún scraper.

El proyecto no conserva actualmente un historial normalizado de partidos individuales. Conserva agregados diarios por jugador en TXT, secuencias de resultados generales y agregados contra rivales. Los scrapers reciben datos más ricos, pero descartan la fecha/hora individual, el identificador del partido y la pertenencia explícita a un grupo al escribir los TXT.

Conclusión resumida:

| Mejora | Viabilidad | Conclusión |
|---|---|---|
| Current Streaks basado en sesiones reales | **Parcialmente viable** | Es viable hacia el futuro si se empieza a persistir cada partido con timestamp y grupo. El histórico completo no puede reconstruirse desde los TXT. GT podría reconstruirse desde la API si esta permite consultar todo el intervalo; eso no puede confirmarse offline. EADRIATIC solo puede reconstruirse con precisión temporal para los siete snapshots HTML conservados. |
| Last 20 y porcentaje reciente H2H | **Parcialmente viable** | El código ya está preparado para acumular secuencias H2H, pero ninguno de los 165 TXT actuales contiene dichas secuencias entre corchetes. Los totales históricos sí existen. Un L20 real solo puede reconstruirse desde fuentes individuales: potencialmente la API de GT y, para EADRIATIC, los siete HTML guardados. Hacia el futuro es plenamente viable. |
| Comparación de partidos coincidentes | **Parcialmente viable** | El algoritmo propuesto es viable con timestamps ordenables. No puede aplicarse correctamente a los TXT actuales porque carecen de hora. Sí puede aplicarse a la porción de EADRIATIC cubierta por HTML; para GT requiere recuperar de nuevo los partidos desde la API o empezar a guardarlos. Las comparaciones entre ligas requieren normalizar zona horaria. |

La recomendación es introducir un historial JSONL canónico y append-safe como capa entre las fuentes y los análisis, manteniendo temporalmente los TXT y `group_analysis.json` como salidas compatibles.

## 2. Estado actual de GT

### 2.1 Fuentes disponibles

El repositorio contiene:

- `gtleagues_api.py`, que consulta `https://api.gtleagues.com/api/fixtures`;
- 105 TXT diarios en `gt/data/`, desde `20260401_player_stats.txt` hasta `20260714_player_stats.txt`;
- nueve CSV derivados en `gt/output/`;
- ningún JSON de respuesta, HTML ni snapshot crudo de GT.

Los CSV de `gt/output/` son agregados de jugadores y rachas. No añaden identidad ni timestamps de partidos.

### 2.2 Datos disponibles durante la descarga

Según el acceso que hace `gtleagues_api.py`, cada objeto recibido de la API contiene al menos:

- `id`: identificador de partido;
- `kickoff`: fecha/hora utilizada para ordenar;
- `participants[]`, con `side` (`home` o `away`) y `participant.player.nickname`;
- `result.stats.home_score` y `result.stats.away_score`.

El script solicita además estados `3,5,4,6`, pagina de 50 en 50 y ordena la consulta por `-kickoff,-matchNr`. No hay una respuesta cruda guardada con la que confirmar otros campos de liga, torneo, ronda o grupo.

El rango diario se construye como medianoche a medianoche en `Europe/Madrid`, se convierte a UTC y se envía con formato `YYYY-MM-DDTHH:MM:SS.000Z`. Por ello existe una definición explícita del día local. El valor real de `kickoff` se usa para ordenar, pero no se guarda, así que no puede confirmarse desde el repositorio si la API devuelve segundos distintos de `00` o precisión superior.

El procesamiento ordena ascendentemente por `m["kickoff"]`. Deduplica por `m["id"]` mediante un conjunto `seen` por jugador. En una ejecución, cada partido físico se procesa una vez y produce dos perspectivas complementarias: V/D o E/E.

### 2.3 Datos persistidos en los TXT

Ejemplo real de `gt/data/20260714_player_stats.txt`:

```text
ESTADÍSTICAS 2026-07-14

player         W   D   L played  stk seq
Crysis         6   3   6     15    2 VDVEDVDEVVDVEDD
```

Y en `VS RIVALES`:

```text
Crysis
Fox: 4 (50.0%/25.0%/25.0%)
Lio: 4 (50.0%/0.0%/50.0%)
```

La secuencia general está en orden cronológico porque el scraper ordena previamente por `kickoff`. No obstante, una letra no se puede vincular de forma inequívoca a un rival, una hora o un ID.

| Dato por partido | Estado en GT | Procedencia o limitación |
|---|---|---|
| Fecha | Derivable solo a nivel de archivo | Nombre/cabecera del TXT; no está asociada a cada letra de la secuencia. Durante scraping se deriva del rango consultado. |
| Hora | Disponible durante scraping, perdida después | `kickoff`; no aparece en TXT/CSV. |
| Timestamp completo | Disponible durante scraping, perdido después | `kickoff`; precisión real no verificable sin respuesta cruda. |
| Zona horaria | Definida para el rango, no persistida por partido | Día local `Europe/Madrid`, consulta convertida a UTC. La zona semántica del `kickoff` devuelto no queda registrada. |
| Jugador y rival | Disponibles durante scraping; agregados en TXT | Nicknames de participantes. El bloque `VS RIVALES` mantiene el rival y totales, pero no cada evento individual. |
| Resultado V/E/D | Disponible y derivado | Se deriva comparando `home_score` y `away_score`; se guarda solo como secuencia del jugador. |
| Marcador | Disponible durante scraping, perdido | `home_score` y `away_score`. |
| Grupo/conjunto | No confirmado | El script no lee ni guarda un campo de grupo. `group_analysis.py` infiere conjuntos a partir de grafos H2H diarios, no de un ID de grupo de la API. |
| ID único | Disponible durante scraping, perdido | `m["id"]`. |
| Liga/competición | No confirmada en respuesta; implícita como GT | La URL identifica la fuente, pero el script no lee ni persiste competición. |
| Orden cronológico | Correcto dentro del TXT, sin timestamps | Orden por `kickoff`; empates exactos quedan sujetos al orden devuelto/estable de Python porque no se usa `matchNr` localmente como desempate. |

### 2.4 Duplicados e identificador estable

- La paginación podría solapar resultados si la fuente cambia mientras se consulta. El `id` evita duplicados dentro del procesamiento diario.
- El mismo partido se refleja en las secuencias de ambos jugadores, pero el TXT no contiene una fila por evento: contiene dos letras agregadas en dos filas de jugador.
- Entre archivos diarios no debería haber solapamiento porque los intervalos UTC son semiabiertos conceptualmente, pero no se conoce si el operador `between` incluye ambos extremos. El ID permitiría resolverlo si se persistiera.
- El identificador canónico preferido es `gt:<id_api>`. No debe sustituirse por un hash mientras el ID nativo exista.
- Para datos heredados sin ID solo podría generarse un hash de `league + timestamp + home + away + score`; los TXT carecen de varios de esos componentes, por lo que no permiten generar un ID histórico fiable.

### 2.5 Reconstrucción posible

Desde los TXT se pueden reconstruir totales diarios y secuencias generales por jugador, pero no partidos individuales completos ni emparejamientos temporales. Una reconstrucción de abril a julio requeriría volver a consultar la API por fecha. El código acepta una fecha por CLI en formato `DDMMYYYY`, pero no se ha verificado si la API conserva todo el intervalo ni si las respuestas históricas son estables.

## 3. Estado actual de EADRIATIC

### 3.1 Fuentes disponibles

El repositorio contiene:

- `eadriatic_leagues.py`, scraper HTTP/BeautifulSoup de LeagueRepublic;
- `repair_eadriatic_day.py`, selector histórico con Playwright;
- 60 TXT desde `20260516_eadriatic_player_stats.txt` hasta `20260714_eadriatic_player_stats.txt`;
- siete HTML descargados: 10, 11, 12, 13 y 17 de junio, 9 y 14 de julio;
- nueve CSV agregados en `eadriatic/output/`.

No existen otros snapshots o formatos crudos de EADRIATIC.

### 3.2 Contenido y pérdida de información en los TXT

Los TXT tienen la misma tabla agregada que GT: jugador, W, D, L, partidos, racha sin empate y secuencia general; después incluyen totales porcentuales contra cada rival.

Los 60 TXT actuales contienen **cero** líneas H2H con secuencia `[VED...]`. Aunque la versión actual de `eadriatic_leagues.py` ya construiría y escribiría esa secuencia, los archivos existentes son anteriores a ese formato o no fueron regenerados. En consecuencia, `group_analysis.py` recupera W/D/L H2H, pero su expresión regular asigna una secuencia vacía.

Existe además una inconsistencia verificable: los 25 archivos cuyos nombres van de `20260516` a `20260609` tienen todos la cabecera `ESTADÍSTICAS 2026-06-09`. El nombre es la única indicación diferenciadora de fecha para esos archivos; la cabecera no la confirma. No es posible demostrar solo con el repositorio si los contenidos corresponden realmente a cada nombre.

Al generar el TXT se pierde:

- `data-match-href`/ID del partido;
- fecha y hora individual;
- marcador;
- orientación home/away;
- encabezado de ronda/competición/grupo;
- asociación evento por evento entre letra, rival y grupo;
- estado jugado/no jugado.

### 3.3 Información conservada en los HTML

Los siete HTML usan la estructura que espera el scraper: filas `tr[data-match-href]`, tres o más `td`, equipos con el formato `Equipo (Jugador)` y marcador en la columna central. Un ejemplo real del snapshot del 14 de julio es:

```html
<span class="fg-heading">FC26 R475(INTERNATIONAL)13.07.2026</span>
<span class="time-heading">00:00</span>
<tr data-match-href="/match/44413067.html">
  ... England (Dexter) ...
  ... 2 - 0 ...
  ... Belgium (Eric) ...
</tr>
```

Los HTML conservan:

- identificador nativo estable aparente, por ejemplo `/match/44413067.html`;
- fecha dentro de `fg-heading`, separada de la hora;
- hora en `time-heading`, con precisión de minutos y sin segundos;
- etiqueta de ronda/competición, por ejemplo `FC26 R475(INTERNATIONAL)`;
- equipo y nickname de ambos participantes;
- marcador, incluido HT cuando está presente;
- orden DOM de grupos, horas y encuentros.

No aparece una zona horaria explícita junto a los partidos. La fecha y la hora están separadas. La suposición `Europe/Madrid` sería una política del proyecto, no un dato probado por estos HTML.

Inventario comprobado:

| Snapshot | Filas con ID | Filas con marcador final | Fechas de grupos presentes |
|---|---:|---:|---|
| 20260610 | 466 | 398 | 09 y 10 de junio |
| 20260611 | 360 | 266 | 10 y 11 de junio |
| 20260612 | 360 | 174 | 11 y 12 de junio |
| 20260613 | 300 | 246 | 12 y 13 de junio |
| 20260617 | 466 | 350 | 16 y 17 de junio |
| 20260709 | 360 | 224 | 8 y 9 de julio |
| 20260714 | 360 | 94 | 13 y 14 de julio |

Las filas sin marcador son fixtures aún no jugados en el momento de captura, no necesariamente corrupción. Las 2.672 apariciones de ID inspeccionadas son únicas entre estos siete archivos; no hay IDs repetidos entre snapshots. Todos los archivos son parseables y comparten los selectores esenciales. Cambian el número de filas, rondas y proporción de resultados completados. No se halló un snapshot estructuralmente incompatible, aunque son capturas parciales tomadas a horas diferentes.

### 3.4 Defecto del parser actual respecto al historial

`parse_matches()` solo lee la fila del partido. No lee `fg-heading` ni `time-heading`, a pesar de estar disponibles en el HTML. También guarda `match_id` únicamente en un conjunto local para deduplicar y después lo descarta. La lista resultante contiene solo `(p1, s1, s2, p2)`.

El orden cronológico no está garantizado globalmente. El código no ordena EADRIATIC; confía en el DOM. Los HTML agrupan por rondas/competiciones, y las horas pueden volver hacia atrás al comenzar otro grupo. Por ejemplo, en el snapshot del 14 de julio aparecen series `00:00, 00:15...` y luego otra serie `00:05, 00:20...`. El orden de append sirve para la presentación de la fuente, pero no equivale necesariamente a una línea temporal global.

### 3.5 Campos reconstruibles

| Dato por partido | TXT | HTML conservado |
|---|---|---|
| Fecha | Solo nombre/cabecera, con inconsistencias | Sí, desde `fg-heading` |
| Hora | No | Sí, `HH:MM`; sin segundos |
| Timestamp | No | Derivable como fecha + hora + zona asumida |
| Jugador/rival | Agregado | Sí |
| Resultado V/E/D | Secuencia agregada | Derivable del marcador para ambas perspectivas |
| Marcador | No | Sí |
| Grupo | Solo inferible por conectividad H2H | Derivable del bloque/ronda y del conjunto de participantes |
| ID | No | Sí, `data-match-href` |
| Orden cronológico | Solo secuencia por jugador | Derivable por timestamp; requiere desempate para misma hora |

El historial individual preciso solo se puede reconstruir para partidos finalizados presentes en esos siete HTML, aproximadamente en 9–13 y 16–17 de junio, y 8–9 y 13–14 de julio. No es una cobertura continua y cada captura puede contener solo parte del segundo día. Los TXT de los demás días no permiten recuperar hora, ID, grupo o correspondencia exacta letra-rival. Una recuperación adicional dependería de que LeagueRepublic permita volver a seleccionar días históricos; `repair_eadriatic_day.py` sugiere que puede hacerlo, pero su disponibilidad y retención no se han verificado.

## 4. Auditoría de Current Streaks

### 4.1 Funcionamiento actual

`web_tracker/generate_site.py`:

1. busca el archivo `*player_stats.txt` de nombre más reciente en cada liga;
2. lee exclusivamente ese archivo;
3. extrae la tabla superior hasta la línea en blanco;
4. toma W, D, L, `played`, `stk` y `seq` ya agregados;
5. recalcula `stk_win` como resultados finales consecutivos distintos de V;
6. recalcula `stk_lose` como resultados finales consecutivos distintos de D;
7. marca como tracked al par `(liga, nombre en minúsculas)`.

No agrupa jugadores en Current Streaks: muestra filas individuales ordenadas por `played`. La agrupación de cinco jugadores de `tracked_players.txt` se usa en `group_analysis.py`, no para separar sesiones en este panel.

### 4.2 Cruces de medianoche y cambios de grupo

GT consulta días civiles de Madrid. Al cambiar de día, el archivo más reciente contiene solo el rango de la nueva fecha; una sesión iniciada antes de medianoche queda cortada.

EADRIATIC tiene un matiz: los HTML observados contienen al inicio rondas del día anterior, por lo que algunos TXT pueden incluir solapamiento. Sin embargo, esa inclusión depende de lo que devuelva la página y no de una regla explícita de sesión. El nombre/cabecera del archivo tampoco identifica la fecha de cada partido. No es una solución fiable al cruce de medianoche.

Si un jugador participa en dos grupos durante el mismo archivo, `process()` acumula todos sus partidos en una sola entrada de `stats[player]`. La secuencia, W/D/L y rachas mezclan las dos sesiones porque no se persiste ni se utiliza grupo, hora o pausa temporal.

### 4.3 Definición técnica propuesta de sesión

Una sesión debería ser una secuencia de partidos que cumpla:

- misma `league`;
- mismo `group_key`, construido a partir del conjunto normalizado de participantes del bloque/grupo;
- timestamps cronológicos, aunque crucen medianoche;
- separación entre eventos consecutivos no superior a `SESSION_IDLE_MINUTES`, configurable;
- cambio de `group_key` implica siempre una sesión nueva;
- si el conjunto de jugadores solo puede conocerse progresivamente, se debe cerrar/reabrir la sesión cuando el conjunto estabilizado cambie, sin fusionar retrospectivamente grupos distintos.

Un valor inicial razonable para `SESSION_IDLE_MINUTES` es 45–60 minutos, pero debe validarse con la cadencia real y dejarse configurable por liga. No se puede fijar empíricamente con los TXT.

Datos mínimos: liga, match_id, ambos jugadores, timestamp comparable con zona, group_key y estado final. Para ordenar empates de minuto también conviene ID/ronda/posición de fuente.

## 5. Auditoría de H2H Betting Alerts

### 5.1 Cálculo actual

`group_analysis.py` lee todos los TXT de una liga. Para cada línea `rival: matches (W%/D%/L%)`, reconstruye enteros mediante redondeo:

- `W = round(matches * W% / 100)`;
- `D = round(matches * D% / 100)`;
- `L = matches - W - D`.

Después suma los valores por jugador/rival. `Win% = W / (W + D + L) * 100`. Una alerta aparece con Win% mínimo 48 %. Se marca `STRONG` desde 50 % y `HIGH` con al menos 20 partidos.

Esta reconstrucción desde porcentajes de una decimal puede diferir del conteo original por redondeos. La fuente canónica futura debería sumar eventos, no porcentajes.

### 5.2 Last 10 actual

El parser acepta opcionalmente una secuencia `[VED...]`; concatena las secuencias por orden lexicográfico de archivo y define `last10 = sequence[-10:]`.

Sin embargo, una búsqueda completa en los 105 TXT de GT y 60 de EADRIATIC encontró cero secuencias H2H entre corchetes. Por tanto, el `group_analysis.json` actual no contiene valores no vacíos de `last10`. La versión actual de ambos scrapers ya escribe el formato nuevo, pero el dataset comprometido no ha sido regenerado después de ese cambio.

No hay evidencia en el repositorio actual para afirmar que GT disponga ya de secuencia H2H histórica persistida. GT sí tiene una vía de reconstrucción potencialmente mejor porque la API entrega partidos individuales y `kickoff`; EADRIATIC solo tiene eventos individuales en los siete HTML.

### 5.3 Last 20, porcentaje y tendencia

Cambiar técnicamente el corte a `sequence[-20:]` es sencillo, pero no genera datos que no existen. Un Last 20 correcto debe obtenerse del historial normalizado, filtrando `(league, player, rival)`, ordenando por timestamp y tomando los últimos 20 eventos finalizados.

Fórmulas propuestas:

```text
Win% histórico = victorias históricas / partidos históricos * 100
Win% L20       = victorias en últimos min(20, N) / min(20, N) * 100
delta          = Win% L20 - Win% histórico
```

Tendencia configurable:

- `UP`: `delta >= +5` puntos porcentuales;
- `DOWN`: `delta <= -5` puntos porcentuales;
- `STABLE`: entre ambos límites.

Debe mostrarse `LOW SAMPLE` si hay menos de 20 partidos recientes. Los 5 puntos son un umbral inicial interpretable, no una conclusión estadística; deberían exponerse como configuración y validarse con backtesting.

## 6. Viabilidad de jugadores seleccionados con `*`

`tracked_players.txt` se parsea en tres sitios:

- `group_analysis.py::load_groups()` usa `line.split("|")` y agrupa cada cinco entradas según el orden global;
- `web_tracker/generate_site.py::load_tracked_players()` usa `split("|", 1)` y guarda `(liga en mayúsculas, jugador en minúsculas)`;
- `build_opportunity_input.py` aplica una lógica equivalente.

Con el parser actual, `Lucas*` sería un nombre literal distinto de `Lucas`, rompería la coincidencia con los datos y contaminaría las agrupaciones.

Propuesta futura: un único parser compartido que, para cada línea no vacía:

1. divida una sola vez por `|`;
2. aplique `strip()` a liga y nombre;
3. detecte únicamente un `*` terminal después de retirar espacios externos;
4. guarde `selected_for_coincidence = True` y elimine ese único sufijo del nombre lógico;
5. rechace nombre vacío o liga desconocida;
6. use una clave `player_key = (league.upper(), casefold(name.strip()))`;
7. conserve `display_name` sin alterar mayúsculas internas.

Las líneas sin asterisco siguen siendo válidas. Nombres iguales en ligas distintas no colisionan. Duplicados de la misma clave deberían deduplicarse conservando `selected=True` si cualquiera de las apariciones tiene `*`, y emitir advertencia. El agrupamiento actual de bloques de cinco también debe hacerse por liga: hoy el acumulador `current` es global y depende de que el archivo esté ordenado en bloques completos; una intercalación de ligas produciría grupos incorrectos.

## 7. Viabilidad del emparejamiento temporal

### 7.1 Regla formal propuesta

Para cada pareja seleccionada A/B:

1. construir dos listas de partidos-perspectiva, ordenadas por `(timestamp, tie_breaker)`;
2. recorrer la unión cronológica;
3. cuando aparezca un evento del jugador X, seleccionar del otro jugador el evento no usado con máximo timestamp tal que `timestamp_otro <= timestamp_actual`;
4. registrar `delta_minutes = (timestamp_actual - timestamp_otro) / 60`;
5. marcar ambos eventos usados dentro de esa comparación A/B;
6. no compartir el estado de “usado” entre comparaciones diferentes, porque cada pareja es un análisis independiente.

Esto reproduce el ejemplo: A 09:55 se empareja con B 10:00 cuando se procesa B 10:00; A 08:00 y 08:20 quedan sin usar.

### 7.2 Disponibilidad actual

- **GT TXT:** no viable temporalmente; no hay horas ni IDs. Potencialmente viable tras reconsulta de la API.
- **EADRIATIC TXT:** no viable temporalmente.
- **EADRIATIC HTML:** viable para partidos finalizados en los siete snapshots, con precisión de minuto y zona horaria asumida/documentada.
- **Futuro JSONL:** plenamente viable si el timestamp y la identidad se persisten.

### 7.3 Ambigüedades

- Misma hora y varios partidos del mismo jugador: al no haber segundos en EADRIATIC, hace falta un desempate determinista (`source_block_order`, `source_row_order`, `match_id`). El orden no prueba cuál ocurrió primero; el resultado debe marcar precisión `minute`.
- Igual timestamp entre A y B: la regla permite igualdad, pero si hay varias opciones iguales debe elegirse por tie-breaker estable y documentado.
- Cruce de medianoche: queda resuelto usando timestamp con fecha, no `HH:MM` aislado.
- Zona horaria: GT se consulta respecto a `Europe/Madrid`; EADRIATIC no declara zona. Comparar ligas exige una política explícita, inicialmente `Europe/Madrid` para EADRIATIC con `timezone_inferred=true`.
- Duplicados: se deben deduplicar antes de emparejar, preferentemente por ID nativo.
- Partido directo A contra B: el mismo partido físico aparece en ambas listas-perspectiva con el mismo `match_id`. Debe decidirse si se permite emparejar consigo mismo. Recomendación: excluir `match_id` idénticos, porque no son dos oportunidades temporales independientes.
- Cruce entre ligas: es computable en UTC, pero su sentido analítico es una decisión de producto pendiente. Los nombres deben seguir identificados por liga.

## 8. Propuesta de modelo de datos

### 8.1 Formato

Se recomienda JSONL UTF-8, un objeto por **perspectiva de jugador**. Es legible, append-friendly, fácil de procesar en streaming y admite campos opcionales. Un partido físico genera normalmente dos registros con el mismo `match_id` y `perspective_id` diferentes.

Ejemplo de esquema propuesto, ilustrativo y no creado:

```json
{"schema_version":1,"league":"EADRIATIC","player":"Dexter","player_key":"dexter","rival":"Eric","rival_key":"eric","result":"V","home_away":"home","home_score":2,"away_score":0,"match_date":"2026-07-13","match_time":"00:00","timestamp":"2026-07-13T00:00:00+02:00","timestamp_utc":"2026-07-12T22:00:00Z","timestamp_precision":"minute","timezone":"Europe/Madrid","timezone_inferred":true,"group_key":"eadriatic:fc26-r475-international:2026-07-13","match_id":"eadriatic:44413067","perspective_id":"eadriatic:44413067:dexter","source_file":"eadriatic/data/20260714_eadriatic_downloaded.html","source_type":"html_snapshot","collected_at":"2026-07-14T06:15:13+02:00"}
```

Los valores proceden del ejemplo real salvo los campos normalizados/inferidos indicados por el propio esquema. El `collected_at` futuro debe venir del momento de descarga; para migración solo puede usarse la mtime como aproximación y marcarse como inferida.

### 8.2 Campos obligatorios

- `schema_version` entero;
- `league`: enum `GT`/`EADRIATIC`;
- `player`, `player_key`, `rival`, `rival_key`;
- `result`: enum `V`/`E`/`D`;
- `match_id` y `perspective_id`;
- `source_file` y `source_type`;
- `collected_at` cuando se conozca, o `null` más flag de calidad;
- `data_quality`: `complete`, `partial` o `inferred`.

Para análisis temporal se consideran además obligatorios funcionales `timestamp`, `timezone` y `timestamp_precision`; un registro migrado que no los tenga puede conservarse como parcial, pero queda excluido de sesiones y coincidencias.

### 8.3 Campos opcionales

- `match_date`, `match_time` cuando solo haya una parte;
- `timestamp`, `timestamp_utc`, `timezone`;
- `timezone_inferred`;
- `home_away`, `home_score`, `away_score`;
- `competition`, `round`, `group_key`, `group_players`;
- `native_match_id`;
- `source_row_order`, `source_block_order`;
- `timestamp_precision` (`second`, `minute`, `date`, `unknown`);
- `migration_notes` y `raw_label`.

Timestamp exacto: ISO 8601/RFC 3339 con offset, `YYYY-MM-DDTHH:MM:SS±HH:MM`, y copia UTC terminada en `Z`. Nunca se debe guardar un datetime naive como completo.

### 8.4 Nombres e identidad

- `display_name`: texto limpio con `strip()` y espacios internos colapsados solo si se demuestra seguro;
- `player_key`: Unicode normalizado (NFKC), `casefold()` y espacios externos eliminados;
- la identidad completa es `(league, player_key)`;
- no eliminar tildes ni signos internos automáticamente;
- mantener una tabla opcional de alias explícitos si la fuente cambia un nickname.

### 8.5 IDs y deduplicación

- GT: `match_id = "gt:" + native_id`.
- EADRIATIC: extraer el número de `/match/<id>.html` y usar `eadriatic:<id>`.
- Dos perspectivas comparten `match_id`; `perspective_id = match_id + ":" + player_key`.
- La clave primaria lógica del JSONL es `perspective_id`.
- Si no hay ID nativo pero hay evento completo, fallback SHA-256 versionado de liga, timestamp UTC, jugadores home/away y marcador. Marcar `match_id_inferred=true`.
- No generar un supuesto match_id desde un TXT agregado: no posee entropía suficiente.
- En conflicto del mismo ID, elegir el registro con estado final/mayor completitud y registrar el conflicto; no sobrescribir silenciosamente.

### 8.6 Migración incremental e idempotente

1. Parsear cada fuente a registros candidatos sin escribir directamente al archivo canónico.
2. Validar esquema y relaciones inversas V↔D, E↔E.
3. Cargar un índice de `perspective_id` existente.
4. Insertar nuevos; actualizar solo si aumenta la completitud mediante una reescritura atómica del JSONL.
5. Guardar un manifiesto por fuente con hash, tamaño, parser_version, fecha de proceso y conteos.
6. Regenerar vistas derivadas desde el canónico.

Para el volumen actual JSONL es suficiente. Si el crecimiento hace costosa la reescritura, SQLite sería una evolución razonable, pero añade binarios y peor revisión en Git; no es necesaria inicialmente.

## 9. Arquitectura recomendada

```text
GT API ───────────────┐
                     ├─> adaptadores de fuente ─> validación/deduplicación
EADRIATIC HTML ───────┘                              │
                                                    v
                                      historial JSONL canónico
                                                    │
                    ┌───────────────────────────────┼──────────────────────┐
                    v                               v                      v
             agregador H2H                 constructor de sesiones   coincidencias
                    │                               │                      │
                    └───────────────────────────────┼──────────────────────┘
                                                    v
                                      payload web versionado/JSON
                                                    v
                                      web_tracker/generate_site.py
```

Los scrapers deberían producir eventos normalizados y, durante una transición, seguir produciendo los TXT actuales. Los analizadores deben leer el historial, no reparsear porcentajes redondeados. El generador web debería consumir un payload estable sin conocer particularidades de GT o EADRIATIC.

## 10. Archivos afectados

### 10.1 Archivos a crear en tareas posteriores

| Archivo propuesto | Responsabilidad |
|---|---|
| `match_history/schema.py` | Validación, enums, normalización de nombres y serialización. |
| `match_history/store.py` | Lectura/escritura JSONL, índice, merge idempotente y conflictos. |
| `match_history/gt_adapter.py` | Convertir respuestas GT a dos perspectivas normalizadas. |
| `match_history/eadriatic_adapter.py` | Leer fecha, hora, grupo, ID y filas de HTML. |
| `match_history/sessions.py` | Construir sesiones por liga, grupo e inactividad. |
| `match_history/coincidences.py` | Generar combinaciones y emparejamientos temporales. |
| `match_history/tracked_players.py` | Parser único de `tracked_players.txt`, incluido `*`. |
| `data/matches.jsonl` | Historial canónico; no debe crearse hasta aprobar la implementación. |
| `data/match_sources.jsonl` | Manifiesto de fuentes procesadas y hashes. |
| `tests/test_match_history_*.py` | Pruebas unitarias, fixtures y regresión. |

La ubicación exacta puede ajustarse a un paquete con otro nombre; lo esencial es no duplicar parsers.

### 10.2 Archivos a modificar posteriormente

| Archivo | Cambio futuro |
|---|---|
| `gtleagues_api.py` | Entregar/persistir eventos con ID, kickoff, marcador y metadatos disponibles antes de agregarlos. Añadir timeouts y manejo explícito de errores. |
| `eadriatic_leagues.py` | Parsear encabezados de grupo, fecha, hora e ID; ordenar cronológicamente y persistir eventos finalizados. |
| `repair_eadriatic_day.py` | Guardar también el HTML seleccionado y usar rutas portables; ejecutar navegador headless en automatización. |
| `group_analysis.py` | Leer eventos para H2H/L20 y utilizar parser compartido de tracked players. |
| `web_tracker/generate_site.py` | Consumir sesiones, L20/trend y coincidencias desde un payload derivado. |
| `tracked_players.txt` | Permitir `*` terminal según la nueva gramática. |
| `.github/workflows/update.yml` | Ejecutar ingestión/validación/análisis en orden y evitar `git add .`; controlar crecimiento y concurrencia. |
| `requirements.txt` | Añadir solo dependencias que finalmente requiera la validación/pruebas. |

### 10.3 Archivos que pueden mantenerse sin cambios durante la transición

- Los 165 TXT históricos y los CSV actuales deben conservarse como evidencia y compatibilidad; no conviene reescribirlos automáticamente.
- `analyze_gt.py`, `analyze_eadriatic.py` y `build_opportunity_input.py` pueden mantenerse inicialmente, aunque después deberían migrar al historial canónico.
- `docs/index.html` seguirá siendo una salida generada; cambiará solo cuando se integre la nueva interfaz.
- `group_analysis.json` puede mantener compatibilidad de esquema añadiendo campos versionados antes de retirar los antiguos.

## 11. Riesgos y limitaciones

| Riesgo | Nivel | Impacto y mitigación |
|---|---|---|
| Historial individual imposible de recuperar desde TXT | **Alto** | Horas, IDs y asociación exacta con rivales ya se perdieron. No inventar eventos; marcar cobertura parcial y reconsultar fuentes si es posible. |
| Cobertura EADRIATIC discontinua | **Alto** | Solo siete HTML; los L20 y sesiones históricas serían sesgados si se presentan como completos. Mostrar rango/cobertura. |
| Cabeceras erróneas en 25 TXT EADRIATIC | **Alto** | El nombre y la cabecera discrepan. No confiar en la cabecera para migración y validar contra fuente externa antes de atribuir fecha. |
| Timestamps EADRIATIC sin segundos | **Medio** | Ambigüedad dentro del minuto. Conservar precisión y tie-breaker de fuente, sin fingir segundos. |
| Zona horaria EADRIATIC no declarada | **Alto** para cruces de liga | Una hora inferida puede desplazar emparejamientos. Hacer configurable la zona y conservar flag de inferencia. |
| Secuencias H2H ausentes en todos los TXT | **Alto** | Last 10/20 actual no tiene base secuencial. Reconstruir desde eventos, no desde totales. |
| Redondeo al reconstruir W/D/L H2H | **Medio** | Puede alterar conteos. El historial futuro debe sumar eventos exactos. |
| Duplicados y fronteras diarias GT | **Medio** | Persistir ID nativo y deduplicar globalmente, no solo por ejecución. |
| Fixtures no finalizados en HTML | **Bajo** | Entre 54 y 266 filas sin marcador por snapshot. Filtrar estado final y permitir posterior actualización. |
| Cambio de HTML/API externa | **Alto** | Selectores/campos pueden romperse silenciosamente por los `except:` amplios. Validar conteos, esquema y muestras; fallar explícitamente. |
| Coste de procesar HTML | **Bajo** actualmente | Siete archivos de 0,63–0,99 MB son pequeños. Usar manifiesto/hash para no reparsear; el riesgo crece linealmente. |
| Crecimiento del JSONL en Git | **Medio** | Dos perspectivas por partido y ejecución cada 15 minutos. Deduplicar, no guardar capturas redundantes y evaluar partición mensual/SQLite fuera de Git. |
| Carreras del workflow | **Medio** | Ejecución cada 15 minutos sin `concurrency`; una ejecución lenta puede solaparse y causar conflictos de push. Añadir grupo de concurrencia futuro. |
| `git add .` en automatización | **Medio** | Puede publicar artefactos inesperados. Añadir rutas explícitas. |
| Rutas Windows en reparación | **Medio** | `repair_eadriatic_day.py` no es portable a Ubuntu y usa navegador visible. Usar `Path(BASE)` y headless. |
| Regresiones en web | **Medio** | Cambios de payload pueden romper el HTML. Mantener schema_version, fixtures dorados y pruebas de render. |
| Orden de igual timestamp | **Medio** | Puede cambiar coincidencias. Definir desempate estable y exponer baja precisión. |
| Alias/cambios de nickname | **Medio** | Fragmentan historiales. Mantener alias explícitos, nunca fuzzy matching silencioso. |
| Emparejamiento del mismo partido directo | **Medio** | Podría inflar coincidencias. Excluir match_id idéntico salvo decisión contraria. |

## 12. Preguntas abiertas

1. ¿La API de GT permite recuperar todos los días desde el 1 de abril y conserva IDs/kickoff estables?
2. ¿Qué precisión y offset exactos devuelve `kickoff` en GT?
3. ¿Qué campos de competición, ronda o grupo incluye realmente la respuesta GT además de los usados por el código?
4. ¿LeagueRepublic publica las horas EADRIATIC en `Europe/Madrid`, en otra zona o en la zona del navegador?
5. ¿Puede `repair_eadriatic_day.py` recuperar todavía todos los días desde el 16 de mayo y se obtienen partidos finalizados completos al esperar hasta el cierre?
6. ¿Los nombres de los primeros 25 TXT EADRIATIC representan fechas reales a pesar de la cabecera repetida del 9 de junio?
7. ¿Qué pausa máxima define operativamente una sesión para cada liga: 45, 60 u otro número de minutos?
8. ¿El conjunto de grupo debe ser exactamente igual o se tolera una sustitución temporal?
9. ¿Las coincidencias entre ligas tienen valor de producto o deben generarse solo dentro de la misma liga?
10. ¿Un enfrentamiento directo entre dos seleccionados debe excluirse del emparejamiento consigo mismo?
11. ¿Cómo se presentan L20 y Trend cuando existen menos de 20 observaciones o cobertura histórica incompleta?
12. ¿Debe el repositorio seguir versionando cada actualización de datos cada 15 minutos o conviene almacenamiento externo?

## 13. Plan de implementación por tareas

1. **Contrato y pruebas del modelo.** Definir schema_version, campos, flags de precisión/calidad, claves e invariantes; crear fixtures reales anonimizados solo si fuera necesario y pruebas de validación.
2. **Parser compartido de jugadores.** Centralizar `tracked_players.txt`, añadir `*`, validación, deduplicación y pruebas, manteniendo idéntico comportamiento para líneas actuales.
3. **Adaptador GT.** Capturar objetos de API, confirmar esquema real, transformar a dos perspectivas y validar zona/precisión sin retirar el TXT.
4. **Adaptador EADRIATIC.** Parsear bloques, fecha, hora, ID, jugadores y marcador; incorporar orden de fuente y flags de zona inferida.
5. **Store idempotente.** Implementar JSONL, manifiesto de fuentes, deduplicación, resolución de registros parciales y escritura atómica.
6. **Reconstrucción GT.** Ejecutar por día en modo auditado, comparar totales por archivo contra TXT y documentar fechas no recuperables.
7. **Reconstrucción EADRIATIC.** Ingerir primero los siete HTML, comparar conteos/resultados con TXT donde sea posible y después evaluar recuperación externa de días faltantes.
8. **H2H Last 20.** Calcular W/D/L exactos, `last20`, Win% L20, delta, Trend y cobertura; añadir pruebas de orden y muestras pequeñas.
9. **Sesiones.** Implementar agrupación por liga/group_key/inactividad, cruces de medianoche, cambios de grupo y precisión temporal; validar umbral con datos observados.
10. **Coincidencias.** Generar combinaciones marcadas con `*`, aplicar predecessor matching sin reutilización, excluir futuros y conservar delta/tie-breaker.
11. **Payload web compatible.** Extender schema_version de `group_analysis.json` o crear una salida derivada, manteniendo campos actuales durante transición.
12. **Interfaz.** Añadir Current Streaks por sesión, H2H L20/Trend y panel de coincidencias en `generate_site.py`.
13. **Workflow.** Ordenar ingestión→validación→análisis→web, añadir concurrencia, caché/manifiesto y `git add` explícito.
14. **Validación de regresión.** Comparar totales actuales, snapshots HTML renderizados, tiempos de ejecución, tamaño de datos y comportamiento ante fuentes incompletas.

## 14. Conclusión

### Current Streaks basado en sesiones reales — parcialmente viable

Los algoritmos son sencillos, pero los TXT actuales no tienen timestamps ni grupos por partido. Es viable para datos futuros y para la pequeña cobertura HTML de EADRIATIC; el histórico GT depende de la capacidad de reconsulta de la API. No debe migrarse fingiendo sesiones a partir de secuencias diarias.

### Last 20 histórico y porcentaje reciente H2H — parcialmente viable

El código tiene soporte estructural reciente para secuencias, pero los 165 TXT reales carecen de ellas. Los totales históricos sirven para Win% global, no para ordenar los últimos 20. Es viable tras reconstruir eventos individuales o acumularlos desde ahora, con cobertura explícita.

### Partidos coincidentes entre seleccionados — parcialmente viable

La regla es implementable y determinista si existe timestamp. EADRIATIC permite una reconstrucción parcial al minuto desde siete HTML. GT y el resto de EADRIATIC no pueden calcularse desde los agregados guardados. Los cruces entre ligas necesitan resolver primero zona horaria, precisión y política sobre partidos directos.

La arquitectura propuesta permite implementar las tres mejoras sin romper inmediatamente las salidas actuales, pero la calidad del resultado histórico estará limitada por la recuperación real de las fuentes. La prioridad debe ser dejar de perder ID, timestamp y grupo en nuevas ejecuciones antes de ampliar la interfaz.
