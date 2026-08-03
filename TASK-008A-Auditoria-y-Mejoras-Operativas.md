# TASK-008A --- Auditoría y mejoras operativas

## Objetivos

Esta tarea reúne las mejoras detectadas tras probar TASK-008 con datos
reales.

No hacer commit ni push.

------------------------------------------------------------------------

# 1. Auditar Current Streaks V2

Current Streaks V2 muestra menos partidos que los realmente disputados.

**No asumir la causa.**

Realizar una auditoría completa comparando para al menos dos jugadores
reales:

-   Legacy (TXT)
-   JSONL
-   Current Streaks V2

Para cada partido indicar:

-   timestamp
-   resultado
-   rival
-   match_id
-   perspective_id
-   si entra en V2
-   motivo de exclusión si no entra

Determinar cuál es la causa real:

-   filtrado temporal incorrecto;
-   persistencia incompleta en JSONL;
-   player_key;
-   timestamps;
-   duplicados;
-   cualquier otra.

No aplicar una corrección sin identificar primero la causa.

Si el problema está en la ventana temporal, corregirla.

------------------------------------------------------------------------

# 2. Nuevo significado del asterisco

Hasta ahora:

``` text
GT|Lucas*
```

significaba "seleccionado".

A partir de ahora debe significar:

> Jugador real del grupo pero NO disponible para la operativa porque no
> aparece actualmente en las apuestas.

El parser debe seguir aceptándolo.

Debe devolver un modelo equivalente a:

``` python
league = "GT"
player = "Lucas"
tracked = True
bettable = False
empty_slot = False
```

El nombre interno puede variar, pero debe existir un estado equivalente.

------------------------------------------------------------------------

# 3. Diferencia entre hueco y jugador excluido

Debe distinguir claramente:

## Posición vacía

``` text
GT|
```

-   no existe jugador;
-   no hay estadísticas;
-   no aparece en ningún sitio.

## Jugador excluido

``` text
GT|Lucas*
```

-   el jugador existe;
-   sus partidos siguen descargándose;
-   sus estadísticas siguen calculándose;
-   mantiene su posición dentro del grupo;
-   no participa en la operativa.

------------------------------------------------------------------------

# 4. Current Streaks

Los jugadores marcados con `*`:

-   NO aparecen en Legacy.
-   NO aparecen en V2.

------------------------------------------------------------------------

# 5. Coincident Matches

Los jugadores marcados con `*`:

-   NO participan en la selección automática;
-   NO aparecen en parejas;
-   NO generan coincidencias.

------------------------------------------------------------------------

# 6. Group Analysis

Los jugadores con `*` siguen perteneciendo al grupo.

Sus partidos deben seguir utilizándose para reconstruir correctamente el
grupo.

No deben eliminarse del análisis interno.

------------------------------------------------------------------------

# 7. H2H

Los partidos contra jugadores marcados con `*` siguen siendo válidos.

Por tanto:

-   pueden seguir apareciendo como rivales;
-   sus enfrentamientos siguen afectando a los porcentajes de los demás
    jugadores.

Sin embargo:

-   un jugador con `*` no debe generar señales operativas como jugador
    principal.

------------------------------------------------------------------------

# 8. Compatibilidad

Mantener compatibilidad con:

-   Current Streaks Legacy.
-   Current Streaks V2.
-   Coincident Matches.
-   H2H.
-   Posiciones vacías.
-   Parser actual.

No eliminar todavía soporte del asterisco.

------------------------------------------------------------------------

# 9. Validación

Probar temporalmente:

``` text
GT|Lucas*
GT|Kratos
GT|
GT|Vendetta
GT|Furious
```

Verificar:

-   Lucas mantiene estadísticas internas.
-   Lucas desaparece de Legacy.
-   Lucas desaparece de V2.
-   Lucas no aparece en Coincident Matches.
-   Lucas sigue siendo rival válido para H2H.
-   El hueco no desplaza jugadores.

------------------------------------------------------------------------

# Informe final

Responder con:

-   Causa raíz de los partidos perdidos en V2.
-   Corrección aplicada.
-   Cambios en el parser.
-   Cambios en Current Streaks.
-   Cambios en Coincident Matches.
-   Cambios en Group Analysis.
-   Cambios en H2H.
-   Pruebas añadidas.
-   Resultado de la suite.
-   Validación real.
-   git diff --stat.
-   git status --short.
-   Desviaciones.
