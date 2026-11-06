from pathlib import PurePosixPath

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_ZIP_FILE_SIZE_BYTES = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".zip", ".mp3"}
MIME_BY_EXTENSION = {
    ".zip": "application/zip",
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".mp3": "audio/mpeg",
}
ALLOWED_MIME_TYPES = set(MIME_BY_EXTENSION.values()) | {"application/x-zip-compressed"}
MP3_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/x-mp3",
    "audio/mpeg3",
    "audio/x-mpeg-3",
    "audio/x-mpeg",
    "application/octet-stream",
    "",
}


def file_extension(filename: str) -> str:
    return PurePosixPath(filename.replace("\\", "/")).suffix.lower()


def max_file_size_for_filename(filename: str) -> int:
    return MAX_ZIP_FILE_SIZE_BYTES if file_extension(filename) == ".zip" else MAX_FILE_SIZE_BYTES


def mime_type_for_filename(filename: str) -> str | None:
    return MIME_BY_EXTENSION.get(file_extension(filename))


def normalize_mime_type(filename: str, content_type: str | None) -> str | None:
    extension = file_extension(filename)
    mime_type = content_type or ""
    if extension == ".mp3":
        mime_type = mime_type.split(";", 1)[0].strip().lower()
        return "audio/mpeg" if mime_type in MP3_MIME_TYPES else None
    if extension == ".zip" and mime_type in {"", "application/octet-stream", "application/x-zip-compressed"}:
        return "application/zip"
    # Keep the existing MIME policy for all previously supported formats.
    return mime_type if mime_type in ALLOWED_MIME_TYPES and mime_type != "audio/mpeg" else None


def _mp3_frame_length(data: bytes, offset: int) -> int | None:
    if len(data) - offset < 4:
        return None
    header = int.from_bytes(data[offset : offset + 4], "big")
    version = (header >> 19) & 3
    layer = (header >> 17) & 3
    bitrate_index = (header >> 12) & 15
    sample_rate_index = (header >> 10) & 3
    if (
        header & 0xFFE00000 != 0xFFE00000
        or version == 1
        or layer != 1  # Only MPEG Layer III belongs in an MP3 file.
        or bitrate_index in {0, 15}
        or sample_rate_index == 3
        or header & 3 == 2  # Reserved emphasis value.
    ):
        return None
    bitrates = (
        (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
        if version == 3
        else (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)
    )
    sample_rate = (44100, 48000, 32000)[sample_rate_index]
    sample_rate //= 1 if version == 3 else 2 if version == 2 else 4
    coefficient = 144 if version == 3 else 72
    return coefficient * bitrates[bitrate_index] * 1000 // sample_rate + ((header >> 9) & 1)


def _has_valid_mp3_signature(data: bytes) -> bool:
    offset = 0
    if data.startswith(b"ID3"):
        if len(data) < 10 or data[3] not in {2, 3, 4} or data[4] == 255:
            return False
        allowed_flags = {2: 0xC0, 3: 0xE0, 4: 0xF0}[data[3]]
        if data[5] & ~allowed_flags or any(value & 0x80 for value in data[6:10]):
            return False
        tag_size = 0
        for value in data[6:10]:
            tag_size = (tag_size << 7) | value
        offset = 10 + tag_size
        if data[3] == 4 and data[5] & 0x10:
            if data[offset : offset + 10] != b"3DI" + data[3:10]:
                return False
            offset += 10

    frame_length = _mp3_frame_length(data, offset)
    if frame_length is None or offset + frame_length > len(data):
        return False
    next_offset = offset + frame_length
    if next_offset == len(data) or (len(data) - next_offset == 128 and data[next_offset : next_offset + 3] == b"TAG"):
        return True
    # A second complete frame at its expected boundary rules out a stray sync word.
    next_length = _mp3_frame_length(data, next_offset)
    return next_length is not None and next_offset + next_length <= len(data)


def has_valid_signature(data: bytes, extension: str) -> bool:
    if extension == ".mp3":
        return _has_valid_mp3_signature(data)
    signatures = {
        ".pdf": (b"%PDF-",),
        ".jpg": (b"\xff\xd8\xff",),
        ".jpeg": (b"\xff\xd8\xff",),
        ".png": (b"\x89PNG\r\n\x1a\n",),
        ".doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
        ".docx": (b"PK\x03\x04",),
        ".zip": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    }
    return any(data.startswith(signature) for signature in signatures.get(extension, ()))
