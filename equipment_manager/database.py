from __future__ import annotations

import hashlib
import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(60), default="Engineer")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class UserPermission(Base):
    __tablename__ = "user_permissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    permission: Mapped[str] = mapped_column(String(100), index=True)
    allowed: Mapped[bool] = mapped_column(Boolean)
    __table_args__ = (UniqueConstraint("username", "permission", name="uq_user_permission"),)


class Equipment(Base):
    __tablename__ = "equipment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    equipment_type: Mapped[str] = mapped_column(String(120), default="")
    manufacturer: Mapped[str] = mapped_column(String(120), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    serial_number: Mapped[str] = mapped_column(String(120), default="")
    asset_number: Mapped[str] = mapped_column(String(120), default="")
    site: Mapped[str] = mapped_column(String(120), default="")
    building: Mapped[str] = mapped_column(String(120), default="")
    floor: Mapped[str] = mapped_column(String(120), default="")
    area: Mapped[str] = mapped_column(String(120), default="")
    line_cell: Mapped[str] = mapped_column(String(120), default="")
    owner: Mapped[str] = mapped_column(String(120), default="")
    criticality: Mapped[str] = mapped_column(String(30), default="Normal")
    status: Mapped[str] = mapped_column(String(40), default="Available")
    disposition: Mapped[str] = mapped_column(String(60), default="Released")
    map_x: Mapped[float] = mapped_column(Float, default=0.0)
    map_y: Mapped[float] = mapped_column(Float, default=0.0)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PMDefinition(Base):
    __tablename__ = "pm_definitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pm_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(250), default="")
    equipment_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    schedule_type: Mapped[str] = mapped_column(String(80), default="Interval")
    frequency_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    frequency_unit: Mapped[str] = mapped_column(String(30), default="days")
    anchor_mode: Mapped[str] = mapped_column(String(40), default="Original Due")
    early_window_days: Mapped[int] = mapped_column(Integer, default=0)
    grace_days: Mapped[int] = mapped_column(Integer, default=0)
    estimated_hours: Mapped[float] = mapped_column(Float, default=0.0)
    required_people: Mapped[int] = mapped_column(Integer, default=1)
    required_skill: Mapped[str] = mapped_column(String(120), default="")
    required_parts: Mapped[str] = mapped_column(Text, default="")
    sop_path: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)


class PMTask(Base):
    __tablename__ = "pm_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    pm_id: Mapped[str] = mapped_column(String(100), index=True)
    pm_name: Mapped[str] = mapped_column(String(250), default="")
    original_due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scheduled_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_completion_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="Pending")
    assigned_to: Mapped[str] = mapped_column(String(120), default="")
    estimated_hours: Mapped[float] = mapped_column(Float, default=0.0)
    priority: Mapped[str] = mapped_column(String(20), default="Normal")
    deferral_reason: Mapped[str] = mapped_column(Text, default="")
    sop_path: Mapped[str] = mapped_column(Text, default="")
    report_path: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("equipment_id", "pm_id", "original_due_date", name="uq_pm_backlog"),)


class PMSpec(Base):
    __tablename__ = "pm_specs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pm_id: Mapped[str] = mapped_column(String(100), index=True)
    step_no: Mapped[int] = mapped_column(Integer)
    activity: Mapped[str] = mapped_column(Text, default="")
    method: Mapped[str] = mapped_column(String(250), default="")
    input_type: Mapped[str] = mapped_column(String(40), default="Text")
    unit: Mapped[str] = mapped_column(String(40), default="")
    target: Mapped[float | None] = mapped_column(Float, nullable=True)
    warning_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    warning_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    control_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    control_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    spec_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    spec_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    acceptance_text: Mapped[str] = mapped_column(Text, default="")
    reaction_plan: Mapped[str] = mapped_column(Text, default="")
    sop_path: Mapped[str] = mapped_column(Text, default="")
    sop_page: Mapped[str] = mapped_column(String(40), default="")
    sop_section: Mapped[str] = mapped_column(String(80), default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint("pm_id", "step_no", "revision", name="uq_pm_spec_revision"),)


class PMExecution(Base):
    __tablename__ = "pm_executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    started_by: Mapped[str] = mapped_column(String(120), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_by: Mapped[str] = mapped_column(String(120), default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="In Progress")
    version: Mapped[int] = mapped_column(Integer, default=1)


