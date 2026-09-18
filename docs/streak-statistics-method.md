# Estadísticas SG/SP por turno

La sección se genera con `python web_tracker/generate_site.py`, a partir del historial
JSONL, y se incorpora a `docs/index.html`. No requiere servicios ni peticiones extra.

## Ventanas

Todos los horarios son Europe/Madrid:

| Liga | Grupo 1 | Grupo 2 |
|---|---|---|
| GT | 05:00, 13:00, 21:00 | 06:00, 14:00, 22:00 |
| Eadriatic | 07:00, 15:00, 23:00 | 07:20, 15:20, 23:20 |

Los rivales conectados durante el tramo común de ambos turnos identifican los grupos
históricos. Solo se aceptan componentes de 4 o 5 jugadores cuyo primer partido observado
coincida exactamente con uno de los dos inicios. La asignación es una reconstrucción,
no una identificación oficial de grupo. Los cambios de composición y los bloques sin
inicio verificable pueden quedar excluidos. No se usa el grupo actual del jugador para
asignar su grupo histórico.

Cada ventana termina antes del siguiente inicio de su grupo, con un máximo de ocho
horas reales. En cambios de hora se conservan los horarios locales y ese límite;
el turno nocturno de otoño puede perder su última hora. Las ventanas atraviesan
medianoche sin reiniciarse. Se deduplican las perspectivas de cada partido y jugador.

Se excluyen jugadores marcados como no apostables de los resúmenes. Se conservan los
resultados frente a ellos para no fabricar rachas al eliminar partidos intermedios.
La cobertura depende del historial almacenado, no de los antiguos TXT diarios.

## Porcentajes

SG se rompe con V; SP con D. E prolonga ambas. Cada racha genera una observación por
longitud alcanzada. Para horizontes de 1, 2 o 3 partidos:

- `broken`: se observa una ruptura dentro del horizonte.
- `continued`: se observan todos los partidos del horizonte sin ruptura.
- `incomplete`: no se observa ruptura ni hay suficientes partidos antes del corte.

El porcentaje es `broken / (broken + continued)`, acompañado de su denominador y del
número de incompletos. Un denominador cero se muestra como ausencia de datos. Son
frecuencias entre casos resueltos, no estimaciones corregidas por censura: la selección
de casos resueltos puede favorecer rupturas tempranas. Los denominadores pueden diferir
y los porcentajes entre horizontes no tienen garantizada la monotonía.

El general agrega observaciones de jugadores, no promedia sus porcentajes ni trata los
partidos de ambos rivales como ensayos independientes. «Pocos datos» usa un umbral
descriptivo de 30 casos resueltos. No se calcula rentabilidad ni se recomienda apostar.

La vista del turno actual usa estas ventanas fijas; Current Streaks mantiene su ventana
móvil original. Se muestran todos los jugadores con turno reconstruible, no solo los
del archivo de seguimiento. El histórico incluye lo observado del turno abierto.

## Validación

`python -m unittest discover -s tests -p test_streak_break_stats.py`

`python -m unittest discover -s tests -p test_current_streaks_v2_rendering.py`

`node tests/test_streak_statistics_ui.cjs`

La prueba JavaScript verifica el controlador con un DOM mínimo; no sustituye una
inspección visual en navegador.
