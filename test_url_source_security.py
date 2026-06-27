from urllib.parse import urlparse

from audiobook.sources import url_source
from audiobook.sources.url_source import UrlSource


def public_resolver(host, port, *args, **kwargs):
    return [(None, None, None, "", ("93.184.216.34", port))]


def private_resolver(host, port, *args, **kwargs):
    return [(None, None, None, "", ("10.0.0.1", port))]


class FakeResponse:
    def __init__(self, status_code=200, headers=None, body=b"<html></html>", encoding="utf-8", apparent_encoding=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = body
        self.encoding = encoding
        self.apparent_encoding = apparent_encoding

    def iter_content(self, chunk_size=65536):
        yield self.content


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requested_urls = []

    def get(self, url, **kwargs):
        self.requested_urls.append(url)
        if not self.responses:
            raise AssertionError("No fake response configured")
        return self.responses.pop(0)


def test_rejects_non_http_urls():
    try:
        url_source.validate_public_http_url("file:///etc/passwd", resolver=public_resolver)
    except ValueError as exc:
        assert "http" in str(exc).lower()
    else:
        raise AssertionError("Expected file URL to be rejected")


def test_rejects_localhost_hostname():
    try:
        url_source.validate_public_http_url("http://localhost/article", resolver=public_resolver)
    except ValueError as exc:
        assert "local" in str(exc).lower()
    else:
        raise AssertionError("Expected localhost to be rejected")


def test_rejects_private_ip_literal():
    try:
        url_source.validate_public_http_url("http://127.0.0.1/article", resolver=public_resolver)
    except ValueError as exc:
        assert "private" in str(exc).lower() or "local" in str(exc).lower()
    else:
        raise AssertionError("Expected loopback IP to be rejected")


def test_rejects_hostname_that_resolves_to_private_ip():
    try:
        url_source.validate_public_http_url("https://example.com/article", resolver=private_resolver)
    except ValueError as exc:
        assert "private" in str(exc).lower()
    else:
        raise AssertionError("Expected private DNS resolution to be rejected")


def test_safe_fetch_blocks_redirect_to_private_ip():
    session = FakeSession([
        FakeResponse(status_code=302, headers={"Location": "http://127.0.0.1/admin"}),
    ])

    try:
        url_source.safe_fetch_url("https://example.com/article", session=session, resolver=public_resolver)
    except ValueError as exc:
        assert "redirect" in str(exc).lower() or "private" in str(exc).lower()
    else:
        raise AssertionError("Expected private redirect to be rejected")

    assert session.requested_urls == ["https://example.com/article"]


def test_safe_fetch_explains_blocked_article_recovery():
    session = FakeSession([
        FakeResponse(status_code=403, body=b"<html>Forbidden</html>"),
    ])

    try:
        url_source.safe_fetch_url("https://example.com/article", session=session, resolver=public_resolver)
    except ValueError as exc:
        message = str(exc)
        assert "couldn't access" in message.lower()
        assert "paste the text" in message.lower()
    else:
        raise AssertionError("Expected blocked article to raise a recovery error")


def test_url_source_load_uses_safe_fetcher():
    original_fetch = url_source.safe_fetch_url
    try:
        def fake_fetch(input_url, **kwargs):
            parsed = urlparse(input_url)
            assert parsed.scheme == "https"
            return """
                <html>
                  <head><title>Readable Article</title></head>
                  <body>
                    <article>
                      <h1>Readable Article</h1>
                      <p>This article has enough readable text for extraction. It is safe public content.</p>
                    </article>
                  </body>
                </html>
            """

        url_source.safe_fetch_url = fake_fetch
        chapters = UrlSource().load("https://example.com/article")
    finally:
        url_source.safe_fetch_url = original_fetch

    assert len(chapters) == 1
    assert chapters[0].title
    assert "safe public content" in chapters[0].text


def test_safe_fetch_decodes_gb2312_article_html():
    html = """
        <html>
          <head><meta http-equiv="Content-Type" content="text/html; charset=gb2312"></head>
          <body><article><h1>红楼梦</h1><p>甄士隐梦幻识通灵。古字𠀀。</p></article></body>
        </html>
    """.encode("gb18030")
    session = FakeSession([
        FakeResponse(
            headers={"Content-Type": "text/html"},
            body=html,
            encoding="ISO-8859-1",
            apparent_encoding="GB2312",
        ),
    ])

    text = url_source.safe_fetch_url("https://example.com/hlm/001.htm", session=session, resolver=public_resolver)

    assert "红楼梦" in text
    assert "甄士隐梦幻识通灵" in text
    assert "古字𠀀" in text
    assert "ºìÂ¥" not in text
    assert "�" not in text


if __name__ == "__main__":
    for test in [
        test_rejects_non_http_urls,
        test_rejects_localhost_hostname,
        test_rejects_private_ip_literal,
        test_rejects_hostname_that_resolves_to_private_ip,
        test_safe_fetch_blocks_redirect_to_private_ip,
        test_safe_fetch_explains_blocked_article_recovery,
        test_url_source_load_uses_safe_fetcher,
        test_safe_fetch_decodes_gb2312_article_html,
    ]:
        test()
    print("url source security tests passed")
