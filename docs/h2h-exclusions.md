# Exclusiones manuales de enfrentamientos destacados

Añade una línea al final de `tracked_players.txt` por cada dirección que quieras ocultar:

```text
@H2H_EXCLUDE||GT|Thug|Troy
```

Sustituye los nombres por jugadores del grupo actual. La liga es `GT` o `EADRIATIC`.
No necesitas indicar el número del grupo: se deduce de los jugadores actuales.
Puedes añadir tantas líneas como exclusiones quieras.

Este ejemplo oculta apostar por Thug frente a Troy; no oculta Troy frente a Thug.
Solo afecta a la tabla de enfrentamientos destacados. Para excluir la dirección
contraria, añade otra línea intercambiando los dos nombres.

La exclusión entra en vigor cuando se regenera la web. Para recuperarla, elimina
la exclusión dejando `@H2H_EXCLUDE||` y regenera la web. Una o varias líneas vacías
no excluyen ninguna pareja; si hay además líneas completas, estas sí se aplican.
El job de actualizar jugadores vacía automáticamente las exclusiones de cada grupo
actualizado y regenera el panel, aunque los nombres del grupo no cambien. Conserva
el número de líneas `@H2H_EXCLUDE||`. Las exclusiones de grupos no actualizados
se conservan con sus nombres.

El formato JSON anterior sigue siendo compatible y el job lo convierte al formato
simple al actualizar el archivo. No se requieren tokens en la web.

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
