
from __future__ import annotations
import io
import contextlib
import traceback
import re
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, Any
from langchain_community.tools import DuckDuckGoSearchResults
_EXEC_GLOBALS: Dict[str, Any] = {}



def _ensure_exec_env():
    """Inicializa un entorno persistente para code_exec con librerías útiles."""
    global _EXEC_GLOBALS
    if not _EXEC_GLOBALS:
        _EXEC_GLOBALS = {}
        try:
            _EXEC_GLOBALS.update({"pd": pd, "plt": plt})
        except Exception:
            # Si fallan importaciones opcionales, seguimos; el usuario podría instalarlas luego.
            pass

# ---------------------------
# Helpers
# ---------------------------


def _sanitize_path_literals(code: str) -> str:
    """
    Detecta literales de cadena en el código que contienen backslashes (rutas Windows)
    y los convierte a una forma segura para que la ejecución vía exec no falle por
    "unicodeescape".


    - Si la cadena ya es raw (prefijo r o R) la deja intacta.
    - Si la cadena contiene backslashes simples (\) los duplica (\\) para
    escapar correctamente en el literal del código fuente.


    Esta función es conservadora pero suficientemente práctica para corregir
    automáticamente los casos comunes en los que el agente genera:
    que produce el error: (unicode error) 'unicodeescape' codec can't decode bytes...
    """


    def _repl(m: re.Match) -> str:
        prefix = m.group('prefix') or ''
        quote = m.group('q')
        body = m.group('body')
        # Si ya es raw (r'...') no hacemos nada
        if prefix.lower() == 'r':
            return m.group(0)
        # Reemplazamos cada backslash simple por dos backslashes
        # Si ya había pares '\\' no los tocamos (replace simple es seguro)
        new_body = body.replace('\\', '\\\\').replace('\\', '\\\\')
        # The double replace above keeps any existing escapes doubled again in a safe way.
        return f"{quote}{new_body}{quote}"


    # Busca literales '...' o "..." posiblemente con prefijo r/R
    pattern = re.compile(r"(?P<prefix>r|R)?(?P<q>['\"])(?P<body>.*?\\.*?)(?P=q)", flags=re.DOTALL)
    return pattern.sub(_repl, code)


# ---------------------------
# Tools: funciones ejecutables
# ---------------------------

def search_web(query: str) -> str:
    """
    Búsqueda de noticias en la web (DuckDuckGo).
    Devuelve texto con títulos/snippets/enlaces.
    """
    engine = DuckDuckGoSearchResults(backend="news")
    return engine.run(query)

def search_yf(query: str) -> str:
    """
    Búsqueda de noticias financieras (acotada a Yahoo Finance).
    """
    engine = DuckDuckGoSearchResults(backend="news")
    return engine.run(f"site:finance.yahoo.com {query}")

def code_exec(code: str) -> str:
    """
    Ejecuta código Python y devuelve la salida estándar (stdout).
    Pensado para uso LOCAL y de confianza.
    """
    _ensure_exec_env()

    try:
        safe_code = _sanitize_path_literals(code)
    except Exception:
        # En caso de fallo en la sanitización, mantenemos el código original
        safe_code = code

    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            exec(safe_code, _EXEC_GLOBALS, _EXEC_GLOBALS)
    except Exception as e:
        print(f"Error: {e}", file=output)
        print(traceback.format_exc(), file=output)
    return output.getvalue()

# ---------------------------
# Descriptores de tools (esquema OpenAI-compatible para Ollama)
# ---------------------------

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Buscar en la web (noticias) para obtener información actual.",
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "tópico o consulta a buscar en la web"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_yf",
            "description": "Buscar noticias financieras (sólo Yahoo Finance).",
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "tópico financiero a buscar"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "code_exec",
            "description": "Ejecuta código Python y devuelve la salida de consola.",
            "parameters": {
                "type": "object",
                "required": ["code"],
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "código Python a ejecutar"
                    }
                }
            }
        }
    }
]

# Mapa nombre->función para enrutar llamadas del modelo
TOOL_FUNCS = {
    "search_web": search_web,
    "search_yf": search_yf,
    "code_exec": code_exec,
}
