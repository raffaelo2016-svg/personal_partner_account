from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.datastructures import Headers, UploadFile

from app.validation.files import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
    has_valid_signature,
    mime_type_for_filename,
    normalize_mime_type,
)

# MPEG-1 Layer III, 128 kbps, 44.1 kHz: one 417-byte frame.
MP3_FRAME = bytes.fromhex("fffb9000") + bytes(413)


@pytest.mark.parametrize(
    "content",
    [
        MP3_FRAME,
        MP3_FRAME * 2,
        bytes.fromhex("fffb9200") + bytes(414),  # MPEG-1 with padding.
        bytes.fromhex("fff38000") + bytes(204),  # MPEG-2, 64 kbps, 22.05 kHz.
        bytes.fromhex("ffe38000") + bytes(413),  # MPEG-2.5, 64 kbps, 11.025 kHz.
        MP3_FRAME + b"TAG" + bytes(125),  # Optional trailing ID3v1 tag.
    ],
)
def test_mp3_accepts_complete_layer_three_frames(content):
    assert has_valid_signature(content, ".mp3")


@pytest.mark.parametrize("version", [2, 3, 4])
def test_mp3_accepts_id3_metadata_followed_by_audio(version):
    tag = b"ID3" + bytes([version, 0, 0, 0, 0, 0, 5]) + bytes(5)
    assert has_valid_signature(tag + MP3_FRAME * 2, ".mp3")


def test_mp3_accepts_id3v24_footer_followed_by_audio():
    header = b"ID3\x04\x00\x10\x00\x00\x00\x05"
    content = header + bytes(5) + b"3DI" + header[3:] + MP3_FRAME
    assert has_valid_signature(content, ".mp3")


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"not an MP3",
        b"ID3not audio",
        b"ID3\x04\x00\x00\x00\x00\x00\x00",  # Metadata alone is not audio.
        b"ID3\x04\x00\x00\x00\x00\x00\x05" + bytes(5),
        b"ID3\x04\x00\x00\x80\x00\x00\x00" + MP3_FRAME,  # Invalid synchsafe size.
        b"ID3\x04\x00\x00\x00\x00\x7f\x7f" + MP3_FRAME,  # Truncated tag.
        b"ID3\x04\x00\x01\x00\x00\x00\x00" + MP3_FRAME,  # Reserved ID3 flag.
        b"ID3\x05\x00\x00\x00\x00\x00\x00" + MP3_FRAME,  # Unsupported ID3 version.
        b"ID3\x04\x00\x10\x00\x00\x00\x00" + bytes(10) + MP3_FRAME,  # Invalid footer.
        b"\xff\xe0" + bytes(500),  # A sync word alone is insufficient.
        MP3_FRAME[:4],
        MP3_FRAME[:-1],
        bytes.fromhex("fffd9000") + bytes(413),  # MPEG Layer II is not MP3.
        bytes.fromhex("ffeb9000") + bytes(413),  # Reserved MPEG version.
        bytes.fromhex("fffbf000") + bytes(413),  # Reserved bitrate.
        bytes.fromhex("fffb0000") + bytes(413),  # Free-format frame has no declared length.
        bytes.fromhex("fffb9c00") + bytes(413),  # Reserved sample rate.
        bytes.fromhex("fffb9002") + bytes(413),  # Reserved emphasis.
        MP3_FRAME + b"arbitrary bytes",
        MP3_FRAME + MP3_FRAME[:4],
    ],
)
def test_mp3_rejects_fake_or_truncated_content(content):
    assert not has_valid_signature(content, ".mp3")


@pytest.mark.parametrize(
    "mime_type",
    [
        None,
        "",
        "application/octet-stream",
        "audio/mpeg",
        "audio/mp3",
        "audio/x-mp3",
        "audio/mpeg3",
        "audio/x-mpeg-3",
        "audio/x-mpeg",
        "Audio/MPEG; charset=binary",
    ],
)
def test_mp3_mime_aliases_are_canonicalized(mime_type):
    assert normalize_mime_type("recording.MP3", mime_type) == "audio/mpeg"


@pytest.mark.parametrize("mime_type", ["application/pdf", "audio/wav", "text/html", "application/zip"])
def test_mp3_rejects_unrelated_mime_types(mime_type):
    assert normalize_mime_type("recording.mp3", mime_type) is None


def test_mp3_is_in_shared_file_policy():
    assert ".mp3" in ALLOWED_EXTENSIONS
    assert "audio/mpeg" in ALLOWED_MIME_TYPES
    assert mime_type_for_filename("recording.MP3") == "audio/mpeg"


