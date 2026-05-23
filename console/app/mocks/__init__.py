"""CONSOLE_MOCK_MODE provider package.

Imported only by app.__init__ when CONSOLE_MOCK_MODE=true. Real-mode code
paths never touch this package.
"""
from .ethos import MockEthosClient
from .colleague_api import MockColleagueApiClient
from .conductor import MockConductorClient
from .unidata import MockUnidataClient
from .cn_repository import MockCnRepository

__all__ = [
    "MockEthosClient",
    "MockColleagueApiClient",
    "MockConductorClient",
    "MockUnidataClient",
    "MockCnRepository",
]
