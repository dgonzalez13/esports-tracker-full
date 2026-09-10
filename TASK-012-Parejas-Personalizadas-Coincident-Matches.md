# Parejas personalizadas y enfrentamientos directos

## Configuración

Al final de `tracked_players.txt` hay diez líneas disponibles:

```text
@COINCIDENT_PAIR||
@COINCIDENT_PAIR||
@COINCIDENT_PAIR||
@COINCIDENT_PAIR||
@COINCIDENT_PAIR||
@COINCIDENT_PAIR||
@COINCIDENT_PAIR||
@COINCIDENT_PAIR||
@COINCIDENT_PAIR||
@COINCIDENT_PAIR||
```

Rellena cada línea con exactamente dos jugadores. Ejemplo (no activado):

```text
@COINCIDENT_PAIR||GT|William|GREEN||EADRIATIC|Dexter|RED
```

Para desactivar una pareja sin borrar su configuración, añade `*` delante:

```text
*@COINCIDENT_PAIR||GT|William|GREEN||EADRIATIC|Dexter|RED
```

Al quitar el `*` vuelve a activarse. Se permiten espacios alrededor del asterisco.
Las líneas desactivadas se ignoran por completo, incluso si están incompletas,
no cuentan para el máximo de diez parejas activas y se conservan al actualizar
los grupos de jugadores.

Se admiten GT y EADRIATIC, y los indicadores GREEN (victoria) y RED
(derrota). Liga e indicador no distinguen mayúsculas. Las líneas vacías no
cuentan. Se rechazan más de diez parejas, parejas duplicadas incluso en
orden inverso, un jugador contra sí mismo y formatos o indicadores inválidos;
el error identifica la línea.

El bloque `Custom Pairs` muestra exclusivamente las parejas escritas, sin
generar combinaciones entre ellas. No exige estar entre los ocho candidatos
automáticos, superar un porcentaje ni tener seis coincidencias. Los jugadores
no necesitan ocupar una posición en los grupos del TXT: se busca su historial
por liga y nombre. Sus indicadores son los configurados, independientemente
del indicador automático. Se conserva la ventana de ocho horas y el máximo
de treinta minutos. Las exclusiones de jugadores no apostables (`*`) siguen
aplicándose al historial. SELECT y EXCLUDE mantienen su función sobre los
candidatos del bloque original; no sustituyen estas parejas explícitas.

El porcentaje Combined usa los porcentajes de victoria/derrota de cada jugador
en la ventana, según el indicador configurado. Las rachas se calculan a partir
de las coincidencias completas. Una pareja sin coincidencias permanece visible.
La actualización de grupos conserva las directivas.

## Enfrentamientos directos en parejas

La regla se aplica tanto a parejas originales como personalizadas:

- GREEN/GREEN o RED/RED: se eliminan ambas perspectivas del enfrentamiento
  antes de emparejar; no cuentan como acierto ni fallo.
- GREEN/RED: se reserva la perspectiva del jugador GREEN y se empareja con
  el siguiente partido estrictamente posterior del jugador RED dentro del
  límite de tiempo. No se busca un resultado favorable: victorias y empates
  también se incluyen y producen fallos cuando corresponda.
- Si falta el siguiente partido o supera el límite, no hay coincidencia completa.
- Los partidos reservados no se reutilizan en otras filas de esa pareja.
  El resto sigue el emparejamiento cronológico anterior. La reserva tiene
  prioridad sobre los emparejamientos ordinarios.

Este cambio de enfrentamientos directos afecta al motor de parejas; el motor
independiente de tríos y grupos de cuatro conserva sus reglas existentes.
