# TASK-004 — H2H Historical and Recent Trend Analysis

## Propósito

TASK-004 crea la capa H2H canónica a partir de perspectivas individuales normalizadas. Calcula totales históricos exactos, secuencia completa, Last N —20 por defecto—, comparación reciente/histórica, tendencia y estado de muestra.

El módulo es puro, determinista, direccional y de solo lectura. No sustituye todavía el H2H basado en TXT de `group_analysis.py` ni está integrado con la web.

## Archivos creados

- `h2h_analysis.py`;
- `tests/test_h2h_analysis.py`;
- `TASK-004-H2H-Historical-and-Recent-Trend-Analysis.md`.

No se modificó ningún archivo existente.

## Arquitectura

```text
match_history.jsonl
        │
        v
history_query.load_all_history / player_vs_rival
        │
        ├── historical_analysis.calculate_player_stats
        └── temporal_analysis.calculate_temporal_window
                         │
                         v
                    h2h_analysis
```

`h2h_analysis.py` nunca abre directamente un JSONL. La única función de carga delega en `history_query.load_all_history()`.

## Modelos públicos

### `H2HStats`

Contiene exactamente:

```python
league: str | None
player: str
rival: str
played: int
wins: int
draws: int
losses: int
win_pct: float
draw_pct: float
loss_pct: float
sequence: str
first_match_date: str | None
last_match_date: str | None
```

### `H2HRecentStats`

Añade a las métricas recientes `window`, `available`, `window_complete`, racha actual y fechas de la ventana. Su `sequence` contiene únicamente los últimos N resultados válidos en orden ascendente.

### `H2HComparison`

Contiene porcentajes históricos y recientes de W/E/D, sus tres deltas, `trend` y `sample_status`. Los tres modelos son `TypedDict` con todas sus claves obligatorias y sin campos adicionales.

## API pública

```python
__all__ = [
    "DEFAULT_H2H_WINDOW",
    "DEFAULT_H2H_TREND_THRESHOLD",
    "H2HStats",
    "H2HRecentStats",
    "H2HComparison",
    "empty_h2h_stats",
    "calculate_h2h_stats",
    "calculate_recent_h2h",
    "compare_recent_h2h_to_history",
    "calculate_all_h2h",
    "load_all_h2h",
]
```

Constantes:

```python
DEFAULT_H2H_WINDOW = 20
DEFAULT_H2H_TREND_THRESHOLD = 5.0
```

## Análisis direccional

Cada resultado pertenece a la perspectiva solicitada:

```text
David → Fox: V
Fox → David: D
```

`calculate_h2h_stats(records, "David", "Fox")` solo selecciona David → Fox mediante `player_vs_rival()`. No añade la perspectiva inversa ni partidos contra terceros.

No se exige que exista el registro complementario. Esta capa analiza lo disponible y no repara historiales.

## Secuencia histórica

Antes de calcular:

1. se filtra jugador, rival y liga opcional;
2. se aplica el orden determinista de `history_query`;
3. se eliminan resultados distintos de `V`, `E` o `D`.

`sequence` concatena todos los resultados válidos desde el más antiguo al más reciente. Los conteos son exactos y los porcentajes se redondean a dos decimales.

## Last 20 y otras ventanas

`calculate_recent_h2h()` usa una ventana de 20 por defecto. La ventana se aplica después de filtrar la relación direccional y eliminar resultados inválidos.

```python
from h2h_analysis import calculate_recent_h2h

recent = calculate_recent_h2h(
    records,
    player="David",
    rival="Fox",
    window=20,
    league="GT",
)

print(recent["sequence"])
```

Si hay menos de N resultados, se usan todos los disponibles y `window_complete=False`. La racha actual representa resultados iguales consecutivos al final de la secuencia reciente.

## Comparación y deltas

`compare_recent_h2h_to_history()` reutiliza los cálculos histórico y reciente:

```text
win_pct_delta  = recent_win_pct  - historical_win_pct
draw_pct_delta = recent_draw_pct - historical_draw_pct
loss_pct_delta = recent_loss_pct - historical_loss_pct
```

Todos los deltas se redondean a dos decimales.

