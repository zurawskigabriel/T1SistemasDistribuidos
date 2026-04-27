from enum import Enum


class TipoMensagem(Enum):
    Pedido = "PEDIDO"
    Resposta = "RESPOSTA"
    Marker = "MARKER"


class EstadoDimex(Enum):
    NaoQueroSc = "NAO_QUERO_SC"
    QueroSc = "QUERO_SC"
    EstouSc = "ESTOU_SC"
