# TASK-003 — Temporal Windows and Recent Form Analysis

## Objetivo

TASK-003 añade análisis puro sobre las últimas N perspectivas válidas de un jugador. Reutiliza `history_query.py` para seleccionar y ordenar y `historical_analysis.py` para el cálculo histórico.

No lee JSONL directamente, no escribe archivos y no está integrada con la web.

## Archivos

- `temporal_analysis.py`;
- `tests/test_temporal_analysis.py`;
- `TASK-003-Temporal-Windows-and-Recent-Form-Analysis.md`.

La corrección de conformidad solo modifica estos tres archivos.

## Modelos públicos exactos

### `TemporalWindowStats`

Es un `TypedDict` independiente, sin heredar de `PlayerHistoricalStats`, con exactamente:

```python
league: str | None
player: str
window: int
available: int
wins: int
draws: int
losses: int
win_pct: float
draw_pct: float
loss_pct: float
sequence: str
current_streak_result: str | None
current_streak: int
first_match_date: str | None
last_match_date: str | None
```

`sequence` contiene únicamente `V`, `E` y `D`, desde el resultado más antiguo al más reciente dentro de la ventana.

### `RecentHistoryComparison`

Modelo separado con exactamente:

```python
league: str | None
player: str
window: int
recent_available: int
historical_played: int
recent_win_pct: float
historical_win_pct: float
win_pct_delta: float
recent_draw_pct: float
historical_draw_pct: float
draw_pct_delta: float
recent_loss_pct: float
historical_loss_pct: float
loss_pct_delta: float
```

No incluye tendencia ni claves adicionales.

## API canónica

### `empty_temporal_window(player, window, league=None)`

Devuelve el modelo exacto con disponibilidad y contadores cero, porcentajes `0.0`, secuencia vacía, racha sin resultado y fechas `None`.

### `calculate_temporal_window(records, player, window, league=None)`

El orden de operaciones es:

1. filtrar por jugador y liga opcional;
2. ordenar cronológicamente mediante `history_query.player_history`;
3. eliminar resultados distintos de `V`, `E` o `D`;
4. tomar las últimas N perspectivas válidas;
5. conservar el subconjunto ascendente;
6. calcular secuencia, W/E/D, porcentajes, racha y fechas.

Ejemplo:

```text
Historial válido: V E D V E
Ventana 3:       D V E
sequence:        "DVE"
```

La ventana debe ser un entero mayor que cero; los booleanos se rechazan.

### `calculate_player_windows(records, player, windows=(5, 10, 20), league=None)`

Acepta cualquier iterable de ventanas, incluidos generadores. Valida todos los valores, elimina duplicados y devuelve las ventanas en orden numérico.

```text
(10, 5, 10, 20) → 5, 10, 20
```

Una colección vacía devuelve `[]`.

### `calculate_all_player_windows(records, windows=(5, 10, 20), league=None)`

Calcula todas las identidades independientes `league + player_key`. El mismo nickname en GT y EADRIATIC permanece separado.

Orden de salida:

1. liga;
2. jugador;
3. ventana.

### `compare_recent_to_history(records, player, window, league=None)`

Reutiliza `calculate_temporal_window()` y `calculate_player_stats()`. No duplica el cálculo histórico.

```text
win_pct_delta  = recent_win_pct  - historical_win_pct
draw_pct_delta = recent_draw_pct - historical_draw_pct
loss_pct_delta = recent_loss_pct - historical_loss_pct
```

Los deltas se redondean a dos decimales.

### `load_temporal_windows(gt_path=..., eadriatic_path=..., windows=(5, 10, 20), league=None)`

Carga exclusivamente mediante `history_query.load_all_history()` y delega en `calculate_all_player_windows()`.

## API pública final

```python
__all__ = [
    "DEFAULT_TREND_THRESHOLD",
    "TemporalWindowStats",
    "RecentHistoryComparison",
    "empty_temporal_window",
    "calculate_temporal_window",
    "calculate_player_windows",
    "calculate_all_player_windows",
    "compare_recent_to_history",
    "load_temporal_windows",
    "calculate_recent_form",
    "calculate_recent_vs_rival",
    "calculate_temporal_windows",
    "calculate_all_recent_forms",
    "load_recent_forms",
]
```

## Compatibilidad

Se conservan las cinco funciones de la primera implementación:

- `calculate_recent_form`;
- `calculate_recent_vs_rival`;
- `calculate_temporal_windows`;
- `calculate_all_recent_forms`;
- `load_recent_forms`.

Continúan proporcionando los campos enriquecidos y la tendencia `UP`, `STABLE`, `DOWN` o `None`. Son API adicional y no sustituyen a `RecentHistoryComparison` ni alteran las claves exactas de los modelos canónicos.

El umbral de tendencia sigue siendo configurable y vale 5 puntos porcentuales por defecto. Esta etiqueta es descriptiva, no una recomendación de apuesta.

## Inmutabilidad

Las funciones materializan o consultan copias de los registros y no modifican el iterable ni sus diccionarios. No escriben JSONL ni ninguna otra salida.

## Pruebas

La suite temporal cubre específicamente:

- claves exactas de ambos `TypedDict`;
- valores de `empty_temporal_window`;
- secuencia cronológica;
- eliminación de inválidos antes de cortar;
- ventana incompleta;
- porcentajes W/E/D;
- racha actual;
- deduplicación, validación y orden de ventanas;
- generadores de ventanas;
- comparación reciente/histórica W/E/D;
- carga mediante `load_temporal_windows`;
- separación GT/EADRIATIC;
- orden liga/jugador/ventana;
- inmutabilidad;
- compatibilidad con forma reciente, H2H y tendencia.

## Exclusiones

TASK-003 no implementa:

- cambios en scrapers, persistencia o JSONL;
- integración web;
- sesiones de actividad;
- alertas o recomendaciones de apuestas;
- backtesting o significación estadística;
- TASK-004.

## Validación

```text
python -m unittest discover -s tests -v
python -m py_compile temporal_analysis.py tests/test_temporal_analysis.py
git diff --check
```
