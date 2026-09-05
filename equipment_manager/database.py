from __future__ import annotations

import hashlib
import os
import secrets
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(50), default="Engineer")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


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


class PMTask(Base):
    __tablename__ = "pm_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    pm_id: Mapped[str] = mapped_column(String(100), index=True)
    pm_name: Mapped[str] = mapped_column(String(250), default="")
    schedule_type: Mapped[str] = mapped_column(String(80), default="Interval")
    frequency_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    frequency_unit: Mapped[str] = mapped_column(String(30), default="days")
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
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("pm_id", "step_no", "revision", name="uq_pm_spec_revision"),)


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
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


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
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("part_number", "location_code", name="uq_part_location"),)


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
    disposition: Mapped[str] = mapped_column(String(80), default="")
    root_cause: Mapped[str] = mapped_column(Text, default="")
    corrective_action: Mapped[str] = mapped_column(Text, default="")
    verification: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


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


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds, salt_hex, digest_hex = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)
        )
        return secrets.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


class Database:
    def __init__(self, url: str | None = None):
        self.url = url or os.getenv("EMS_DATABASE_URL", "sqlite:///equipment_manager.db")
        connect_args = {"check_same_thread": False} if self.url.startswith("sqlite") else {}
        self.engine = create_engine(self.url, future=True, pool_pre_ping=True, connect_args=connect_args)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False, future=True)
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def health(self) -> tuple[bool, str]:
        try:
            with self.engine.connect() as conn:
                conn.execute(select(func.now()))
            backend = "PostgreSQL" if self.url.startswith("postgresql") else "SQLite local/demo"
            return True, backend
        except Exception as exc:
            return False, str(exc)

    def has_users(self) -> bool:
        with self.session() as s:
            return (s.scalar(select(func.count()).select_from(User)) or 0) > 0

    def create_user(self, username: str, display_name: str, password: str, role: str = "Administrator") -> int:
        with self.session() as s:
            user = User(
                username=username.strip(),
                display_name=display_name.strip() or username.strip(),
                password_hash=hash_password(password),
                role=role,
            )
            s.add(user)
            s.flush()
            return user.id

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        with self.session() as s:
            user = s.scalar(select(User).where(User.username == username.strip()))
            if not user or not user.active or not verify_password(password, user.password_hash):
                return None
            user.last_login = datetime.utcnow()
            s.flush()
            return {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role,
            }

    def audit(self, user: str, action: str, entity_type: str, entity_key: str = "", detail: str = "", workstation: str = ""):
        with self.session() as s:
            s.add(AuditLog(user=user, action=action, entity_type=entity_type, entity_key=entity_key, detail=detail, workstation=workstation))

    def list_equipment(self, search_text: str = "") -> list[Equipment]:
        with self.session() as s:
            stmt = select(Equipment).order_by(Equipment.equipment_id)
            if search_text:
                q = f"%{search_text}%"
                stmt = stmt.where(
                    Equipment.equipment_id.ilike(q)
                    | Equipment.name.ilike(q)
                    | Equipment.area.ilike(q)
                    | Equipment.status.ilike(q)
                )
            return list(s.scalars(stmt).all())

    def save_equipment(self, data: dict[str, Any], expected_version: int | None = None) -> Equipment:
        with self.session() as s:
            item = s.scalar(select(Equipment).where(Equipment.equipment_id == data["equipment_id"]))
            if item:
                if expected_version is not None and item.version != expected_version:
                    raise RuntimeError("CONFLICT: Equipment record changed by another user.")
                for key, value in data.items():
                    if hasattr(item, key) and key not in {"id", "version"}:
                        setattr(item, key, value)
                item.version += 1
            else:
                item = Equipment(**data)
                s.add(item)
            s.flush()
            return item

    def dashboard_counts(self) -> dict[str, int]:
        with self.session() as s:
            total = s.scalar(select(func.count()).select_from(Equipment)) or 0
            down = s.scalar(select(func.count()).select_from(Equipment).where(Equipment.status == "Down")) or 0
            hold = s.scalar(select(func.count()).select_from(Equipment).where(Equipment.disposition.ilike("%Hold%"))) or 0
            pm_overdue = s.scalar(select(func.count()).select_from(PMTask).where(PMTask.status == "Overdue")) or 0
            pm_open = s.scalar(select(func.count()).select_from(PMTask).where(PMTask.status.in_(["Pending", "Scheduled", "In Progress", "Overdue"]))) or 0
            tickets = s.scalar(select(func.count()).select_from(Ticket).where(Ticket.status.notin_(["Closed", "Cancelled"]))) or 0
            p1p2 = s.scalar(select(func.count()).select_from(Ticket).where(Ticket.priority.in_(["P1", "P2"]), Ticket.status.notin_(["Closed", "Cancelled"]))) or 0
            low_stock = s.scalar(select(func.count()).select_from(InventoryItem).where(InventoryItem.quantity <= InventoryItem.min_quantity)) or 0
            return {
                "equipment_total": int(total), "equipment_down": int(down), "equipment_hold": int(hold),
                "pm_open": int(pm_open), "pm_overdue": int(pm_overdue), "tickets_open": int(tickets),
                "tickets_critical": int(p1p2), "inventory_low": int(low_stock),
            }

    def list_pm_tasks(self) -> list[PMTask]:
        with self.session() as s:
            return list(s.scalars(select(PMTask).order_by(PMTask.original_due_date.asc().nullslast(), PMTask.equipment_id)).all())

    def list_pm_specs(self, pm_id: str = "") -> list[PMSpec]:
        with self.session() as s:
            stmt = select(PMSpec).where(PMSpec.active.is_(True)).order_by(PMSpec.pm_id, PMSpec.step_no)
            if pm_id:
                stmt = stmt.where(PMSpec.pm_id == pm_id)
            return list(s.scalars(stmt).all())

    def upsert_pm_task(self, data: dict[str, Any]):
        with self.session() as s:
            stmt = select(PMTask).where(
                PMTask.equipment_id == data.get("equipment_id", ""),
                PMTask.pm_id == data.get("pm_id", ""),
                PMTask.original_due_date == data.get("original_due_date"),
            )
            item = s.scalar(stmt)
            if item:
                for key, value in data.items():
                    if hasattr(item, key) and key not in {"id", "version"}:
                        setattr(item, key, value)
                item.version += 1
            else:
                s.add(PMTask(**data))

    def upsert_pm_spec(self, data: dict[str, Any], create_revision: bool = False):
        with self.session() as s:
            pm_id = data["pm_id"]
            step_no = int(data["step_no"])
            current = s.scalar(
                select(PMSpec)
                .where(PMSpec.pm_id == pm_id, PMSpec.step_no == step_no, PMSpec.active.is_(True))
                .order_by(PMSpec.revision.desc())
            )
            if current and create_revision:
                current.active = False
                new_data = dict(data)
                new_data["revision"] = current.revision + 1
                new_data["active"] = True
                s.add(PMSpec(**new_data))
            elif current:
                for key, value in data.items():
                    if hasattr(current, key) and key not in {"id", "version", "revision"}:
                        setattr(current, key, value)
                current.version += 1
            else:
                s.add(PMSpec(**data))

    def list_storage_locations(self) -> list[StorageLocation]:
        with self.session() as s:
            return list(s.scalars(select(StorageLocation).order_by(StorageLocation.location_code)).all())

    def save_storage_location(self, data: dict[str, Any], expected_version: int | None = None):
        with self.session() as s:
            item = s.scalar(select(StorageLocation).where(StorageLocation.location_code == data["location_code"]))
            if item:
                if expected_version is not None and item.version != expected_version:
                    raise RuntimeError("CONFLICT: Storage location changed by another user.")
                for key, value in data.items():
                    if hasattr(item, key) and key not in {"id", "version"}:
                        setattr(item, key, value)
                item.version += 1
            else:
                s.add(StorageLocation(**data))

    def list_inventory(self, search_text: str = "") -> list[InventoryItem]:
        with self.session() as s:
            stmt = select(InventoryItem).order_by(InventoryItem.part_number, InventoryItem.location_code)
            if search_text:
                q = f"%{search_text}%"
                stmt = stmt.where(
                    InventoryItem.part_number.ilike(q)
                    | InventoryItem.description.ilike(q)
                    | InventoryItem.location_code.ilike(q)
                )
            return list(s.scalars(stmt).all())

    def save_inventory_item(self, data: dict[str, Any], expected_version: int | None = None):
        with self.session() as s:
            item = s.scalar(select(InventoryItem).where(
                InventoryItem.part_number == data["part_number"],
                InventoryItem.location_code == data["location_code"],
            ))
            if item:
                if expected_version is not None and item.version != expected_version:
                    raise RuntimeError("CONFLICT: Inventory record changed by another user.")
                for key, value in data.items():
                    if hasattr(item, key) and key not in {"id", "version"}:
                        setattr(item, key, value)
                item.version += 1
            else:
                s.add(InventoryItem(**data))

    def consume_inventory(self, part_number: str, location_code: str, qty: float) -> tuple[bool, float]:
        if qty <= 0:
            raise ValueError("Quantity must be positive")
        with self.session() as s:
            stmt = select(InventoryItem).where(
                InventoryItem.part_number == part_number,
                InventoryItem.location_code == location_code,
            )
            if not self.url.startswith("sqlite"):
                stmt = stmt.with_for_update()
            item = s.scalar(stmt)
            if not item or item.quantity < qty:
                return False, item.quantity if item else 0.0
            item.quantity -= qty
            item.version += 1
            s.flush()
            return True, item.quantity

    def list_tickets(self) -> list[Ticket]:
        with self.session() as s:
            return list(s.scalars(select(Ticket).order_by(Ticket.created_at.desc())).all())

    def save_ticket(self, data: dict[str, Any], expected_version: int | None = None):
        with self.session() as s:
            item = s.scalar(select(Ticket).where(Ticket.ticket_no == data["ticket_no"]))
            if item:
                if expected_version is not None and item.version != expected_version:
                    raise RuntimeError("CONFLICT: Ticket changed by another user.")
                for key, value in data.items():
                    if hasattr(item, key) and key not in {"id", "version"}:
                        setattr(item, key, value)
                item.version += 1
            else:
                s.add(Ticket(**data))

    def add_document(self, data: dict[str, Any]):
        with self.session() as s:
            s.add(DocumentLink(**data))

    def list_documents(self, entity_type: str = "", entity_key: str = "") -> list[DocumentLink]:
        with self.session() as s:
            stmt = select(DocumentLink).order_by(DocumentLink.added_at.desc())
            if entity_type:
                stmt = stmt.where(DocumentLink.entity_type == entity_type)
            if entity_key:
                stmt = stmt.where(DocumentLink.entity_key == entity_key)
            return list(s.scalars(stmt).all())

    def list_audit(self, limit: int = 500) -> list[AuditLog]:
        with self.session() as s:
            return list(s.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all())
