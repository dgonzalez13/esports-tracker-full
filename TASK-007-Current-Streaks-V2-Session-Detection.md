# TASK-007 — Current Streaks V2 con detección de sesiones

## Motivo y coexistencia

Current Streaks Legacy calcula el estado desde el último TXT diario. V2 usa las perspectivas normalizadas de `match_history.jsonl` para evitar que la medianoche corte una actividad continua y que dos bloques separados del mismo día se sumen como uno solo.

> Current Streaks Legacy se mantiene visible durante esta fase. Current Streaks V2 no lo sustituye todavía; ambas versiones se muestran en paralelo para comparar resultados reales.

## Definición de sesión

Una sesión agrupa los partidos cronológicos de una identidad `league + player_key`. El umbral inicial es de 90 minutos: un hueco exactamente igual permanece en la sesión y solo un hueco superior inicia otra.

> La medianoche no corta una sesión. Una sesión solo termina cuando el hueco temporal entre dos partidos consecutivos supera el umbral configurado.

El valor `DEFAULT_SESSION_GAP_MINUTES = 90` es configurable y podrá ajustarse después de comparar V2 con Legacy. Los timestamps se normalizan a UTC; se aceptan `Z`, offsets y valores naive interpretados como UTC. La presentación utiliza siempre `Europe/Madrid`.

## Sesión visible y actividad

V2 calcula todas las sesiones de cada jugador tracked, pero muestra únicamente la más reciente. De esta forma, dos grupos separados el mismo día no se mezclan ni suman sus partidos. Una sesión es ACTIVE si terminó entre cero y 180 minutos antes del tiempo de referencia; una sesión futura o más antigua es INACTIVE. La ventana `DEFAULT_ACTIVE_WINDOW_MINUTES = 180` es independiente del umbral de separación.

Cada sesión incluye inicio, fin, duración, W/E/D, porcentajes, secuencia completa, Last 10 cronológico, racha final de resultados iguales, balance tracked y estado activo. Los jugadores seleccionados con `*` siguen siendo tracked y el marcador nunca forma parte del nombre.

## Presentación paralela

La página mantiene este orden:

1. Current Streaks — Legacy.
2. Current Streaks V2 — Sessions.
3. Coincident Matches.
4. Group Analysis.

La cabecera V2 muestra el hueco de sesión, la ventana activa y la fuente JSONL. Hay una tabla independiente por liga con PLAYER, STATUS, START, END, DURATION, W, D, L, PLAYED, LAST 10 y STREAK.

## Diferencias esperadas

Legacy puede cortar a medianoche, mezclar bloques diarios o incluir filas del TXT que no sean tracked. V2 puede cruzar días, separa por huecos y muestra la última sesión normalizada de cada tracked player. No se fuerza que ambas versiones coincidan y nunca se copian datos legacy para completar ausencias JSONL.

## Rendimiento y pruebas

La web carga `tracked_players.txt` una vez y reutiliza una única carga de ambos JSONL para Coincident Matches y V2. Cada identidad V2 se filtra una sola vez. Las pruebas cubren modelos, identidad, tiempo, medianoche y cambio de año, múltiples grupos, umbrales, actividad, métricas, inmutabilidad, carga ausente, renderizado y regresión Legacy.

## Retirada futura de Legacy

Legacy solo debería retirarse después de observar durante varios días que el umbral de 90 minutos separa correctamente los grupos, que la cobertura JSONL es suficiente y que las diferencias observadas son explicables. Esta tarea no inicia esa retirada.
