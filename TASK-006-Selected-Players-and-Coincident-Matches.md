# TASK-006 — Selected Players and Coincident Matches

## Selección y compatibilidad

`tracked_players.txt` admite un asterisco final para seleccionar jugadores, por ejemplo `GT|Lucas*`. El marcador se elimina al analizar la línea: `Lucas` continúa siendo el nombre visible, permanece tracked en Current Streaks y conserva sus indicadores en H2H Betting Alerts. La identidad siempre combina liga y nombre normalizado, por lo que nombres iguales de ligas diferentes son jugadores distintos.

El parser compartido conserva el orden del archivo, normaliza la liga, soporta Unicode y consolida duplicados. Si una identidad aparece con y sin asterisco, se conserva una entrada seleccionada con la primera grafía visible.

## Combinaciones y algoritmo

Se generan todas las combinaciones no dirigidas de dos jugadores seleccionados. Los historiales se construyen una vez por jugador y se reutilizan entre parejas.

> El emparejamiento es cronológico y siempre hacia atrás. Cada partido se compara con el partido no utilizado más reciente del otro jugador. Nunca se usa un partido futuro.

Cada línea temporal se recorre de antigua a reciente. Una coincidencia consume ambos partidos dentro de esa pareja y conserva la orientación estable A/B definida por la combinación.

> Un partido puede reutilizarse en comparaciones con parejas distintas, pero no puede reutilizarse dos veces dentro de la misma pareja.

## Distancia y tiempo

La distancia máxima predeterminada es `DEFAULT_MAX_COINCIDENT_GAP_MINUTES = 30`. Son válidas diferencias reales entre 0 y 30 minutos, ambos inclusive. `gap_minutes` se obtiene con `int(total_seconds // 60)`, aunque la aceptación del límite utiliza los segundos reales.

Se prioriza `timestamp_utc`, con `timestamp` como alternativa. Se aceptan `Z`, offsets y timestamps naive —estos últimos se interpretan como UTC—. La salida interna queda normalizada a UTC con terminación `Z`; la web presenta las fechas explícitamente en `Europe/Madrid`.

## Sección visible

Coincident Matches aparece después de Current Streaks. Cada panel identifica inequívocamente las ligas y jugadores, el límite y el número de coincidencias. La tabla muestra orden, ambos jugadores, horas, resultados, rivales y gap. Sin combinaciones se muestra `No selected player combinations.`; una pareja sin filas muestra `No coincident matches within 30 minutes.`.

## Rendimiento y pruebas

La generación web carga una vez el listado tracked y una vez ambos JSONL mediante las APIs existentes. Los historiales filtrados de cada jugador se calculan una vez. Las pruebas cubren parser, modelos, combinaciones, normalización temporal, límites, elección del anterior inmediato, ausencia de futuro, no reutilización, determinismo, caché, renderizado y regresiones de Current Streaks/H2H.

## Limitaciones y TASK-007

Solo participan perspectivas normalizadas disponibles en los JSONL y jugadores marcados expresamente. TASK-006 no introduce sesiones, cortes por medianoche ni cambios en la lógica diaria; esas evoluciones quedan fuera de alcance y podrán abordarse en TASK-007.
