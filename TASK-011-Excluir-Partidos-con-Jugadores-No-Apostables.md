# TASK-011 — Excluir partidos contra jugadores no apostables de toda la capa operativa

## Contexto

El marcador `*` en `tracked_players.txt` representa un jugador real del grupo que sigue existiendo en el histórico bruto, mantiene su posición y conserva sus partidos para reconstrucción y auditoría, pero no está disponible para apostar.

Se ha detectado que los partidos disputados **contra** jugadores marcados con `*` siguen contabilizándose en:

- Current Streaks Legacy
- Current Streaks V2
- indicadores verde/rojo
- selección automática
- Coincident Matches
- H2H Betting Alerts

Eso es incorrecto.

## Regla funcional definitiva

Cualquier partido en el que participe un jugador marcado con `*` debe conservarse en el histórico bruto, pero quedar excluido de toda la capa operativa.

Ejemplo:

```text
GT|Lucas
GT|Fox*
```

Para un partido:

```text
Lucas vs Fox
```

el partido:

- permanece en `match_history.jsonl`;
- puede utilizarse para auditoría o reconstrucción histórica;
- no cuenta para las estadísticas operativas de Lucas;
- no cuenta para las estadísticas operativas de Fox;
- no genera señales;
- no aparece en Coincident Matches;
- no afecta a porcentajes, indicadores, Last 10 o rachas operativas.

## Objetivo

Crear una regla operativa común:

```python
player_identity not in excluded_player_keys
and rival_identity not in excluded_player_keys
```

La identidad debe ser siempre:

```text
league + player_key
```

## 1. Fuente canónica

Usar exclusivamente:

```python
load_tracked_players(...)
excluded_player_keys(...)
```

No crear parsers manuales ni buscar asteriscos en nombres normalizados.

## 2. Filtro operativo común

Crear una función reutilizable, por ejemplo:

```python
is_operational_record(record, excluded_keys) -> bool
```

Debe comprobar:

- registro válido;
- liga válida;
- `player_key` válido;
- `rival_key` válido;
- jugador principal no excluido;
- rival no excluido.

Identidades:

```python
league = record["league"].strip().upper()
player_identity = (league, record["player_key"])
rival_identity = (league, record["rival_key"])
```

No modificar el registro original.

## 3. Current Streaks V2

Filtrar antes de calcular:

- W
- D
- L
- Played
- porcentajes
- sequence
- Last 10
- racha
- indicador
- selección automática

Un partido contra un rival marcado con `*` no debe contar.

No modificar la ventana de ocho horas.

## 4. Selección automática

La selección automática debe calcularse únicamente con el snapshot filtrado.

Los partidos contra jugadores `*`:

- no ayudan a alcanzar el mínimo de 5 partidos;
- no cambian porcentajes;
- no cambian indicadores;
- no pueden hacer entrar al jugador entre los 8 candidatos.

Mantener:

```python
MAX_AUTOMATIC_CANDIDATES = 8
```

## 5. Coincident Matches

Excluir antes de construir historiales y emparejar cualquier evento donde:

- el jugador principal esté excluido;
- el rival esté excluido.

No cambiar:

- gap máximo de 30 minutos;
- ventana de ocho horas;
- no reutilización;
- orden cronológico;
- confirmaciones.

## 6. H2H Betting Alerts

Excluir cualquier alerta donde:

```text
player está excluido
o
rival está excluido
```

No debe aparecer ni como principal ni como rival.

Mantener:

- umbrales 48/50;
- mínimo de muestra;
- Last 20;
- Trend;
- Sample.

## 7. Current Streaks Legacy

Legacy usa TXT diarios con totales ya agregados y no permite restar de forma fiable partidos contra rivales excluidos.

Aplicar por orden de preferencia:

### Opción preferida

Reconstruir los valores visibles de Legacy para jugadores tracked usando perspectivas operativas del JSONL y el mismo filtro.

Mantener el nombre visual `Current Streaks — Legacy` durante la comparación.

### Opción alternativa

Si reconstruir Legacy desde JSONL implica alto riesgo:

- mantener Legacy sin filtrar;
- mostrar una advertencia visible:
  `Legacy totals include matches against excluded players.`
- no usar Legacy para indicadores o decisiones operativas;
- documentar la limitación.

No hacer restas aproximadas.

## 8. Group Analysis

Los jugadores marcados con `*` siguen perteneciendo al grupo y conservan su posición.

No eliminar su identidad ni sus partidos del histórico bruto.

Sin embargo, cualquier salida operativa debe ignorar enfrentamientos donde participe un excluido.

Revisar especialmente:

- Betting Suggestion
- rankings operativos
- H2H Betting Alerts

Documentar qué cálculos siguen siendo históricos y cuáles son operativos.

## 9. Histórico bruto

No modificar manualmente:

```text
gt/data/match_history.jsonl
eadriatic/data/match_history.jsonl
```

No eliminar registros ni impedir que los scrapers los persistan.

La exclusión es solo de lectura y cálculo operativo.

## 10. Carga eficiente

En `generate_site.py`:

- cargar `tracked_players.txt` una vez;
- obtener `excluded_keys` una vez;
- cargar JSONL una vez;
- reutilizar el conjunto en V2, selección automática, Coincident Matches, H2H y Legacy si se reconstruye.

## 11. Compatibilidad

