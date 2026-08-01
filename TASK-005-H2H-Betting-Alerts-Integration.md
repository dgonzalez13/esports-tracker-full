# TASK-005 — Integración de estadísticas recientes en H2H Betting Alerts

## Integración híbrida

Las alertas conservan como fuente de verdad histórica la agregación de los TXT realizada por `group_analysis.py`. Por ello, W, D, L, Matches, Win %, los umbrales de selección (48 % y 50 %) y Signal no cambian.

El historial JSONL se carga una sola vez mediante `history_query.load_all_history()`. Para cada alerta legacy, `h2h_analysis.calculate_recent_h2h()` obtiene las últimas 20 perspectivas normalizadas de la misma liga, jugador y rival. Esta fuente aporta la secuencia reciente, disponibilidad, resultados, porcentajes y estado de la ventana.

> Last 20 solo puede incluir los eventos normalizados disponibles en `match_history.jsonl`. El porcentaje histórico visible continúa utilizando el histórico agregado anterior para no perder cobertura.

## Campos añadidos

Cada alerta incorpora `recent_window`, `recent_available`, `recent_sequence`, `recent_wins`, `recent_draws`, `recent_losses`, `recent_win_pct`, `recent_draw_pct`, `recent_loss_pct`, `recent_win_pct_delta`, `recent_trend`, `recent_sample_status` y `recent_window_complete`.

El delta es el porcentaje reciente menos el porcentaje histórico legacy. La tendencia es `UP` desde +5 puntos, `DOWN` desde -5 puntos, `STABLE` dentro de ese intervalo y `None` sin muestra. Sample distingue `EMPTY`, `LOW_SAMPLE` y `COMPLETE`.

## Presentación y compatibilidad

La tabla visible contiene Player, Rival, W, D, L, Matches, Win %, Last 20, Win % L20, Trend, Signal y Sample. No muestra STK WIN ni STK LOSE. La secuencia permanece en orden cronológico y se presenta como texto sin colorear letras individuales.

Los indicadores de Current Streaks junto a Player y Rival se mantienen sin recalcular. Los JSON anteriores siguen siendo renderizables: al faltar las claves recientes, Last 20, Win % L20, Trend y Sample muestran una raya. Los campos legacy `seq`, `last5`, `last10`, `stk_win` y `stk_lose` permanecen en la salida para evitar romper consumidores existentes, aunque las rachas y Last 10 ya no se muestran en esta tabla.

## Cobertura parcial y limitaciones

Una ventana parcial muestra todos los eventos disponibles y su disponibilidad, por ejemplo `8/20 · LOW`; no se inventan resultados. Sin perspectivas normalizadas se muestra una raya y la alerta histórica sigue disponible. Hasta que el JSONL alcance la misma cobertura que los TXT, Last 20 no representa necesariamente los últimos 20 encuentros de todo el histórico legacy.
