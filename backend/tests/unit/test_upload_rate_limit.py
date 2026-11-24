from starlette.requests import Request

from app.api.files import _upload_rate_key


def make_request(*, token: str | None = None, host: str = "10.0.0.1") -> Request:
    headers = []
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    return Request({"type": "http", "headers": headers, "client": (host, 41234)})


def test_считает_лимит_по_пользователю_а_не_по_адресу():
    первый = _upload_rate_key(make_request(token="token-one", host="10.0.0.1"))
    второй = _upload_rate_key(make_request(token="token-one", host="10.0.0.2"))

    assert первый == второй
    assert первый.startswith("upload:user:")


def test_разные_токены_получают_разные_ключи():
    первый = _upload_rate_key(make_request(token="token-one"))
    второй = _upload_rate_key(make_request(token="token-two"))

    assert первый != второй


def test_без_токена_падает_обратно_на_ip():
    ключ = _upload_rate_key(make_request(host="192.0.2.7"))

    assert ключ == "upload:ip:192.0.2.7"


def test_неразборчивый_заголовок_не_ломает_ключ():
    запрос = Request({"type": "http", "headers": [(b"authorization", b"Basic abc")], "client": ("10.0.0.1", 1)})

    assert _upload_rate_key(запрос) == "upload:ip:10.0.0.1"


def test_токен_не_попадает_в_ключ_в_открытом_виде():
    ключ = _upload_rate_key(make_request(token="super-secret-token"))

    assert "super-secret-token" not in ключ
