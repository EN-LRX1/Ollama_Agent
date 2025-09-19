from __future__ import annotations
import ollama
import os
import sys
import traceback
from typing import List, Dict, Any
from tools import TOOL_SPECS, TOOL_FUNCS

#llm = "deepseek-r1:8b" # !! Definir bien el nombre
#stream = ollama.generate(model=llm, prompt='''what time is it?''', stream=True)
#for chunk in stream:
    #print(chunk['response'], end='', flush=True)

# Usa un modelo con tool-calling Nativo:
#   - Recomendado: 'qwen2.5'  (ligero y capaz)
#   - Alternativa estable: 'llama3.1:8b'
#   - Si quieres DeepSeek R1 con tools, usa una variante comunitaria como:
#         'MFDoom/deepseek-r1-tool-calling:8b'


_raw_model = os.environ.get("MODEL")
if _raw_model is None:
    print("[DEBUG] No hay variable de entorno MODEL; se usará el valor por defecto 'qwen3:8b'.")
else:
    print(f"[DEBUG] Variable de entorno MODEL detectada: {_raw_model!r}")

def _looks_like_model_name(name: str) -> bool:
    """
    Reglas heurísticas simples para decidir si una cadena puede ser
    un nombre de modelo válido para Ollama (p. ej. 'qwen3:8b').
    - Rechaza cadenas numéricas puras (p.ej. '5450').
    - Rechaza rutas o cadenas con separadores de fichero.
    - Acepta si contiene letras y no contiene caracteres sospechosos.
    """
    if not name or name.isdigit():
        return False
    # No aceptamos rutas ni ids con barras
    if any(ch in name for ch in ("/", "\\", ":", " ")) and ":" not in name:
        # si tiene ":" probablemente es un modelo (ej. qwen3:8b)
        # pero si tiene espacios o barras lo descartamos
        return False
    # Si tiene caracteres no alfanuméricos raros, descartamos
    for bad in ('$', '%', '@', '#'):
        if bad in name:
            return False
    # Heurística final: al menos una letra
    return any(c.isalpha() for c in name)


if _raw_model and _looks_like_model_name(_raw_model):
    MODEL = _raw_model
    print(f"[INFO] Usando MODEL desde entorno: {MODEL!r} (validados).")
else:
    if _raw_model is not None:
        print(f"[WARN] Ignorando MODEL={_raw_model!r} porque no parece un nombre de modelo válido. Usando 'qwen3:8b' por defecto.")
    MODEL = "qwen3:8b"

SYSTEM_PROMPT = (
    "Eres un asistente experto con acceso a herramientas para buscar información actual y ejecutar código Python.\n"
    "Decide con criterio CUÁNDO usar herramientas. Si no es necesario, responde directamente y en español.\n"
    "Si el usuario proporciona una ruta CSV con el formato 'path = <ruta>' entonces:\n"
    "  1) Ejecuta EXACTAMENTE: df = pd.read_csv(path); print(df.head())\n"
    "  2) Si generas gráficos, añade SIEMPRE 'plt.show()' al final del código.\n"
)

MEMO = "Recuerda: el DataFrame principal se llama 'df'. Añade 'plt.show()' al final de cada gráfico."

SEARCH_TOOLS = {"search_web", "search_yf"}
CODE_TOOLS = {"code_exec"}

def ask_llm_generate(model: str, prompt: str) -> str:
    """Conveniencia: una sola pasada de generación (no streaming)."""
    res = ollama.generate(model=model, prompt=prompt)
    return res.get("response", "")

def summarize_for_user(question: str, tool_output: str) -> str:
    prompt = (
        f"Pregunta del usuario: {question}\n\n"
        "Resume objetivamente lo relevante del siguiente texto para responder la pregunta. "
        "Sé conciso (máx. 6-8 líneas) e incluye 1-2 fuentes si están en el texto.\n\n"
        f"=== TEXTO ===\n{tool_output}"
    )
    return ask_llm_generate(MODEL, prompt)

