# INFRASTRUCTURE
import json


# FUNCTIONS

class _FakeAsyncClient:

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
    content = "\n".join(rows)
    return f'<html><script>self.__next_f.push([1,{json.dumps(content)}])</script></html>'


class _RaisingAsyncClient:

    def __init__(self, exc: Exception):
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, **kwargs):
        raise self._exc


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"", text: str = None):
        self.status_code = status_code
        self.content = content
        self.text = text if text is not None else content.decode("utf-8", errors="ignore")
