from pathlib import PurePosixPath

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".zip"}
MIME_BY_EXTENSION = {
    ".zip": "application/zip",
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
ALLOWED_MIME_TYPES = set(MIME_BY_EXTENSION.values()) | {"application/x-zip-compressed"}


def file_extension(filename: str) -> str:
    return PurePosixPath(filename.replace("\\", "/")).suffix.lower()


def mime_type_for_filename(filename: str) -> str | None:
    return MIME_BY_EXTENSION.get(file_extension(filename))


def has_valid_signature(data: bytes, extension: str) -> bool:
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
