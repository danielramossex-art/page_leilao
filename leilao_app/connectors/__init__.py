from .bb import BancoBrasilConnector
from .caixa import CaixaConnector
from .itau import ItauConnector
from .leiloeiros import LeiloeirosConnector
from .santander import SantanderConnector


def get_connectors():
    return [
        CaixaConnector(),
        BancoBrasilConnector(),
        SantanderConnector(),
        ItauConnector(),
        LeiloeirosConnector(),
    ]
