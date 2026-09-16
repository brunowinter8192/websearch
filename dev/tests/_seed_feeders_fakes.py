import json


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"", text: str = None):
        self.status_code = status_code
        self.content = content
        self.text = text if text is not None else content.decode("utf-8", errors="ignore")


class _FakeAsyncClient:
    """Routes GET requests by exact URL; unmapped URLs come back 404."""

    def __init__(self, routes: dict):
        self._routes = routes

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, **kwargs):
        return self._routes.get(url, _FakeResponse(404))


def _xml(body: str) -> bytes:
    return f'<?xml version="1.0" encoding="UTF-8"?>{body}'.encode()


def _next_data_html(payload: dict) -> str:
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script></html>'


def _rsc_html(rows: list) -> str:
    # One push call carrying every row, JSON-escaped exactly as a real page embeds it
    content = "\n".join(rows)
    return f'<html><script>self.__next_f.push([1,{json.dumps(content)}])</script></html>'
