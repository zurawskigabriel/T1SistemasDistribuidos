import json
from typing import Any


def SerializarMensagem(mensagem: dict[str, Any]) -> bytes:
    """Serializa a mensagem em JSON delimitado por nova linha."""
    return (json.dumps(mensagem, ensure_ascii=True) + "\n").encode("utf-8")


def DesserializarMensagem(linha: str) -> dict[str, Any]:
    """Converte uma linha JSON em dicionario de mensagem."""
    return json.loads(linha)