def call_agent(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Invoca al modelo con tools habilitadas y devuelve la respuesta cruda."""
    return ollama.chat(model=MODEL, messages=messages, tools=TOOL_SPECS, options={"num_ctx": 2048})

def handle_tool_calls(agent_res: Dict[str, Any], messages: List[Dict[str, Any]], user_input: str) -> bool:
    msg = agent_res.get("message", {})
    tool_calls = msg.get("tool_calls", [])
    if not tool_calls:
        return False

    printed_any = False
    web_summaries: List[str] = []

    for call in tool_calls:
        try:
            name = call["function"]["name"]
            args = call["function"]["arguments"]
        except Exception:
            print("[!] tool_call mal formada:", call)
            continue

        func = TOOL_FUNCS.get(name)
        if not func:
            print(f"[!] Tool no encontrada: {name}")
            continue

        print(f" [·] Ejecutando tool: {name} args={args}")
        try:
            output = func(**args)
        except Exception as e:
            output = f"[ERROR ejecutando {name}] {e}\n{traceback.format_exc()}"

        messages.append({"role": "tool", "tool_name": name, "content": output})

        if name in SEARCH_TOOLS:
            summary = summarize_for_user(user_input, output)
            web_summaries.append(summary)
        elif name in CODE_TOOLS:
            print("\n[ Salida ejecución ]\n")
            print(output if output.strip() else "(sin salida)")
            printed_any = True

    if web_summaries:
        print("\n[ Resumen de resultados ]\n")
        print("\n\n".join(web_summaries))
        messages.append({"role": "assistant", "content": "\n\n".join(web_summaries)})
        printed_any = True

    return printed_any

# -------------------
# Manejo/selección de modelo
# -------------------
def try_model_probe(model_name: str) -> bool:
    """
    Prueba de forma robusta si un modelo responde.
    - Intenta primero una llamada no interactiva (stream=False).
    - Si falla, intenta una llamada con stream=True (la que tú probaste y sí funcionó).
    - Imprime el error completo para depuración (es lo que faltaba antes).
    """
    if not model_name:
        return False

    import traceback
    # 1) intento rápido (no-stream)
    try:
        res = ollama.generate(model=model_name, prompt="Hola", stream=False)
        # Si no lanza excepción, asumimos que el modelo está presente
        print("  -> probe: respuesta (no-stream) OK")
        return True
    except Exception as e:
        print("  -> probe (no-stream) falló:", e)
        traceback.print_exc()

    # 2) intento alternativo (stream), porque en tu test comentaste que stream=True sí funcionó
    try:
        # Hacemos un intento con stream=True (consumir poco)
        stream = ollama.generate(model=model_name, prompt="Hola", stream=True)
        # Si devuelve un iterador/stream, consumimos el primer chunk con seguridad
        try:
            first = next(iter(stream))
            print("  -> probe: respuesta (stream) OK (primer chunk recibido)")
            return True
        except Exception:
            # quizá retorna un dict simple en tu versión, así que probamos acceder a 'response'
            if isinstance(stream, dict) and stream.get("response"):
                print("  -> probe: respuesta (stream como dict) OK")
                return True
            # si no podemos leer, lo consideramos fallido pero ya lo registramos arriba
            print("  -> probe: stream no iterable / sin 'response'")
    except Exception as e:
        print("  -> probe (stream) falló:", e)
        traceback.print_exc()

    return False


def select_working_model(candidates: List[str]) -> str | None:
    seen = []
    for c in candidates:
        if not c:
            continue
        if c in seen:
            continue
        seen.append(c)
        print(f"[Comprobando modelo] {c} ...", end=" ")
        ok = try_model_probe(c)
        if ok:
            print("OK")
            return c
        else:
            print("NO disponible")
    return None

def print_model_help(model_name: str):
    print("\n[ERROR] No se encontró ningún modelo válido entre los candidatos.")
    print("  Sugerencias:")
    print("   - Ejecuta `ollama list` para ver modelos disponibles en tu host.")
    print("   - Pulsa (pull) un modelo que quieras usar: `ollama pull qwen3:8b`")
    print(f"   - O exporta otra variable de entorno MODEL antes de ejecutar (ej: MODEL=qwen3:8b).")
    print()

# ---------------------------
# Bucle principal
# ---------------------------
def main():
    global MODEL

    # Lista de candidatos razonable: primero el que venga en env, luego fallbacks comunes.
    candidates = [MODEL, "qwen3:8b", "deepseek-r1:8b", "qwen2.5", "llama3.1:8b"]

    chosen = select_working_model(candidates)
    if not chosen:
        print_model_help(MODEL)
        sys.exit(1)

    MODEL = chosen
    print(f"\nUsando modelo: {MODEL}\n")
    print("Escribe tu consulta. También puedes indicar:  path = <ruta/al/archivo.csv>\n(Escribe 'quit' para salir.)")

    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    data_mode_initialized = False

    while True:
        try:
            user = input(" > ").strip()
        except EOFError:
            break

        if not user:
            continue
        if user.lower() in {"quit", "exit"}:
            break

        inject = ""
        if ("path =" in user) or data_mode_initialized:
            data_mode_initialized = True
            inject = MEMO + "\n"

        messages.append({"role": "user", "content": inject + user})

        try:
            agent_res = call_agent(messages)

            used_tools = handle_tool_calls(agent_res, messages, user)
            if used_tools:
                continue

            content = agent_res.get("message", {}).get("content", "")
            if content:
                print("\n" + content + "\n")
                messages.append({"role": "assistant", "content": content})
            else:
                print("(sin respuesta del modelo)")

        except KeyboardInterrupt:
            print("\n[Interrumpido por el usuario]")
            continue
        except Exception as e:
            err_text = str(e).lower()
            if "not found" in err_text and "model" in err_text:
                print_model_help(MODEL)
                break
            else:
                print(f"[ERROR] {e}")
                traceback.print_exc(file=sys.stdout)

if __name__ == "__main__":
    main()
