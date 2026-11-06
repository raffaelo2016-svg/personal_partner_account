from enum import StrEnum


class UserRole(StrEnum):
    PARTNER = "partner"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class ClientType(StrEnum):
    BEFORE_COURT = "before_court"
    IN_COURT = "in_court"


class DocumentPreparationMode(StrEnum):
    URITECH = "uritech"
    PARTNER = "partner"


class ClientStatus(StrEnum):
    DOCUMENTS_COLLECTION = "documents_collection"
    DOCUMENTS_FORMATION = "documents_formation"
    SENT_TO_COURT = "sent_to_court"
    DOCUMENTS_DECISION = "documents_decision"
    WAITING_HEARING = "waiting_hearing"
    RESTRUCTURING = "restructuring"
    AUCTION = "auction"
    REALIZATION = "realization"


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PartnerStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"


class CourtFeeStatus(StrEnum):
    UNPAID = "unpaid"
    PAID = "paid"
    OVERDUE = "overdue"


class TransactionStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
