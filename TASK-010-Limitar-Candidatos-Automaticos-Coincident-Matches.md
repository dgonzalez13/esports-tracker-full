# TASK-010 --- Limitar candidatos automáticos de Coincident Matches

## Objetivo

Reducir el número de cruces generados automáticamente manteniendo
únicamente los candidatos más relevantes.

No modificar la lógica de selección automática existente; únicamente
limitar el número máximo de candidatos utilizados para construir las
parejas.

No hacer commit. No hacer push.

------------------------------------------------------------------------

## Situación actual

Actualmente todos los jugadores que cumplen:

-   mínimo 5 partidos;
-   50 % o más de victorias o 50 % o más de derrotas;

entran automáticamente en Coincident Matches.

Cuando existen muchos candidatos, el número de parejas crece muy
rápidamente.

------------------------------------------------------------------------

## Nueva constante pública

``` python
MAX_AUTOMATIC_CANDIDATES = 8
```

## Proceso de selección

Calcular primero exactamente los mismos candidatos que ahora.

Después ordenarlos por:

1.  Fuerza del indicador:
    -   GREEN: `win_pct - 50`
    -   RED: `loss_pct - 50`
2.  Partidos disputados (descendente).
3.  Porcentaje relevante (descendente).
4.  Liga.
5.  Nombre.

El orden debe ser completamente determinista.

## Recorte

Conservar únicamente:

``` python
MAX_AUTOMATIC_CANDIDATES
```

Los restantes quedan descartados antes de generar parejas.

## Coincident Matches

Generar las combinaciones únicamente con esos candidatos.

Con el valor por defecto:

``` text
8 candidatos
↓

28 parejas máximo
```

## Información visible

Mostrar al comienzo:

``` text
Eligible players: X
Selected candidates: Y
Candidate limit: 8
```

## Compatibilidad

No modificar:

-   Current Streaks Legacy.
-   Current Streaks V2.
-   H2H.
-   Group Analysis.
-   Parser de tracked_players.
-   Selección automática.
-   Umbral del 50 %.
-   Mínimo de 5 partidos.

## Pruebas

Añadir pruebas para:

1.  Menos de 8 candidatos.
2.  Exactamente 8.
3.  Más de 8.
4.  Empates por fuerza.
5.  Empates por partidos.
6.  Orden determinista.
7.  GT y EADRIATIC.
8.  GREEN.
9.  RED.
10. Prioridad GREEN existente en 50/50.

## Validación

Ejecutar:

``` text
python -m unittest discover -s tests -v
python -m py_compile coincident_matches.py selected_players.py web_tracker/generate_site.py
git diff --check
```

## Respuesta

Responder con:

-   Archivos modificados.
-   Cambios realizados.
-   Pruebas añadidas.
-   Resultado de la suite.
-   Validación manual.
-   git diff --stat.
-   git status --short.
-   Desviaciones.

Indicar expresamente si no hubo desviaciones funcionales.