class PMResult(Base):
    __tablename__ = "pm_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(Integer, index=True)
    step_no: Mapped[int] = mapped_column(Integer)
    value_text: Mapped[str] = mapped_column(Text, default="")
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    result: Mapped[str] = mapped_column(String(40), default="")
    comment: Mapped[str] = mapped_column(Text, default="")
    evidence_path: Mapped[str] = mapped_column(Text, default="")
    entered_by: Mapped[str] = mapped_column(String(120), default="")
    entered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint("execution_id", "step_no", name="uq_execution_step"),)


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(20), default="S3")
    priority: Mapped[str] = mapped_column(String(20), default="P3")
    status: Mapped[str] = mapped_column(String(50), default="Open")
    owner: Mapped[str] = mapped_column(String(120), default="")
    root_cause: Mapped[str] = mapped_column(Text, default="")
    corrective_action: Mapped[str] = mapped_column(Text, default="")
    verification: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1)


class TicketInvestigation(Base):
    __tablename__ = "ticket_investigations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(100), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    observation: Mapped[str] = mapped_column(Text, default="")
    check_performed: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(Text, default="")
    conclusion: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(Text, default="")
    evidence_path: Mapped[str] = mapped_column(Text, default="")
    entered_by: Mapped[str] = mapped_column(String(120), default="")
    entered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Disposition(Base):
    __tablename__ = "dispositions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    state: Mapped[str] = mapped_column(String(80), default="Released")
    reason: Mapped[str] = mapped_column(Text, default="")
    restrictions: Mapped[str] = mapped_column(Text, default="")
    release_criteria: Mapped[str] = mapped_column(Text, default="")
    related_ticket: Mapped[str] = mapped_column(String(100), default="")
    effective_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    approved_by: Mapped[str] = mapped_column(String(120), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class EquipmentRelease(Base):
    __tablename__ = "equipment_releases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    related_ticket: Mapped[str] = mapped_column(String(100), default="")
    checks_json: Mapped[str] = mapped_column(Text, default="{}")
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="Pending Verification")
    requested_by: Mapped[str] = mapped_column(String(120), default="")
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    verified_by: Mapped[str] = mapped_column(String(120), default="")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[str] = mapped_column(String(120), default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Endorsement(Base):
    __tablename__ = "endorsements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endorsement_no: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    current_condition: Mapped[str] = mapped_column(Text, default="")
    work_completed: Mapped[str] = mapped_column(Text, default="")
    pending_work: Mapped[str] = mapped_column(Text, default="")
    restrictions: Mapped[str] = mapped_column(Text, default="")
    next_action: Mapped[str] = mapped_column(Text, default="")
    next_owner: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(40), default="Open")
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    acknowledged_by: Mapped[str] = mapped_column(String(120), default="")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class StorageLocation(Base):
    __tablename__ = "storage_locations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    site: Mapped[str] = mapped_column(String(120), default="")
    building: Mapped[str] = mapped_column(String(120), default="")
    floor: Mapped[str] = mapped_column(String(120), default="")
    area: Mapped[str] = mapped_column(String(120), default="")
    cabinet: Mapped[str] = mapped_column(String(120), default="")
    shelf: Mapped[str] = mapped_column(String(120), default="")
    drawer_bin: Mapped[str] = mapped_column(String(120), default="")
    map_x: Mapped[float] = mapped_column(Float, default=0.0)
    map_y: Mapped[float] = mapped_column(Float, default=0.0)
    image_path: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_number: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(String(300), default="")
    category: Mapped[str] = mapped_column(String(120), default="")
    manufacturer: Mapped[str] = mapped_column(String(120), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    compatible_equipment: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    min_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(40), default="pcs")
    condition: Mapped[str] = mapped_column(String(60), default="Available")
    location_code: Mapped[str] = mapped_column(String(100), index=True)
    image_path: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("part_number", "location_code", name="uq_part_location"),)


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_number: Mapped[str] = mapped_column(String(120), index=True)
    location_code: Mapped[str] = mapped_column(String(100), index=True)
    transaction_type: Mapped[str] = mapped_column(String(40))
    quantity: Mapped[float] = mapped_column(Float)
    equipment_id: Mapped[str] = mapped_column(String(100), default="")
    related_ticket: Mapped[str] = mapped_column(String(100), default="")
    user: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped[str] = mapped_column(Text, default="")


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_number: Mapped[str] = mapped_column(String(120), index=True)
    location_code: Mapped[str] = mapped_column(String(100), default="", index=True)
    quantity: Mapped[float] = mapped_column(Float)
    pm_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(40), default="Reserved")
    reserved_by: Mapped[str] = mapped_column(String(120), default="")
    reserved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)


