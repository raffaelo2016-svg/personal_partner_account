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


async def test_list_all_uses_start_pagination():
    starts: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        starts.append(payload["start"])
        count = 50 if payload["start"] == 0 else 2
        return httpx.Response(200, json={"result": [{"ID": i} for i in range(count)]})

    transport = httpx.MockTransport(handler)
    async with Bitrix24Client("https://portal.example/rest/", "token", transport=transport) as client:
        result = await client.list_all("user.get")

    assert len(result) == 52
    assert starts == [0, 50]
