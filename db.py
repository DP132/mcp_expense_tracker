# from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Boolean, ForeignKey, DateTime
# from sqlalchemy.orm import sessionmaker, DeclarativeBase, relationship

# DATABASE_URL = "postgresql://postgres:12345@localhost:5432/expense_tracker"
# engine = create_engine(DATABASE_URL, echo=False)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# class Base(DeclarativeBase):
#     pass

# class User(Base):
#     __tablename__ = "users"
#     id              = Column(Integer, primary_key=True, index=True)
#     name            = Column(String, nullable=False)
#     nickname        = Column(String, nullable=True)
#     email           = Column(String, unique=True, nullable=False, index=True)
#     phone           = Column(String, nullable=True)
#     hashed_password = Column(String, nullable=False)
#     expenses        = relationship("Expense", back_populates="owner", cascade="all, delete-orphan")

# class Expense(Base):
#     __tablename__ = "expenses"
#     id             = Column(Integer, primary_key=True, index=True)
#     user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
#     amount         = Column(Float, nullable=False)
#     category       = Column(String, nullable=False)
#     date           = Column(Date, nullable=False)
#     description    = Column(String, nullable=True)
#     tags           = Column(String, nullable=True)
#     is_recurring   = Column(Boolean, default=False)
#     payment_method = Column(String, nullable=True)
#     owner          = relationship("User", back_populates="expenses")

# class OAuthClient(Base):
#     __tablename__ = "oauth_clients"
#     client_id     = Column(String, primary_key=True)
#     client_secret = Column(String, nullable=False)
#     redirect_uris = Column(String, default="")

# class AuthCode(Base):
#     __tablename__ = "auth_codes"
#     code                  = Column(String, primary_key=True)
#     user_id               = Column(Integer, ForeignKey("users.id"), nullable=False)
#     client_id             = Column(String, nullable=False)
#     redirect_uri          = Column(String, default="")
#     code_challenge        = Column(String, default="")
#     code_challenge_method = Column(String, default="S256")
#     expires_at            = Column(DateTime, nullable=False)

# class AccessToken(Base):
#     __tablename__ = "access_tokens"
#     token      = Column(String, primary_key=True)
#     user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
#     client_id  = Column(String, nullable=False)
#     expires_at = Column(DateTime, nullable=False)

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# def init_db():
#     Base.metadata.create_all(bind=engine)

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date,
    Boolean, ForeignKey, DateTime, Enum, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import sessionmaker, DeclarativeBase, relationship
from sqlalchemy.sql import func
import enum

DATABASE_URL = "postgresql://postgres:12345@localhost:5432/expense_tracker"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class GroupType(str, enum.Enum):
    family    = "family"
    friends   = "friends"
    trip      = "trip"
    office    = "office"
    roommates = "roommates"
    event     = "event"
    other     = "other"


class GroupMemberRole(str, enum.Enum):
    owner  = "owner"
    admin  = "admin"
    member = "member"


class SplitType(str, enum.Enum):
    equal      = "equal"
    percentage = "percentage"
    fixed      = "fixed"
    by_days    = "by_days"
    custom     = "custom"


class GroupStatus(str, enum.Enum):
    active   = "active"
    archived = "archived"


class ExpenseCategory(str, enum.Enum):
    food          = "food"
    travel        = "travel"
    hotel         = "hotel"
    fuel          = "fuel"
    entertainment = "entertainment"
    shopping      = "shopping"
    miscellaneous = "miscellaneous"


class SettlementStatus(str, enum.Enum):
    pending = "pending"
    settled = "settled"


# V2 / V3 ── new enums

class JoinRequestStatus(str, enum.Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"


class AuditActionType(str, enum.Enum):
    join_requested        = "join_requested"
    join_approved         = "join_approved"
    join_rejected         = "join_rejected"
    member_promoted       = "member_promoted"
    member_demoted        = "member_demoted"
    ownership_transferred = "ownership_transferred"
    member_removed        = "member_removed"
    member_added          = "member_added"          # ADD if missing
    member_reactivated    = "member_reactivated"    # ADD if missing
    member_deactivated    = "member_deactivated"    # ADD if missing
    group_created         = "group_created"
    group_archived        = "group_archived"
    group_unarchived      = "group_unarchived"      # ADD if missing
    group_deleted         = "group_deleted"
    invite_code_generated   = "invite_code_generated"
    invite_code_regenerated = "invite_code_regenerated"


# ─────────────────────────────────────────────
# EXISTING MODELS  (unchanged columns)
# ─────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String, nullable=False)
    nickname        = Column(String, nullable=True)
    email           = Column(String, unique=True, nullable=False, index=True)
    phone           = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)

    # original
    expenses = relationship("Expense", back_populates="owner", cascade="all, delete-orphan")

    # group (V1)
    group_memberships      = relationship("GroupMember",      back_populates="user",             cascade="all, delete-orphan")
    paid_group_expenses    = relationship("GroupExpense",     back_populates="paid_by_user",      foreign_keys="GroupExpense.paid_by")
    settlements_owed       = relationship("SettlementRecord", back_populates="from_user",         foreign_keys="SettlementRecord.from_user_id")
    settlements_receivable = relationship("SettlementRecord", back_populates="to_user",           foreign_keys="SettlementRecord.to_user_id")

    # V2 / V3
    join_requests           = relationship("JoinRequest", back_populates="user",              foreign_keys="JoinRequest.user_id", cascade="all, delete-orphan")
    approved_join_requests  = relationship("JoinRequest", back_populates="approved_by_user",  foreign_keys="JoinRequest.approved_by")
    audit_actions_performed = relationship("AuditLog",    back_populates="performed_by_user", foreign_keys="AuditLog.performed_by")
    audit_actions_received  = relationship("AuditLog",    back_populates="target_user_obj",   foreign_keys="AuditLog.target_user")


