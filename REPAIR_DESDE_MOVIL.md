# Reparar Eadriatic desde el movil

Abre en el navegador e inicia sesion en GitHub:
https://github.com/dgonzalez13/esports-tracker-full/actions/workflows/repair-eadriatic.yml

1. En **Repair Eadriatic Day**, pulsa **Run workflow**.
2. Deja la rama **main**.
3. Deja la fecha vacia para reparar ayer en horario de Madrid, o indica
   una fecha YYYYMMDD (por ejemplo, 20261116). Tambien admite DDMMYYYY.
4. Pulsa **Run workflow** y espera a que la ejecucion termine en verde.
5. Recarga el tracker cuando termine la publicacion de la web.

Si no ves el boton, prueba la opcion ?Sitio de escritorio? de tu navegador.
Puedes guardar el enlace en la pantalla de inicio del movil.

El PC puede estar apagado. La tarea se ejecuta en GitHub y descarga los resultados
oficiales mediante Chromium, repara el TXT y el historial, recalcula el analisis de
Eadriatic y el de grupos, genera la web y sube los cambios al repositorio.
Usa un escritorio virtual para ejecutar el mismo navegador visible que el repair
local. No requiere conexion remota al PC ni instalar Python en el movil.

Comparte la cola con los otros workflows del tracker para evitar escrituras
simultaneas. Puede tardar varios minutos instalando el navegador y procesando datos.
No se programa automaticamente: se ejecuta cuando pulses el boton.

Si termina en rojo, abre el paso que ha fallado. Si la descarga falla, no se ejecutan
los pasos de analisis ni publicacion. En **Artifacts** se conservan durante siete
dias los archivos disponibles para revisar o recuperar una ejecucion fallida.
El acceso desde GitHub puede ser bloqueado por la web de origen; el escritorio
virtual no garantiza evitarlo. La primera ejecucion real debe verificar ese acceso.

Como alternativa manual ya existe **Import Eadriatic Manual Results**, que acepta
archivos HTML/MHTML guardados de BetsAPI/BsportsFan. Consulta
[MANUAL_EADRIATIC_IMPORT.md](MANUAL_EADRIATIC_IMPORT.md). Guardar esos archivos puede
requerir un navegador de escritorio; no es necesario para el nuevo workflow.
