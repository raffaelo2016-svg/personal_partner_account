from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FileDeletionTombstone(Base, TimestampMixin):
    """Marker for a Bitrix24 Disk file whose cabinet copy was deleted.

    The CRM copy stays on the Disk by design, so the reconciler must not import
    the same document back into the cabinet. Only the remote file ID is kept:
    the document itself, its name and its content are removed from the cabinet.
    """

    __tablename__ = "file_deletion_tombstones"
    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "bitrix_disk_file_id",
            name="uq_file_deletion_tombstones_client_disk_file",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        index=True,
    )
    bitrix_disk_file_id: Mapped[str] = mapped_column(String(100))
