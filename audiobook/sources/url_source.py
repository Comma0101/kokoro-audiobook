import ipaddress
import os
import socket
from urllib.parse import urljoin, urlparse

import requests
import trafilatura
from ..models import Chapter


MAX_URL_BYTES = int(os.getenv("URL_FETCH_MAX_BYTES", str(5 * 1024 * 1024)))
MAX_REDIRECTS = int(os.getenv("URL_FETCH_MAX_REDIRECTS", "5"))
REQUEST_TIMEOUT = (5, 20)
USER_AGENT = "kokoro-audiobook/1.0"
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain"}


def validate_public_http_url(input_url: str, *, resolver=socket.getaddrinfo) -> str:
    parsed = urlparse(input_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Article URL must use http or https.")
    if not parsed.hostname:
        raise ValueError("Article URL is missing a host.")

    host = parsed.hostname.strip().lower().rstrip(".")
    if host in LOCAL_HOSTNAMES or host.endswith(".localhost"):
        raise ValueError("Article URL cannot point to a local host.")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        _validate_resolved_host(host, parsed.port or _default_port(parsed.scheme), resolver)
    else:
        _validate_public_ip(ip)

    return input_url


def safe_fetch_url(input_url: str, *, session=None, resolver=socket.getaddrinfo) -> str:
    current_url = validate_public_http_url(input_url, resolver=resolver)
    http = session or requests.Session()

    for _ in range(MAX_REDIRECTS + 1):
        response = http.get(
            current_url,
            allow_redirects=False,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            stream=True,
        )
        status = int(response.status_code)

        if status in REDIRECT_STATUSES:
            location = response.headers.get("Location")
            if not location:
                raise ValueError(f"Redirect without Location header: {current_url}")
            current_url = validate_public_http_url(urljoin(current_url, location), resolver=resolver)
            continue

        if status >= 400:
            if status in {401, 403, 451}:
                raise ValueError(
                    "We couldn't access this article. The page may be private, blocked, "
                    "or behind a login. Paste the text instead."
                )
            raise ValueError(f"Could not fetch url: {current_url} (HTTP {status})")

        return _read_limited_text(response, MAX_URL_BYTES)

    raise ValueError("Too many redirects while fetching article URL.")


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def _validate_resolved_host(host: str, port: int, resolver) -> None:
    try:
        infos = resolver(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve article URL host: {host}") from exc

    addresses = []
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        raw_ip = str(sockaddr[0]).split("%", 1)[0]
        try:
            addresses.append(ipaddress.ip_address(raw_ip))
        except ValueError:
            continue

    if not addresses:
        raise ValueError(f"Could not resolve article URL host: {host}")

    for ip in addresses:
        _validate_public_ip(ip)


def _validate_public_ip(ip) -> None:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise ValueError("Article URL cannot point to a private or local network address.")


def _read_limited_text(response, max_bytes: int) -> str:
    data = bytearray()
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        data.extend(chunk)
        if len(data) > max_bytes:
            raise ValueError(f"Article response is too large (max {max_bytes // (1024 * 1024)} MB).")

    encoding = getattr(response, "encoding", None) or "utf-8"
    return bytes(data).decode(encoding, errors="replace")


class UrlSource:
    def load(self, input_str: str) -> list[Chapter]:
        downloaded = safe_fetch_url(input_str)
        
        doc = trafilatura.bare_extraction(downloaded)
        if not doc or not getattr(doc, "text", None):
            raise ValueError(f"Could not extract readable text from {input_str}")
            
        text = doc.text
        title = getattr(doc, "title", "Web Article") or "Web Article"
        
        text = " ".join(text.split())
        
        if not text.strip():
            raise ValueError(f"Could not extract readable text from {input_str}")
            
        return [Chapter(index=1, title=title.strip(), text=text)]
