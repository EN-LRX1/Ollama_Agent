# Ollama_Agent
## README — Agente de IA (cliente Ollama + herramientas)

Este repositorio contiene un agente conversacional que usa Ollama (local) como LLM y un conjunto de tools (definidas en tools.py) para búsquedas web, ejecución de código y operaciones auxiliares.
El README explica cómo crear el entorno, instalar dependencias y Ollama, preparar modelos y arrancar el agente. También describe qué hace el agente y cómo usarlo.

## Resumen rápido (one-liner)

Crea un venv Python, instala dependencias (pip install -r requirements.txt).

Instala Ollama (CLI / servidor local) y baja un modelo (ollama pull qwen3:8b). 
ollama.com
+1

Define MODEL si quieres un modelo distinto, y ejecuta python agent.py.

Contenido del repositorio (lo relevante)

agent.py — script principal (el código que compartiste).

tools.py — definiciones de TOOL_SPECS y TOOL_FUNCS (búsqueda web, ejecución de código, guardado de archivos, etc.).

requirements.txt — paquetes Python necesarios (te muestro un ejemplo más abajo).

### Requisitos mínimos

Python 3.9+ (recomendado 3.10/3.11).

Espacio en disco para modelos (depende del modelo; qwen3:8b suele ocupar varios GB).

Ollama (daemon/CLI) instalado y en ejecución en la máquina local. 
ollama.com
+1

1) Crear entorno Python e instalar dependencias


ollama>=0.4.0
pandas
numpy
matplotlib
langchain-community
wikipedia-api


Comandos:

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt


2) Instalar Ollama (CLI / servidor local)


Comandos útiles de Ollama:

ollama list — lista modelos instalados localmente.

ollama pull <modelo> — descarga/pulsa un modelo (ej.: ollama pull qwen3:8b).

ollama serve — arranca el servicio (en algunas versiones el CLI inicia el servicio por sí mismo).


ollama pull qwen3:8b
ollama list   



4) Ejecutar el agente



Flujo esperado:

El agente intentará detectar y seleccionar (probe) un modelo de la lista de candidatos (MODEL, qwen3:8b, deepseek-r1:8b, qwen2.5, llama3.1:8b).

Si se encuentra un modelo válido imprime Usando modelo: <modelo> y entra en el bucle interactivo.

En el prompt puedes escribir consultas; el agente formará mensajes, llamará al LLM local vía ollama.chat y, si el modelo solicita tool-calls, ejecutará las tools definidas en tools.py.

Ejemplo de uso interactivo:

 > Inserte su consulta aquí: Crea un DataFrame con 100 filas aleatorias y guarda hist.png


Si el modelo no está disponible verás recomendaciones como ollama list o ollama pull (el script ya imprime sugerencias). 
GitHub

5) ¿Qué hace este agente? (explicación de alto nivel)

Selección de modelo: prueba varios nombres de modelo con ollama.generate/ollama.chat para ver cuál responde y selecciona el primero que funciona.

Prompt system: incluye instrucciones para que el LLM actúe como asistente experto y use herramientas cuando haga falta.

Soporte de tools: el agente carga TOOL_SPECS y TOOL_FUNCS desde tools.py y pasa esos descriptores a ollama.chat para habilitar tool-calling nativo. Cuando el modelo solicita una herramienta:

handle_tool_calls ejecuta la función Python correspondiente,

añade la salida como mensaje con role: "tool" y reenvía la conversación al modelo para continuar su razonamiento.

Modo data: si el usuario indica path = <ruta> el agente inyecta un memo con instrucciones para cargar el CSV (df = pd.read_csv(path) y print(df.head())) y obliga a usar plt.show() si genera gráficos.

Resúmenes web: si se usan las herramientas de búsqueda, el agente resume resultados llamando de nuevo al modelo con el texto obtenido.

En resumen: es un agente conversacional que puede ejecutar herramientas (búsquedas, ejecución de código, guardado) y mezclar LLM + I/O real.

6) Herramientas típicas en tools.py (ejemplos)

Tu tools.py suele incluir (según tu descripción previa):

search_web(query) — usa un motor (DuckDuckGo, news, etc.) para obtener snippets.

search_yf(query) — búsqueda enfocada en Yahoo Finance.

wikipedia_lookup(query) — resumen Wikipedia.

code_exec(code) — ejecuta código Python en un sandbox local y devuelve la salida.

save_text_to_file(data, filename, b64=False) — guarda texto o contenidos base64.

Verifica tools.py para conocer parámetros exactos y comportamiento (timeout, sandboxing). Si code_exec está sin aislamiento fuerte, ten cuidado con código no confiable.

7) Ejemplos de prompts / pruebas rápidas

Smoke test (comprobación code_exec):
Crea un script Python que imprima "Hola desde code_exec" y cree un archivo hola.txt con "Generado por el agente". Ejecuta y devuelve consola.

Data + plot:
Genera un DataFrame con 100 filas aleatorias, calcula medias, dibuja histograma de la primera columna y guarda hist1.png. Devuelve la salida.

Estas son las pruebas que hemos usado para verificar flujo de tools y guardado de artefactos.

8) Resolución de problemas comunes

model not found / No se encontró modelo válido

Ejecuta ollama list para ver modelos locales.

Si falta, descarga con ollama pull qwen3:8b. 
ollama.com
+1

ollama no encontrado

Asegúrate de que el binario está instalado y en PATH (ollama version). Instálalo según la web oficial. 
ollama.com

Problemas con la librería Python ollama

Si import ollama falla, instala el paquete PyPI: pip install ollama. La librería requiere que el servicio local de Ollama esté corriendo. 
PyPI

Dependencias faltan (ModuleNotFoundError)

Activa tu venv y ejecuta pip install -r requirements.txt.

code_exec no crea archivos accesibles

Revisa path de trabajo del sandbox y si code_exec devuelve files en base64 (si implementaste ese comportamiento). Considera cambiar save_text_to_file para aceptar b64=True.

9) Seguridad y buenas prácticas

Nunca ejecutes código no confiable sin aislamiento. Si tu code_exec ejecuta exec(...) dentro del mismo proceso, es riesgoso. Usa sandboxing (proceso hijo, contenedor o límites de recurso).

Usa timeouts y límites de memoria en code_exec.

Si vas a exponer el agente en una red, añade autenticación y logging.

Mantén modelos grandes en sistemas con suficiente RAM / disco; los modelos pueden consumir decenas de GB. 
ollama.com

10) Mejoras sugeridas (rápidas)

Hacer que code_exec devuelva JSON con stdout, traceback, files (base64).

Persistir automáticamente los archivos devueltos por code_exec usando save_text_to_file(..., b64=True).

Añadir una tool run_pytest para ejecutar tests automáticamente.

Forzar en SYSTEM_PROMPT que el modelo muestre el código antes de ejecutar (reduce errores).

11) Referencias útiles / lectura

Página de descarga e instalación de Ollama (install script y binarios). 
ollama.com

Página del modelo Qwen3 (ej. qwen3:8b) en la librería de modelos Ollama. 
ollama.com

Repo / docs CLI de Ollama (comandos list, pull, run, etc.). 
GitHub

PyPI: paquete ollama (cliente Python). 
PyPI

12) Ejemplo de flujo completo (comandos copy-paste)
# 1) preparar venv e instalar deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2) instalar Ollama

# 3) arrancar (si tu versión requiere 'serve')
ollama serve &     

# 4) bajar modelo
ollama pull qwen3:8b
ollama list

# 5) ejecutar agente
export MODEL=qwen3:8b
python agent.py


