import json

import httpx
import pytest

from app.integrations.bitrix24.client import Bitrix24Client, Bitrix24Error


def test_rejects_non_https_endpoint():
    with pytest.raises(ValueError, match="HTTPS"):
        Bitrix24Client("http://bitrix.example/rest/", "token")


async def test_call_sends_oauth_token_without_exposing_it_in_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["auth"] == "top-secret-token"
        return httpx.Response(403, json={"error": "insufficient_scope", "error_description": "Denied"})

    transport = httpx.MockTransport(handler)
    async with Bitrix24Client("https://portal.example/rest/", "top-secret-token", transport=transport) as client:
        with pytest.raises(Bitrix24Error) as exc_info:
            await client.call("scope")

    assert exc_info.value.code == "insufficient_scope"
    assert "top-secret-token" not in str(exc_info.value)


async def test_list_all_uses_next_cursor_from_response():
    starts: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        starts.append(payload["start"])
        if payload["start"] == 0:
            return httpx.Response(200, json={"result": [{"ID": 1}], "next": 75, "total": 2})
        return httpx.Response(200, json={"result": [{"ID": 2}], "total": 2})

    transport = httpx.MockTransport(handler)
    async with Bitrix24Client("https://portal.example/rest/", "token", transport=transport) as client:
        result = await client.list_all("user.get")

    assert result == [{"ID": 1}, {"ID": 2}]
    assert starts == [0, 75]


async def test_empty_error_code_uses_http_status():
    transport = httpx.MockTransport(lambda _: httpx.Response(400, json={"error": "", "error_description": "Failed"}))
    async with Bitrix24Client("https://portal.example/rest/", "token", transport=transport) as client:
        with pytest.raises(Bitrix24Error) as exc_info:
            await client.call("scope")
    assert exc_info.value.code == "HTTP_400"


async def test_disk_upload_uses_signed_multipart_endpoint():
    calls = []

    async def handler(request):
        calls.append(request)
        if len(calls) == 1:
            payload = json.loads(request.content)
            assert "fileContent" not in payload
            assert payload["data"]["NAME"] == "test.pdf"
            return httpx.Response(
                200, json={"result": {"uploadUrl": "https://portal.example/upload?key=signed", "field": "file"}}
            )
        assert request.url.path == "/upload"
        assert b"%PDF" in request.content
        assert b"test.pdf" in request.content
        assert b"secret-token" not in request.content
        return httpx.Response(200, json={"result": {"ID": "700"}})

    async with Bitrix24Client(
        "https://portal.example/rest/", "secret-token", transport=httpx.MockTransport(handler)
    ) as client:
        result = await client.call(
            "disk.folder.uploadfile",
            {"id": "600", "data": {"NAME": "test.pdf"}, "fileContent": ["test.pdf", "JVBERg=="]},
        )
    assert result == {"ID": "700"}
    assert len(calls) == 2


async def test_disk_upload_rejects_external_endpoint():
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200, json={"result": {"uploadUrl": "https://attacker.example/upload", "field": "file"}}
        )
    )
    async with Bitrix24Client("https://portal.example/rest/", "token", transport=transport) as client:
        with pytest.raises(Bitrix24Error) as exc_info:
            await client.call("disk.folder.uploadfile", {"fileContent": ["test.pdf", "JVBERg=="]})
    assert exc_info.value.code == "INVALID_UPLOAD_URL"


async def test_list_all_stops_when_next_cursor_is_absent():
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"result": [{"ID": i} for i in range(50)], "total": 50})

    transport = httpx.MockTransport(handler)
    async with Bitrix24Client("https://portal.example/rest/", "token", transport=transport) as client:
        result = await client.list_all("crm.status.list")

    assert len(result) == 50
    assert calls == 1


async def test_list_all_rejects_repeated_next_cursor():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": [], "next": 0})

    transport = httpx.MockTransport(handler)
    async with Bitrix24Client("https://portal.example/rest/", "token", transport=transport) as client:
        with pytest.raises(Bitrix24Error, match="repeated pagination cursor"):
            await client.list_all("user.get")


async def test_download_file_accepts_only_bounded_portal_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "portal.example"
        return httpx.Response(200, content=b"%PDF-1.7", headers={"content-length": "8"})

    transport = httpx.MockTransport(handler)
    async with Bitrix24Client("https://portal.example/rest/", "token", transport=transport) as client:
        data = await client.download_file("https://portal.example/rest/download.json?token=signed", max_bytes=32)

    assert data == b"%PDF-1.7"


async def test_download_file_rejects_external_host_before_request():
    transport = httpx.MockTransport(lambda _request: pytest.fail("unsafe URL must not be requested"))
    async with Bitrix24Client("https://portal.example/rest/", "token", transport=transport) as client:
        with pytest.raises(Bitrix24Error) as exc_info:
            await client.download_file("https://attacker.example/file.pdf", max_bytes=32)

    assert exc_info.value.code == "INVALID_DOWNLOAD_URL"


async def test_download_file_stops_when_limit_is_exceeded():
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, content=b"x" * 33))
    async with Bitrix24Client("https://portal.example/rest/", "token", transport=transport) as client:
        with pytest.raises(Bitrix24Error) as exc_info:
            await client.download_file("https://portal.example/download", max_bytes=32)

    assert exc_info.value.code == "FILE_TOO_LARGE"
