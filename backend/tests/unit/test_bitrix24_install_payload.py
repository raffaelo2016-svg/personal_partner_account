from datetime import UTC

import pytest
from fastapi import HTTPException

from app.api.bitrix24_integration import _auth_from, _token_expiry


def test_auth_from_requires_complete_oauth_payload():
    with pytest.raises(HTTPException, match="Incomplete"):
        _auth_from({"auth": {"access_token": "token"}})


def test_token_expiry_accepts_unix_timestamp():
    result = _token_expiry({"expires": "1780319382"})

    assert result is not None
    assert result.tzinfo == UTC
    assert int(result.timestamp()) == 1780319382