Mantener firmas existentes cuando sea razonable.

Si se añade:

```python
excluded_keys=None
```

debe tener un valor seguro por defecto.

Actualizar pruebas que contradigan la nueva regla.

## 12. Pruebas obligatorias del filtro

Cubrir:

1. normal contra normal → incluido;
2. excluido contra normal → excluido;
3. normal contra excluido → excluido;
4. ambos excluidos → excluido;
5. mismo nombre en distintas ligas;
6. exclusión solo en una liga;
7. Unicode normalizado;
8. falta `rival_key`;
9. falta `player_key`;
10. inmutabilidad;
11. conjunto vacío;
12. identidad por liga + player_key.

## 13. Pruebas de V2

Cubrir:

1. 6 partidos, 2 contra rival excluido → Played = 4;
2. W/D/L recalculados;
3. porcentajes recalculados;
4. Last 10 filtrado;
5. racha filtrada;
6. indicador puede cambiar;
7. no cuenta para mínimo 5;
8. no entra en selección si queda con 4;
9. cruce de medianoche;
10. ventana de ocho horas intacta.

## 14. Pruebas de Coincident Matches

Cubrir:

1. evento contra rival normal disponible;
2. evento contra rival excluido descartado;
3. descarte en ambos lados;
4. pareja conserva eventos restantes;
5. no genera Confirmation con excluidos;
6. rival excluido no aparece;
7. límite 8 intacto;
8. contadores coherentes;
9. jugador `*` nunca candidato;
10. ninguna fila contiene rival excluido.

## 15. Pruebas de Betting Alerts

Cubrir:

1. normal/normal posible;
2. principal excluido descartado;
3. rival excluido descartado;
4. ambos excluidos descartados;
5. histórico bruto intacto;
6. Last 20 y Trend conservados;
7. misma identidad nominal en distintas ligas;
8. umbrales intactos.

## 16. Pruebas de Legacy

Si se reconstruye desde JSONL:

- excluir partidos contra excluidos;
- W/D/L correctos;
- jugador excluido ausente;
- HTML estable;
- sin segunda carga del historial.

Si se mantiene sin filtrar:

- advertencia visible;
- no se usa para indicadores operativos;
- limitación documentada.

## 17. Validación real obligatoria

Usar temporalmente:

```text
GT|Lucas
GT|Fox*
GT|Kratos
GT|Furious
GT|Vendetta
```

Elegir un jugador con partidos contra Fox y comparar:

```text
Jugador:
Partidos JSONL totales:
Partidos contra Fox:
Partidos operativos esperados:
Current Streaks Legacy:
Current Streaks V2:
Selección automática:
Coincident Matches:
Betting Alerts:
```

Confirmar que esos partidos:

- siguen en JSONL;
- no cuentan en V2;
- no generan coincidencias;
- no aparecen en Betting Alerts;
- no afectan al indicador;
- no ayudan a alcanzar el mínimo de 5.

Restaurar `tracked_players.txt`.

## 18. Archivos a revisar

```text
selected_players.py
current_streaks_v2.py
coincident_matches.py
group_analysis.py
web_tracker/generate_site.py
build_opportunity_input.py
tests/
```

No modificar salvo razón imprescindible:

```text
gtleagues_api.py
eadriatic_leagues.py
match_history.py
history_query.py
historical_analysis.py
temporal_analysis.py
h2h_analysis.py
repair_eadriatic_day.py
```

## 19. Validación técnica

```text
python -m unittest discover -s tests -v
python -m py_compile selected_players.py current_streaks_v2.py coincident_matches.py group_analysis.py build_opportunity_input.py web_tracker/generate_site.py
git diff --check
git diff --stat
git status --short
```

Ejecutar también:

```text
python group_analysis.py ALL
python web_tracker/generate_site.py
```

## 20. Criterios de aceptación

TASK-011 queda aprobada cuando:

1. Los jugadores `*` siguen en el histórico bruto.
2. Sus partidos no cuentan operativamente.
3. Los partidos de jugadores normales contra rivales `*` tampoco cuentan.
4. V2 recalcula correctamente todas sus métricas.
5. La selección automática usa solo partidos operativos.
6. Coincident Matches descarta esos eventos.
7. Betting Alerts descarta jugador o rival excluido.
8. Legacy se reconstruye correctamente o muestra limitación explícita.
9. Group Analysis conserva la posición del jugador marcado.
10. Los JSONL no se alteran.
11. No se modifican scrapers.
12. Las pruebas pasan.
13. La validación real confirma el comportamiento.

## 21. Informe final

Responder con:

- Causa raíz.
- Regla operativa implementada.
- Archivos creados.
- Archivos modificados.
- Filtro común.
- Current Streaks Legacy.
- Current Streaks V2.
- Selección automática.
- Coincident Matches.
- H2H Betting Alerts.
- Group Analysis.
- Pruebas añadidas.
- Resultado de la suite.
- Validación real.
- Estado final de tracked_players.txt.
- `git diff --stat`.
- `git status --short`.
- Desviaciones.

## Restricciones

- No eliminar registros del JSONL.
- No editar JSONL manualmente.
- No modificar scrapers.
- No cambiar la ventana de ocho horas.
- No cambiar el límite de ocho candidatos.
- No cambiar el mínimo de cinco partidos.
- No cambiar umbrales H2H.
- No hacer commit.
- No hacer push.
