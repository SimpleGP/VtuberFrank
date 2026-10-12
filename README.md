# Cargar FrankVtuber en OBS

1. Descarga este repositorio con **Code → Download ZIP** y extrae su contenido en `D:\FrankVtuber`. Si Windows pide Python, instala Python 3.12 o posterior con **Add Python to PATH**.
2. Haz doble clic en **Iniciar FrankVtuber.vbs**. Espera a que termine la primera instalación y se abra el panel local. Déjalo funcionando mientras uses el avatar.
3. En tu escena de OBS, ve a **Fuentes → + → Navegador** y crea una fuente llamada **Frank · Richard**.
4. Introduce esta URL: **http://127.0.0.1:18766/avatar.html**. Configura **Ancho: 800**, **Alto: 800** y **FPS personalizados: 30**. Mantén desactivados **Cerrar la fuente cuando no sea visible** y **Actualizar el navegador cuando la escena se active**.
5. Deja el CSS personalizado predeterminado para el fondo transparente. Coloca la fuente sobre la captura del juego. En un lienzo de **1920 × 1080**, puedes usar **posición X: 1420, Y: 560** y ajustar el avatar a **490 × 490**.
6. En el panel, pulsa **Automático**. Con Overwatch al frente, pulsa la tecla física **encima de Tab y a la izquierda del 1** (`º` o `` ` ``). Tras **0,5 segundos** revisará únicamente el retrato de abajo a la izquierda y cambiará de skin. Si no reconoce un personaje o no hay retrato disponible, volverá a **Richard · Original**, con sus PNG de boca abierta y cerrada. También puedes elegir la skin directamente en el panel.
7. Habla para alternar la boca abierta y cerrada. Conserva tu fuente de micrófono y su configuración actual en OBS; este proyecto no las modifica. No hay animaciones ni seguimiento de WASD/mouse, ni fuente de chat.
8. Si otra apariencia del héroe no se reconoce, abre **Usar el retrato de otra skin**, elige el personaje y añade una captura del juego. Para la gladiadora de Junker Queen, añade su retrato o elige esa skin manualmente.
9. Al terminar, pulsa **Cerrar servidor** en el panel. Para volver a usar el avatar, abre de nuevo **Iniciar FrankVtuber.vbs**.

Usa la URL local del paso 4 en la fuente de navegador de OBS. El avatar del directo necesita que el iniciador local permanezca abierto.