```python
from history_query import load_all_history
from h2h_analysis import compare_recent_h2h_to_history

records = load_all_history()

comparison = compare_recent_h2h_to_history(
    records,
    player="David",
    rival="Fox",
    window=20,
    league="GT",
)

print(comparison["historical_win_pct"])
print(comparison["recent_win_pct"])
print(comparison["trend"])
```

## Tendencia

Se calcula únicamente con `win_pct_delta`:

- `UP`: delta positivo mayor o igual que el umbral;
- `DOWN`: delta negativo menor o igual que el umbral negativo;
- `STABLE`: entre ambos;
- `None`: sin muestra reciente.

El umbral predeterminado es 5 puntos porcentuales, es configurable y debe ser numérico no negativo. Con umbral cero y delta cero se conserva `STABLE`.

La tendencia es descriptiva; no es una recomendación de apuesta ni una prueba de significación estadística.

## Sample status

- `EMPTY`: `recent_available == 0`;
- `LOW_SAMPLE`: `0 < recent_available < window`;
- `COMPLETE`: `recent_available >= window`.

Este estado solo indica si la ventana reciente tiene N eventos. No demuestra que el histórico total de la liga esté completo.

## Todas las relaciones

`calculate_all_h2h()` descubre identidades direccionales mediante:

```text
league + player_key + rival_key
```

Descarta registros que no tengan valores textuales no vacíos para esos componentes, mantiene GT y EADRIATIC separados y ordena por liga, jugador y rival.

`min_historical_matches`, entero mínimo 1, permite excluir relaciones con poca cobertura histórica. No se ordena por porcentaje.

`load_all_h2h()` combina los historiales mediante la API compartida y delega todo el cálculo en `calculate_all_h2h()`.

## Timestamps

Se mantiene la política de capas anteriores:

- preferencia por `timestamp_utc` y después `timestamp`;
- `Z` y offsets explícitos aceptados;
- timestamps naive interpretados como UTC;
- fechas finales `YYYY-MM-DD` en UTC;
- fechas inválidas no provocan fallo global;
- un registro sin fecha puede contar en totales y secuencia, pero no participa en primera/última fecha;
- nunca se usa la zona local del sistema.

## Cobertura histórica parcial

La capa solo conoce los eventos presentes en los JSONL. No reconstruye ni presume partidos ausentes.

`historical_played` expresa el número exacto de perspectivas direccionales disponibles. `sample_status` describe únicamente la ventana reciente; no certifica la cobertura histórica completa.

## Inmutabilidad

Los cálculos materializan o consultan copias y devuelven diccionarios nuevos. No cambian registros, orden de entrada, JSONL ni otros archivos.

## Validaciones

- `window`: entero no booleano mayor que cero;
- `trend_threshold`: número no booleano y no negativo;
- `min_historical_matches`: entero no booleano mayor o igual que uno;
- jugador y rival: cadenas no vacías después de `strip()`;
- liga opcional: cadena no vacía y comparación insensible a mayúsculas.

## Pruebas

Las 40 pruebas específicas cubren:

- claves exactas y obligatoriedad de los tres modelos;
- resultados vacíos;
- histórico direccional exacto;
- perspectivas inversas y terceros;
- separación y filtro de ligas;
- orden cronológico y desempates;
- resultados y fechas inválidos;
- Last 20 y ventanas personalizadas;
- ventanas completas/incompletas;
- secuencia, porcentajes, fechas y rachas recientes;
- deltas W/E/D;
- tendencias y umbrales;
- los tres estados de muestra;
- todas las relaciones y filtro mínimo;
- registros incompletos;
- carga con archivos presentes o ausentes;
- validaciones e inmutabilidad;
- ausencia de escrituras.

## Limitaciones y siguiente tarea

TASK-004 no modifica `group_analysis.py`, H2H Betting Alerts ni la web. Tampoco repara simetrías o reconstruye datos históricos.

Una tarea posterior podrá consumir esta API para presentación o alertas, pero TASK-005 no forma parte de este alcance.

## Validación

```text
python -m unittest discover -s tests -v
python -m py_compile h2h_analysis.py tests/test_h2h_analysis.py
git diff --check
git diff --stat
git status --short
```