@pytest.mark.parametrize("mime_type", [None, "", "application/octet-stream", "application/x-zip-compressed"])
def test_existing_zip_mime_normalization_is_preserved(mime_type):
    assert normalize_mime_type("documents.zip", mime_type) == "application/zip"


def test_existing_document_mime_policy_is_preserved():
    assert normalize_mime_type("document.pdf", "application/pdf") == "application/pdf"
    assert normalize_mime_type("document.pdf", "application/octet-stream") is None
    assert normalize_mime_type("document.pdf", "audio/mpeg") is None
    assert normalize_mime_type("document.pdf", None) is None


def _upload_file(filename, content, mime_type):
    return UploadFile(
        BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": mime_type}) if mime_type is not None else Headers(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mime_type", [None, "", "application/octet-stream", "audio/x-mp3"])
async def test_chat_upload_accepts_mp3_with_canonical_mime(monkeypatch, mime_type):
    from app.services import chat_service

    upload = AsyncMock(return_value="uploads/recording.mp3")
    monkeypatch.setattr(chat_service, "upload_file_async", upload)

    result = await chat_service.upload_chat_file(_upload_file("recording.MP3", MP3_FRAME, mime_type))

    assert result == ("uploads/recording.mp3", "recording.MP3", len(MP3_FRAME), "audio/mpeg")
    upload.assert_awaited_once_with(MP3_FRAME, "recording.MP3", "audio/mpeg")


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [b"not audio", b"ID3\x04\x00\x00\x00\x00\x00\x00", b"\xff\xe0" + bytes(500)])
async def test_chat_upload_rejects_fake_mp3_before_s3(monkeypatch, content):
    from app.core.exceptions import UnsupportedFileType
    from app.services import chat_service

    upload = AsyncMock()
    monkeypatch.setattr(chat_service, "upload_file_async", upload)

    with pytest.raises(UnsupportedFileType):
        await chat_service.upload_chat_file(_upload_file("recording.mp3", content, "audio/mpeg"))

    upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_upload_rejects_oversized_mp3_before_s3(monkeypatch):
    from app.core.exceptions import FileTooLarge
    from app.services import chat_service

    upload = AsyncMock()
    monkeypatch.setattr(chat_service, "upload_file_async", upload)
    content = MP3_FRAME + bytes(MAX_FILE_SIZE_BYTES + 1 - len(MP3_FRAME))

    with pytest.raises(FileTooLarge):
        await chat_service.upload_chat_file(_upload_file("recording.mp3", content, "audio/mpeg"))

    upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_upload_keeps_existing_pdf_content_policy(monkeypatch):
    from app.services import chat_service

    upload = AsyncMock(return_value="uploads/document.pdf")
    monkeypatch.setattr(chat_service, "upload_file_async", upload)

    result = await chat_service.upload_chat_file(_upload_file("document.pdf", b"legacy fixture", "application/pdf"))

    assert result == ("uploads/document.pdf", "document.pdf", 14, "application/pdf")
    upload.assert_awaited_once_with(b"legacy fixture", "document.pdf", "application/pdf")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "mime_type", "accepted"),
    [
        (MP3_FRAME, "application/octet-stream", True),
        (MP3_FRAME, "audio/x-mp3", True),
        (b"ID3 fake", "audio/mpeg", False),
    ],
)
async def test_bitrix_chat_import_checks_mp3_content_and_normalizes_mime(monkeypatch, content, mime_type, accepted):
    from app.integrations.bitrix24 import chat as bitrix_chat

    remote = AsyncMock()
    remote.call.return_value = {"downloadUrl": "https://example.test/recording.mp3"}
    response = Mock(content=content)
    http = AsyncMock()
    http.get.return_value = response
    context = AsyncMock()
    context.__aenter__.return_value = http
    monkeypatch.setattr(bitrix_chat.httpx, "AsyncClient", Mock(return_value=context))
    upload = AsyncMock(return_value="uploads/imported.mp3")
    monkeypatch.setattr(bitrix_chat, "upload_file_async", upload)

    result = await bitrix_chat._import_attachment(
        remote,
        SimpleNamespace(im_bot_id=None, portal_domain="example.test"),
        dialog_id="chat123",
        file_data={"id": 42, "name": "recording.mp3", "size": len(content), "mimeType": mime_type},
    )

    if accepted:
        assert result == ("uploads/imported.mp3", "recording.mp3", len(content), "audio/mpeg")
        upload.assert_awaited_once_with(content, "recording.mp3", "audio/mpeg")
    else:
        assert result is None
        upload.assert_not_awaited()
