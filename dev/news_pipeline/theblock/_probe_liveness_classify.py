# INFRASTRUCTURE

import asyncio
import re
import time

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import (
    RequestException,
    Timeout,
    ProxyError,
    SSLError,
)
from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError
from curl_cffi.const import CurlECode

CHECK_URL   = "http://ipv4.icanhazip.com"
_IP_RE      = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

# FUNCTIONS

async def check_proxy(
    session: AsyncSession,
    sem: asyncio.Semaphore,
    proto: str,
    host_port: str,
    connect_s: float,
    read_s: float,
) -> dict:
    proxy_proto = "socks5h" if proto == "socks5" else proto
    proxy_url   = f"{proxy_proto}://{host_port}"

    async with sem:
        t0      = time.monotonic()
        elapsed = 0.0
        try:
            resp    = await asyncio.wait_for(
                session.get(
                    CHECK_URL,
                    proxy=proxy_url,
                    timeout=(connect_s, read_s),
                    allow_redirects=False,
                ),
                timeout=connect_s + read_s + 2.0,
            )
            elapsed = time.monotonic() - t0
            body    = resp.text.strip() if resp.text else ""

            if resp.status_code == 200 and _IP_RE.match(body):
                return _res(proto, host_port, True,  "alive",       "",                   elapsed)
            if resp.status_code == 200:
                return _res(proto, host_port, False, "bad_body",    body[:80],            elapsed)
            return     _res(proto, host_port, False, "http_non200", f"status={resp.status_code}", elapsed)

        except asyncio.TimeoutError:
            elapsed = time.monotonic() - t0
            return _res(proto, host_port, False, "hard_timeout",
                        f"asyncio.wait_for exceeded at {elapsed:.2f}s", elapsed)
        except RequestException as e:
            elapsed = time.monotonic() - t0
            bucket, detail = classify_error(e, elapsed, connect_s, read_s)
            return _res(proto, host_port, False, bucket, detail, elapsed)
        except Exception as e:
            elapsed = time.monotonic() - t0
            return _res(proto, host_port, False, "unknown",
                        f"{type(e).__name__}: {str(e)[:120]}", elapsed)


def _res(proto: str, host_port: str, alive: bool, bucket: str, detail: str, elapsed: float) -> dict:
    return {"proto": proto, "host_port": host_port,
            "alive": alive, "bucket": bucket, "detail": detail, "elapsed": elapsed}


def classify_error(
    exc: RequestException, elapsed_s: float, connect_s: float, read_s: float
) -> tuple[str, str]:
    code    = getattr(exc, "code", 0)
    msg     = str(exc)
    total_s = connect_s + read_s

    if isinstance(exc, Timeout):
        slack = 0.5
        if elapsed_s <= connect_s + slack:
            return "connect_timeout", f"elapsed={elapsed_s:.2f}s"
        if elapsed_s >= total_s - slack:
            return "read_timeout", f"elapsed={elapsed_s:.2f}s"
        if "Connection timed out" in msg:
            return "connect_timeout", f"msg-text elapsed={elapsed_s:.2f}s"
        if "Operation timed out" in msg:
            return "read_timeout", f"msg-text elapsed={elapsed_s:.2f}s"
        return "unknown", (
            f"Timeout unclassified elapsed={elapsed_s:.2f}s "
            f"connect_limit={connect_s}s total_limit={total_s}s msg={msg!r}"
        )

    if int(code) in (CurlECode.COULDNT_RESOLVE_PROXY, CurlECode.COULDNT_RESOLVE_HOST):
        return "resolve_error", f"code={int(code)} {msg[:80]}"

    if isinstance(exc, ProxyError) or int(code) in (CurlECode.GOT_NOTHING, CurlECode.WEIRD_SERVER_REPLY):
        return "proxy_handshake_error", f"code={int(code)} {msg[:80]}"

    if isinstance(exc, CurlConnectionError):
        return "connection_refused", f"code={int(code)} {msg[:80]}"

    if isinstance(exc, SSLError):
        return "tls_error", f"code={int(code)} {msg[:80]}"

    return "unknown", f"code={int(code)} type={type(exc).__name__} {msg[:120]}"
