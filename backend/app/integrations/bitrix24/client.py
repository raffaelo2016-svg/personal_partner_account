from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx


class Bitrix24Error(RuntimeError):
    """A safe Bitrix24 API error that never contains credentials."""

    def __init__(self, code: str, description: str, *, status_code: int | None = None) -> None:
        self.code = code
        self.description = description
        self.status_code = status_code
        super().__init__(f"Bitrix24 API error {code}: {description}")


class Bitrix24Client:
    """Small OAuth REST client used by the Bitrix24 integration."""

    def __init__(
        self,
        client_endpoint: str,
        access_token: str,
        *,
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.client_endpoint = self._normalize_endpoint(client_endpoint)
        if not access_token.strip():
            raise ValueError("BITRIX_ACCESS_TOKEN is required")
        self._access_token = access_token
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport)

    @staticmethod
    def _normalize_endpoint(value: str) -> str:
        endpoint = value.strip().rstrip("/") + "/"
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("BITRIX_CLIENT_ENDPOINT must be an absolute HTTPS URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("BITRIX_CLIENT_ENDPOINT must not contain credentials, query, or fragment")
        return endpoint

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Bitrix24Client:
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.close()

    async def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not method or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789._" for char in method.lower()):
            raise ValueError("Invalid Bitrix24 method name")

        payload = dict(params or {})
        payload["auth"] = self._access_token

        try:
            response = await self._client.post(f"{self.client_endpoint}{method}", json=payload)
        except httpx.TimeoutException as exc:
            raise Bitrix24Error("TIMEOUT", "Bitrix24 did not respond in time") from exc
        except httpx.HTTPError as exc:
            raise Bitrix24Error("TRANSPORT_ERROR", "Could not reach Bitrix24") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise Bitrix24Error(
                "INVALID_RESPONSE",
                "Bitrix24 returned non-JSON response",
                status_code=response.status_code,
            ) from exc

        if not isinstance(data, dict):
            raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 returned an unexpected JSON shape")
        if response.is_error or "error" in data:
            raise Bitrix24Error(
                str(data.get("error", f"HTTP_{response.status_code}")),
                str(data.get("error_description", "Request failed")),
                status_code=response.status_code,
            )
        return data

    async def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        data = await self._request(method, params)
        return data.get("result")

    async def list_all(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        result_key: str | None = None,
        max_pages: int = 100,
    ) -> list[Any]:
        """Load every page of a Bitrix24 list without unbounded requests."""
        items: list[Any] = []
        start = 0
        seen_starts: set[int] = set()
        for _ in range(max_pages):
            if start in seen_starts:
                raise Bitrix24Error("INVALID_RESPONSE", f"{method} returned a repeated pagination cursor")
            seen_starts.add(start)

            page_params = dict(params or {})
            page_params["start"] = start
            data = await self._request(method, page_params)
            result = data.get("result")
            page = result.get(result_key, []) if result_key and isinstance(result, dict) else result
            if not isinstance(page, list):
                raise Bitrix24Error("INVALID_RESPONSE", f"{method} returned an unexpected list shape")
            items.extend(page)

            next_start = data.get("next")
            if next_start is None:
                return items
            if isinstance(next_start, bool) or not isinstance(next_start, int) or next_start < 0:
                raise Bitrix24Error("INVALID_RESPONSE", f"{method} returned an invalid pagination cursor")
            start = next_start
        raise Bitrix24Error("PAGINATION_LIMIT", f"{method} exceeded {max_pages} pages")
