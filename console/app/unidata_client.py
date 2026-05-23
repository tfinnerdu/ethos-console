"""Thin wrapper around uopy (Rocket Software's UniData/UniVerse Python API).

Lives behind app.extensions['unidata_client'] so phase3 routes call through
one seam — the real client when UNIDATA_HOST + UNIDATA_ACCOUNT are set,
MockUnidataClient when CONSOLE_MOCK_MODE=true.
"""
try:
    import uopy as _uopy
    _UOPY_AVAILABLE = True
except ImportError:
    _UOPY_AVAILABLE = False


_PARSE_SKIP = {"LIST", "VOC", "records listed", "@ID", "....."}


def _parse_list_ids(response: str) -> list[str]:
    ids = []
    for line in response.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(skip in line for skip in _PARSE_SKIP):
            continue
        ids.append(line)
    return ids


class UnidataClient:
    def __init__(self, host: str = "", port: int = 31438, user: str = "", password: str = "", account: str = ""):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._account = account

    def is_configured(self) -> bool:
        return bool(_UOPY_AVAILABLE and self._host and self._account)

    def _connect(self):
        return _uopy.connect(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            account=self._account,
        )

    def run_command(self, statement: str) -> str:
        with self._connect() as _:
            cmd = _uopy.Command(statement)
            cmd.run()
            return cmd.response

    def list_files(self) -> list[str]:
        response = self.run_command("LIST VOC WITH F1 = 'F' BY @ID")
        return _parse_list_ids(response)

    def call_subroutine(self, name: str, args: list) -> dict:
        n_args = len(args)
        with self._connect() as _:
            sub = _uopy.Subroutine(name, n_args)
            for i, arg in enumerate(args):
                if arg.get("direction", "in").lower() in ("in", "inout"):
                    sub.args[i] = str(arg.get("value", ""))
            sub.call()
            return {
                "subroutine": name,
                "args": [
                    {
                        "index": i,
                        "label": arg.get("label", f"ARG{i + 1}"),
                        "direction": arg.get("direction", "in"),
                        "value": str(sub.args[i]),
                    }
                    for i, arg in enumerate(args)
                ],
            }