class Expense(Base):
    __tablename__ = "expenses"

    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount         = Column(Float,  nullable=False)
    category       = Column(String, nullable=False)
    date           = Column(Date,   nullable=False)
    description    = Column(String, nullable=True)
    tags           = Column(String, nullable=True)
    is_recurring   = Column(Boolean, default=False)
    payment_method = Column(String, nullable=True)

    owner = relationship("User", back_populates="expenses")


class OAuthClient(Base):
    __tablename__ = "oauth_clients"

    client_id     = Column(String, primary_key=True)
    client_secret = Column(String, nullable=False)
    redirect_uris = Column(String, default="")


class AuthCode(Base):
    __tablename__ = "auth_codes"

    code                  = Column(String, primary_key=True)
    user_id               = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id             = Column(String, nullable=False)
    redirect_uri          = Column(String, default="")
    code_challenge        = Column(String, default="")
    code_challenge_method = Column(String, default="S256")
    expires_at            = Column(DateTime, nullable=False)


class AccessToken(Base):
    __tablename__ = "access_tokens"

    token      = Column(String, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id  = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)


# ─────────────────────────────────────────────
# GROUP EXPENSE SYSTEM
# ─────────────────────────────────────────────

class Group(Base):
    __tablename__ = "groups"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    group_type  = Column(Enum(GroupType),   nullable=False, default=GroupType.other)
    status      = Column(Enum(GroupStatus), nullable=False, default=GroupStatus.active)
    created_by  = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at  = Column(DateTime, nullable=False, server_default=func.now())
    updated_at  = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    archived_at = Column(DateTime, nullable=True)

    # V2 ── invite code
    invite_code                = Column(String(16), nullable=True, unique=True)
    invite_code_created_at     = Column(DateTime,   nullable=True)
    invite_code_regenerated_at = Column(DateTime,   nullable=True)

    # relationships
    creator      = relationship("User",         foreign_keys=[created_by])
    members      = relationship("GroupMember",  back_populates="group",  cascade="all, delete-orphan")
    expenses     = relationship("GroupExpense", back_populates="group",  cascade="all, delete-orphan")
    join_requests = relationship("JoinRequest", back_populates="group",  cascade="all, delete-orphan")  # V2
    audit_logs   = relationship("AuditLog",     back_populates="group",  cascade="all, delete-orphan")  # V2

    __table_args__ = (
        Index("ix_groups_created_by",  "created_by"),
        Index("ix_groups_status",      "status"),
        Index("ix_groups_invite_code", "invite_code"),  # V2 — fast code lookup
    )


class GroupMember(Base):
    __tablename__ = "group_members"

    id        = Column(Integer, primary_key=True, index=True)
    group_id  = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id   = Column(Integer, ForeignKey("users.id",  ondelete="CASCADE"), nullable=False)
    role      = Column(Enum(GroupMemberRole), nullable=False, default=GroupMemberRole.member)
    joined_at = Column(DateTime, nullable=False, server_default=func.now())
    is_active = Column(Boolean,  nullable=False, default=True)

    group = relationship("Group", back_populates="members")
    user  = relationship("User",  back_populates="group_memberships")

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_member"),
        Index("ix_group_members_group_id", "group_id"),
        Index("ix_group_members_user_id",  "user_id"),
        Index("ix_group_members_role",     "role"),     # V2 — RBAC queries
    )


# ─────────────────────────────────────────────
# V2  NEW: JoinRequest
# ─────────────────────────────────────────────

class JoinRequest(Base):
    """
    A user's request to join a group via invite code.

    Lifecycle:  PENDING → APPROVED  (GroupMember row created on approval)
                        → REJECTED

    DB constraint: UniqueConstraint(group_id, user_id, status) prevents a user
    from having two simultaneous PENDING requests to the same group.
    Service layer additionally blocks already-approved members from re-requesting.
    """
    __tablename__ = "join_requests"

    id           = Column(Integer, primary_key=True, index=True)
    group_id     = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id      = Column(Integer, ForeignKey("users.id",  ondelete="CASCADE"), nullable=False)
    status       = Column(Enum(JoinRequestStatus), nullable=False, default=JoinRequestStatus.pending)
    requested_at = Column(DateTime, nullable=False, server_default=func.now())
    approved_by  = Column(Integer, ForeignKey("users.id"), nullable=True)   # NULL until resolved
    approved_at  = Column(DateTime, nullable=True)                          # NULL until resolved

    group            = relationship("Group", back_populates="join_requests")
    user             = relationship("User",  back_populates="join_requests",         foreign_keys=[user_id])
    approved_by_user = relationship("User",  back_populates="approved_join_requests", foreign_keys=[approved_by])

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", "status", name="uq_join_request_pending"),
        Index("ix_join_requests_group_id", "group_id"),
        Index("ix_join_requests_user_id",  "user_id"),
        Index("ix_join_requests_status",   "status"),
    )


