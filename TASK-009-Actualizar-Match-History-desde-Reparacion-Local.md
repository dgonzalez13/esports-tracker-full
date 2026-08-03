# TASK-009 --- Integrar la reparación local con `match_history.jsonl`

## Contexto

La auditoría de TASK-008A ha demostrado que:

-   Current Streaks V2 muestra correctamente todos los partidos
    existentes en `match_history.jsonl`.
-   La diferencia con Legacy no se debe al cálculo de V2.
-   Algunos partidos presentes tras la reparación local nunca llegan a
    persistirse en el histórico normalizado.

Actualmente la reparación local se realiza mediante:

``` text
repair_eadriatic.bat
```

que ejecuta:

``` text
repair_eadriatic_day.py
```

La idea de esta tarea **no es mover esa reparación a GitHub Actions**,
sino aprovecharla para mantener actualizado también el histórico
normalizado.

------------------------------------------------------------------------

# Objetivo

Cuando se ejecute `repair_eadriatic.bat`, además de reparar el TXT
diario deberá actualizar automáticamente:

``` text
eadriatic/data/match_history.jsonl
```

utilizando exactamente la misma infraestructura de persistencia que usa
el scraper normal.

No escribir JSONL manualmente.

------------------------------------------------------------------------

# Auditoría inicial

Revisar:

-   repair_eadriatic.bat
-   repair_eadriatic_day.py
-   eadriatic_leagues.py
-   match_history.py
-   history_query.py

Determinar:

-   qué información devuelve la reparación;
-   si contiene fecha, hora, jugadores, marcador y resultado;
-   qué funciones existentes pueden reutilizarse para construir las
    perspectivas.

No duplicar lógica existente.

------------------------------------------------------------------------

# Comportamiento requerido

Después de reparar el TXT:

1.  Obtener todos los partidos reparados.
2.  Normalizarlos con el mismo formato utilizado por
    `eadriatic_leagues.py`.
3.  Generar `match_id` y `perspective_id` mediante la infraestructura
    existente.
4.  Persistir usando exclusivamente la API de `match_history.py`.
5.  No escribir JSONL directamente.
6.  No duplicar registros.
7.  Mantener orden cronológico.
8.  Mantener timestamps UTC.
9.  Mantener:
    -   timezone = Europe/Madrid
    -   timezone_inferred = True
10. Si no existen partidos nuevos, el JSONL no debe modificarse.

------------------------------------------------------------------------

# Cambio de día

La reparación puede ejecutarse después de medianoche.

La fecha reparada debe proceder del día que se está reparando, nunca de
`datetime.now()` si existe una fecha explícita.

Ejemplo:

``` text
repair_eadriatic.bat 20260803
```

Debe reconstruir el 3 de agosto aunque se ejecute el 4.

------------------------------------------------------------------------

# Idempotencia

Dos ejecuciones consecutivas del mismo día deben producir:

``` text
Primera ejecución:
  registros añadidos > 0

Segunda ejecución:
  registros añadidos = 0
```

El JSONL debe quedar idéntico tras la segunda ejecución.

------------------------------------------------------------------------

# Datos incompletos

No inventar:

-   timestamps
-   match_id
-   perspective_id
-   rivales
-   resultados

Si un partido no contiene la información mínima para crear perspectivas
fiables:

-   no añadirlo al JSONL;
-   explicar claramente el motivo.

------------------------------------------------------------------------

# Salida esperada

Mostrar un resumen similar a:

``` text
TXT reparado: XX partidos
Perspectivas generadas: XX
Perspectivas nuevas añadidas: XX
Perspectivas duplicadas: XX
Partidos omitidos: XX
```

------------------------------------------------------------------------

# Pruebas obligatorias

Añadir pruebas para:

1.  reparación con partidos nuevos;
2.  actualización simultánea TXT + JSONL;
3.  creación correcta de perspectivas;
4.  estabilidad de `perspective_id`;
5.  deduplicado;
6.  segunda ejecución idempotente;
7.  fecha explícita;
8.  ejecución tras medianoche;
9.  timestamps UTC;
10. timezone correcta;
11. JSONL inexistente;
12. JSONL ya poblado;
13. JSONL malformado;
14. ausencia de modificaciones cuando no hay novedades.

------------------------------------------------------------------------

# Validación real

Usar un día donde previamente existan diferencias entre TXT y JSONL.

Mostrar:

``` text
Jugador
TXT antes
JSONL antes
JSONL después
Perspectivas añadidas
```

Si no pueden añadirse determinados partidos, explicar exactamente qué
información falta.

------------------------------------------------------------------------

# Restricciones

-   No modificar Current Streaks V2.
-   No modificar Coincident Matches.
-   No modificar H2H.
-   No trasladar esta reparación a GitHub Actions.
-   No editar manualmente los JSONL.
-   No inventar registros.
-   No hacer commit.
-   No hacer push.

------------------------------------------------------------------------

# Validación técnica

Ejecutar:

``` text
python -m unittest discover -s tests -v
python -m py_compile repair_eadriatic_day.py eadriatic_leagues.py match_history.py
git diff --check
git diff --stat
git status --short
```

------------------------------------------------------------------------

# Informe final

Responder con:

-   Auditoría del flujo local.
-   Archivos modificados.
-   Integración con `match_history.py`.
-   Gestión del cambio de día.
-   Idempotencia.
-   Pruebas añadidas.
-   Resultado de la suite.
-   Validación real.
-   Diferencias restantes.
-   `git diff --stat`.
-   `git status --short`.
-   Desviaciones.

Indicar expresamente si no hubo desviaciones funcionales.
