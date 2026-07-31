# TASK-002 — Historical Reconstruction Engine

## Objetivo

TASK-002 crea el primer motor de estadísticas históricas basado exclusivamente en las perspectivas normalizadas de `match_history.jsonl` y la capa de consulta de `history_query.py`.

El motor no modifica historiales, no escribe salidas y no está integrado con la web.

## Archivos creados

- `historical_analysis.py`: cálculos puros y función de carga inicial.
- `tests/test_historical_analysis.py`: 16 pruebas offline.
- `TASK-002-Historical-Reconstruction-Engine.md`: este documento.

No se modificó ningún archivo existente.

## API pública

```python
from historical_analysis import (
    empty_player_stats,
    calculate_player_stats,
    calculate_historical_stats,
    load_historical_stats,
)
```

### `empty_player_stats(player, league=None)`

Devuelve el contrato completo con contadores y porcentajes a cero, rachas vacías y fechas `None`.

### `calculate_player_stats(records, player, league=None)`

Calcula las estadísticas de una identidad concreta. Usa `history_query.player_history`, por lo que:

- solo cuenta perspectivas propias del jugador;
- normaliza el nombre mediante las reglas de TASK-001;
- permite restringir por liga;
- procesa los registros en orden cronológico determinista;
- no modifica la entrada.

Solo los resultados `V`, `E` y `D` se consideran partidos válidos.

### `calculate_historical_stats(records, league=None)`

Calcula una fila para cada identidad `(league, player_key)`. Un nickname idéntico en GT y EADRIATIC genera dos filas independientes. El resultado se ordena por liga y nombre normalizado.

Puede limitarse a una liga sin distinguir mayúsculas ni espacios exteriores.

### `load_historical_stats(gt_path=..., eadriatic_path=..., league=None)`

Es el único punto de carga. Reutiliza `history_query.load_all_history` y pasa los registros combinados al motor puro. No abre directamente los JSONL.

## Estadísticas implementadas

Cada fila contiene:

| Campo | Definición |
|---|---|
| `league` | Liga normalizada en mayúsculas. |
| `player` | Nombre visible más reciente dentro de la selección cronológica. |
| `played` | Número de perspectivas válidas del jugador. |
| `wins` | Resultados `V`. |
| `draws` | Resultados `E`. |
| `losses` | Resultados `D`. |
| `win_pct` | `wins / played * 100`, redondeado a dos decimales. |
| `draw_pct` | `draws / played * 100`, redondeado a dos decimales. |
| `loss_pct` | `losses / played * 100`, redondeado a dos decimales. |
| `current_streak_result` | Resultado al final de la secuencia: `V`, `E`, `D` o `None`. |
| `current_streak` | Número de resultados iguales consecutivos al final. |
| `best_win_streak` | Máximo número de `V` consecutivas. |
| `best_loss_streak` | Máximo número de `D` consecutivas. |
| `first_match_date` | Primera fecha UTC con formato `YYYY-MM-DD`. |
| `last_match_date` | Última fecha UTC con formato `YYYY-MM-DD`. |

## Definición de racha actual

“Racha actual” se interpreta como la longitud del mismo resultado que cierra el historial cronológico. Ejemplos:

- `VVV` → resultado `V`, racha 3;
- `VDD` → resultado `D`, racha 2;
- `VEE` → resultado `E`, racha 2.

Se expone también `current_streak_result` para que el entero no sea ambiguo. Esta definición no es la futura sesión de Current Streaks ni una racha sin empates.

## Orden y fechas

La selección y el orden reutilizan `history_query`. La fecha se obtiene primero de `timestamp_utc` y, si no existe o es inválido, de `timestamp`.

- Sufijo `Z`: UTC.
- Timestamp con offset: convertido a UTC.
- Timestamp naive heredado: interpretado como UTC, en consonancia con TASK-001.5.
- Sin fecha válida: el partido sigue contando en W/E/D y rachas, pero no contribuye a `first_match_date` o `last_match_date`.

## Jugadores sin partidos

`calculate_player_stats([], "Nobody", league="GT")` devuelve una fila estable:

```python
{
    "league": "GT",
    "player": "Nobody",
    "played": 0,
    "wins": 0,
    "draws": 0,
    "losses": 0,
    "win_pct": 0.0,
    "draw_pct": 0.0,
    "loss_pct": 0.0,
    "current_streak_result": None,
    "current_streak": 0,
    "best_win_streak": 0,
    "best_loss_streak": 0,
    "first_match_date": None,
    "last_match_date": None,
}
```

`calculate_historical_stats([])` devuelve `[]`, porque no existe ninguna identidad que enumerar.

## Ejemplos

Un jugador:

```python
from history_query import load_all_history
from historical_analysis import calculate_player_stats

records = load_all_history()
david = calculate_player_stats(records, "David", league="GT")
```

Todos los jugadores de ambas ligas:

```python
from historical_analysis import load_historical_stats

rows = load_historical_stats()
```

Solo EADRIATIC:

```python
eadriatic_rows = load_historical_stats(league="EADRIATIC")
```

## Pruebas añadidas

Las 16 pruebas específicas cubren:

- totales y porcentajes;
- historial vacío;
- solo victorias;
- solo derrotas;
- empates;
- racha actual y mejores rachas;
- entrada desordenada;
- exclusión de perspectivas ajenas;
- resultados inválidos;
- timestamps ausentes;
- separación de ligas;
- filtro por liga;
- varios jugadores;
- carga combinada GT + EADRIATIC;
- archivo de una liga inexistente.

## Exclusiones

TASK-002 no incluye:

- escritura de CSV, JSON o HTML;
- modificación o reparación de JSONL;
- cambios en scrapers o persistencia;
- integración visual;
- Current Streaks por sesiones;
- Last 20, tendencias o alertas H2H;
- estrategias de apuestas.

## Validación

```text
python -m unittest discover -s tests -v
python -m py_compile historical_analysis.py tests/test_historical_analysis.py
git diff --check
```
