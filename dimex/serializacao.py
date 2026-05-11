import json
from typing import Any

def SerializarMensagem(mensagem: dict[str, Any]) -> bytes:
    return (json.dumps(mensagem, ensure_ascii=True) + "\n").encode("utf-8")

def DesserializarMensagem(linha: str) -> dict[str, Any]:
    return json.loads(linha)
