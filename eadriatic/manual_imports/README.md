# Entrada de resultados manuales

Sube aquí las páginas HTML/MHTML de resultados de Eadriatic guardadas desde
BetsAPI/BsportsFan. Nombre recomendado: `20261019_p007.mhtml` (fecha y página).
La fecha real del partido se lee del contenido, no del nombre del archivo.

1. En GitHub, **Add file → Upload files** y guarda los cambios en `main`.
2. En **Actions → Import Eadriatic Manual Results → Run workflow**, deja
   `Aplicar importación` desmarcado para revisar primero, o márcalo para incorporar.
3. Si has reunido todas las páginas de un día de Madrid, indica esa fecha en
   `Días completos`, por ejemplo `2026-10-19`. Varios días se separan con comas.
   Esto reconstruye también los TXT diarios. Déjalo vacío para archivos parciales.
4. Comprueba que la ejecución que aplica los datos termina en verde. Los resultados
   quedan en el historial y los archivos procesados en `eadriatic/manual_import_log.json`.
5. Después puedes borrar los HTML/MHTML de esta carpeta; no borres el registro de
   importaciones. El historial conserva resultados y procedencia. La web se regenera
   en la misma ejecución que aplica la importación.

Solo se leen archivos `.html`, `.htm`, `.mhtml` y `.mht` directamente dentro de
esta carpeta. No se buscan archivos en otras carpetas ni se visita otra web.
Subir o borrar archivos no inicia la importación por sí solo: se activa con la
acción manual. El proceso diario oficial sigue funcionando como antes.

Los archivos ya procesados se reconocen por SHA-256, aunque cambien de nombre.
Los partidos presentes en la fuente oficial no vuelven a sumarse. Cuando esta se
restablezca, el repair habitual puede sustituir los provisionales por los oficiales.
