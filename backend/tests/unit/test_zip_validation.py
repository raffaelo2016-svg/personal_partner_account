from io import BytesIO
from zipfile import ZipFile

from app.validation.files import ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES, has_valid_signature, mime_type_for_filename


def test_zip_document_validation():
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("document.pdf", b"%PDF-1.4 test")
    assert ".zip" in ALLOWED_EXTENSIONS
    assert "application/zip" in ALLOWED_MIME_TYPES
    assert "application/x-zip-compressed" in ALLOWED_MIME_TYPES
    assert mime_type_for_filename("Documents.ZIP") == "application/zip"
    assert has_valid_signature(buffer.getvalue(), ".zip")
    assert not has_valid_signature(b"not an archive", ".zip")


def test_empty_zip_signature():
    buffer = BytesIO()
    with ZipFile(buffer, "w"):
        pass
    assert has_valid_signature(buffer.getvalue(), ".zip")
