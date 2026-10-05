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

## Diferencia mínima de victorias

Por defecto, no se resaltan ni se muestran en destacados los casos con diferencia
histórica `V% de A − V% de B` menor que −10 puntos. Exactamente −10 sí se admite.
Se usan los recuentos históricos completos, incluyendo empates en el denominador.

Puedes cambiar el límite añadiendo esta línea (una sola) al archivo:

```text
@H2H_MIN_GAP||-5
```

−5 es más restrictivo: también elimina las diferencias entre −10 y −5. Para volver
al límite inicial, cambia el valor a −10 o elimina la línea. El job conserva esta
configuración global al actualizar los grupos. No afecta a las tablas estadísticas.
