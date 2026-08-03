# TASK-008 — Snapshot operativo de ocho horas

El tracker fija una sola hora de referencia UTC por generación y usa el intervalo inclusivo
`referencia - 8 horas <= timestamp <= referencia`. Los timestamps sin zona se interpretan
como UTC y los eventos futuros se excluyen.

> Un jugador no participa en dos grupos distintos dentro de la misma ventana de ocho horas. Por ese motivo, Current Streaks V2 utiliza todos los partidos válidos del jugador dentro de esa ventana y no aplica el corte de sesión de 90 minutos.

`calculate_operational_snapshot` es la fuente única de W/E/D, porcentajes, secuencia,
Last 10, racha e indicador. V2 presenta PLAYER, W, D, L, PLAYED, LAST 10 y STREAK,
ordenados por victorias, porcentaje de victorias, partidos y nombre. Las APIs de sesiones
y sus claves de payload se conservan como compatibilidad, pero no deciden el contenido visible.

Coincident Matches reutiliza el mismo snapshot. Selecciona automáticamente jugadores con
al menos cinco partidos y un 50 % de victorias (GREEN) o derrotas (RED); GREEN tiene prioridad
en un empate 50/50. Solo empareja partidos de la ventana de ocho horas y marca confirmaciones
simultáneas como BOTH GREEN, BOTH RED o MIXED, además del sombreado accesible correspondiente.

> El marcador `*` continúa siendo aceptado por compatibilidad, pero Coincident Matches selecciona ahora automáticamente a los jugadores que cumplen los criterios operativos.

Las líneas `GT|` y `EADRIATIC|` son posiciones vacías. Se conservan al cargar el fichero y
cuentan al formar bloques de cinco, pero no son jugadores ni participan en V2, coincidencias,
H2H, rankings o HTML. Los targets y sus coincidencias exactas se calculan respecto del número
real de jugadores; se publican `target_size`, `exact_target_matches` y
`near_target_matches`, manteniendo a la vez las claves legacy.

Limitaciones: se mantienen Current Streaks Legacy, las APIs de sesión y la terminología 5/5
del análisis histórico. El asterisco conserva su valor parseado solo para consumidores antiguos.
Las pruebas cubren límites temporales, selección, confirmaciones y huecos. La diferencia central
respecto a TASK-007 es que una pausa de más de 90 minutos ya no corta el snapshot visible.
