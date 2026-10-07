# Estadísticas por jugadores y equipos

Los nuevos partidos guardan `player_team` y `rival_team`. GT también aporta
`player_team_id` y `rival_team_id`; EADRIATIC publica los nombres dentro de
`Equipo (Jugador)`. Los calendarios conservan estos campos, aunque los encuentros
sin resultado no participan en las estadísticas.

Cada combinación liga / jugador A / equipo A / jugador B / equipo B cuenta por
separado. Los IDs de GT identifican los equipos cuando están disponibles; en los
demás casos se normalizan los nombres. La dirección inversa tiene sus propios
resultados. Un partido repetido no se cuenta dos veces para el mismo jugador.

V%, E% y D% usan únicamente los encuentros finalizados con ambos equipos
registrados. Se excluyen resultados futuros y partidos sin alguno de los equipos.
Los partidos antiguos mantienen su participación en el histórico general.
El historial se puede enriquecer al volver a recoger un partido existente, sin
duplicar sus perspectivas. No se adivinan equipos para partidos antiguos.

El bloque desplegable muestra los recuentos y la muestra por combinación,
ordenada de mayor a menor. La búsqueda admite varios términos simultáneos para
filtrar jugador, rival, equipo y liga. Los porcentajes con pocas observaciones
son descriptivos y pueden variar mucho.

La primera recogida del 7 de octubre de 2026 añadió equipos a una muestra de
10 encuentros de cada liga. Los colectores habituales continúan la recogida
desde la siguiente ejecución del job.
