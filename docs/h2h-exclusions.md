# Exclusiones manuales de enfrentamientos destacados

Añade una línea al final de `tracked_players.txt` por cada dirección que quieras ocultar:

```text
@H2H_EXCLUDE||{"league":"GT","group":1,"player":"Thug","rival":"Troy"}
```

Sustituye los nombres por jugadores del grupo actual. `league` es `GT` o `EADRIATIC`.
`group` es el número del bloque de cinco jugadores dentro de esa liga: 1 para los
primeros cinco y 2 para los siguientes cinco. Los huecos vacíos también cuentan.

Este ejemplo oculta apostar por Thug frente a Troy; no oculta Troy frente a Thug.
Solo afecta a la tabla de enfrentamientos destacados. Para excluir la dirección
contraria, añade otra línea intercambiando `player` y `rival`.

La exclusión entra en vigor cuando se regenera la web. Para recuperarla, elimina
la línea y regenera la web. El job de actualizar jugadores elimina automáticamente
las exclusiones de cada grupo actualizado y regenera el panel, aunque los nombres
del grupo no cambien. Las exclusiones de grupos no actualizados se conservan.

Las líneas antiguas con `members` siguen siendo compatibles. No hace falta ese
campo en las nuevas exclusiones manuales. No se requieren tokens en la web.