class LayoutBackground(Base):
    __tablename__ = "layout_backgrounds"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    image_path: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[str] = mapped_column(String(120), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentLink(Base):
    __tablename__ = "document_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_key: Mapped[str] = mapped_column(String(120), index=True)
    document_type: Mapped[str] = mapped_column(String(80), default="Document")
    title: Mapped[str] = mapped_column(String(250), default="")
    revision: Mapped[str] = mapped_column(String(60), default="")
    path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="Active")
    added_by: Mapped[str] = mapped_column(String(120), default="")
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user: Mapped[str] = mapped_column(String(120), index=True)
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_key: Mapped[str] = mapped_column(String(120), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    workstation: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


PBKDF2_ROUNDS = 310_000

ROLE_PERMISSIONS = {
    "Administrator": {"*"},
    "Manager": {"view", "equipment.edit", "pm.edit", "pm.execute", "pm.approve", "ticket.edit", "disposition.edit", "release.approve", "endorsement.edit", "inventory.edit", "inventory.reserve", "document.link", "report.view"},
    "Supervisor": {"view", "equipment.edit", "pm.edit", "pm.execute", "ticket.edit", "disposition.edit", "release.verify", "endorsement.edit", "inventory.edit", "inventory.reserve", "document.link", "report.view"},
    "Equipment Engineer": {"view", "equipment.edit", "pm.edit", "pm.execute", "ticket.edit", "disposition.edit", "release.verify", "endorsement.edit", "inventory.edit", "inventory.reserve", "document.link", "report.view"},
    "Maintenance": {"view", "pm.execute", "ticket.edit", "endorsement.edit", "inventory.consume", "inventory.reserve", "document.link"},
    "Technician": {"view", "pm.execute", "ticket.edit", "inventory.consume", "document.link"},
    "Process Engineer": {"view", "ticket.edit", "release.verify", "document.link", "report.view"},
    "Inventory Controller": {"view", "inventory.edit", "inventory.consume", "inventory.reserve", "document.link"},
    "Document Controller": {"view", "document.link", "document.control"},
    "Read Only": {"view", "report.view"},
}

PERMISSIONS = [
    "view", "equipment.edit", "layout.edit", "pm.edit", "pm.execute", "pm.approve",
    "ticket.edit", "disposition.edit", "release.verify", "release.approve", "endorsement.edit",
    "inventory.edit", "inventory.consume", "inventory.reserve", "document.link", "document.control",
    "user.admin", "audit.view", "report.view",
]


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds, salt_hex, digest_hex = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return secrets.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


class Database:
    def __init__(self, url: str | None = None):
        self.url = url or os.getenv("EMS_DATABASE_URL", "sqlite:///equipment_manager.db")
        args = {"check_same_thread": False} if self.url.startswith("sqlite") else {}
        self.engine = create_engine(self.url, future=True, pool_pre_ping=True, connect_args=args)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False, future=True)
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self):
        s = self.Session()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def health(self) -> tuple[bool, str]:
        try:
            with self.engine.connect() as c:
                c.execute(select(func.now()))
            return True, "PostgreSQL" if self.url.startswith("postgresql") else "SQLite local/demo"
        except Exception as exc:
            return False, str(exc)

    def has_users(self) -> bool:
        with self.session() as s:
            return bool(s.scalar(select(func.count()).select_from(User)))

    def create_user(self, username: str, display_name: str, password: str, role: str = "Administrator") -> int:
        if len(password) < 10:
            raise ValueError("Password must be at least 10 characters")
        with self.session() as s:
            u = User(username=username.strip(), display_name=display_name.strip() or username.strip(), password_hash=hash_password(password), role=role)
            s.add(u); s.flush(); return u.id

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        with self.session() as s:
            u = s.scalar(select(User).where(User.username == username.strip()))
            if not u or not u.active or not verify_password(password, u.password_hash):
                return None
            u.last_login = datetime.utcnow(); s.flush()
            return {"id": u.id, "username": u.username, "display_name": u.display_name, "role": u.role}

    def list_users(self):
        with self.session() as s:
            return list(s.scalars(select(User).order_by(User.username)))

    def update_user(self, username: str, role: str | None = None, active: bool | None = None, password: str | None = None):
        with self.session() as s:
            u = s.scalar(select(User).where(User.username == username))
            if not u: raise ValueError("User not found")
            if role is not None: u.role = role
            if active is not None: u.active = active
            if password is not None:
                if len(password) < 10: raise ValueError("Password must be at least 10 characters")
                u.password_hash = hash_password(password)
            s.flush(); return u

    def set_permission_override(self, username: str, permission: str, allowed: bool | None):
        with self.session() as s:
            row = s.scalar(select(UserPermission).where(UserPermission.username == username, UserPermission.permission == permission))
            if allowed is None:
                if row: s.delete(row)
                return
            if row: row.allowed = bool(allowed)
            else: s.add(UserPermission(username=username, permission=permission, allowed=bool(allowed)))

    def permission_overrides(self, username: str) -> dict[str, bool]:
        with self.session() as s:
            return {x.permission: x.allowed for x in s.scalars(select(UserPermission).where(UserPermission.username == username))}

    def has_permission(self, user: dict[str, Any], permission: str) -> bool:
        overrides = self.permission_overrides(user["username"])
        if permission in overrides: return overrides[permission]
        base = ROLE_PERMISSIONS.get(user.get("role", "Read Only"), {"view"})
        return "*" in base or permission in base or (permission != "view" and "*" in base)

    def audit(self, user: str, action: str, entity_type: str, entity_key: str = "", detail: str = "", workstation: str = ""):
        with self.session() as s:
            s.add(AuditLog(user=user, action=action, entity_type=entity_type, entity_key=entity_key, detail=detail, workstation=workstation))

    @staticmethod
    def _update_versioned(item, data: dict[str, Any], expected_version: int | None, label: str):
        if expected_version is not None and item.version != expected_version:
            raise RuntimeError(f"CONFLICT: {label} changed by another user.")
        for k, v in data.items():
            if hasattr(item, k) and k not in {"id", "version"}: setattr(item, k, v)
        item.version += 1

    def list_equipment(self, search_text: str = ""):
        with self.session() as s:
            stmt = select(Equipment).order_by(Equipment.equipment_id)
            if search_text:
                q = f"%{search_text}%"
                stmt = stmt.where(Equipment.equipment_id.ilike(q) | Equipment.name.ilike(q) | Equipment.area.ilike(q) | Equipment.status.ilike(q))
            return list(s.scalars(stmt))

    def get_equipment(self, equipment_id: str):
        with self.session() as s: return s.scalar(select(Equipment).where(Equipment.equipment_id == equipment_id))

    def save_equipment(self, data: dict[str, Any], expected_version: int | None = None):
        with self.session() as s:
            item = s.scalar(select(Equipment).where(Equipment.equipment_id == data["equipment_id"]))
            if item: self._update_versioned(item, data, expected_version, "Equipment")
            else: item = Equipment(**data); s.add(item)
            s.flush(); return item

    def update_map_position(self, entity_type: str, key: str, x: float, y: float, expected_version: int | None = None):
        with self.session() as s:
            if entity_type == "equipment":
                item = s.scalar(select(Equipment).where(Equipment.equipment_id == key)); label = "Equipment layout"
            elif entity_type == "storage":
                item = s.scalar(select(StorageLocation).where(StorageLocation.location_code == key)); label = "Storage layout"
            else: raise ValueError("Unknown map entity")
            if not item: raise ValueError("Map entity not found")
            self._update_versioned(item, {"map_x": float(x), "map_y": float(y)}, expected_version, label)
            s.flush(); return item

    def set_layout_background(self, scope_key: str, image_path: str, user: str):
        with self.session() as s:
            item = s.scalar(select(LayoutBackground).where(LayoutBackground.scope_key == scope_key))
            if item: item.image_path=image_path; item.updated_by=user
            else: item=LayoutBackground(scope_key=scope_key,image_path=image_path,updated_by=user); s.add(item)
            s.flush(); return item

    def get_layout_background(self, scope_key: str) -> str:
        with self.session() as s:
            item=s.scalar(select(LayoutBackground).where(LayoutBackground.scope_key==scope_key)); return item.image_path if item else ""

    def save_pm_definition(self, data: dict[str, Any], expected_version: int | None = None):
        with self.session() as s:
            item = s.scalar(select(PMDefinition).where(PMDefinition.pm_id == data["pm_id"]))
            if item: self._update_versioned(item, data, expected_version, "PM definition")
            else: item = PMDefinition(**data); s.add(item)
            s.flush(); return item

    def list_pm_definitions(self):
        with self.session() as s: return list(s.scalars(select(PMDefinition).order_by(PMDefinition.pm_id)))

    def upsert_pm_task(self, data: dict[str, Any]):
        with self.session() as s:
            item = s.scalar(select(PMTask).where(PMTask.equipment_id == data.get("equipment_id", ""), PMTask.pm_id == data.get("pm_id", ""), PMTask.original_due_date == data.get("original_due_date")))
            if item: self._update_versioned(item, data, None, "PM task")
            else: item = PMTask(**data); s.add(item)
            s.flush(); return item

    def list_pm_tasks(self):
        with self.session() as s: return list(s.scalars(select(PMTask).order_by(PMTask.original_due_date.asc().nullslast(), PMTask.equipment_id)))

    def get_pm_task(self, task_id: int):
        with self.session() as s: return s.get(PMTask, task_id)

    def upsert_pm_spec(self, data: dict[str, Any], create_revision: bool = False):
        with self.session() as s:
            current = s.scalar(select(PMSpec).where(PMSpec.pm_id == data["pm_id"], PMSpec.step_no == int(data["step_no"]), PMSpec.active.is_(True)).order_by(PMSpec.revision.desc()))
            if current and create_revision:
                current.active = False
                nd = dict(data); nd["revision"] = current.revision + 1; nd["active"] = True
                current = PMSpec(**nd); s.add(current)
            elif current: self._update_versioned(current, data, None, "PM specification")
            else: current = PMSpec(**data); s.add(current)
            s.flush(); return current

    def list_pm_specs(self, pm_id: str = ""):
        with self.session() as s:
            stmt = select(PMSpec).where(PMSpec.active.is_(True)).order_by(PMSpec.pm_id, PMSpec.step_no)
            if pm_id: stmt = stmt.where(PMSpec.pm_id == pm_id)
            return list(s.scalars(stmt))

    def start_pm_execution(self, task_id: int, user: str):
        with self.session() as s:
            ex = s.scalar(select(PMExecution).where(PMExecution.task_id == task_id))
            if ex: return ex
            task = s.get(PMTask, task_id)
            if not task: raise ValueError("PM task not found")
            ex = PMExecution(task_id=task_id, started_by=user); s.add(ex)
            task.status = "In Progress"; task.version += 1; s.flush(); return ex

    def save_pm_result(self, execution_id: int, step_no: int, data: dict[str, Any], expected_version: int | None = None):
        with self.session() as s:
            item = s.scalar(select(PMResult).where(PMResult.execution_id == execution_id, PMResult.step_no == step_no))
            payload = dict(data); payload.update(execution_id=execution_id, step_no=step_no)
            if item: self._update_versioned(item, payload, expected_version, "PM result")
            else: item = PMResult(**payload); s.add(item)
            s.flush(); return item

    def list_pm_results(self, execution_id: int):
        with self.session() as s: return list(s.scalars(select(PMResult).where(PMResult.execution_id == execution_id).order_by(PMResult.step_no)))

    def complete_pm_execution(self, execution_id: int, user: str):
        with self.session() as s:
            ex = s.get(PMExecution, execution_id)
            if not ex: raise ValueError("Execution not found")
            if ex.status == "Completed": return ex
            task = s.get(PMTask, ex.task_id)
            specs = list(s.scalars(select(PMSpec).where(PMSpec.pm_id == task.pm_id, PMSpec.active.is_(True))))
            results = list(s.scalars(select(PMResult).where(PMResult.execution_id == execution_id)))
            have = {r.step_no for r in results}
            missing = [p.step_no for p in specs if p.step_no not in have]
            if missing: raise ValueError(f"Missing required PM steps: {missing}")
            hard_fail = [r.step_no for r in results if r.result in {"SPECIFICATION FAILURE", "CONTROL FAILURE", "FAIL", "INVALID"}]
            if hard_fail: raise ValueError(f"Failed/invalid PM steps require correction, disposition, or engineering review: {hard_fail}")
            now = datetime.utcnow(); ex.status="Completed"; ex.completed_by=user; ex.completed_at=now; ex.version += 1
            task.status="Completed"; task.last_completion_date=now; task.version += 1; s.flush(); return ex

    def list_tickets(self):
        with self.session() as s: return list(s.scalars(select(Ticket).order_by(Ticket.created_at.desc())))

    def save_ticket(self, data: dict[str, Any], expected_version: int | None = None):
        with self.session() as s:
            item = s.scalar(select(Ticket).where(Ticket.ticket_no == data["ticket_no"]))
            if item: self._update_versioned(item, data, expected_version, "Ticket")
            else: item=Ticket(**data); s.add(item)
            s.flush(); return item

    def add_ticket_investigation(self, ticket_no: str, data: dict[str, Any]):
        with self.session() as s:
            seq = (s.scalar(select(func.max(TicketInvestigation.sequence)).where(TicketInvestigation.ticket_no == ticket_no)) or 0) + 1
            item=TicketInvestigation(ticket_no=ticket_no,sequence=seq,**data); s.add(item); s.flush(); return item

    def list_ticket_investigations(self, ticket_no: str):
        with self.session() as s:
            return list(s.scalars(select(TicketInvestigation).where(TicketInvestigation.ticket_no==ticket_no).order_by(TicketInvestigation.sequence)))

    def set_disposition(self, data: dict[str, Any]):
        with self.session() as s:
            stmt = select(Equipment).where(Equipment.equipment_id == data["equipment_id"])
            if not self.url.startswith("sqlite"): stmt = stmt.with_for_update()
            eq = s.scalar(stmt)
            if not eq: raise ValueError("Equipment not found")
            for d in s.scalars(select(Disposition).where(Disposition.equipment_id==data["equipment_id"],Disposition.active.is_(True))): d.active=False
            d=Disposition(**data); s.add(d); eq.disposition=d.state; eq.version += 1; s.flush(); return d

    def list_dispositions(self, active_only: bool = False):
        with self.session() as s:
            stmt=select(Disposition).order_by(Disposition.effective_at.desc())
            if active_only: stmt=stmt.where(Disposition.active.is_(True))
            return list(s.scalars(stmt))

    def release_precheck(self, equipment_id: str) -> dict[str, Any]:
        with self.session() as s:
            critical = int(s.scalar(select(func.count()).select_from(Ticket).where(Ticket.equipment_id==equipment_id,Ticket.priority.in_(["P1","P2"]),Ticket.status.notin_(["Closed","Cancelled"]))) or 0)
            overdue = int(s.scalar(select(func.count()).select_from(PMTask).where(PMTask.equipment_id==equipment_id,PMTask.status=="Overdue")) or 0)
            return {"critical_tickets_open": critical, "overdue_pm": overdue}

    def create_release_request(self, equipment_id: str, related_ticket: str, checks: dict[str, bool], notes: str, user: str):
        with self.session() as s:
            if not s.scalar(select(Equipment).where(Equipment.equipment_id==equipment_id)): raise ValueError("Equipment not found")
            r=EquipmentRelease(equipment_id=equipment_id,related_ticket=related_ticket,checks_json=json.dumps(checks),notes=notes,requested_by=user)
            s.add(r); s.flush(); return r

    def list_release_requests(self):
        with self.session() as s: return list(s.scalars(select(EquipmentRelease).order_by(EquipmentRelease.requested_at.desc())))

    def verify_release(self, release_id: int, checks: dict[str, bool], user: str, expected_version: int | None=None):
        with self.session() as s:
            r=s.get(EquipmentRelease,release_id)
            if not r: raise ValueError("Release request not found")
            if expected_version is not None and r.version!=expected_version: raise RuntimeError("CONFLICT: Release request changed by another user.")
            r.checks_json=json.dumps(checks); r.verified_by=user; r.verified_at=datetime.utcnow(); r.status="Verified" if all(checks.values()) else "Verification Failed"; r.version+=1
            s.flush(); return r

    def approve_release(self, release_id: int, user: str, expected_version: int | None=None):
        with self.session() as s:
            r=s.get(EquipmentRelease,release_id)
            if not r: raise ValueError("Release request not found")
            if expected_version is not None and r.version!=expected_version: raise RuntimeError("CONFLICT: Release request changed by another user.")
            checks=json.loads(r.checks_json or "{}")
            if r.status!="Verified" or not checks or not all(checks.values()): raise ValueError("Release must be fully verified before approval")
            critical = int(s.scalar(select(func.count()).select_from(Ticket).where(Ticket.equipment_id==r.equipment_id, Ticket.priority.in_(["P1","P2"]), Ticket.status.notin_(["Closed","Cancelled"]))) or 0)
            if critical: raise ValueError(f"Cannot release equipment while {critical} P1/P2 ticket(s) remain open")
            stmt=select(Equipment).where(Equipment.equipment_id==r.equipment_id)
            if not self.url.startswith("sqlite"): stmt=stmt.with_for_update()
            eq=s.scalar(stmt)
            for d in s.scalars(select(Disposition).where(Disposition.equipment_id==r.equipment_id,Disposition.active.is_(True))): d.active=False
            s.add(Disposition(equipment_id=r.equipment_id,state="Released",reason="Verified equipment release",related_ticket=r.related_ticket,created_by=r.requested_by,approved_by=user))
            eq.disposition="Released"; eq.version+=1
            r.status="Approved / Released"; r.approved_by=user; r.approved_at=datetime.utcnow(); r.version+=1; s.flush(); return r

    def save_endorsement(self, data: dict[str, Any], expected_version: int | None = None):
        with self.session() as s:
            item=s.scalar(select(Endorsement).where(Endorsement.endorsement_no==data["endorsement_no"]))
            if item: self._update_versioned(item,data,expected_version,"Endorsement")
            else: item=Endorsement(**data); s.add(item)
            s.flush(); return item

    def acknowledge_endorsement(self, endorsement_no: str, user: str):
        with self.session() as s:
            item=s.scalar(select(Endorsement).where(Endorsement.endorsement_no==endorsement_no))
            if not item: raise ValueError("Endorsement not found")
            if item.status == "Open": item.status="Acknowledged"; item.acknowledged_by=user; item.acknowledged_at=datetime.utcnow(); item.version += 1
            s.flush(); return item

    def list_endorsements(self):
        with self.session() as s: return list(s.scalars(select(Endorsement).order_by(Endorsement.created_at.desc())))

    def save_storage_location(self, data: dict[str, Any], expected_version: int | None = None):
        with self.session() as s:
            item=s.scalar(select(StorageLocation).where(StorageLocation.location_code==data["location_code"]))
            if item: self._update_versioned(item,data,expected_version,"Storage location")
            else: item=StorageLocation(**data); s.add(item)
            s.flush(); return item

    def list_storage_locations(self):
        with self.session() as s: return list(s.scalars(select(StorageLocation).order_by(StorageLocation.location_code)))

    def save_inventory_item(self, data: dict[str, Any], expected_version: int | None = None):
        with self.session() as s:
            item=s.scalar(select(InventoryItem).where(InventoryItem.part_number==data["part_number"],InventoryItem.location_code==data["location_code"]))
            if item: self._update_versioned(item,data,expected_version,"Inventory")
            else: item=InventoryItem(**data); s.add(item)
            s.flush(); return item

    def list_inventory(self, search_text: str = ""):
        with self.session() as s:
            stmt=select(InventoryItem).order_by(InventoryItem.part_number,InventoryItem.location_code)
            if search_text:
                q=f"%{search_text}%"; stmt=stmt.where(InventoryItem.part_number.ilike(q)|InventoryItem.description.ilike(q)|InventoryItem.location_code.ilike(q))
            return list(s.scalars(stmt))

    def inventory_available(self, part_number: str, location_code: str = "") -> float:
        with self.session() as s:
            stmt=select(func.sum(InventoryItem.quantity)).where(InventoryItem.part_number==part_number,InventoryItem.condition=="Available")
            if location_code: stmt=stmt.where(InventoryItem.location_code==location_code)
            stock=float(s.scalar(stmt) or 0.0)
            rstmt=select(func.sum(InventoryReservation.quantity)).where(InventoryReservation.part_number==part_number,InventoryReservation.status=="Reserved")
            if location_code: rstmt=rstmt.where(InventoryReservation.location_code==location_code)
            return max(0.0, stock-float(s.scalar(rstmt) or 0.0))

    def reserve_inventory(self, part_number: str, qty: float, user: str, pm_task_id: int | None=None, equipment_id: str="", location_code: str="", note: str=""):
        if qty<=0: raise ValueError("Quantity must be positive")
        with self.session() as s:
            stmt=select(InventoryItem).where(InventoryItem.part_number==part_number,InventoryItem.condition=="Available")
            if location_code: stmt=stmt.where(InventoryItem.location_code==location_code)
            if not self.url.startswith("sqlite"): stmt=stmt.with_for_update()
            stock=list(s.scalars(stmt))
            total=sum(x.quantity for x in stock)
            rstmt=select(func.sum(InventoryReservation.quantity)).where(InventoryReservation.part_number==part_number,InventoryReservation.status=="Reserved")
            if location_code: rstmt=rstmt.where(InventoryReservation.location_code==location_code)
            reserved=float(s.scalar(rstmt) or 0.0)
            if total-reserved < qty: return False, max(0.0,total-reserved)
            loc=location_code or (stock[0].location_code if len(stock)==1 else "")
            r=InventoryReservation(part_number=part_number,location_code=loc,quantity=qty,pm_task_id=pm_task_id,equipment_id=equipment_id,reserved_by=user,note=note)
            s.add(r); s.flush(); return True,r.id

    def release_reservation(self, reservation_id: int, user: str):
        with self.session() as s:
            r=s.get(InventoryReservation,reservation_id)
            if not r: raise ValueError("Reservation not found")
            if r.status=="Reserved": r.status="Released"; r.released_at=datetime.utcnow(); r.note=(r.note+f"\nReleased by {user}").strip(); r.version+=1
            s.flush(); return r

    def list_reservations(self, active_only: bool=False):
        with self.session() as s:
            stmt=select(InventoryReservation).order_by(InventoryReservation.reserved_at.desc())
            if active_only: stmt=stmt.where(InventoryReservation.status=="Reserved")
            return list(s.scalars(stmt))

    def consume_inventory(self, part_number: str, location_code: str, qty: float, user: str="", equipment_id: str="", related_ticket: str=""):
        if qty <= 0: raise ValueError("Quantity must be positive")
        with self.session() as s:
            stmt=select(InventoryItem).where(InventoryItem.part_number==part_number,InventoryItem.location_code==location_code)
            if not self.url.startswith("sqlite"): stmt=stmt.with_for_update()
            item=s.scalar(stmt)
            if not item or item.quantity < qty: return False, item.quantity if item else 0.0
            item.quantity -= qty; item.version += 1
            s.add(InventoryTransaction(part_number=part_number,location_code=location_code,transaction_type="Consume",quantity=-qty,equipment_id=equipment_id,related_ticket=related_ticket,user=user))
            s.flush(); return True,item.quantity

    def list_inventory_transactions(self, limit: int=500):
        with self.session() as s: return list(s.scalars(select(InventoryTransaction).order_by(InventoryTransaction.created_at.desc()).limit(limit)))

    def add_document(self, data: dict[str, Any]):
        with self.session() as s: s.add(DocumentLink(**data))

    def list_documents(self, entity_type: str="", entity_key: str=""):
        with self.session() as s:
            stmt=select(DocumentLink).order_by(DocumentLink.added_at.desc())
            if entity_type: stmt=stmt.where(DocumentLink.entity_type==entity_type)
            if entity_key: stmt=stmt.where(DocumentLink.entity_key==entity_key)
            return list(s.scalars(stmt))

    def list_audit(self, limit: int=500):
        with self.session() as s: return list(s.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)))

    def dashboard_counts(self):
        with self.session() as s:
            c=lambda model,*w: int(s.scalar(select(func.count()).select_from(model).where(*w)) or 0)
            return {
                "equipment_total":c(Equipment), "equipment_down":c(Equipment,Equipment.status=="Down"),
                "equipment_hold":c(Equipment,Equipment.disposition.ilike("%Hold%")),
                "pm_open":c(PMTask,PMTask.status.in_(["Pending","Scheduled","In Progress","Overdue"])),
                "pm_overdue":c(PMTask,PMTask.status=="Overdue"),
                "tickets_open":c(Ticket,Ticket.status.notin_(["Closed","Cancelled"])),
                "tickets_critical":c(Ticket,Ticket.priority.in_(["P1","P2"]),Ticket.status.notin_(["Closed","Cancelled"])),
                "inventory_low":c(InventoryItem,InventoryItem.quantity<=InventoryItem.min_quantity),
                "endorsements_open":c(Endorsement,Endorsement.status.in_(["Open","Acknowledged"])),
                "dispositions_active":c(Disposition,Disposition.active.is_(True)),
                "release_pending":c(EquipmentRelease,EquipmentRelease.status.in_(["Pending Verification","Verified","Verification Failed"])),
                "reservations_active":c(InventoryReservation,InventoryReservation.status=="Reserved"),
            }
