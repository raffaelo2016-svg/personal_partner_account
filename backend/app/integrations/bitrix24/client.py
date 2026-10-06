from __future__ import annotations

import base64
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
        self._portal_host = (urlparse(self.client_endpoint).hostname or "").lower()
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

        return self._decode_response(response)

    @staticmethod
    def _decode_response(response: httpx.Response) -> dict[str, Any]:
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
                str(data.get("error") or f"HTTP_{response.status_code}"),
                str(data.get("error_description", "Request failed")),
                status_code=response.status_code,
            )
        return data

    async def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if method.lower() == "disk.folder.uploadfile" and params and "fileContent" in params:
            return await self._upload_disk_file(method, params)
        data = await self._request(method, params)
        return data.get("result")

    async def _upload_disk_file(self, method: str, params: dict[str, Any]) -> Any:
        """Use the portal's multipart upload endpoint instead of its Base64 save path."""
        upload_params = dict(params)
        name, encoded = upload_params.pop("fileContent")
        target = (await self._request(method, upload_params)).get("result")
        if not isinstance(target, dict):
            raise Bitrix24Error("INVALID_RESPONSE", "Bitrix24 did not return an upload endpoint")
        url = str(target.get("uploadUrl") or target.get("UploadUrl") or "")
        field = target.get("field")
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or (parsed.hostname or "").lower() != self._portal_host
            or parsed.username
            or parsed.password
            or not isinstance(field, str)
            or not field
        ):
            raise Bitrix24Error("INVALID_UPLOAD_URL", "Bitrix24 returned an unsafe upload endpoint")
        try:
            response = await self._client.post(
                url, files={field: (name, base64.b64decode(encoded, validate=True), "application/octet-stream")}
            )
        except httpx.TimeoutException as exc:
            raise Bitrix24Error("TIMEOUT", "Bitrix24 file upload timed out") from exc
        except httpx.HTTPError as exc:
            raise Bitrix24Error("TRANSPORT_ERROR", "Could not upload the Bitrix24 file") from exc
        if response.is_redirect:
            raise Bitrix24Error("INVALID_UPLOAD_URL", "Bitrix24 redirected the upload request")
        return self._decode_response(response).get("result")

    async def download_file(self, url: str, *, max_bytes: int) -> bytes:
        """Download a signed Bitrix24 file without allowing arbitrary hosts or unbounded bodies."""
        parsed = urlparse(str(url).strip())
        if (
            parsed.scheme != "https"
            or (parsed.hostname or "").lower() != self._portal_host
            or parsed.username
            or parsed.password
        ):
            raise Bitrix24Error("INVALID_DOWNLOAD_URL", "Bitrix24 returned an unsafe file URL")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")

        try:
            async with self._client.stream("GET", url) as response:
                if response.is_redirect or response.is_error:
                    raise Bitrix24Error(
                        f"HTTP_{response.status_code}",
                        "Bitrix24 file download failed",
                        status_code=response.status_code,
                    )
                content_length = response.headers.get("content-length")
                if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                    raise Bitrix24Error("FILE_TOO_LARGE", "Bitrix24 file exceeds the configured limit")
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise Bitrix24Error("FILE_TOO_LARGE", "Bitrix24 file exceeds the configured limit")
                    chunks.append(chunk)
        except Bitrix24Error:
            raise
        except httpx.TimeoutException as exc:
            raise Bitrix24Error("TIMEOUT", "Bitrix24 file download timed out") from exc
        except httpx.HTTPError as exc:
            raise Bitrix24Error("TRANSPORT_ERROR", "Could not download the Bitrix24 file") from exc
        return b"".join(chunks)

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
