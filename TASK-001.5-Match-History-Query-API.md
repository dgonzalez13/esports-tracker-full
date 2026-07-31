# TASK-001.5 — Match History Query API

## Objetivo

TASK-001.5 incorpora una API Python pequeña y de solo lectura para consultar los historiales JSONL normalizados creados por TASK-001. Centraliza la carga, el orden y los filtros sin realizar cálculos estadísticos ni modificar datos.

No es una funcionalidad visible de la web y todavía no está integrada con otros scripts.

## Alcance

La implementación se limita a:

- `history_query.py`;
- `tests/test_history_query.py`;
- `TASK-001.5-Match-History-Query-API.md`.

No se han modificado scrapers, JSONL, TXT, análisis, web, workflows ni tracked players.

## Archivos creados

### `history_query.py`

Módulo compartido sin efectos secundarios al importarse. Utiliza únicamente la biblioteca estándar y `name_key` de `match_history.py`.

### `tests/test_history_query.py`

Suite offline de 50 pruebas. Usa archivos JSONL temporales dentro del directorio temporal de pruebas e ignora los historiales reales.

### `TASK-001.5-Match-History-Query-API.md`

Este documento.

## API pública

El módulo declara explícitamente:

```python
__all__ = [
    "HistoryQueryError",
    "BASE_DIR",
    "GT_HISTORY_PATH",
    "EADRIATIC_HISTORY_PATH",
    "load_history",
    "load_gt_history",
    "load_eadriatic_history",
    "load_all_history",
    "filter_by_league",
    "player_history",
    "player_vs_rival",
    "head_to_head",
    "filter_by_time",
    "latest_matches",
    "duplicate_perspective_ids",
]
```

### Carga

- `load_history(path)`: carga un JSONL genérico.
- `load_gt_history(path=GT_HISTORY_PATH)`: carga GT.
- `load_eadriatic_history(path=EADRIATIC_HISTORY_PATH)`: carga EADRIATIC.
- `load_all_history(...)`: combina ambos archivos y vuelve a ordenar.

Las rutas predeterminadas se resuelven desde `Path(__file__).resolve().parent`, no desde el directorio de ejecución.

Un archivo inexistente representa un historial vacío. Las líneas vacías se ignoran. Una línea con JSON inválido lanza `HistoryQueryError` incluyendo ruta, número de línea, detalle y excepción original encadenada. También se rechaza cualquier línea JSON cuyo valor no sea un objeto.

### Filtros

- `filter_by_league(records, league)`: selección insensible a mayúsculas y espacios exteriores, sin enum cerrado.
- `player_history(records, player, league=None)`: solo perspectivas propias del jugador.
- `player_vs_rival(records, player, rival, league=None)`: únicamente la dirección solicitada.
- `head_to_head(records, player_a, player_b, league=None)`: ambas direcciones del enfrentamiento.
- `filter_by_time(records, start=None, end=None, field="timestamp_utc")`: rango temporal inclusivo.
- `latest_matches(records, limit, player=None, league=None)`: últimas N perspectivas, no partidos físicos agrupados.
- `duplicate_perspective_ids(records)`: diagnóstico alfabético de IDs repetidos.

Todas aceptan cualquier iterable, devuelven listas nuevas ordenadas y no realizan estadísticas.

## Normalización de nombres

Las consultas reutilizan `match_history.name_key`, por lo que aplican exactamente:

- eliminación de espacios exteriores;
- Unicode NFKC;
- `casefold()`;
- conservación de tildes y caracteres internos;
- ninguna coincidencia difusa.

Los valores visibles `player` y `rival` almacenados no se alteran. Los argumentos vacíos o no textuales se rechazan con `ValueError`.

## Orden cronológico determinista

Todos los resultados se ordenan por estos campos, en orden:

1. `timestamp_utc`;
2. `timestamp`;
3. `match_id`;
4. `player_key`;
5. `perspective_id`.

Los campos ausentes o `None` se representan mediante una clave de orden vacía, evitando errores de tipos y manteniendo un resultado determinista. No se usa la fecha de modificación del archivo.

`latest_matches` selecciona el final de esta secuencia y devuelve el subconjunto en orden ascendente. No combina las dos perspectivas de un partido.

## Tratamiento de timestamps

`filter_by_time` acepta límites como:

- `datetime`;
- cadena ISO 8601;
- `None`.

El sufijo `Z` se interpreta como UTC. Los timestamps con offset se convierten a UTC antes de comparar.

### Datetimes naive

Un `datetime` o cadena ISO sin información de zona se interpreta explícitamente como UTC. Nunca se aplica la zona local del sistema. Esta política evita resultados distintos según la máquina donde se ejecute la consulta.

Las comparaciones son inclusivas:

```text
start <= timestamp <= end
```

Un rango invertido o un límite inválido produce `ValueError`.

### Registros sin timestamp

Cuando existe al menos un límite, un registro sin el campo consultado o con un timestamp ISO inválido queda excluido de esa consulta; no se corrige y no detiene la selección.

Cuando ambos límites son `None`, todos los registros se devuelven ordenados, incluidos los que carezcan de timestamp.

## Inmutabilidad

`load_history` obtiene objetos nuevos mediante `json.loads`. Todas las consultas realizan una copia superficial con `dict(record)` de cada resultado.

Modificar un diccionario devuelto no cambia el registro original entregado a la consulta. No se aplica `deepcopy`, porque el contrato actual solo requiere copia superficial y el esquema principal es plano. Los historiales nunca se reescriben, reparan ni deduplican desde esta API.

## Duplicados

`duplicate_perspective_ids`:

- devuelve cada ID repetido una sola vez;
- ordena alfabéticamente;
- ignora valores ausentes, vacíos o no textuales;
- no elimina registros;
- no emite advertencias ni escribe archivos.

## Ejemplos de uso

```python
from history_query import (
    load_all_history,
    player_history,
    head_to_head,
    latest_matches,
)

records = load_all_history()

lucas = player_history(records, "Lucas", league="GT")
lucas_vs_kratos = head_to_head(records, "Lucas", "Kratos", league="GT")
recent = latest_matches(lucas, 10)
```

Consulta temporal:

```python
from history_query import filter_by_time

july = filter_by_time(
    records,
    start="2026-07-01T00:00:00Z",
    end="2026-07-31T23:59:59Z",
)
```

Diagnóstico sin modificar el historial:

```python
from history_query import duplicate_perspective_ids

duplicates = duplicate_perspective_ids(records)
```

## Exclusiones explícitas

TASK-001.5 no implementa:

- porcentajes, W/D/L o tendencias;
- Last 20;
- sesiones o Current Streaks;
- alertas H2H visibles;
- deduplicación o reparación del JSONL;
- consistencia estadística entre perspectivas;
- reconstrucción histórica;
- integración con web o análisis existentes;
- base de datos, ORM o dependencias externas;
- TASK-002.

## Validación

Suite completa:

```text
python -m unittest discover -s tests -v
```

Compilación del módulo y sus pruebas:

```text
python -m py_compile history_query.py tests/test_history_query.py
```

Validación del diff:

```text
git diff --check
```

Las pruebas cubren carga, archivos inexistentes o corruptos, tipos JSON inválidos, orden y desempates, filtros de liga y Unicode, direcciones H2H, timestamps aware/naive, rangos inclusivos, registros sin fecha, últimos resultados, duplicados, copias superficiales y ausencia de escrituras.
