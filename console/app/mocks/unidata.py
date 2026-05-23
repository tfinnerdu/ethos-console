"""Mock UnidataClient. Active only when CONSOLE_MOCK_MODE=true."""
from app.unidata_client import UnidataClient
from . import fixtures


class MockUnidataClient(UnidataClient):
    def __init__(self):
        super().__init__(host="mock", account="mock")

    def is_configured(self) -> bool:
        return True

    def run_command(self, statement: str) -> str:
        return fixtures.unidata_command_response(statement)

    def list_files(self) -> list[str]:
        return list(fixtures.UNIDATA_FILE_LIST)

    def call_subroutine(self, name: str, args: list) -> dict:
        return fixtures.unidata_subroutine_result(name, args)