# ─────────────────────────────────────────────
# V2  NEW: AuditLog
# ─────────────────────────────────────────────

class AuditLog(Base):
    """
    Append-only audit trail for every admin/owner action in a group.

    target_user is NULL for non-user-specific actions (e.g. invite_code_generated).
    metadata_json holds optional JSON context (e.g. {"old_role": "member", "new_role": "admin"}).
    """
    __tablename__ = "audit_logs"

    id            = Column(Integer, primary_key=True, index=True)
    group_id      = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    performed_by  = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_user   = Column(Integer, ForeignKey("users.id"), nullable=True)
    action_type   = Column(Enum(AuditActionType), nullable=False)
    metadata_json = Column(Text,     nullable=True)
    timestamp     = Column(DateTime, nullable=False, server_default=func.now())

    group             = relationship("Group", back_populates="audit_logs")
    performed_by_user = relationship("User",  back_populates="audit_actions_performed", foreign_keys=[performed_by])
    target_user_obj   = relationship("User",  back_populates="audit_actions_received",  foreign_keys=[target_user])

    __table_args__ = (
        Index("ix_audit_logs_group_id",     "group_id"),
        Index("ix_audit_logs_performed_by", "performed_by"),
        Index("ix_audit_logs_action_type",  "action_type"),
        Index("ix_audit_logs_timestamp",    "timestamp"),
    )


# ─────────────────────────────────────────────
# EXISTING GROUP EXPENSE MODELS  (unchanged)
# ─────────────────────────────────────────────

class GroupExpense(Base):
    __tablename__ = "group_expenses"

    id          = Column(Integer, primary_key=True, index=True)
    group_id    = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    title       = Column(String(255), nullable=False)
    amount      = Column(Float, nullable=False)
    category    = Column(Enum(ExpenseCategory), nullable=False, default=ExpenseCategory.miscellaneous)
    paid_by     = Column(Integer, ForeignKey("users.id"), nullable=False)
    split_type  = Column(Enum(SplitType),       nullable=False, default=SplitType.equal)
    date        = Column(Date, nullable=False)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, nullable=False, server_default=func.now())
    is_settled  = Column(Boolean,  nullable=False, default=False)

    group        = relationship("Group", back_populates="expenses")
    paid_by_user = relationship("User",  back_populates="paid_group_expenses", foreign_keys=[paid_by])
    participants = relationship("ExpenseParticipant", back_populates="expense", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_group_expenses_group_id", "group_id"),
        Index("ix_group_expenses_paid_by",  "paid_by"),
        Index("ix_group_expenses_date",     "date"),
    )


class ExpenseParticipant(Base):
    __tablename__ = "expense_participants"

    id           = Column(Integer, primary_key=True, index=True)
    expense_id   = Column(Integer, ForeignKey("group_expenses.id", ondelete="CASCADE"), nullable=False)
    user_id      = Column(Integer, ForeignKey("users.id",          ondelete="CASCADE"), nullable=False)
    share_value  = Column(Float, nullable=True)
    share_amount = Column(Float, nullable=False)
    is_settled   = Column(Boolean, nullable=False, default=False)

    expense = relationship("GroupExpense", back_populates="participants")
    user    = relationship("User")

    __table_args__ = (
        UniqueConstraint("expense_id", "user_id", name="uq_expense_participant"),
        Index("ix_expense_participants_expense_id", "expense_id"),
        Index("ix_expense_participants_user_id",    "user_id"),
    )


class SettlementRecord(Base):
    __tablename__ = "settlement_records"

    id           = Column(Integer, primary_key=True, index=True)
    group_id     = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount       = Column(Float, nullable=False)
    status       = Column(Enum(SettlementStatus), nullable=False, default=SettlementStatus.pending)
    created_at   = Column(DateTime, nullable=False, server_default=func.now())
    settled_at   = Column(DateTime, nullable=True)
    note         = Column(Text, nullable=True)

    group     = relationship("Group")
    from_user = relationship("User", back_populates="settlements_owed",       foreign_keys=[from_user_id])
    to_user   = relationship("User", back_populates="settlements_receivable", foreign_keys=[to_user_id])

    __table_args__ = (
        Index("ix_settlement_records_group_id",     "group_id"),
        Index("ix_settlement_records_from_user_id", "from_user_id"),
        Index("ix_settlement_records_to_user_id",   "to_user_id"),
        Index("ix_settlement_records_status",       "status"),
    )


# ─────────────────────────────────────────────
# DB UTILITIES
# ─────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)