from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


class TokenStorageError(RuntimeError):
    pass


def _encryption_key() -> str:
    key = settings.BITRIX_TOKEN_ENCRYPTION_KEY
    if len(key) < 32:
        raise TokenStorageError("BITRIX_TOKEN_ENCRYPTION_KEY must contain at least 32 characters")
    return key


async def encrypt_token(db: AsyncSession, value: str) -> bytes:
    if not value:
        raise TokenStorageError("Refusing to encrypt an empty token")
    encrypted = await db.scalar(
        select(func.pgp_sym_encrypt(value, _encryption_key(), "cipher-algo=aes256, compress-algo=0"))
    )
    if not isinstance(encrypted, bytes):
        raise TokenStorageError("PostgreSQL did not return encrypted token bytes")
    return encrypted


async def decrypt_token(db: AsyncSession, value: bytes) -> str:
    decrypted = await db.scalar(select(func.pgp_sym_decrypt(value, _encryption_key())))
    if not isinstance(decrypted, str):
        raise TokenStorageError("PostgreSQL could not decrypt the token")
    return decrypted
