from __future__ import annotations

import hashlib
import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, create_engine, func, inspect, or_, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from domain import (
    DOWNTIME_STATES, EQUIPMENT_STATES, STATE_CLASS, TICKET_STATES, REASON_CODES, TICKET_REASON_CODES,
    validate_ticket_transition, validate_transition,
)
from equipment_health import classify_health, health_rank


class Base(DeclarativeBase):
    pass


class SchemaMigration(Base):
    __tablename__ = "schema_migrations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    checksum: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(250))
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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


class UserRecentItem(Base):
    __tablename__ = "user_recent_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_key: Mapped[str] = mapped_column(String(180), index=True)
    title: Mapped[str] = mapped_column(String(250), default="")
    equipment_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    __table_args__ = (UniqueConstraint("username","entity_type","entity_key",name="uq_user_recent_item"),)


class UserFavorite(Base):
    __tablename__ = "user_favorites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_key: Mapped[str] = mapped_column(String(180), index=True)
    title: Mapped[str] = mapped_column(String(250), default="")
    equipment_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("username","entity_type","entity_key",name="uq_user_favorite"),)


class UserNotification(Base):
    __tablename__ = "user_notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(30), default="INFO", index=True)
    title: Mapped[str] = mapped_column(String(250))
    body: Mapped[str] = mapped_column(Text, default="")
    entity_type: Mapped[str] = mapped_column(String(60), default="", index=True)
    entity_key: Mapped[str] = mapped_column(String(180), default="", index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    dedupe_key: Mapped[str] = mapped_column(String(250), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class UserDraft(Base):
    __tablename__ = "user_drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_key: Mapped[str] = mapped_column(String(180), index=True)
    draft_key: Mapped[str] = mapped_column(String(120), default="main")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("username","entity_type","entity_key","draft_key",name="uq_user_draft"),)


class UserPreference(Base):
    __tablename__ = "user_preferences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    preference_key: Mapped[str] = mapped_column(String(180), index=True)
    value_json: Mapped[str] = mapped_column(Text, default="null")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("username","preference_key",name="uq_user_preference"),)


class EntityAttachment(Base):
    __tablename__ = "entity_attachments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attachment_key: Mapped[str] = mapped_column(String(48), unique=True, index=True, default=lambda: secrets.token_hex(20))
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_key: Mapped[str] = mapped_column(String(180), index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    category: Mapped[str] = mapped_column(String(60), default="Evidence", index=True)
    original_name: Mapped[str] = mapped_column(String(260), default="")
    stored_path: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(120), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_sha256: Mapped[str] = mapped_column(String(64), default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="")
    copied_from_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[str] = mapped_column(String(120), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AuthSecurityState(Base):
    __tablename__ = "auth_security_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(String(80), default="")
    workstation: Mapped[str] = mapped_column(String(120), default="")
    attempted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class FactoryNode(Base):
    __tablename__ = "factory_nodes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_code: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    parent_code: Mapped[str] = mapped_column(String(180), default="", index=True)
    node_type: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(180))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class EquipmentLocationAssignment(Base):
    __tablename__ = "equipment_location_assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    node_code: Mapped[str] = mapped_column(String(180), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    assigned_by: Mapped[str] = mapped_column(String(120), default="")
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("equipment_id","node_code","active",name="uq_equipment_location_active"),)


class ApprovalDelegation(Base):
    __tablename__ = "approval_delegations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delegator: Mapped[str] = mapped_column(String(80), index=True)
    delegate: Mapped[str] = mapped_column(String(80), index=True)
    permission: Mapped[str] = mapped_column(String(100), index=True)
    scope_type: Mapped[str] = mapped_column(String(30), default="GLOBAL")
    scope_key: Mapped[str] = mapped_column(String(180), default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    reason: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    revoked_by: Mapped[str] = mapped_column(String(80), default="")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoke_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class UserAccessPolicy(Base):
    __tablename__ = "user_access_policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    scope_mode: Mapped[str] = mapped_column(String(30), default="UNRESTRICTED")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class UserEquipmentScope(Base):
    __tablename__ = "user_equipment_scopes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    scope_type: Mapped[str] = mapped_column(String(30), index=True)
    scope_key: Mapped[str] = mapped_column(String(180), index=True)
    permission: Mapped[str] = mapped_column(String(100), default="*")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("username","scope_type","scope_key","permission",name="uq_user_equipment_scope"),)


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


class EquipmentAlarmEvent(Base):
    __tablename__ = "equipment_alarm_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    alarm_code: Mapped[str] = mapped_column(String(120), index=True)
    severity: Mapped[str] = mapped_column(String(30), default="Warning", index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(80), default="Manual", index=True)
    state: Mapped[str] = mapped_column(String(30), default="ACTIVE", index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    acknowledged_by: Mapped[str] = mapped_column(String(120), default="")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    related_ticket: Mapped[str] = mapped_column(String(100), default="", index=True)
    raw_payload_json: Mapped[str] = mapped_column(Text, default="{}")


class EquipmentStateEvent(Base):
    __tablename__ = "equipment_state_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(40), unique=True, index=True, default=lambda: secrets.token_hex(16))
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    from_state: Mapped[str] = mapped_column(String(40), default="")
    to_state: Mapped[str] = mapped_column(String(40), index=True)
    state_class: Mapped[str] = mapped_column(String(40), default="")
    downtime: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(60), index=True)
    reason_text: Mapped[str] = mapped_column(Text, default="")
    related_ticket: Mapped[str] = mapped_column(String(100), default="", index=True)
    related_pm_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    owner: Mapped[str] = mapped_column(String(120), default="")
    changed_by: Mapped[str] = mapped_column(String(120), default="", index=True)
    workstation: Mapped[str] = mapped_column(String(120), default="")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class EquipmentComponent(Base):
    __tablename__ = "equipment_components"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    parent_component_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    component_type: Mapped[str] = mapped_column(String(120), default="")
    manufacturer: Mapped[str] = mapped_column(String(120), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    serial_number: Mapped[str] = mapped_column(String(120), default="")
    part_number: Mapped[str] = mapped_column(String(120), default="", index=True)
    status: Mapped[str] = mapped_column(String(40), default="Installed", index=True)
    installed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    life_limit_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    life_limit_unit: Mapped[str] = mapped_column(String(40), default="")
    usage_value: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComponentEvent(Base):
    __tablename__ = "component_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_id: Mapped[str] = mapped_column(String(120), index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    parent_component_id: Mapped[str] = mapped_column(String(120), default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    related_ticket: Mapped[str] = mapped_column(String(100), default="")
    related_pm_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user: Mapped[str] = mapped_column(String(120), index=True)
    workstation: Mapped[str] = mapped_column(String(120), default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class EquipmentMeter(Base):
    __tablename__ = "equipment_meters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    meter_code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    unit: Mapped[str] = mapped_column(String(40), default="")
    current_value: Mapped[float] = mapped_column(Float, default=0.0)
    last_reading_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("equipment_id","meter_code",name="uq_equipment_meter"),)


class EquipmentMeterBehavior(Base):
    __tablename__ = "equipment_meter_behaviors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    meter_code: Mapped[str] = mapped_column(String(80), index=True)
    meter_mode: Mapped[str] = mapped_column(String(20), default="COUNTER")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("equipment_id","meter_code",name="uq_equipment_meter_behavior"),)


class MeterReading(Base):
    __tablename__ = "meter_readings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    meter_code: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[float] = mapped_column(Float)
    reading_type: Mapped[str] = mapped_column(String(30), default="Reading")
    note: Mapped[str] = mapped_column(Text, default="")
    recorded_by: Mapped[str] = mapped_column(String(120), index=True)
    workstation: Mapped[str] = mapped_column(String(120), default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PMUsageTrigger(Base):
    __tablename__ = "pm_usage_triggers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trigger_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    pm_id: Mapped[str] = mapped_column(String(100), index=True)
    meter_code: Mapped[str] = mapped_column(String(80), index=True)
    interval_value: Mapped[float] = mapped_column(Float)
    last_trigger_value: Mapped[float] = mapped_column(Float, default=0.0)
    next_trigger_value: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class PMUsageOccurrence(Base):
    __tablename__ = "pm_usage_occurrences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trigger_id: Mapped[str] = mapped_column(String(100), index=True)
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    pm_id: Mapped[str] = mapped_column(String(100), index=True)
    meter_code: Mapped[str] = mapped_column(String(80), index=True)
    trigger_value: Mapped[float] = mapped_column(Float)
    reading_value: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PMConditionTrigger(Base):
    __tablename__ = "pm_condition_triggers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trigger_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    pm_id: Mapped[str] = mapped_column(String(100), index=True)
    meter_code: Mapped[str] = mapped_column(String(80), index=True)
    comparator: Mapped[str] = mapped_column(String(10))
    threshold: Mapped[float] = mapped_column(Float)
    reset_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    latched: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class PMConditionOccurrence(Base):
    __tablename__ = "pm_condition_occurrences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trigger_id: Mapped[str] = mapped_column(String(100), index=True)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    pm_id: Mapped[str] = mapped_column(String(100), index=True)
    meter_code: Mapped[str] = mapped_column(String(80), index=True)
    threshold: Mapped[float] = mapped_column(Float)
    reading_value: Mapped[float] = mapped_column(Float)
    event_type: Mapped[str] = mapped_column(String(30), default="TRIGGERED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


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


class PMTaskSchedule(Base):
    __tablename__ = "pm_task_schedules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    baseline_start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scheduled_start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    scheduled_end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    planned_hours: Mapped[float] = mapped_column(Float, default=0.0)
    updated_by: Mapped[str] = mapped_column(String(120), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class PMTaskScheduleEvent(Base):
    __tablename__ = "pm_task_schedule_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    old_start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    old_end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    new_start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    new_end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    old_assignee: Mapped[str] = mapped_column(String(120), default="")
    new_assignee: Mapped[str] = mapped_column(String(120), default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    outside_window: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    changed_by: Mapped[str] = mapped_column(String(120), default="")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PMDeferral(Base):
    __tablename__ = "pm_deferrals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    pm_id: Mapped[str] = mapped_column(String(100), index=True)
    original_due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    requested_due_date: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(Text)
    risk_assessment: Mapped[str] = mapped_column(Text)
    mitigation: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(String(120), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(30), default="Pending", index=True)
    reviewed_by: Mapped[str] = mapped_column(String(120), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class TechnicianCertification(Base):
    __tablename__ = "technician_certifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    cert_code: Mapped[str] = mapped_column(String(100), index=True)
    issuer: Mapped[str] = mapped_column(String(180), default="")
    issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("username","cert_code",name="uq_technician_certification"),)


class PMRequirement(Base):
    __tablename__ = "pm_requirements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requirement_id: Mapped[str] = mapped_column(String(120), index=True)
    pm_id: Mapped[str] = mapped_column(String(100), index=True)
    requirement_type: Mapped[str] = mapped_column(String(40), index=True)
    requirement_key: Mapped[str] = mapped_column(String(160), default="")
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("requirement_id","revision",name="uq_pm_requirement_revision"),)


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
    screenshot_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    comment_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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


class PMExecutionPauseEvent(Base):
    __tablename__ = "pm_execution_pause_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(Integer, index=True)
    reason: Mapped[str] = mapped_column(String(80), index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    paused_by: Mapped[str] = mapped_column(String(120), default="")
    paused_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    resumed_by: Mapped[str] = mapped_column(String(120), default="")
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class PMExecutionStepSnapshot(Base):
    __tablename__ = "pm_execution_step_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(Integer, index=True)
    pm_id: Mapped[str] = mapped_column(String(100), index=True)
    source_spec_id: Mapped[int] = mapped_column(Integer)
    source_revision: Mapped[int] = mapped_column(Integer)
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
    screenshot_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    comment_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (UniqueConstraint("execution_id", "step_no", name="uq_pm_execution_snapshot_step"),)


class PMExecutionRequirementSnapshot(Base):
    __tablename__ = "pm_execution_requirement_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(Integer, index=True)
    source_requirement_id: Mapped[int] = mapped_column(Integer)
    requirement_id: Mapped[str] = mapped_column(String(120))
    requirement_type: Mapped[str] = mapped_column(String(40), index=True)
    requirement_key: Mapped[str] = mapped_column(String(160), default="")
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    source_revision: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("execution_id","requirement_id",name="uq_pm_execution_requirement"),)


class PMExecutionRequirementAck(Base):
    __tablename__ = "pm_execution_requirement_acks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(Integer, index=True)
    requirement_id: Mapped[str] = mapped_column(String(120), index=True)
    acknowledged_by: Mapped[str] = mapped_column(String(120))
    note: Mapped[str] = mapped_column(Text, default="")
    evidence_path: Mapped[str] = mapped_column(Text, default="")
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("execution_id","requirement_id",name="uq_pm_execution_requirement_ack"),)


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


class TicketOperationalControl(Base):
    __tablename__ = "ticket_operational_controls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    containment: Mapped[str] = mapped_column(Text, default="")
    production_impact: Mapped[str] = mapped_column(Text, default="")
    affected_lots: Mapped[str] = mapped_column(Text, default="")
    safety_quality_risk: Mapped[str] = mapped_column(Text, default="")
    response_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    containment_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0, index=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    escalation_reason: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class EntityLotLink(Base):
    __tablename__ = "entity_lot_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_key: Mapped[str] = mapped_column(String(140), index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    lot_number: Mapped[str] = mapped_column(String(120), index=True)
    product: Mapped[str] = mapped_column(String(160), default="")
    process_operation: Mapped[str] = mapped_column(String(160), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    __table_args__ = (
        UniqueConstraint("entity_type","entity_key","lot_number",name="uq_entity_lot_link"),
    )


class TicketEscalationEvent(Base):
    __tablename__ = "ticket_escalation_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(100), index=True)
    from_level: Mapped[int] = mapped_column(Integer, default=0)
    to_level: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    user: Mapped[str] = mapped_column(String(120), default="system")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class IncidentWhy(Base):
    __tablename__ = "incident_whys"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(100), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[str] = mapped_column(String(120), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("ticket_no","sequence",name="uq_incident_why_sequence"),)


class IncidentCausalFactor(Base):
    __tablename__ = "incident_causal_factors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(60), default="Other", index=True)
    factor_type: Mapped[str] = mapped_column(String(30), default="Suspected", index=True)
    description: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="Open", index=True)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class IncidentAction(Base):
    __tablename__ = "incident_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(100), index=True)
    action_type: Mapped[str] = mapped_column(String(30), default="Corrective", index=True)
    description: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(120), default="", index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="Open", index=True)
    effectiveness_criteria: Mapped[str] = mapped_column(Text, default="")
    completion_note: Mapped[str] = mapped_column(Text, default="")
    completed_by: Mapped[str] = mapped_column(String(120), default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verification_note: Mapped[str] = mapped_column(Text, default="")
    verified_by: Mapped[str] = mapped_column(String(120), default="")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class TicketStateEvent(Base):
    __tablename__ = "ticket_state_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(40), unique=True, index=True, default=lambda: secrets.token_hex(16))
    ticket_no: Mapped[str] = mapped_column(String(100), index=True)
    from_state: Mapped[str] = mapped_column(String(50), default="")
    to_state: Mapped[str] = mapped_column(String(50), index=True)
    reason_code: Mapped[str] = mapped_column(String(60), index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(120), default="")
    changed_by: Mapped[str] = mapped_column(String(120), default="", index=True)
    workstation: Mapped[str] = mapped_column(String(120), default="")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


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


class QualificationProtocol(Base):
    __tablename__ = "qualification_protocols"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    protocol_id: Mapped[str] = mapped_column(String(120), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(250))
    equipment_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    equipment_type: Mapped[str] = mapped_column(String(120), default="")
    checks_json: Mapped[str] = mapped_column(Text, default="[]")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("protocol_id","revision",name="uq_qualification_protocol_revision"),)


class QualificationRun(Base):
    __tablename__ = "qualification_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    protocol_id: Mapped[str] = mapped_column(String(120), index=True)
    protocol_revision: Mapped[int] = mapped_column(Integer)
    protocol_name: Mapped[str] = mapped_column(String(250), default="")
    frozen_checks_json: Mapped[str] = mapped_column(Text, default="[]")
    results_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="In Progress", index=True)
    started_by: Mapped[str] = mapped_column(String(120))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_by: Mapped[str] = mapped_column(String(120), default="")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_by: Mapped[str] = mapped_column(String(120), default="")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[str] = mapped_column(String(120), default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    conclusion: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class QualificationEvent(Base):
    __tablename__ = "qualification_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_no: Mapped[str] = mapped_column(String(120), index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    user: Mapped[str] = mapped_column(String(120), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    workstation: Mapped[str] = mapped_column(String(120), default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


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


class WorkOrder(Base):
    __tablename__ = "work_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    source_type: Mapped[str] = mapped_column(String(40), default="ENGINEERING", index=True)
    source_key: Mapped[str] = mapped_column(String(120), default="", index=True)
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(30), default="Normal", index=True)
    status: Mapped[str] = mapped_column(String(40), default="Open", index=True)
    owner: Mapped[str] = mapped_column(String(120), default="", index=True)
    team: Mapped[str] = mapped_column(String(160), default="")
    planned_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    planned_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    qualification_required: Mapped[bool] = mapped_column(Boolean, default=False)
    release_required: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class WorkOrderEvent(Base):
    __tablename__ = "work_order_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_no: Mapped[str] = mapped_column(String(120), index=True)
    from_state: Mapped[str] = mapped_column(String(40), default="")
    to_state: Mapped[str] = mapped_column(String(40), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(120), default="")
    changed_by: Mapped[str] = mapped_column(String(120), default="")
    workstation: Mapped[str] = mapped_column(String(120), default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class WorkOrderLink(Base):
    __tablename__ = "work_order_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_no: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_key: Mapped[str] = mapped_column(String(160), index=True)
    relation: Mapped[str] = mapped_column(String(60), default="RELATED")
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("work_order_no","entity_type","entity_key","relation",name="uq_work_order_link"),)


class WorkLog(Base):
    __tablename__ = "work_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_key: Mapped[str] = mapped_column(String(120), index=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    work_type: Mapped[str] = mapped_column(String(80), default="Engineering")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    duration_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="Active", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


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


class PartCatalog(Base):
    __tablename__ = "part_catalog"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_number: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(300), default="")
    category: Mapped[str] = mapped_column(String(120), default="")
    manufacturer: Mapped[str] = mapped_column(String(120), default="")
    supplier: Mapped[str] = mapped_column(String(180), default="")
    supplier_part_number: Mapped[str] = mapped_column(String(160), default="", index=True)
    barcode: Mapped[str] = mapped_column(String(180), default="", index=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0)
    reorder_qty: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class PartAlternate(Base):
    __tablename__ = "part_alternates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_number: Mapped[str] = mapped_column(String(120), index=True)
    alternate_part_number: Mapped[str] = mapped_column(String(120), index=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("part_number","alternate_part_number",name="uq_part_alternate"),)



class SupplierOrder(Base):
    __tablename__ = "supplier_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    supplier: Mapped[str] = mapped_column(String(180), index=True)
    status: Mapped[str] = mapped_column(String(40), default="Draft", index=True)
    order_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    expected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    external_reference: Mapped[str] = mapped_column(String(180), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(120), default="")
    submitted_by: Mapped[str] = mapped_column(String(120), default="")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class SupplierOrderLine(Base):
    __tablename__ = "supplier_order_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_no: Mapped[str] = mapped_column(String(120), index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    part_number: Mapped[str] = mapped_column(String(120), index=True)
    supplier_part_number: Mapped[str] = mapped_column(String(160), default="")
    ordered_qty: Mapped[float] = mapped_column(Float)
    received_qty: Mapped[float] = mapped_column(Float, default=0.0)
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(12), default="JPY")
    destination_location: Mapped[str] = mapped_column(String(100), default="", index=True)
    status: Mapped[str] = mapped_column(String(40), default="Open", index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("order_no","line_no",name="uq_supplier_order_line"),)


class RotableAsset(Base):
    __tablename__ = "rotable_assets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    part_number: Mapped[str] = mapped_column(String(120), index=True)
    serial_number: Mapped[str] = mapped_column(String(160), default="", index=True)
    description: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(40), default="Stock", index=True)
    condition: Mapped[str] = mapped_column(String(60), default="Serviceable", index=True)
    current_location: Mapped[str] = mapped_column(String(100), default="", index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    component_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    vendor: Mapped[str] = mapped_column(String(180), default="")
    repair_reference: Mapped[str] = mapped_column(String(180), default="")
    repair_count: Mapped[int] = mapped_column(Integer, default=0)
    installed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_for_repair_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class RotableEvent(Base):
    __tablename__ = "rotable_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(120), index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    from_status: Mapped[str] = mapped_column(String(40), default="")
    to_status: Mapped[str] = mapped_column(String(40), default="")
    location_code: Mapped[str] = mapped_column(String(100), default="")
    equipment_id: Mapped[str] = mapped_column(String(100), default="")
    reference: Mapped[str] = mapped_column(String(180), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    user: Mapped[str] = mapped_column(String(120), default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PMKitStage(Base):
    __tablename__ = "pm_kit_stages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    staging_location: Mapped[str] = mapped_column(String(100), default="", index=True)
    status: Mapped[str] = mapped_column(String(40), default="Reserved", index=True)
    staged_by: Mapped[str] = mapped_column(String(120), default="")
    staged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    issued_by: Mapped[str] = mapped_column(String(120), default="")
    issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
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


class ControlledDocument(Base):
    __tablename__ = "controlled_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_key: Mapped[str] = mapped_column(String(120), index=True)
    document_type: Mapped[str] = mapped_column(String(80), default="SOP")
    title: Mapped[str] = mapped_column(String(250))
    owner: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(40), default="Draft", index=True)
    current_revision: Mapped[str] = mapped_column(String(60), default="")
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ControlledDocumentRevision(Base):
    __tablename__ = "controlled_document_revisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[str] = mapped_column(String(120), index=True)
    revision: Mapped[str] = mapped_column(String(60))
    path: Mapped[str] = mapped_column(Text)
    file_sha256: Mapped[str] = mapped_column(String(64))
    change_summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="Draft", index=True)
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_by: Mapped[str] = mapped_column(String(120), default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("document_id","revision",name="uq_controlled_document_revision"),)


class ConfigOption(Base):
    __tablename__ = "config_options"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(100), index=True)
    code: Mapped[str] = mapped_column(String(120), index=True)
    label: Mapped[str] = mapped_column(String(180))
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    system_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("category","code",name="uq_config_option"),)


class NumberSequence(Base):
    __tablename__ = "number_sequences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scheme_code: Mapped[str] = mapped_column(String(120), index=True)
    period_key: Mapped[str] = mapped_column(String(40), index=True)
    next_value: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("scheme_code","period_key",name="uq_number_sequence"),)


class EntityTemplate(Base):
    __tablename__ = "entity_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(180))
    applies_to: Mapped[str] = mapped_column(String(180), default="", index=True)
    defaults_json: Mapped[str] = mapped_column(Text, default="{}")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class CustomFieldDefinition(Base):
    __tablename__ = "custom_field_definitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    field_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    applies_to: Mapped[str] = mapped_column(String(180), default="", index=True)
    label: Mapped[str] = mapped_column(String(180))
    field_type: Mapped[str] = mapped_column(String(40), default="TEXT")
    options_json: Mapped[str] = mapped_column(Text, default="[]")
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class CustomFieldValue(Base):
    __tablename__ = "custom_field_values"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_key: Mapped[str] = mapped_column(String(180), index=True)
    field_id: Mapped[str] = mapped_column(String(120), index=True)
    value_json: Mapped[str] = mapped_column(Text, default="null")
    updated_by: Mapped[str] = mapped_column(String(120), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("entity_type","entity_key","field_id",name="uq_custom_field_value"),)



class FormSectionDefinition(Base):
    __tablename__ = "form_section_definitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    applies_to: Mapped[str] = mapped_column(String(180), default="", index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    columns: Mapped[int] = mapped_column(Integer, default=1)
    collapsible: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class CustomFieldLayout(Base):
    __tablename__ = "custom_field_layouts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    field_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    section_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    column_index: Mapped[int] = mapped_column(Integer, default=0)
    width_span: Mapped[int] = mapped_column(Integer, default=1)
    placeholder: Mapped[str] = mapped_column(String(250), default="")
    help_text: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

class WorkflowAutomationRule(Base):
    __tablename__ = "workflow_automation_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    trigger: Mapped[str] = mapped_column(String(80), index=True)
    match_json: Mapped[str] = mapped_column(Text, default="{}")
    actions_json: Mapped[str] = mapped_column(Text, default="[]")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class WorkflowAutomationExecution(Base):
    __tablename__ = "workflow_automation_executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_key: Mapped[str] = mapped_column(String(48), unique=True, index=True, default=lambda: secrets.token_hex(20))
    rule_id: Mapped[str] = mapped_column(String(100), index=True)
    trigger: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), default="", index=True)
    entity_key: Mapped[str] = mapped_column(String(180), default="", index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    context_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(30), default="Completed", index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RecordComment(Base):
    __tablename__ = "record_comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_key: Mapped[str] = mapped_column(String(180), index=True)
    equipment_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    body: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class RecordWatcher(Base):
    __tablename__ = "record_watchers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_key: Mapped[str] = mapped_column(String(180), index=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("entity_type","entity_key","username",name="uq_record_watcher"),)


class RecordMention(Base):
    __tablename__ = "record_mentions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comment_id: Mapped[int] = mapped_column(Integer, index=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("comment_id","username",name="uq_comment_mention"),)


class IntegrationEndpoint(Base):
    __tablename__ = "integration_endpoints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endpoint_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), default="")
    adapter_type: Mapped[str] = mapped_column(String(30), index=True)
    target: Mapped[str] = mapped_column(Text)
    topics: Mapped[str] = mapped_column(Text, default="*")
    auth_env: Mapped[str] = mapped_column(String(120), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class IntegrationEvent(Base):
    __tablename__ = "integration_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(40), unique=True, index=True, default=lambda: secrets.token_hex(16))
    topic: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_key: Mapped[str] = mapped_column(String(160), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class IntegrationDelivery(Base):
    __tablename__ = "integration_deliveries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(40), index=True)
    endpoint_id: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(30), default="Pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("event_id","endpoint_id",name="uq_integration_delivery"),)


class IntegrationInboundEndpoint(Base):
    __tablename__ = "integration_inbound_endpoints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endpoint_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), default="")
    adapter_type: Mapped[str] = mapped_column(String(30), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    source_path: Mapped[str] = mapped_column(Text)
    file_pattern: Mapped[str] = mapped_column(String(180), default="*.json")
    mapping_json: Mapped[str] = mapped_column(Text, default="{}")
    defaults_json: Mapped[str] = mapped_column(Text, default="{}")
    archive_path: Mapped[str] = mapped_column(Text, default="")
    quarantine_path: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class IntegrationInboundReceipt(Base):
    __tablename__ = "integration_inbound_receipts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endpoint_id: Mapped[str] = mapped_column(String(100), index=True)
    source_name: Mapped[str] = mapped_column(String(300))
    source_sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    records_total: Mapped[int] = mapped_column(Integer, default=0)
    records_applied: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    __table_args__ = (UniqueConstraint("endpoint_id","source_sha256",name="uq_inbound_receipt_file"),)


class IntegrationInboundRecord(Base):
    __tablename__ = "integration_inbound_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endpoint_id: Mapped[str] = mapped_column(String(100), index=True)
    receipt_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    record_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    row_index: Mapped[int] = mapped_column(Integer)
    target_entity: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    entity_key: Mapped[str] = mapped_column(String(180), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RecoveryDrill(Base):
    __tablename__ = "recovery_drills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    backup_path: Mapped[str] = mapped_column(Text)
    database_type: Mapped[str] = mapped_column(String(30))
    success: Mapped[bool] = mapped_column(Boolean)
    detail: Mapped[str] = mapped_column(Text, default="")
    performed_by: Mapped[str] = mapped_column(String(120), default="")
    workstation: Mapped[str] = mapped_column(String(120), default="")
    performed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


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
AUTH_MAX_FAILURES = 5
AUTH_LOCKOUT_MINUTES = 15

ROLE_PERMISSIONS = {
    "Administrator": {"*"},
    "Manager": {"view", "workflow.override", "worklog.edit", "qualification.edit", "qualification.execute", "qualification.verify", "qualification.approve", "equipment.meter.record", "equipment.edit", "equipment.transition", "equipment.component.edit", "pm.edit", "pm.execute", "pm.approve", "pm.defer", "pm.defer.approve", "ticket.edit", "disposition.edit", "release.approve", "endorsement.edit", "inventory.edit", "inventory.consume", "inventory.reserve", "document.link", "report.view"},
    "Supervisor": {"view", "worklog.edit", "qualification.execute", "qualification.verify", "qualification.approve", "equipment.meter.record", "equipment.edit", "equipment.transition", "equipment.component.edit", "pm.edit", "pm.execute", "pm.defer", "pm.defer.approve", "ticket.edit", "disposition.edit", "release.verify", "endorsement.edit", "inventory.edit", "inventory.consume", "inventory.reserve", "document.link", "report.view"},
    "Equipment Engineer": {"view", "worklog.edit", "qualification.edit", "qualification.execute", "qualification.verify", "equipment.meter.record", "equipment.edit", "equipment.transition", "equipment.component.edit", "pm.edit", "pm.execute", "pm.defer", "ticket.edit", "disposition.edit", "release.verify", "endorsement.edit", "inventory.edit", "inventory.consume", "inventory.reserve", "document.link", "report.view"},
    "Maintenance": {"view", "worklog.edit", "qualification.execute", "equipment.meter.record", "equipment.component.edit", "pm.execute", "pm.defer", "ticket.edit", "endorsement.edit", "inventory.consume", "inventory.reserve", "document.link"},
    "Technician": {"view", "worklog.edit", "equipment.meter.record", "pm.execute", "ticket.edit", "inventory.consume", "document.link"},
    "Operator": {"view", "ticket.edit", "document.link", "report.view"},
    "Manufacturing Technician": {"view", "worklog.edit", "equipment.meter.record", "pm.execute", "ticket.edit", "endorsement.edit", "inventory.consume", "document.link", "report.view"},
    "Shift Leader": {"view", "worklog.edit", "qualification.execute", "qualification.verify", "equipment.meter.record", "equipment.transition", "pm.edit", "pm.execute", "pm.defer", "ticket.edit", "release.verify", "endorsement.edit", "inventory.consume", "inventory.reserve", "document.link", "report.view"},
    "Process Engineer": {"view", "worklog.edit", "qualification.verify", "qualification.approve", "ticket.edit", "release.verify", "document.link", "report.view"},
    "Inventory Controller": {"view", "inventory.edit", "inventory.consume", "inventory.reserve", "document.link"},
    "Document Controller": {"view", "document.link", "document.control"},
    "Read Only": {"view", "report.view"},
}

PERMISSIONS = [
    "view", "workflow.override", "worklog.edit", "qualification.edit", "qualification.execute", "qualification.verify", "qualification.approve", "equipment.edit", "equipment.transition", "equipment.component.edit", "equipment.meter.record", "layout.edit", "pm.edit", "pm.execute", "pm.approve", "pm.defer", "pm.defer.approve",
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
        inspector=inspect(self.engine)
        existing=set(inspector.get_table_names())
        if not existing:
            Base.metadata.create_all(self.engine)
            self._record_bootstrap_migrations()
        else:
            SchemaMigration.__table__.create(self.engine,checkfirst=True)
            self._apply_schema_migrations()
        self._assert_schema_compatible()
        self._bootstrap_legacy_event_history()
        self._bootstrap_factory_hierarchy()
        self._bootstrap_configuration_catalog()

    @staticmethod
    def _migration_checksum(revision: str, description: str) -> str:
        return hashlib.sha256(f"{revision}|{description}".encode("utf-8")).hexdigest()

    def _migration_plan(self):
        return [
            ("20260923_001","Create additive production-core tables",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260923_002","Create operational event and lookup indexes",self._migration_indexes),
            ("20260923_003","Create productivity workspace and universal evidence tables",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260923_004","Create account-level productivity preferences",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260923_005","Create structured incident RCA and CAPA tables",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260923_006","Create governed work-order and relationship tables",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260923_007","Create part catalog and approved-alternate logistics tables",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260924_008","Create configurable workflow orchestration tables",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260924_009","Create record comments watchers and mentions",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260924_010","Create configuration catalog templates and custom fields",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260924_011","Create inbound integration endpoint receipt and record tables",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260924_012","Create configurable numbering sequences",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260924_013","Create supplier-order rotable and PM-kit staging lifecycle tables",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260924_014","Create configurable form-section and custom-field layout tables",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260924_015","Create persistent per-user record drafts",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260924_016","Create persistent user notification center",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260925_017","Create first-class lot context links for manual operations",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260925_018","Create flexible PM calendar schedule and audit tables",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260925_019","Create PM pause and carry-over history",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260925_020","Add PM per-step completion evidence rules",self._migration_pm_step_completion_rules),
        ]

    def _migration_indexes(self):
        statements=[
            "CREATE INDEX IF NOT EXISTS ix_eq_state_equipment_time ON equipment_state_events (equipment_id, changed_at)",
            "CREATE INDEX IF NOT EXISTS ix_ticket_state_ticket_time ON ticket_state_events (ticket_no, changed_at)",
            "CREATE INDEX IF NOT EXISTS ix_ticket_escalation_ticket_time ON ticket_escalation_events (ticket_no, occurred_at)",
            "CREATE INDEX IF NOT EXISTS ix_meter_reading_equipment_meter_time ON meter_readings (equipment_id, meter_code, recorded_at)",
            "CREATE INDEX IF NOT EXISTS ix_qualification_equipment_status ON qualification_runs (equipment_id, status)",
            "CREATE INDEX IF NOT EXISTS ix_pm_task_equipment_status ON pm_tasks (equipment_id, status)",
        ]
        with self.engine.begin() as conn:
            for sql in statements:conn.exec_driver_sql(sql)

    def _migration_pm_step_completion_rules(self):
        inspector=inspect(self.engine)
        targets={
            "pm_specs":["screenshot_required","comment_required"],
            "pm_execution_step_snapshots":["screenshot_required","comment_required"],
        }
        with self.engine.begin() as conn:
            for table,columns in targets.items():
                existing={x["name"] for x in inspector.get_columns(table)} if table in inspector.get_table_names() else set()
                for column in columns:
                    if column not in existing:
                        conn.exec_driver_sql(
                            f"ALTER TABLE {table} ADD COLUMN {column} BOOLEAN NOT NULL DEFAULT FALSE"
                        )

    def _record_bootstrap_migrations(self):
        SchemaMigration.__table__.create(self.engine,checkfirst=True)
        with self.Session.begin() as s:
            for revision,description,_ in self._migration_plan():
                if not s.scalar(select(SchemaMigration).where(SchemaMigration.revision==revision)):
                    s.add(SchemaMigration(
                        revision=revision,
                        checksum=self._migration_checksum(revision,description),
                        description=description,
                    ))

    def _apply_schema_migrations(self):
        SchemaMigration.__table__.create(self.engine,checkfirst=True)
        with self.Session() as s:
            applied={row.revision:row for row in s.scalars(select(SchemaMigration))}
        for revision,description,apply_fn in self._migration_plan():
            expected=self._migration_checksum(revision,description)
            row=applied.get(revision)
            if row:
                if row.checksum!=expected:
                    raise RuntimeError(
                        f"DATABASE MIGRATION CHECKSUM MISMATCH for {revision}. "
                        "Migration history was modified after deployment."
                    )
                continue
            apply_fn()
            with self.Session.begin() as s:
                s.add(SchemaMigration(
                    revision=revision,checksum=expected,description=description,
                ))

    def list_schema_migrations(self):
        with self.session() as s:
            return list(s.scalars(select(SchemaMigration).order_by(SchemaMigration.applied_at,SchemaMigration.id)))

    def _assert_schema_compatible(self):
        """Fail fast if an existing database is missing model columns.

        SQLAlchemy create_all() can add new tables but intentionally does not alter
        existing tables. Without this guard, an old production database may appear
        to start successfully and then fail later during an operational workflow.
        """
        inspector=inspect(self.engine)
        actual_tables=set(inspector.get_table_names())
        errors=[]
        for table in Base.metadata.sorted_tables:
            if table.name not in actual_tables:
                errors.append(f"missing table {table.name}")
                continue
            actual_columns={col["name"] for col in inspector.get_columns(table.name)}
            expected_columns={col.name for col in table.columns}
            missing=sorted(expected_columns-actual_columns)
            if missing:
                errors.append(f"{table.name}: missing columns {', '.join(missing)}")
        if errors:
            raise RuntimeError(
                "DATABASE SCHEMA INCOMPATIBLE. Controlled migration required before use: "
                + "; ".join(errors)
            )

    def schema_health(self) -> tuple[bool,str]:
        try:
            self._assert_schema_compatible()
            return True,"Schema matches application model"
        except Exception as exc:
            return False,str(exc)

    def _bootstrap_legacy_event_history(self):
        """Backfill baseline event history for databases created before governed workflows.

        New installations already create events at record creation. This only acts
        on records that have no event history at all, so it is idempotent.
        """
        legacy_ticket_states={"In Progress":"Investigation","Completed":"Closed"}
        with self.session() as s:
            equipment=list(s.scalars(select(Equipment)))
            for eq in equipment:
                exists=s.scalar(select(func.count()).select_from(EquipmentStateEvent).where(
                    EquipmentStateEvent.equipment_id==eq.equipment_id
                ))
                if exists:
                    continue
                state=eq.status if eq.status in EQUIPMENT_STATES else "Available"
                if eq.status!=state:
                    eq.status=state
                    eq.version+=1
                occurred=eq.updated_at or datetime.utcnow()
                s.add(EquipmentStateEvent(
                    equipment_id=eq.equipment_id,
                    from_state="",
                    to_state=state,
                    state_class=STATE_CLASS.get(state,""),
                    downtime=state in DOWNTIME_STATES,
                    reason_code="INITIAL_STATE",
                    reason_text="Baseline state captured during governed-workflow upgrade",
                    owner=eq.owner or "",
                    changed_by="system-migration",
                    workstation="DATABASE-UPGRADE",
                    changed_at=occurred,
                ))

            tickets=list(s.scalars(select(Ticket)))
            for ticket in tickets:
                exists=s.scalar(select(func.count()).select_from(TicketStateEvent).where(
                    TicketStateEvent.ticket_no==ticket.ticket_no
                ))
                if exists:
                    continue
                state=legacy_ticket_states.get(ticket.status,ticket.status)
                if state not in TICKET_STATES:
                    state="Open"
                if ticket.status!=state:
                    ticket.status=state
                    ticket.version+=1
                occurred=ticket.updated_at or ticket.created_at or datetime.utcnow()
                s.add(TicketStateEvent(
                    ticket_no=ticket.ticket_no,
                    from_state="",
                    to_state=state,
                    reason_code="INITIAL_STATE",
                    note="Baseline lifecycle state captured during governed-workflow upgrade",
                    owner=ticket.owner or "",
                    changed_by="system-migration",
                    workstation="DATABASE-UPGRADE",
                    changed_at=occurred,
                ))

    @staticmethod
    def _factory_code(parent: str, node_type: str, name: str) -> str:
        clean="".join(ch if ch.isalnum() else "-" for ch in (name or "").strip().upper()).strip("-") or "UNSPECIFIED"
        base=f"{node_type.upper()}:{clean}"
        return f"{parent}/{base}" if parent else base

    def _bootstrap_factory_hierarchy(self):
        with self.session() as s:
            for eq in s.scalars(select(Equipment)):
                parent=""
                levels=[
                    ("Site",eq.site),
                    ("Building",eq.building),
                    ("Floor",eq.floor),
                    ("Area",eq.area),
                    ("Line",eq.line_cell),
                ]
                deepest=""
                for node_type,name in levels:
                    if not (name or "").strip():
                        continue
                    code=self._factory_code(parent,node_type,name)
                    if not s.scalar(select(FactoryNode).where(FactoryNode.node_code==code)):
                        s.add(FactoryNode(node_code=code,parent_code=parent,node_type=node_type,name=name.strip()))
                        s.flush()
                    parent=code
                    deepest=code
                if deepest:
                    active=s.scalar(select(EquipmentLocationAssignment).where(
                        EquipmentLocationAssignment.equipment_id==eq.equipment_id,
                        EquipmentLocationAssignment.active.is_(True),
                    ))
                    if not active:
                        s.add(EquipmentLocationAssignment(
                            equipment_id=eq.equipment_id,node_code=deepest,active=True,
                            assigned_by="system-migration",
                        ))

    def list_factory_nodes(self, active_only: bool = True):
        with self.session() as s:
            stmt=select(FactoryNode).order_by(FactoryNode.node_code)
            if active_only:stmt=stmt.where(FactoryNode.active.is_(True))
            return list(s.scalars(stmt))

    def equipment_location(self, equipment_id: str):
        with self.session() as s:
            return s.scalar(select(EquipmentLocationAssignment).where(
                EquipmentLocationAssignment.equipment_id==equipment_id,
                EquipmentLocationAssignment.active.is_(True),
            ))

    def set_equipment_location(self, equipment_id: str, node_code: str, user: str, workstation: str = ""):
        with self.session() as s:
            eq=s.scalar(select(Equipment).where(Equipment.equipment_id==equipment_id))
            if not eq:raise ValueError("Equipment not found")
            node=s.scalar(select(FactoryNode).where(FactoryNode.node_code==node_code,FactoryNode.active.is_(True)))
            if not node:raise ValueError("Factory location node not found")
            now=datetime.utcnow()
            for old in s.scalars(select(EquipmentLocationAssignment).where(
                EquipmentLocationAssignment.equipment_id==equipment_id,
                EquipmentLocationAssignment.active.is_(True),
            )):
                old.active=False;old.ended_at=now
            row=EquipmentLocationAssignment(
                equipment_id=equipment_id,node_code=node_code,active=True,
                assigned_by=user,assigned_at=now,
            )
            s.add(row)
            s.add(AuditLog(
                user=user,action="EQUIPMENT_LOCATION_ASSIGN",entity_type="EQUIPMENT",
                entity_key=equipment_id,detail=node_code,workstation=workstation,
            ))
            s.flush();return row

    def _node_ancestors(self, s, node_code: str) -> set[str]:
        result=set()
        current=node_code
        guard=0
        while current and guard<32:
            if current in result:break
            result.add(current)
            node=s.scalar(select(FactoryNode).where(FactoryNode.node_code==current))
            current=node.parent_code if node else ""
            guard+=1
        return result

    def list_approval_delegations(self, active_only: bool = False):
        now=datetime.utcnow()
        with self.session() as s:
            stmt=select(ApprovalDelegation).order_by(ApprovalDelegation.created_at.desc())
            if active_only:
                stmt=stmt.where(
                    ApprovalDelegation.active.is_(True),
                    ApprovalDelegation.starts_at<=now,
                    ApprovalDelegation.ends_at>now,
                )
            return list(s.scalars(stmt))

    def _delegation_scope_allows(self, s, row: ApprovalDelegation, equipment_id: str) -> bool:
        scope=(row.scope_type or "GLOBAL").upper()
        if scope=="GLOBAL":return True
        if not equipment_id:return False
        if scope=="EQUIPMENT":return row.scope_key==equipment_id
        if scope=="NODE":
            assignment=s.scalar(select(EquipmentLocationAssignment).where(
                EquipmentLocationAssignment.equipment_id==equipment_id,
                EquipmentLocationAssignment.active.is_(True),
            ))
            return bool(assignment and row.scope_key in self._node_ancestors(s,assignment.node_code))
        return False

    def delegated_permission(self, username: str, permission: str, equipment_id: str = "") -> bool:
        now=datetime.utcnow()
        with self.session() as s:
            rows=list(s.scalars(select(ApprovalDelegation).where(
                ApprovalDelegation.delegate==username,
                ApprovalDelegation.permission==permission,
                ApprovalDelegation.active.is_(True),
                ApprovalDelegation.starts_at<=now,
                ApprovalDelegation.ends_at>now,
            )))
            return any(self._delegation_scope_allows(s,row,equipment_id) for row in rows)

    def create_approval_delegation(
        self,
        delegator: str,
        delegate: str,
        permission: str,
        ends_at: datetime,
        reason: str,
        actor: str,
        scope_type: str = "GLOBAL",
        scope_key: str = "",
        starts_at: datetime | None = None,
        workstation: str = "",
    ):
        if permission in {"user.admin","workflow.override"}:
            raise ValueError(f"Permission '{permission}' cannot be delegated.")
        if permission not in PERMISSIONS:
            raise ValueError("Unknown permission.")
        if delegator==delegate:raise ValueError("Delegator and delegate must be different users.")
        if not reason.strip():raise ValueError("Delegation reason is required.")
        starts_at=starts_at or datetime.utcnow()
        if ends_at<=starts_at:raise ValueError("Delegation end must be after its start.")
        scope_type=scope_type.upper()
        if scope_type not in {"GLOBAL","EQUIPMENT","NODE"}:raise ValueError("Delegation scope must be GLOBAL, EQUIPMENT, or NODE.")
        with self.session() as s:
            delegator_user=s.scalar(select(User).where(User.username==delegator,User.active.is_(True)))
            delegate_user=s.scalar(select(User).where(User.username==delegate,User.active.is_(True)))
            actor_user=s.scalar(select(User).where(User.username==actor,User.active.is_(True)))
            if not delegator_user or not delegate_user or not actor_user:raise ValueError("Delegator, delegate, and actor must be active EMS users.")
            delegator_ctx={"username":delegator_user.username,"role":delegator_user.role}
            if not self._direct_permission(delegator_ctx,permission):
                raise PermissionError("Delegator does not directly own the permission being delegated.")
            if actor!=delegator and actor_user.role!="Administrator":
                raise PermissionError("Only the delegator or an Administrator may create this delegation.")
            if scope_type=="EQUIPMENT" and not s.scalar(select(Equipment).where(Equipment.equipment_id==scope_key)):
                raise ValueError("Delegation equipment scope not found.")
            if scope_type=="NODE" and not s.scalar(select(FactoryNode).where(FactoryNode.node_code==scope_key)):
                raise ValueError("Delegation factory-node scope not found.")
            row=ApprovalDelegation(
                delegator=delegator,delegate=delegate,permission=permission,
                scope_type=scope_type,scope_key=scope_key,starts_at=starts_at,ends_at=ends_at,
                reason=reason.strip(),created_by=actor,
            )
            s.add(row);s.flush()
            s.add(AuditLog(
                user=actor,action="APPROVAL_DELEGATION_CREATE",entity_type="DELEGATION",entity_key=str(row.id),
                detail=json.dumps({"delegator":delegator,"delegate":delegate,"permission":permission,
                    "scope_type":scope_type,"scope_key":scope_key,"starts_at":starts_at.isoformat(),
                    "ends_at":ends_at.isoformat(),"reason":reason.strip()},sort_keys=True),
                workstation=workstation,
            ))
            return row

    def revoke_approval_delegation(self, delegation_id: int, actor: str, reason: str, workstation: str = ""):
        if not reason.strip():raise ValueError("Revocation reason is required.")
        with self.session() as s:
            row=s.get(ApprovalDelegation,delegation_id)
            if not row:raise ValueError("Delegation not found.")
            actor_user=s.scalar(select(User).where(User.username==actor,User.active.is_(True)))
            if not actor_user:raise PermissionError("Active actor required.")
            if actor!=row.delegator and actor_user.role!="Administrator":
                raise PermissionError("Only the delegator or an Administrator may revoke this delegation.")
            if not row.active:return row
            row.active=False;row.revoked_by=actor;row.revoked_at=datetime.utcnow();row.revoke_reason=reason.strip();row.version+=1
            s.add(AuditLog(
                user=actor,action="APPROVAL_DELEGATION_REVOKE",entity_type="DELEGATION",entity_key=str(row.id),
                detail=reason.strip(),workstation=workstation,
            ))
            s.flush();return row

    def user_access_policy(self, username: str):
        with self.session() as s:
            return s.scalar(select(UserAccessPolicy).where(UserAccessPolicy.username==username))

    def set_user_access_policy(self, username: str, scope_mode: str):
        mode=scope_mode.strip().upper()
        if mode not in {"UNRESTRICTED","RESTRICTED"}:
            raise ValueError("Scope mode must be UNRESTRICTED or RESTRICTED.")
        with self.session() as s:
            if not s.scalar(select(User).where(User.username==username)):
                raise ValueError("User not found")
            row=s.scalar(select(UserAccessPolicy).where(UserAccessPolicy.username==username))
            if row:
                row.scope_mode=mode;row.version+=1
            else:
                row=UserAccessPolicy(username=username,scope_mode=mode);s.add(row)
            s.flush();return row

    def list_user_scopes(self, username: str):
        with self.session() as s:
            return list(s.scalars(select(UserEquipmentScope).where(
                UserEquipmentScope.username==username,
                UserEquipmentScope.active.is_(True),
            ).order_by(UserEquipmentScope.scope_type,UserEquipmentScope.scope_key)))

    def add_user_scope(self, username: str, scope_type: str, scope_key: str, permission: str = "*"):
        scope_type=scope_type.strip().upper()
        if scope_type not in {"EQUIPMENT","NODE"}:raise ValueError("Scope type must be EQUIPMENT or NODE.")
        with self.session() as s:
            if not s.scalar(select(User).where(User.username==username)):raise ValueError("User not found")
            if scope_type=="EQUIPMENT" and not s.scalar(select(Equipment).where(Equipment.equipment_id==scope_key)):
                raise ValueError("Scoped equipment not found")
            if scope_type=="NODE" and not s.scalar(select(FactoryNode).where(FactoryNode.node_code==scope_key)):
                raise ValueError("Scoped factory node not found")
            row=s.scalar(select(UserEquipmentScope).where(
                UserEquipmentScope.username==username,UserEquipmentScope.scope_type==scope_type,
                UserEquipmentScope.scope_key==scope_key,UserEquipmentScope.permission==permission,
            ))
            if row:
                row.active=True
            else:
                row=UserEquipmentScope(username=username,scope_type=scope_type,scope_key=scope_key,permission=permission,active=True);s.add(row)
            s.flush();return row

    def clear_user_scopes(self, username: str):
        with self.session() as s:
            for row in s.scalars(select(UserEquipmentScope).where(UserEquipmentScope.username==username,UserEquipmentScope.active.is_(True))):
                row.active=False

    def equipment_in_scope(self, username: str, equipment_id: str, permission: str = "*") -> bool:
        with self.session() as s:
            user=s.scalar(select(User).where(User.username==username))
            if user and user.role=="Administrator":return True
            policy=s.scalar(select(UserAccessPolicy).where(UserAccessPolicy.username==username))
            if not policy or policy.scope_mode!="RESTRICTED":return True
            scopes=list(s.scalars(select(UserEquipmentScope).where(
                UserEquipmentScope.username==username,UserEquipmentScope.active.is_(True),
            )))
            if any(x.scope_type=="EQUIPMENT" and x.scope_key==equipment_id and x.permission in {"*",permission} for x in scopes):
                return True
            assignment=s.scalar(select(EquipmentLocationAssignment).where(
                EquipmentLocationAssignment.equipment_id==equipment_id,
                EquipmentLocationAssignment.active.is_(True),
            ))
            if not assignment:return False
            ancestors=self._node_ancestors(s,assignment.node_code)
            return any(x.scope_type=="NODE" and x.scope_key in ancestors and x.permission in {"*",permission} for x in scopes)

    def assert_equipment_scope(self, username: str, equipment_id: str, permission: str = "*"):
        if username and not self.equipment_in_scope(username,equipment_id,permission):
            raise PermissionError(f"User '{username}' is not authorized for equipment {equipment_id}.")

    def assert_authorized(self, username: str, permission: str, equipment_id: str = ""):
        strict=os.getenv("EMS_STRICT_AUTHZ","0").strip().lower() in {"1","true","yes","on"}
        delegated=False
        with self.session() as s:
            user=s.scalar(select(User).where(User.username==username)) if username else None
            if strict and (not user or not user.active):
                raise PermissionError("Authenticated active EMS user is required for this operation.")
            if user:
                user_ctx={"username":user.username,"role":user.role}
                if not self._direct_permission(user_ctx,permission):
                    delegated=self.delegated_permission(username,permission,equipment_id)
                    if not delegated:
                        raise PermissionError(f"User '{username}' lacks permission '{permission}'.")
        if equipment_id and not delegated:
            self.assert_equipment_scope(username,equipment_id,permission)

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

    def authenticate(self, username: str, password: str, workstation: str = "") -> dict[str, Any] | None:
        username=username.strip()
        now=datetime.utcnow()
        with self.session() as s:
            u=s.scalar(select(User).where(User.username==username))
            if not u:
                if username:
                    s.add(LoginAttempt(username=username[:80],success=False,reason="Unknown user",workstation=workstation,attempted_at=now))
                return None
            state=s.scalar(select(AuthSecurityState).where(AuthSecurityState.username==username))
            if not state:
                state=AuthSecurityState(username=username)
                s.add(state)
                s.flush()
            if state.locked_until and state.locked_until>now:
                s.add(LoginAttempt(username=username,success=False,reason="Locked",workstation=workstation,attempted_at=now))
                return None
            if state.locked_until and state.locked_until<=now:
                state.locked_until=None
                state.failed_attempts=0
                state.version+=1
            if not u.active:
                s.add(LoginAttempt(username=username,success=False,reason="Inactive",workstation=workstation,attempted_at=now))
                return None
            if not verify_password(password,u.password_hash):
                state.failed_attempts+=1
                state.last_failed_at=now
                state.version+=1
                reason="Invalid password"
                if state.failed_attempts>=AUTH_MAX_FAILURES:
                    state.locked_until=now+timedelta(minutes=AUTH_LOCKOUT_MINUTES)
                    reason="Locked after repeated failures"
                s.add(LoginAttempt(username=username,success=False,reason=reason,workstation=workstation,attempted_at=now))
                return None
            state.failed_attempts=0
            state.locked_until=None
            state.last_failed_at=None
            state.version+=1
            u.last_login=now
            s.add(LoginAttempt(username=username,success=True,reason="Authenticated",workstation=workstation,attempted_at=now))
            s.flush()
            return {"id":u.id,"username":u.username,"display_name":u.display_name,"role":u.role}

    def auth_security_status(self, username: str):
        with self.session() as s:
            return s.scalar(select(AuthSecurityState).where(AuthSecurityState.username==username))

    def unlock_user(self, username: str, actor: str = "", workstation: str = ""):
        with self.session() as s:
            if not s.scalar(select(User).where(User.username==username)):
                raise ValueError("User not found")
            state=s.scalar(select(AuthSecurityState).where(AuthSecurityState.username==username))
            if not state:
                state=AuthSecurityState(username=username)
                s.add(state)
            state.failed_attempts=0
            state.locked_until=None
            state.last_failed_at=None
            state.version+=1
            s.add(AuditLog(user=actor,action="AUTH_UNLOCK",entity_type="USER",entity_key=username,workstation=workstation))
            s.flush()
            return state

    def list_login_attempts(self, username: str = "", limit: int = 500):
        with self.session() as s:
            stmt=select(LoginAttempt).order_by(LoginAttempt.attempted_at.desc()).limit(max(1,min(int(limit),5000)))
            if username:
                stmt=stmt.where(LoginAttempt.username==username)
            return list(s.scalars(stmt))

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
                state=s.scalar(select(AuthSecurityState).where(AuthSecurityState.username==username))
                if state:
                    state.failed_attempts=0
                    state.locked_until=None
                    state.last_failed_at=None
                    state.version+=1
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

    def _direct_permission(self, user: dict[str, Any], permission: str) -> bool:
        overrides=self.permission_overrides(user["username"])
        if permission in overrides:return overrides[permission]
        base=ROLE_PERMISSIONS.get(user.get("role","Read Only"),{"view"})
        return "*" in base or permission in base

    def has_permission(self, user: dict[str, Any], permission: str) -> bool:
        if self._direct_permission(user,permission):return True
        now=datetime.utcnow()
        with self.session() as s:
            return bool(s.scalar(select(func.count()).select_from(ApprovalDelegation).where(
                ApprovalDelegation.delegate==user["username"],
                ApprovalDelegation.permission==permission,
                ApprovalDelegation.active.is_(True),
                ApprovalDelegation.starts_at<=now,
                ApprovalDelegation.ends_at>now,
            )) or 0)

    def _bootstrap_configuration_catalog(self):
        defaults={
            "EQUIPMENT_CRITICALITY":[("Low","Low"),("Normal","Normal"),("High","High"),("Critical","Critical")],
            "TICKET_SEVERITY":[("S1","S1"),("S2","S2"),("S3","S3"),("S4","S4")],
            "TICKET_PRIORITY":[("P1","P1"),("P2","P2"),("P3","P3"),("P4","P4")],
            "DISPOSITION_STATE":[
                ("Released With Conditions","Released With Conditions"),("Restricted Use","Restricted Use"),
                ("Engineering Use","Engineering Use"),("Monitoring","Monitoring"),("Hold","Hold"),
                ("PM Hold","PM Hold"),("Quality Hold","Quality Hold"),("Safety Hold","Safety Hold"),
                ("Waiting Parts","Waiting Parts"),("Waiting Vendor","Waiting Vendor"),
                ("Qualification","Qualification"),("Decommission","Decommission"),("Scrap","Scrap"),
            ],
            "INVENTORY_CONDITION":[
                ("Available","Available"),("Reserved","Reserved"),("Installed","Installed"),("In Use","In Use"),
                ("Repair","Repair"),("Quarantine","Quarantine"),("Inspection Required","Inspection Required"),
                ("Expired","Expired"),("Obsolete","Obsolete"),("Scrap","Scrap"),("Vendor","Vendor"),
            ],
            "WORK_TYPE":[("Engineering","Engineering"),("Maintenance","Maintenance"),("Troubleshooting","Troubleshooting"),("Qualification","Qualification")],
            "EQUIPMENT_REASON_LABEL":list(REASON_CODES.items()),
            "TICKET_REASON_LABEL":list(TICKET_REASON_CODES.items()),
        }
        with self.session() as s:
            for category,items in defaults.items():
                for order,(code,label) in enumerate(items,10):
                    row=s.scalar(select(ConfigOption).where(ConfigOption.category==category,ConfigOption.code==code))
                    if not row:s.add(ConfigOption(category=category,code=code,label=label,sort_order=order,active=True,system_locked=True))

    def list_config_options(self, category: str, active_only: bool = True):
        with self.session() as s:
            stmt=select(ConfigOption).where(ConfigOption.category==category.strip().upper()).order_by(ConfigOption.sort_order,ConfigOption.label)
            if active_only:stmt=stmt.where(ConfigOption.active.is_(True))
            return list(s.scalars(stmt))

    def _matching_config_options(self, s, category: str, equipment_id: str = "", context: dict[str,Any] | None = None):
        context=dict(context or {})
        eq=s.scalar(select(Equipment).where(Equipment.equipment_id==equipment_id)) if equipment_id else None
        actual={
            "equipment_id":equipment_id or "",
            "equipment_type":eq.equipment_type if eq else "",
            "area":eq.area if eq else "",
            "site":eq.site if eq else "",
            **{str(k):v for k,v in context.items()},
        }
        rows=list(s.scalars(select(ConfigOption).where(
            ConfigOption.category==category.strip().upper(),
            ConfigOption.active.is_(True),
        ).order_by(ConfigOption.sort_order,ConfigOption.code)))
        matches=[]
        for row in rows:
            try:meta=json.loads(row.metadata_json or "{}")
            except Exception:continue
            if not isinstance(meta,dict):continue
            constraints=meta.get("match",{})
            if constraints and not isinstance(constraints,dict):continue
            ok=True;score=0
            for key,expected in (constraints or {}).items():
                value=actual.get(key,"")
                if isinstance(expected,list):
                    if value not in expected:ok=False;break
                elif str(expected)!=str(value):
                    ok=False;break
                score+=1
            if ok:matches.append((score,row,meta))
        matches.sort(key=lambda x:(-x[0],x[1].sort_order,x[1].code))
        return matches

    @staticmethod
    def _sequence_period(reset: str, now: datetime) -> str:
        reset=(reset or "DAILY").upper()
        if reset=="NEVER":return "ALL"
        if reset=="YEARLY":return now.strftime("%Y")
        if reset=="MONTHLY":return now.strftime("%Y%m")
        return now.strftime("%Y%m%d")

    def _next_configured_number_in_session(
        self,
        s,
        entity_type: str,
        equipment_id: str = "",
        context: dict[str,Any] | None = None,
        now: datetime | None = None,
    ) -> str:
        now=now or datetime.utcnow()
        matches=self._matching_config_options(s,"NUMBERING_SCHEME",equipment_id,{"entity_type":entity_type.upper(),**(context or {})})
        if matches:
            _,option,meta=matches[0]
            prefix=str(meta.get("prefix") or option.code or entity_type[:4]).strip()
            separator=str(meta.get("separator","-"))
            date_format=str(meta.get("date_format","%Y%m%d"))
            width=max(1,min(int(meta.get("width",5)),12))
            period=self._sequence_period(str(meta.get("reset","DAILY")),now)
            stmt=select(NumberSequence).where(NumberSequence.scheme_code==option.code,NumberSequence.period_key==period)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            seq=s.scalar(stmt)
            if not seq:
                seq=NumberSequence(scheme_code=option.code,period_key=period,next_value=1);s.add(seq);s.flush()
            value=seq.next_value;seq.next_value+=1;seq.version+=1
            date_part=now.strftime(date_format) if date_format else ""
            parts=[x for x in [prefix,date_part,f"{value:0{width}d}"] if x]
            return separator.join(parts)
        fallback={"TICKET":"INC","WORK_ORDER":"WO","QUALIFICATION":"QUAL"}.get(entity_type.upper(),entity_type.upper()[:6] or "REC")
        return f"{fallback}-{now:%Y%m%d%H%M%S%f}"

    def preview_configured_number(self, entity_type: str, equipment_id: str = "", context: dict[str,Any] | None = None) -> str:
        now=datetime.utcnow()
        with self.session() as s:
            matches=self._matching_config_options(s,"NUMBERING_SCHEME",equipment_id,{"entity_type":entity_type.upper(),**(context or {})})
            if not matches:
                fallback={"TICKET":"INC","WORK_ORDER":"WO","QUALIFICATION":"QUAL"}.get(entity_type.upper(),entity_type.upper()[:6] or "REC")
                return f"{fallback}-{now:%Y%m%d…}"
            _,option,meta=matches[0]
            prefix=str(meta.get("prefix") or option.code or entity_type[:4]).strip()
            separator=str(meta.get("separator","-"));date_format=str(meta.get("date_format","%Y%m%d"));width=max(1,min(int(meta.get("width",5)),12))
            date_part=now.strftime(date_format) if date_format else ""
            return separator.join([x for x in [prefix,date_part,"0"*width] if x])

    def resolve_default_owner(self, entity_type: str, equipment_id: str = "", context: dict[str,Any] | None = None) -> str:
        with self.session() as s:
            matches=self._matching_config_options(s,"DEFAULT_OWNER_RULE",equipment_id,{"entity_type":entity_type.upper(),**(context or {})})
            if not matches:return ""
            return str(matches[0][2].get("owner","")).strip()

    def resolve_sla_policy(self, equipment_id: str = "", context: dict[str,Any] | None = None) -> dict[str,int]:
        with self.session() as s:
            matches=self._matching_config_options(s,"SLA_POLICY",equipment_id,context or {})
            if not matches:return {}
            meta=matches[0][2]
            out={}
            for key in ["response_minutes","containment_minutes","resolution_minutes"]:
                if meta.get(key) is not None:
                    try:out[key]=max(0,int(meta[key]))
                    except Exception:pass
            return out

    def resolve_report_template(self, report_type: str, equipment_id: str = "", context: dict[str,Any] | None = None) -> str:
        with self.session() as s:
            matches=self._matching_config_options(
                s,"REPORT_TEMPLATE",equipment_id,
                {"report_type":report_type.strip().upper(),**(context or {})},
            )
            if not matches:return ""
            path=str(matches[0][2].get("path","")).strip()
            return path if path and os.path.isfile(path) else ""

    def save_config_option(self, data: dict[str,Any], expected_version: int | None = None):
        payload=dict(data);payload["category"]=str(payload.get("category","")).strip().upper();payload["code"]=str(payload.get("code","")).strip()
        if not payload["category"] or not payload["code"] or not str(payload.get("label","")).strip():raise ValueError("Category, code and label are required.")
        metadata=payload.get("metadata_json","{}")
        if isinstance(metadata,dict):metadata=json.dumps(metadata,sort_keys=True)
        try:json.loads(metadata or "{}")
        except Exception as exc:raise ValueError(f"Option metadata JSON is invalid: {exc}")
        payload["metadata_json"]=metadata or "{}"
        with self.session() as s:
            row=s.scalar(select(ConfigOption).where(ConfigOption.category==payload["category"],ConfigOption.code==payload["code"]))
            if row:
                if row.system_locked:
                    allowed={"label","sort_order","active","metadata_json"}
                    payload={k:v for k,v in payload.items() if k in allowed}
                    if row.category in {"EQUIPMENT_REASON_LABEL","TICKET_REASON_LABEL"}:
                        payload["active"]=True
                self._update_versioned(row,payload,expected_version,"Configuration option")
            else:
                row=ConfigOption(**payload);s.add(row)
            s.flush();return row

    def list_entity_templates(self, entity_type: str = "", active_only: bool = True):
        with self.session() as s:
            stmt=select(EntityTemplate).order_by(EntityTemplate.entity_type,EntityTemplate.name)
            if entity_type:stmt=stmt.where(EntityTemplate.entity_type==entity_type.strip().upper())
            if active_only:stmt=stmt.where(EntityTemplate.active.is_(True))
            return list(s.scalars(stmt))

    def save_entity_template(self, data: dict[str,Any], user: str = "", expected_version: int | None = None):
        payload=dict(data);payload["template_id"]=str(payload.get("template_id","")).strip();payload["entity_type"]=str(payload.get("entity_type","")).strip().upper()
        if not payload["template_id"] or not payload["entity_type"] or not str(payload.get("name","")).strip():raise ValueError("Template ID, entity type and name are required.")
        defaults=payload.get("defaults_json","{}")
        if isinstance(defaults,dict):defaults=json.dumps(defaults,sort_keys=True)
        try:
            decoded=json.loads(defaults or "{}")
            if not isinstance(decoded,dict):raise ValueError("Defaults must be a JSON object.")
        except Exception as exc:raise ValueError(f"Template defaults JSON is invalid: {exc}")
        payload["defaults_json"]=defaults or "{}";payload["created_by"]=payload.get("created_by") or user
        with self.session() as s:
            row=s.scalar(select(EntityTemplate).where(EntityTemplate.template_id==payload["template_id"]))
            if row:self._update_versioned(row,payload,expected_version,"Entity template")
            else:row=EntityTemplate(**payload);s.add(row)
            s.flush();return row

    def apply_entity_template(self, template_id: str, base: dict[str,Any] | None = None) -> dict[str,Any]:
        with self.session() as s:
            row=s.scalar(select(EntityTemplate).where(EntityTemplate.template_id==template_id,EntityTemplate.active.is_(True)))
            if not row:raise ValueError("Template not found or inactive.")
            defaults=json.loads(row.defaults_json or "{}")
        result=dict(defaults);result.update(base or {});return result

    def list_custom_field_definitions(self, entity_type: str, applies_to: str = "", active_only: bool = True):
        with self.session() as s:
            stmt=select(CustomFieldDefinition).where(CustomFieldDefinition.entity_type==entity_type.strip().upper()).order_by(CustomFieldDefinition.sort_order,CustomFieldDefinition.label)
            if active_only:stmt=stmt.where(CustomFieldDefinition.active.is_(True))
            rows=list(s.scalars(stmt))
            if applies_to:rows=[x for x in rows if not x.applies_to or x.applies_to==applies_to]
            return rows

    def save_form_section(self, data: dict[str,Any], expected_version: int | None = None):
        payload=dict(data)
        payload["section_id"]=str(payload.get("section_id","")).strip()
        payload["entity_type"]=str(payload.get("entity_type","")).strip().upper()
        payload["applies_to"]=str(payload.get("applies_to","")).strip()
        payload["title"]=str(payload.get("title","")).strip()
        payload["columns"]=max(1,min(3,int(payload.get("columns",1) or 1)))
        if not payload["section_id"] or not payload["entity_type"] or not payload["title"]:
            raise ValueError("Section ID, entity type and title are required.")
        with self.session() as s:
            row=s.scalar(select(FormSectionDefinition).where(FormSectionDefinition.section_id==payload["section_id"]))
            if row:self._update_versioned(row,payload,expected_version,"Form section")
            else:row=FormSectionDefinition(**payload);s.add(row)
            s.flush();return row

    def list_form_sections(self, entity_type: str = "", applies_to: str = "", active_only: bool = True):
        with self.session() as s:
            stmt=select(FormSectionDefinition).order_by(FormSectionDefinition.entity_type,FormSectionDefinition.sort_order,FormSectionDefinition.title)
            if entity_type:stmt=stmt.where(FormSectionDefinition.entity_type==entity_type.strip().upper())
            if active_only:stmt=stmt.where(FormSectionDefinition.active.is_(True))
            rows=list(s.scalars(stmt))
            if applies_to:rows=[x for x in rows if not x.applies_to or x.applies_to==applies_to]
            return rows

    def save_custom_field_layout(self, field_id: str, data: dict[str,Any], expected_version: int | None = None):
        field_id=field_id.strip()
        if not field_id:raise ValueError("Field ID is required.")
        payload=dict(data);payload["field_id"]=field_id
        payload["section_id"]=str(payload.get("section_id","")).strip()
        payload["column_index"]=max(0,min(2,int(payload.get("column_index",0) or 0)))
        payload["width_span"]=max(1,min(3,int(payload.get("width_span",1) or 1)))
        with self.session() as s:
            if not s.scalar(select(CustomFieldDefinition).where(CustomFieldDefinition.field_id==field_id)):
                raise ValueError("Custom field definition not found.")
            if payload["section_id"] and not s.scalar(select(FormSectionDefinition).where(FormSectionDefinition.section_id==payload["section_id"])):
                raise ValueError("Form section not found.")
            row=s.scalar(select(CustomFieldLayout).where(CustomFieldLayout.field_id==field_id))
            if row:self._update_versioned(row,payload,expected_version,"Custom field layout")
            else:row=CustomFieldLayout(**payload);s.add(row)
            s.flush();return row

    def custom_field_layouts(self, field_ids: list[str] | None = None) -> dict[str,CustomFieldLayout]:
        with self.session() as s:
            stmt=select(CustomFieldLayout)
            if field_ids:stmt=stmt.where(CustomFieldLayout.field_id.in_(field_ids))
            return {x.field_id:x for x in s.scalars(stmt)}

    def save_custom_field_definition(self, data: dict[str,Any], expected_version: int | None = None):
        payload=dict(data);payload["field_id"]=str(payload.get("field_id","")).strip();payload["entity_type"]=str(payload.get("entity_type","")).strip().upper();payload["field_type"]=str(payload.get("field_type","TEXT")).strip().upper()
        if payload["field_type"] not in {"TEXT","MULTILINE","NUMBER","BOOLEAN","DATE","CHOICE"}:raise ValueError("Unsupported custom field type.")
        if not payload["field_id"] or not payload["entity_type"] or not str(payload.get("label","")).strip():raise ValueError("Field ID, entity type and label are required.")
        options=payload.get("options_json","[]")
        if isinstance(options,list):options=json.dumps(options)
        try:
            decoded=json.loads(options or "[]")
            if not isinstance(decoded,list):raise ValueError("Options must be a JSON array.")
        except Exception as exc:raise ValueError(f"Custom field options JSON is invalid: {exc}")
        payload["options_json"]=options or "[]"
        with self.session() as s:
            row=s.scalar(select(CustomFieldDefinition).where(CustomFieldDefinition.field_id==payload["field_id"]))
            if row:self._update_versioned(row,payload,expected_version,"Custom field definition")
            else:row=CustomFieldDefinition(**payload);s.add(row)
            s.flush();return row

    @staticmethod
    def _validate_custom_field_value(definition: CustomFieldDefinition, value: Any):
        if value is None or value=="":
            if definition.required:raise ValueError(f"{definition.label} is required.")
            return None
        if definition.field_type=="NUMBER":
            try:return float(value)
            except Exception:raise ValueError(f"{definition.label} must be numeric.")
        if definition.field_type=="BOOLEAN":
            if isinstance(value,bool):return value
            return str(value).strip().lower() in {"1","true","yes","on"}
        if definition.field_type=="CHOICE":
            options=json.loads(definition.options_json or "[]")
            if value not in options:raise ValueError(f"{definition.label} must be one of: {', '.join(map(str,options))}")
        return value

    def save_custom_field_values(self, entity_type: str, entity_key: str, values: dict[str,Any], user: str = "", applies_to: str = ""):
        entity_type=entity_type.strip().upper();entity_key=str(entity_key);applies_to=(applies_to or "").strip()
        with self.session() as s:
            definitions=list(s.scalars(select(CustomFieldDefinition).where(CustomFieldDefinition.entity_type==entity_type,CustomFieldDefinition.active.is_(True))))
            if applies_to:definitions=[x for x in definitions if not x.applies_to or x.applies_to==applies_to]
            defs={x.field_id:x for x in definitions}
            unknown=set(values)-set(defs)
            if unknown:raise ValueError("Unknown custom field(s): "+", ".join(sorted(unknown)))
            for field_id,definition in defs.items():
                incoming=values.get(field_id)
                if field_id not in values and definition.required:
                    existing=s.scalar(select(CustomFieldValue).where(CustomFieldValue.entity_type==entity_type,CustomFieldValue.entity_key==entity_key,CustomFieldValue.field_id==field_id))
                    if not existing:raise ValueError(f"{definition.label} is required.")
                    continue
                if field_id not in values:continue
                normalized=self._validate_custom_field_value(definition,incoming)
                row=s.scalar(select(CustomFieldValue).where(CustomFieldValue.entity_type==entity_type,CustomFieldValue.entity_key==entity_key,CustomFieldValue.field_id==field_id))
                encoded=json.dumps(normalized,default=str)
                if row:row.value_json=encoded;row.updated_by=user;row.updated_at=datetime.utcnow();row.version+=1
                else:s.add(CustomFieldValue(entity_type=entity_type,entity_key=entity_key,field_id=field_id,value_json=encoded,updated_by=user))
            s.flush()

    def custom_field_values(self, entity_type: str, entity_key: str) -> dict[str,Any]:
        with self.session() as s:
            rows=list(s.scalars(select(CustomFieldValue).where(CustomFieldValue.entity_type==entity_type.strip().upper(),CustomFieldValue.entity_key==str(entity_key))))
            out={}
            for row in rows:
                try:out[row.field_id]=json.loads(row.value_json)
                except Exception:out[row.field_id]=row.value_json
            return out

    def export_configuration_bundle(self) -> dict[str,Any]:
        with self.session() as s:
            options=list(s.scalars(select(ConfigOption).order_by(ConfigOption.category,ConfigOption.sort_order,ConfigOption.code)))
            templates=list(s.scalars(select(EntityTemplate).order_by(EntityTemplate.entity_type,EntityTemplate.template_id)))
            fields=list(s.scalars(select(CustomFieldDefinition).order_by(CustomFieldDefinition.entity_type,CustomFieldDefinition.sort_order,CustomFieldDefinition.field_id)))
            form_sections=list(s.scalars(select(FormSectionDefinition).order_by(FormSectionDefinition.entity_type,FormSectionDefinition.sort_order,FormSectionDefinition.section_id)))
            layouts=list(s.scalars(select(CustomFieldLayout).order_by(CustomFieldLayout.field_id)))
            rules=list(s.scalars(select(WorkflowAutomationRule).order_by(WorkflowAutomationRule.priority,WorkflowAutomationRule.rule_id)))
        return {
            "schema":"EMS_CONFIGURATION_V2",
            "exported_at":datetime.utcnow().isoformat(),
            "config_options":[{
                "category":x.category,"code":x.code,"label":x.label,"sort_order":x.sort_order,
                "active":x.active,"system_locked":x.system_locked,"metadata_json":x.metadata_json,
            } for x in options],
            "entity_templates":[{
                "template_id":x.template_id,"entity_type":x.entity_type,"name":x.name,"applies_to":x.applies_to,
                "defaults_json":x.defaults_json,"active":x.active,
            } for x in templates],
            "custom_fields":[{
                "field_id":x.field_id,"entity_type":x.entity_type,"applies_to":x.applies_to,"label":x.label,
                "field_type":x.field_type,"options_json":x.options_json,"required":x.required,
                "sort_order":x.sort_order,"active":x.active,
            } for x in fields],
            "form_sections":[{
                "section_id":x.section_id,"entity_type":x.entity_type,"applies_to":x.applies_to,"title":x.title,
                "description":x.description,"sort_order":x.sort_order,"columns":x.columns,"collapsible":x.collapsible,"active":x.active,
            } for x in form_sections],
            "custom_field_layouts":[{
                "field_id":x.field_id,"section_id":x.section_id,"column_index":x.column_index,"width_span":x.width_span,
                "placeholder":x.placeholder,"help_text":x.help_text,
            } for x in layouts],
            "workflow_rules":[{
                "rule_id":x.rule_id,"name":x.name,"trigger":x.trigger,"match_json":x.match_json,
                "actions_json":x.actions_json,"enabled":x.enabled,"priority":x.priority,
            } for x in rules],
        }

    def _validate_configuration_bundle(self,bundle: dict[str,Any]) -> dict[str,int]:
        if not isinstance(bundle,dict) or bundle.get("schema") not in {"EMS_CONFIGURATION_V1","EMS_CONFIGURATION_V2"}:
            raise ValueError("Unsupported configuration package schema.")
        sections={
            "config_options":bundle.get("config_options",[]),
            "entity_templates":bundle.get("entity_templates",[]),
            "custom_fields":bundle.get("custom_fields",[]),
            "form_sections":bundle.get("form_sections",[]),
            "custom_field_layouts":bundle.get("custom_field_layouts",[]),
            "workflow_rules":bundle.get("workflow_rules",[]),
        }
        for name,rows in sections.items():
            if not isinstance(rows,list):raise ValueError(f"{name} must be an array.")
            if not all(isinstance(row,dict) for row in rows):raise ValueError(f"{name} contains an invalid record.")
        seen=set()
        for row in sections["config_options"]:
            key=(str(row.get("category","")).strip().upper(),str(row.get("code","")).strip())
            if not all(key):raise ValueError("Configuration option category/code is required.")
            if key in seen:raise ValueError(f"Duplicate configuration option: {key[0]} / {key[1]}")
            seen.add(key)
            json.loads(row.get("metadata_json","{}") or "{}")
        seen=set()
        for row in sections["entity_templates"]:
            key=str(row.get("template_id","")).strip()
            if not key or key in seen:raise ValueError(f"Invalid or duplicate template ID: {key or '<blank>'}")
            seen.add(key);defaults=json.loads(row.get("defaults_json","{}") or "{}")
            if not isinstance(defaults,dict):raise ValueError(f"Template {key} defaults must be a JSON object.")
        seen=set()
        for row in sections["custom_fields"]:
            key=str(row.get("field_id","")).strip()
            if not key or key in seen:raise ValueError(f"Invalid or duplicate custom field ID: {key or '<blank>'}")
            seen.add(key);field_type=str(row.get("field_type","TEXT")).upper()
            if field_type not in {"TEXT","MULTILINE","NUMBER","BOOLEAN","DATE","CHOICE"}:raise ValueError(f"Unsupported field type for {key}: {field_type}")
            options=json.loads(row.get("options_json","[]") or "[]")
            if not isinstance(options,list):raise ValueError(f"Custom field {key} options must be an array.")
        seen=set()
        for row in sections["form_sections"]:
            key=str(row.get("section_id","")).strip()
            if not key or key in seen:raise ValueError(f"Invalid or duplicate form section ID: {key or '<blank>'}")
            seen.add(key)
            if not str(row.get("entity_type","")).strip() or not str(row.get("title","")).strip():raise ValueError(f"Form section {key} requires entity type and title.")
        seen=set()
        for row in sections["custom_field_layouts"]:
            key=str(row.get("field_id","")).strip()
            if not key or key in seen:raise ValueError(f"Invalid or duplicate custom-field layout: {key or '<blank>'}")
            seen.add(key)
        seen=set();allowed_triggers={"ALARM_ACTIVE","ALARM_BURST","PM_ABNORMAL_RESULT","QUALIFICATION_APPROVED","RELEASE_APPROVED"};allowed_actions={"CREATE_INCIDENT","CREATE_WORK_ORDER","CREATE_HANDOVER","SET_DISPOSITION"}
        for row in sections["workflow_rules"]:
            key=str(row.get("rule_id","")).strip();trigger=str(row.get("trigger","")).strip().upper()
            if not key or key in seen:raise ValueError(f"Invalid or duplicate workflow rule ID: {key or '<blank>'}")
            seen.add(key)
            if trigger not in allowed_triggers:raise ValueError(f"Unsupported trigger for {key}: {trigger}")
            match=json.loads(row.get("match_json","{}") or "{}");actions=json.loads(row.get("actions_json","[]") or "[]")
            if not isinstance(match,dict) or not isinstance(actions,list) or not actions:raise ValueError(f"Invalid workflow rule JSON for {key}.")
            for action in actions:
                if not isinstance(action,dict) or str(action.get("type","")).upper() not in allowed_actions:raise ValueError(f"Unsupported action in workflow rule {key}.")
        return {name:len(rows) for name,rows in sections.items()}

    def import_configuration_bundle(self,bundle: dict[str,Any],user: str,dry_run: bool = True) -> dict[str,Any]:
        counts=self._validate_configuration_bundle(bundle)
        with self.session() as s:
            existing={
                "config_options":{(x.category,x.code) for x in s.scalars(select(ConfigOption))},
                "entity_templates":{x.template_id for x in s.scalars(select(EntityTemplate))},
                "custom_fields":{x.field_id for x in s.scalars(select(CustomFieldDefinition))},
                "form_sections":{x.section_id for x in s.scalars(select(FormSectionDefinition))},
                "custom_field_layouts":{x.field_id for x in s.scalars(select(CustomFieldLayout))},
                "workflow_rules":{x.rule_id for x in s.scalars(select(WorkflowAutomationRule))},
            }
        creates={
            "config_options":sum(1 for x in bundle.get("config_options",[]) if (str(x.get("category","")).strip().upper(),str(x.get("code","")).strip()) not in existing["config_options"]),
            "entity_templates":sum(1 for x in bundle.get("entity_templates",[]) if str(x.get("template_id","")).strip() not in existing["entity_templates"]),
            "custom_fields":sum(1 for x in bundle.get("custom_fields",[]) if str(x.get("field_id","")).strip() not in existing["custom_fields"]),
            "form_sections":sum(1 for x in bundle.get("form_sections",[]) if str(x.get("section_id","")).strip() not in existing["form_sections"]),
            "custom_field_layouts":sum(1 for x in bundle.get("custom_field_layouts",[]) if str(x.get("field_id","")).strip() not in existing["custom_field_layouts"]),
            "workflow_rules":sum(1 for x in bundle.get("workflow_rules",[]) if str(x.get("rule_id","")).strip() not in existing["workflow_rules"]),
        }
        preview={"counts":counts,"creates":creates,"updates":{k:counts[k]-creates[k] for k in counts},"dry_run":dry_run}
        if dry_run:return preview
        with self.session() as s:
            for data in bundle.get("config_options",[]):
                category=str(data["category"]).strip().upper();code=str(data["code"]).strip()
                row=s.scalar(select(ConfigOption).where(ConfigOption.category==category,ConfigOption.code==code))
                payload={
                    "label":str(data.get("label") or code),"sort_order":int(data.get("sort_order",100)),
                    "active":bool(data.get("active",True)),"metadata_json":data.get("metadata_json","{}") or "{}",
                }
                if row:
                    if row.category in {"EQUIPMENT_REASON_LABEL","TICKET_REASON_LABEL"}:payload["active"]=True
                    for k,v in payload.items():setattr(row,k,v)
                    row.version+=1
                else:s.add(ConfigOption(category=category,code=code,system_locked=bool(data.get("system_locked",False)),**payload))
            for data in bundle.get("entity_templates",[]):
                key=str(data["template_id"]).strip();row=s.scalar(select(EntityTemplate).where(EntityTemplate.template_id==key))
                payload={"entity_type":str(data["entity_type"]).strip().upper(),"name":str(data["name"]).strip(),"applies_to":str(data.get("applies_to","")).strip(),"defaults_json":data.get("defaults_json","{}") or "{}","active":bool(data.get("active",True)),"created_by":user}
                if row:
                    for k,v in payload.items():setattr(row,k,v)
                    row.version+=1
                else:s.add(EntityTemplate(template_id=key,**payload))
            for data in bundle.get("custom_fields",[]):
                key=str(data["field_id"]).strip();row=s.scalar(select(CustomFieldDefinition).where(CustomFieldDefinition.field_id==key))
                payload={"entity_type":str(data["entity_type"]).strip().upper(),"applies_to":str(data.get("applies_to","")).strip(),"label":str(data["label"]).strip(),"field_type":str(data.get("field_type","TEXT")).upper(),"options_json":data.get("options_json","[]") or "[]","required":bool(data.get("required",False)),"sort_order":int(data.get("sort_order",100)),"active":bool(data.get("active",True))}
                if row:
                    for k,v in payload.items():setattr(row,k,v)
                    row.version+=1
                else:s.add(CustomFieldDefinition(field_id=key,**payload))
            for data in bundle.get("form_sections",[]):
                key=str(data["section_id"]).strip();row=s.scalar(select(FormSectionDefinition).where(FormSectionDefinition.section_id==key))
                payload={"entity_type":str(data["entity_type"]).strip().upper(),"applies_to":str(data.get("applies_to","")).strip(),"title":str(data["title"]).strip(),"description":str(data.get("description","")).strip(),"sort_order":int(data.get("sort_order",100)),"columns":max(1,min(3,int(data.get("columns",1) or 1))),"collapsible":bool(data.get("collapsible",False)),"active":bool(data.get("active",True))}
                if row:
                    for k,v in payload.items():setattr(row,k,v)
                    row.version+=1
                else:s.add(FormSectionDefinition(section_id=key,**payload))
            for data in bundle.get("custom_field_layouts",[]):
                key=str(data["field_id"]).strip();row=s.scalar(select(CustomFieldLayout).where(CustomFieldLayout.field_id==key))
                payload={"section_id":str(data.get("section_id","")).strip(),"column_index":max(0,min(2,int(data.get("column_index",0) or 0))),"width_span":max(1,min(3,int(data.get("width_span",1) or 1))),"placeholder":str(data.get("placeholder","")),"help_text":str(data.get("help_text",""))}
                if row:
                    for k,v in payload.items():setattr(row,k,v)
                    row.version+=1
                else:s.add(CustomFieldLayout(field_id=key,**payload))
            for data in bundle.get("workflow_rules",[]):
                key=str(data["rule_id"]).strip();row=s.scalar(select(WorkflowAutomationRule).where(WorkflowAutomationRule.rule_id==key))
                payload={"name":str(data["name"]).strip(),"trigger":str(data["trigger"]).strip().upper(),"match_json":data.get("match_json","{}") or "{}","actions_json":data.get("actions_json","[]") or "[]","enabled":bool(data.get("enabled",True)),"priority":int(data.get("priority",100)),"created_by":user}
                if row:
                    for k,v in payload.items():setattr(row,k,v)
                    row.version+=1
                else:s.add(WorkflowAutomationRule(rule_id=key,**payload))
            s.add(AuditLog(user=user,action="CONFIGURATION_IMPORT",entity_type="SYSTEM_CONFIGURATION",entity_key=str(bundle.get("schema","EMS_CONFIGURATION_V1")),detail=json.dumps(preview,sort_keys=True)))
            s.flush()
        preview["dry_run"]=False
        return preview

    def save_workflow_rule(self, data: dict[str, Any], user: str = "", expected_version: int | None = None):
        payload=dict(data);trigger=str(payload.get("trigger","")).strip().upper()
        allowed={"ALARM_ACTIVE","ALARM_BURST","PM_ABNORMAL_RESULT","QUALIFICATION_APPROVED","RELEASE_APPROVED"}
        if trigger not in allowed:raise ValueError(f"Unsupported workflow trigger: {trigger}")
        payload["trigger"]=trigger;rule_id=str(payload.get("rule_id","")).strip()
        if not rule_id:raise ValueError("Rule ID is required.")
        try:
            match=json.loads(payload.get("match_json","{}") or "{}");actions=json.loads(payload.get("actions_json","[]") or "[]")
        except Exception as exc:raise ValueError(f"Rule JSON is invalid: {exc}")
        if not isinstance(match,dict):raise ValueError("match_json must be an object.")
        if not isinstance(actions,list) or not actions:raise ValueError("actions_json must be a non-empty list.")
        supported={"CREATE_INCIDENT","CREATE_WORK_ORDER","CREATE_HANDOVER","SET_DISPOSITION"}
        for action in actions:
            if not isinstance(action,dict) or str(action.get("type","")).upper() not in supported:raise ValueError("Unsupported or invalid workflow action.")
        payload["match_json"]=json.dumps(match,sort_keys=True);payload["actions_json"]=json.dumps(actions,sort_keys=True);payload["created_by"]=payload.get("created_by") or user
        with self.session() as s:
            row=s.scalar(select(WorkflowAutomationRule).where(WorkflowAutomationRule.rule_id==rule_id))
            if row:self._update_versioned(row,payload,expected_version,"Workflow automation rule")
            else:row=WorkflowAutomationRule(**payload);s.add(row)
            s.flush();return row

    def list_workflow_rules(self, enabled_only: bool = False):
        with self.session() as s:
            stmt=select(WorkflowAutomationRule).order_by(WorkflowAutomationRule.priority,WorkflowAutomationRule.rule_id)
            if enabled_only:stmt=stmt.where(WorkflowAutomationRule.enabled.is_(True))
            return list(s.scalars(stmt))

    def list_workflow_automation_executions(self, limit: int = 500):
        with self.session() as s:return list(s.scalars(select(WorkflowAutomationExecution).order_by(WorkflowAutomationExecution.executed_at.desc(),WorkflowAutomationExecution.id.desc()).limit(max(1,min(int(limit),5000)))))

    @staticmethod
    def _automation_matches(match: dict[str, Any], context: dict[str, Any]) -> bool:
        for key,expected in match.items():
            actual=context.get(key)
            if isinstance(expected,list):
                if actual not in expected:return False
            elif isinstance(expected,str) and expected.startswith("contains:"):
                if expected.split(":",1)[1].lower() not in str(actual or "").lower():return False
            elif str(actual or "").lower()!=str(expected or "").lower():return False
        return True

    def _execute_workflow_action(self,s,action: dict[str,Any],context: dict[str,Any],rule: WorkflowAutomationRule):
        kind=str(action.get("type","")).upper();equipment_id=str(context.get("equipment_id","") or "");actor=f"automation:{rule.rule_id}"
        if kind=="CREATE_INCIDENT":
            ticket_no=f"{str(action.get('ticket_prefix') or 'AUTO')}-{datetime.utcnow():%Y%m%d%H%M%S%f}"
            ticket=Ticket(ticket_no=ticket_no,equipment_id=equipment_id,title=str(action.get("title") or context.get("summary") or context.get("message") or "Automated incident"),description=str(action.get("description") or context.get("detail") or context.get("message") or ""),severity=str(action.get("severity") or "S2"),priority=str(action.get("priority") or "P2"),status="Open",owner=str(action.get("owner") or ""),root_cause="",corrective_action="",verification="",created_by=actor)
            s.add(ticket);s.flush()
            s.add(TicketStateEvent(ticket_no=ticket_no,from_state="",to_state="Open",reason_code="INITIAL_STATE",note=f"Created by workflow rule {rule.rule_id}",owner=ticket.owner,changed_by=actor,workstation="AUTOMATION"))
            alarm_keys=context.get("alarm_ids") or ([context.get("entity_key")] if context.get("entity_type")=="ALARM" else [])
            for alarm_key in alarm_keys:
                if not alarm_key:continue
                alarm=s.scalar(select(EquipmentAlarmEvent).where(EquipmentAlarmEvent.event_key==str(alarm_key)))
                if alarm and (not alarm.related_ticket or alarm.related_ticket==ticket_no):alarm.related_ticket=ticket_no
            context["ticket_no"]=ticket_no
            return {"type":kind,"ticket_no":ticket_no}
        if kind=="CREATE_WORK_ORDER":
            work_order_no=f"AUTO-WO-{datetime.utcnow():%Y%m%d%H%M%S%f}"
            source_type="TICKET" if context.get("ticket_no") else str(context.get("entity_type") or "AUTOMATION")
            source_key=str(context.get("ticket_no") or context.get("entity_key") or "")
            row=WorkOrder(work_order_no=work_order_no,equipment_id=equipment_id,source_type=source_type,source_key=source_key,title=str(action.get("title") or context.get("summary") or "Automated follow-up"),description=str(action.get("description") or context.get("detail") or ""),priority=str(action.get("priority") or "Normal"),status="Open",owner=str(action.get("owner") or ""),team=str(action.get("team") or ""),qualification_required=bool(action.get("qualification_required",False)),release_required=bool(action.get("release_required",False)),created_by=actor)
            s.add(row);s.flush()
            if context.get("ticket_no"):
                s.add(WorkOrderLink(work_order_no=work_order_no,entity_type="TICKET",entity_key=str(context["ticket_no"]),relation="SOURCE",created_by=actor))
            return {"type":kind,"work_order_no":work_order_no,"source_type":source_type,"source_key":source_key}
        if kind=="CREATE_HANDOVER":
            number=f"AUTO-HO-{datetime.utcnow():%Y%m%d%H%M%S%f}"
            row=Endorsement(endorsement_no=number,equipment_id=equipment_id,current_condition=str(action.get("condition") or context.get("summary") or context.get("message") or ""),pending_work=str(action.get("pending_work") or context.get("detail") or ""),restrictions=str(action.get("restrictions") or ""),next_action=str(action.get("next_action") or ""),next_owner=str(action.get("next_owner") or ""),status="Open",created_by=actor)
            s.add(row);s.flush();return {"type":kind,"endorsement_no":number}
        if kind=="SET_DISPOSITION":
            state=str(action.get("state") or "Hold");eq=s.scalar(select(Equipment).where(Equipment.equipment_id==equipment_id))
            if not eq:raise ValueError("Automation disposition requires valid equipment.")
            for current in s.scalars(select(Disposition).where(Disposition.equipment_id==equipment_id,Disposition.active.is_(True))):current.active=False
            row=Disposition(equipment_id=equipment_id,state=state,reason=str(action.get("reason") or context.get("summary") or context.get("message") or f"Workflow rule {rule.rule_id}"),restrictions=str(action.get("restrictions") or ""),release_criteria=str(action.get("release_criteria") or ""),related_ticket=str(context.get("ticket_no") or ""),created_by=actor,active=True)
            s.add(row);eq.disposition=state;eq.version+=1;s.flush();return {"type":kind,"disposition":state}
        raise ValueError(f"Unsupported workflow action {kind}")

    def _apply_workflow_automation_in_session(self,s,trigger: str,context: dict[str,Any]):
        trigger=trigger.upper();context=dict(context);context["trigger"]=trigger
        rules=list(s.scalars(select(WorkflowAutomationRule).where(WorkflowAutomationRule.enabled.is_(True),WorkflowAutomationRule.trigger==trigger).order_by(WorkflowAutomationRule.priority,WorkflowAutomationRule.rule_id)));results=[]
        for rule in rules:
            if not self._automation_matches(json.loads(rule.match_json or "{}"),context):continue
            entity_type=str(context.get("entity_type",""));entity_key=str(context.get("entity_key",""))
            prior=s.scalar(select(WorkflowAutomationExecution).where(WorkflowAutomationExecution.rule_id==rule.rule_id,WorkflowAutomationExecution.trigger==trigger,WorkflowAutomationExecution.entity_type==entity_type,WorkflowAutomationExecution.entity_key==entity_key,WorkflowAutomationExecution.status=="Completed").order_by(WorkflowAutomationExecution.id.desc()))
            if prior:continue
            execution=WorkflowAutomationExecution(rule_id=rule.rule_id,trigger=trigger,entity_type=entity_type,entity_key=entity_key,equipment_id=str(context.get("equipment_id","")),context_json=json.dumps(context,default=str,sort_keys=True),status="Completed");s.add(execution);s.flush();action_results=[]
            try:
                for action in json.loads(rule.actions_json or "[]"):action_results.append(self._execute_workflow_action(s,action,context,rule))
                execution.result_json=json.dumps(action_results,default=str,sort_keys=True)
            except Exception as exc:execution.status="Failed";execution.error=str(exc);raise
            results.append({"rule_id":rule.rule_id,"actions":action_results})
        return results

    @staticmethod
    def _mention_tokens(body: str) -> list[str]:
        tokens=[]
        for raw in (body or "").replace("\n"," ").split():
            if raw.startswith("@") and len(raw)>1:
                token=raw[1:].strip(".,:;!?()[]{}<>").lower()
                if token and token not in tokens:tokens.append(token)
        return tokens

    def add_record_comment(self, entity_type: str, entity_key: str, body: str, user: str, equipment_id: str = ""):
        text=(body or "").strip()
        if not text:raise ValueError("Comment cannot be empty.")
        entity_type=entity_type.strip().upper();entity_key=str(entity_key)
        with self.session() as s:
            row=RecordComment(entity_type=entity_type,entity_key=entity_key,equipment_id=equipment_id.strip(),body=text,created_by=user)
            s.add(row);s.flush()
            valid_users={u.username.lower():u.username for u in s.scalars(select(User).where(User.active.is_(True)))}
            for token in self._mention_tokens(text):
                username=valid_users.get(token)
                if username and username.lower()!=user.lower():
                    s.add(RecordMention(comment_id=row.id,username=username))
            watcher=s.scalar(select(RecordWatcher).where(RecordWatcher.entity_type==entity_type,RecordWatcher.entity_key==entity_key,RecordWatcher.username==user))
            if not watcher:s.add(RecordWatcher(entity_type=entity_type,entity_key=entity_key,username=user))
            s.add(AuditLog(user=user,action="COMMENT_ADD",entity_type=entity_type,entity_key=entity_key,detail=str(row.id)))
            s.flush();return row

    def edit_record_comment(self, comment_id: int, body: str, user: str, expected_version: int | None = None):
        text=(body or "").strip()
        if not text:raise ValueError("Comment cannot be empty.")
        with self.session() as s:
            row=s.get(RecordComment,comment_id)
            if not row or not row.active:raise ValueError("Comment not found")
            if row.created_by!=user:raise PermissionError("Only the comment author can edit it.")
            if expected_version is not None and row.version!=expected_version:raise RuntimeError("CONFLICT: Comment changed by another user.")
            row.body=text;row.edited_at=datetime.utcnow();row.version+=1
            for mention in s.scalars(select(RecordMention).where(RecordMention.comment_id==row.id)):s.delete(mention)
            valid_users={u.username.lower():u.username for u in s.scalars(select(User).where(User.active.is_(True)))}
            for token in self._mention_tokens(text):
                username=valid_users.get(token)
                if username and username.lower()!=user.lower():s.add(RecordMention(comment_id=row.id,username=username))
            s.flush();return row

    def remove_record_comment(self, comment_id: int, user: str):
        with self.session() as s:
            row=s.get(RecordComment,comment_id)
            if not row or not row.active:raise ValueError("Comment not found")
            if row.created_by!=user:raise PermissionError("Only the comment author can remove it.")
            row.active=False;row.version+=1;s.flush();return row

    def list_record_comments(self, entity_type: str, entity_key: str, limit: int = 500):
        with self.session() as s:
            return list(s.scalars(select(RecordComment).where(
                RecordComment.entity_type==entity_type.strip().upper(),
                RecordComment.entity_key==str(entity_key),
                RecordComment.active.is_(True),
            ).order_by(RecordComment.created_at.desc(),RecordComment.id.desc()).limit(max(1,min(int(limit),5000)))))

    def set_record_watch(self, entity_type: str, entity_key: str, username: str, watching: bool):
        entity_type=entity_type.strip().upper();entity_key=str(entity_key)
        with self.session() as s:
            row=s.scalar(select(RecordWatcher).where(RecordWatcher.entity_type==entity_type,RecordWatcher.entity_key==entity_key,RecordWatcher.username==username))
            if watching and not row:
                row=RecordWatcher(entity_type=entity_type,entity_key=entity_key,username=username);s.add(row)
            elif not watching and row:
                s.delete(row);row=None
            s.flush();return row

    def is_record_watching(self, entity_type: str, entity_key: str, username: str) -> bool:
        with self.session() as s:return bool(s.scalar(select(func.count()).select_from(RecordWatcher).where(RecordWatcher.entity_type==entity_type.strip().upper(),RecordWatcher.entity_key==str(entity_key),RecordWatcher.username==username)))

    def list_watched_records(self, username: str, limit: int = 200) -> list[dict[str,Any]]:
        with self.session() as s:
            watches=list(s.scalars(select(RecordWatcher).where(
                RecordWatcher.username==username
            ).order_by(RecordWatcher.created_at.desc()).limit(max(1,min(int(limit),1000)))))
            out=[]
            for watch in watches:
                last=s.scalar(select(RecordComment).where(
                    RecordComment.entity_type==watch.entity_type,
                    RecordComment.entity_key==watch.entity_key,
                    RecordComment.active.is_(True),
                ).order_by(RecordComment.created_at.desc(),RecordComment.id.desc()))
                equipment_id=last.equipment_id if last else ""
                if not equipment_id and watch.entity_type=="EQUIPMENT":equipment_id=watch.entity_key
                out.append({
                    "entity_type":watch.entity_type,"entity_key":watch.entity_key,
                    "equipment_id":equipment_id,"watched_at":watch.created_at,
                    "last_activity":last.created_at if last else watch.created_at,
                    "last_by":last.created_by if last else "",
                    "last_comment":last.body if last else "",
                })
            out.sort(key=lambda x:x["last_activity"],reverse=True)
            return out

    def list_record_watchers(self, entity_type: str, entity_key: str):
        with self.session() as s:return list(s.scalars(select(RecordWatcher).where(RecordWatcher.entity_type==entity_type.strip().upper(),RecordWatcher.entity_key==str(entity_key)).order_by(RecordWatcher.username)))

    def list_unacknowledged_mentions(self, username: str, limit: int = 200):
        with self.session() as s:
            rows=[]
            mentions=list(s.scalars(select(RecordMention).where(RecordMention.username==username,RecordMention.acknowledged.is_(False)).order_by(RecordMention.created_at.desc()).limit(limit)))
            for mention in mentions:
                comment=s.get(RecordComment,mention.comment_id)
                if comment and comment.active:rows.append((mention,comment))
            return rows

    def acknowledge_mention(self, mention_id: int, username: str):
        with self.session() as s:
            row=s.get(RecordMention,mention_id)
            if not row or row.username!=username:raise ValueError("Mention not found")
            row.acknowledged=True;row.acknowledged_at=datetime.utcnow();s.flush();return row

    def save_inbound_endpoint(self, data: dict[str, Any], expected_version: int | None = None):
        payload=dict(data)
        payload["endpoint_id"]=str(payload.get("endpoint_id","")).strip()
        payload["adapter_type"]=str(payload.get("adapter_type","")).strip().upper()
        payload["entity_type"]=str(payload.get("entity_type","")).strip().upper()
        if payload["adapter_type"] not in {"FILE_JSON","FILE_CSV"}:
            raise ValueError("Inbound adapter must be FILE_JSON or FILE_CSV.")
        if payload["entity_type"] not in {"ALARM","METER"}:
            raise ValueError("Inbound entity type must be ALARM or METER.")
        if not payload["endpoint_id"] or not str(payload.get("source_path","")).strip():
            raise ValueError("Inbound endpoint ID and source path are required.")
        for key in ["mapping_json","defaults_json"]:
            value=payload.get(key,"{}")
            if isinstance(value,dict):value=json.dumps(value,sort_keys=True)
            try:
                parsed=json.loads(value or "{}")
                if not isinstance(parsed,dict):raise ValueError(f"{key} must be a JSON object.")
            except Exception as exc:raise ValueError(f"{key} is invalid: {exc}")
            payload[key]=value or "{}"
        payload["file_pattern"]=str(payload.get("file_pattern","")).strip() or ("*.json" if payload["adapter_type"]=="FILE_JSON" else "*.csv")
        payload["source_path"]=str(payload.get("source_path","")).strip()
        payload["archive_path"]=str(payload.get("archive_path","")).strip()
        payload["quarantine_path"]=str(payload.get("quarantine_path","")).strip()
        with self.session() as s:
            row=s.scalar(select(IntegrationInboundEndpoint).where(IntegrationInboundEndpoint.endpoint_id==payload["endpoint_id"]))
            if row:self._update_versioned(row,payload,expected_version,"Inbound integration endpoint")
            else:row=IntegrationInboundEndpoint(**payload);s.add(row)
            s.flush();return row

    def list_inbound_endpoints(self, enabled_only: bool = False):
        with self.session() as s:
            stmt=select(IntegrationInboundEndpoint).order_by(IntegrationInboundEndpoint.endpoint_id)
            if enabled_only:stmt=stmt.where(IntegrationInboundEndpoint.enabled.is_(True))
            return list(s.scalars(stmt))

    def get_inbound_endpoint(self, endpoint_id: str):
        with self.session() as s:
            return s.scalar(select(IntegrationInboundEndpoint).where(IntegrationInboundEndpoint.endpoint_id==endpoint_id))

    def inbound_receipt_by_hash(self, endpoint_id: str, source_sha256: str):
        with self.session() as s:
            return s.scalar(select(IntegrationInboundReceipt).where(
                IntegrationInboundReceipt.endpoint_id==endpoint_id,
                IntegrationInboundReceipt.source_sha256==source_sha256,
            ))

    def save_inbound_receipt(self, data: dict[str, Any]):
        payload=dict(data)
        with self.session() as s:
            row=s.scalar(select(IntegrationInboundReceipt).where(
                IntegrationInboundReceipt.endpoint_id==payload["endpoint_id"],
                IntegrationInboundReceipt.source_sha256==payload["source_sha256"],
            ))
            if row:
                for key,value in payload.items():
                    if key not in {"endpoint_id","source_sha256"} and hasattr(row,key):setattr(row,key,value)
            else:
                row=IntegrationInboundReceipt(**payload);s.add(row)
            s.flush();return row

    def list_inbound_receipts(self, endpoint_id: str = "", limit: int = 1000):
        with self.session() as s:
            stmt=select(IntegrationInboundReceipt).order_by(IntegrationInboundReceipt.processed_at.desc(),IntegrationInboundReceipt.id.desc())
            if endpoint_id:stmt=stmt.where(IntegrationInboundReceipt.endpoint_id==endpoint_id)
            return list(s.scalars(stmt.limit(max(1,min(int(limit),5000)))))

    def inbound_record(self, record_key: str):
        with self.session() as s:
            return s.scalar(select(IntegrationInboundRecord).where(IntegrationInboundRecord.record_key==record_key))

    def save_inbound_record(self, data: dict[str, Any]):
        payload=dict(data)
        with self.session() as s:
            row=s.scalar(select(IntegrationInboundRecord).where(IntegrationInboundRecord.record_key==payload["record_key"]))
            if row:
                for key,value in payload.items():
                    if key!="record_key" and hasattr(row,key):setattr(row,key,value)
            else:
                row=IntegrationInboundRecord(**payload);s.add(row)
            s.flush();return row

    def list_inbound_records(self, endpoint_id: str = "", receipt_id: int | None = None, limit: int = 2000):
        with self.session() as s:
            stmt=select(IntegrationInboundRecord).order_by(IntegrationInboundRecord.processed_at.desc(),IntegrationInboundRecord.id.desc())
            if endpoint_id:stmt=stmt.where(IntegrationInboundRecord.endpoint_id==endpoint_id)
            if receipt_id is not None:stmt=stmt.where(IntegrationInboundRecord.receipt_id==receipt_id)
            return list(s.scalars(stmt.limit(max(1,min(int(limit),10000)))))

    def save_integration_endpoint(self, data: dict[str, Any], expected_version: int | None = None):
        payload=dict(data)
        adapter=str(payload.get("adapter_type","")).upper()
        if adapter not in {"FILE","HTTP"}:raise ValueError("Integration adapter must be FILE or HTTP.")
        payload["adapter_type"]=adapter
        if not str(payload.get("endpoint_id","")).strip() or not str(payload.get("target","")).strip():
            raise ValueError("Endpoint ID and target are required.")
        with self.session() as s:
            row=s.scalar(select(IntegrationEndpoint).where(IntegrationEndpoint.endpoint_id==payload["endpoint_id"]))
            if row:self._update_versioned(row,payload,expected_version,"Integration endpoint")
            else:row=IntegrationEndpoint(**payload);s.add(row)
            s.flush();return row

    def list_integration_endpoints(self, enabled_only: bool = False):
        with self.session() as s:
            stmt=select(IntegrationEndpoint).order_by(IntegrationEndpoint.endpoint_id)
            if enabled_only:stmt=stmt.where(IntegrationEndpoint.enabled.is_(True))
            return list(s.scalars(stmt))

    def _queue_integration_event(self, s, topic: str, entity_type: str, entity_key: str, payload: dict[str, Any]):
        event=IntegrationEvent(
            topic=topic,entity_type=entity_type,entity_key=str(entity_key),
            payload_json=json.dumps(payload,default=str,sort_keys=True),
        )
        s.add(event);s.flush()
        endpoints=list(s.scalars(select(IntegrationEndpoint).where(IntegrationEndpoint.enabled.is_(True))))
        for endpoint in endpoints:
            topics={x.strip() for x in (endpoint.topics or "*").split(",") if x.strip()}
            if "*" in topics or topic in topics:
                s.add(IntegrationDelivery(event_id=event.event_id,endpoint_id=endpoint.endpoint_id))
        return event

    def pending_integration_deliveries(self, limit: int = 100):
        now=datetime.utcnow()
        with self.session() as s:
            deliveries=list(s.scalars(
                select(IntegrationDelivery)
                .where(
                    IntegrationDelivery.status.in_(["Pending","Retry"]),
                    ((IntegrationDelivery.next_attempt_at.is_(None)) | (IntegrationDelivery.next_attempt_at<=now)),
                )
                .order_by(IntegrationDelivery.id)
                .limit(max(1,min(int(limit),1000)))
            ))
            result=[]
            for delivery in deliveries:
                event=s.scalar(select(IntegrationEvent).where(IntegrationEvent.event_id==delivery.event_id))
                endpoint=s.scalar(select(IntegrationEndpoint).where(IntegrationEndpoint.endpoint_id==delivery.endpoint_id))
                if event and endpoint and endpoint.enabled:result.append((delivery,event,endpoint))
            return result

    def mark_integration_delivery(self, delivery_id: int, success: bool, error: str = ""):
        with self.session() as s:
            row=s.get(IntegrationDelivery,delivery_id)
            if not row:raise ValueError("Integration delivery not found")
            row.attempts+=1
            if success:
                row.status="Sent";row.sent_at=datetime.utcnow();row.last_error="";row.next_attempt_at=None
            else:
                row.status="Retry";row.last_error=error[:4000]
                delay=min(3600,30*(2**min(row.attempts,7)))
                row.next_attempt_at=datetime.utcnow()+timedelta(seconds=delay)
            s.flush();return row

    def integration_delivery_rows(self, limit: int = 1000) -> list[dict[str, Any]]:
        with self.session() as s:
            deliveries=list(s.scalars(
                select(IntegrationDelivery).order_by(IntegrationDelivery.id.desc()).limit(max(1,min(int(limit),5000)))
            ))
            rows=[]
            for delivery in deliveries:
                event=s.scalar(select(IntegrationEvent).where(IntegrationEvent.event_id==delivery.event_id))
                endpoint=s.scalar(select(IntegrationEndpoint).where(IntegrationEndpoint.endpoint_id==delivery.endpoint_id))
                rows.append({
                    "id":delivery.id,
                    "event_id":delivery.event_id,
                    "endpoint_id":delivery.endpoint_id,
                    "endpoint_name":endpoint.name if endpoint else "",
                    "adapter_type":endpoint.adapter_type if endpoint else "",
                    "target":endpoint.target if endpoint else "",
                    "topic":event.topic if event else "",
                    "entity_type":event.entity_type if event else "",
                    "entity_key":event.entity_key if event else "",
                    "payload_json":event.payload_json if event else "",
                    "created_at":event.created_at if event else None,
                    "status":delivery.status,
                    "attempts":delivery.attempts,
                    "next_attempt_at":delivery.next_attempt_at,
                    "last_error":delivery.last_error,
                    "sent_at":delivery.sent_at,
                })
            return rows

    def requeue_integration_delivery(self, delivery_id: int, reset_attempts: bool = False):
        with self.session() as s:
            row=s.get(IntegrationDelivery,int(delivery_id))
            if not row:raise ValueError("Integration delivery not found")
            row.status="Pending";row.next_attempt_at=None;row.sent_at=None
            if reset_attempts:row.attempts=0
            s.flush();return row

    def dead_letter_integration_delivery(self, delivery_id: int, reason: str = ""):
        with self.session() as s:
            row=s.get(IntegrationDelivery,int(delivery_id))
            if not row:raise ValueError("Integration delivery not found")
            if row.status=="Sent":raise ValueError("Sent delivery cannot be dead-lettered.")
            row.status="DeadLetter";row.next_attempt_at=None
            if reason.strip():row.last_error=(reason.strip()+"\n"+(row.last_error or "")).strip()[:4000]
            s.flush();return row

    def requeue_dead_letters(self, endpoint_id: str = "") -> int:
        with self.session() as s:
            stmt=select(IntegrationDelivery).where(IntegrationDelivery.status=="DeadLetter")
            if endpoint_id:stmt=stmt.where(IntegrationDelivery.endpoint_id==endpoint_id)
            rows=list(s.scalars(stmt))
            for row in rows:
                row.status="Pending";row.next_attempt_at=None
            return len(rows)

    def integration_delivery_status(self, limit: int = 500):
        with self.session() as s:
            return list(s.scalars(select(IntegrationDelivery).order_by(IntegrationDelivery.id.desc()).limit(limit)))

    def record_recovery_drill(self, backup_path: str, database_type: str, success: bool, detail: str, user: str = "", workstation: str = ""):
        with self.session() as s:
            row=RecoveryDrill(
                backup_path=backup_path,database_type=database_type,success=bool(success),
                detail=detail,performed_by=user,workstation=workstation,
            )
            s.add(row)
            s.add(AuditLog(
                user=user,action="RECOVERY_DRILL_PASS" if success else "RECOVERY_DRILL_FAIL",
                entity_type="SYSTEM",entity_key=backup_path,detail=detail,workstation=workstation,
            ))
            s.flush();return row

    def list_recovery_drills(self, limit: int = 100):
        with self.session() as s:
            return list(s.scalars(select(RecoveryDrill).order_by(RecoveryDrill.performed_at.desc()).limit(max(1,min(int(limit),1000)))))

    def set_user_preference(self, username: str, key: str, value: Any):
        if not username or not key:raise ValueError("Username and preference key are required.")
        encoded=json.dumps(value,default=str,sort_keys=True)
        with self.session() as s:
            row=s.scalar(select(UserPreference).where(UserPreference.username==username,UserPreference.preference_key==key))
            if row:row.value_json=encoded;row.updated_at=datetime.utcnow()
            else:row=UserPreference(username=username,preference_key=key,value_json=encoded);s.add(row)
            s.flush();return row

    def _add_notification_in_session(
        self,s,username: str,category: str,title: str,body: str="",
        severity: str="INFO",entity_type: str="",entity_key: str="",equipment_id: str="",dedupe_key: str="",
    ):
        username=(username or "").strip()
        if not username:return None
        if not s.scalar(select(User).where(User.username==username,User.active.is_(True))):return None
        dedupe_key=(dedupe_key or "").strip()
        if dedupe_key:
            existing=s.scalar(select(UserNotification).where(
                UserNotification.username==username,UserNotification.dedupe_key==dedupe_key,
                UserNotification.dismissed_at.is_(None),UserNotification.read_at.is_(None),
            ).order_by(UserNotification.id.desc()))
            if existing:
                existing.title=title;existing.body=body;existing.severity=severity;existing.created_at=datetime.utcnow()
                return existing
        row=UserNotification(
            username=username,category=category.strip().upper() or "GENERAL",severity=severity.strip().upper() or "INFO",
            title=title.strip(),body=body.strip(),entity_type=entity_type.strip().upper(),entity_key=str(entity_key or ""),
            equipment_id=equipment_id.strip(),dedupe_key=dedupe_key,
        )
        s.add(row);s.flush();return row

    def create_notification(self,username: str,category: str,title: str,body: str="",severity: str="INFO",entity_type: str="",entity_key: str="",equipment_id: str="",dedupe_key: str=""):
        with self.session() as s:
            return self._add_notification_in_session(s,username,category,title,body,severity,entity_type,entity_key,equipment_id,dedupe_key)

    def list_notifications(self,username: str,unread_only: bool=False,include_dismissed: bool=False,limit: int=500):
        with self.session() as s:
            stmt=select(UserNotification).where(UserNotification.username==username)
            if unread_only:stmt=stmt.where(UserNotification.read_at.is_(None),UserNotification.dismissed_at.is_(None))
            elif not include_dismissed:stmt=stmt.where(UserNotification.dismissed_at.is_(None))
            return list(s.scalars(stmt.order_by(UserNotification.created_at.desc(),UserNotification.id.desc()).limit(max(1,min(int(limit),5000)))))

    def unread_notification_count(self,username: str) -> int:
        with self.session() as s:
            return int(s.scalar(select(func.count()).select_from(UserNotification).where(
                UserNotification.username==username,UserNotification.read_at.is_(None),UserNotification.dismissed_at.is_(None),
            )) or 0)

    def mark_notification_read(self,notification_id: int,username: str,read: bool=True):
        with self.session() as s:
            row=s.get(UserNotification,int(notification_id))
            if not row or row.username!=username:raise ValueError("Notification not found.")
            row.read_at=datetime.utcnow() if read else None;s.flush();return row

    def dismiss_notification(self,notification_id: int,username: str):
        with self.session() as s:
            row=s.get(UserNotification,int(notification_id))
            if not row or row.username!=username:raise ValueError("Notification not found.")
            row.dismissed_at=datetime.utcnow();s.flush();return row

    def mark_all_notifications_read(self,username: str) -> int:
        with self.session() as s:
            rows=list(s.scalars(select(UserNotification).where(UserNotification.username==username,UserNotification.read_at.is_(None),UserNotification.dismissed_at.is_(None))))
            now=datetime.utcnow()
            for row in rows:row.read_at=now
            return len(rows)

    def save_user_draft(self, username: str, entity_type: str, entity_key: str, payload: dict[str,Any], draft_key: str = "main"):
        username=username.strip();entity_type=entity_type.strip().upper();entity_key=str(entity_key);draft_key=draft_key.strip() or "main"
        if not username or not entity_type or not entity_key:raise ValueError("Draft username, entity type and key are required.")
        encoded=json.dumps(payload,default=str,sort_keys=True)
        with self.session() as s:
            row=s.scalar(select(UserDraft).where(UserDraft.username==username,UserDraft.entity_type==entity_type,UserDraft.entity_key==entity_key,UserDraft.draft_key==draft_key))
            if row:row.payload_json=encoded;row.updated_at=datetime.utcnow();row.version+=1
            else:row=UserDraft(username=username,entity_type=entity_type,entity_key=entity_key,draft_key=draft_key,payload_json=encoded);s.add(row)
            s.flush();return row

    def get_user_draft(self, username: str, entity_type: str, entity_key: str, draft_key: str = "main"):
        with self.session() as s:
            row=s.scalar(select(UserDraft).where(UserDraft.username==username,UserDraft.entity_type==entity_type.strip().upper(),UserDraft.entity_key==str(entity_key),UserDraft.draft_key==(draft_key.strip() or "main")))
            if not row:return None
            try:payload=json.loads(row.payload_json or "{}")
            except Exception:payload={}
            return {"payload":payload,"updated_at":row.updated_at,"version":row.version}

    def clear_user_draft(self, username: str, entity_type: str, entity_key: str, draft_key: str = "main"):
        with self.session() as s:
            row=s.scalar(select(UserDraft).where(UserDraft.username==username,UserDraft.entity_type==entity_type.strip().upper(),UserDraft.entity_key==str(entity_key),UserDraft.draft_key==(draft_key.strip() or "main")))
            if row:s.delete(row);return True
            return False

    def list_user_drafts(self, username: str, limit: int = 100):
        with self.session() as s:
            return list(s.scalars(select(UserDraft).where(UserDraft.username==username).order_by(UserDraft.updated_at.desc()).limit(max(1,min(int(limit),1000)))))

    def get_user_preference(self, username: str, key: str, default: Any = None):
        with self.session() as s:
            row=s.scalar(select(UserPreference).where(UserPreference.username==username,UserPreference.preference_key==key))
            if not row:return default
            try:return json.loads(row.value_json)
            except Exception:return default

    def list_user_preferences(self, username: str):
        with self.session() as s:
            rows=list(s.scalars(select(UserPreference).where(UserPreference.username==username).order_by(UserPreference.preference_key)))
            result={}
            for row in rows:
                try:result[row.preference_key]=json.loads(row.value_json)
                except Exception:result[row.preference_key]=None
            return result

    def record_recent_item(
        self,
        username: str,
        entity_type: str,
        entity_key: str,
        title: str = "",
        equipment_id: str = "",
    ):
        if not username or not entity_type or not entity_key:return
        now=datetime.utcnow()
        with self.session() as s:
            row=s.scalar(select(UserRecentItem).where(
                UserRecentItem.username==username,
                UserRecentItem.entity_type==entity_type,
                UserRecentItem.entity_key==entity_key,
            ))
            if row:
                row.title=title or row.title;row.equipment_id=equipment_id or row.equipment_id;row.opened_at=now
            else:
                row=UserRecentItem(
                    username=username,entity_type=entity_type,entity_key=entity_key,
                    title=title,equipment_id=equipment_id,opened_at=now,
                );s.add(row)
            s.flush();return row

    def list_recent_items(self, username: str, limit: int = 20):
        with self.session() as s:
            return list(s.scalars(
                select(UserRecentItem)
                .where(UserRecentItem.username==username)
                .order_by(UserRecentItem.opened_at.desc())
                .limit(max(1,min(int(limit),100)))
            ))

    def set_favorite(
        self,
        username: str,
        entity_type: str,
        entity_key: str,
        favorite: bool,
        title: str = "",
        equipment_id: str = "",
    ):
        with self.session() as s:
            row=s.scalar(select(UserFavorite).where(
                UserFavorite.username==username,
                UserFavorite.entity_type==entity_type,
                UserFavorite.entity_key==entity_key,
            ))
            if favorite:
                if not row:
                    row=UserFavorite(
                        username=username,entity_type=entity_type,entity_key=entity_key,
                        title=title,equipment_id=equipment_id,
                    );s.add(row)
                else:
                    row.title=title or row.title;row.equipment_id=equipment_id or row.equipment_id
            elif row:
                s.delete(row);row=None
            s.flush();return row

    def is_favorite(self, username: str, entity_type: str, entity_key: str) -> bool:
        with self.session() as s:
            return bool(s.scalar(select(func.count()).select_from(UserFavorite).where(
                UserFavorite.username==username,
                UserFavorite.entity_type==entity_type,
                UserFavorite.entity_key==entity_key,
            )))

    def list_favorites(self, username: str):
        with self.session() as s:
            return list(s.scalars(
                select(UserFavorite).where(UserFavorite.username==username)
                .order_by(UserFavorite.entity_type,UserFavorite.title,UserFavorite.entity_key)
            ))

    def global_search(self, query: str, limit: int = 80) -> list[dict[str, Any]]:
        q=(query or "").strip()
        if not q:return []
        like=f"%{q}%";out=[]
        max_each=max(5,min(20,int(limit)//8 or 5))
        def add(entity_type,key,title,subtitle="",equipment_id=""):
            if len(out)>=limit:return
            out.append({
                "entity_type":entity_type,"entity_key":str(key),"title":str(title or key),
                "subtitle":str(subtitle or ""),"equipment_id":str(equipment_id or ""),
            })
        with self.session() as s:
            for row in s.scalars(select(Equipment).where(or_(
                Equipment.equipment_id.ilike(like),Equipment.name.ilike(like),Equipment.equipment_type.ilike(like),
                Equipment.model.ilike(like),Equipment.serial_number.ilike(like),Equipment.area.ilike(like),
            )).limit(max_each)):
                add("EQUIPMENT",row.equipment_id,f"{row.equipment_id} — {row.name}",f"{row.status} · {row.area} · {row.model}",row.equipment_id)
            for row in s.scalars(select(Ticket).where(or_(
                Ticket.ticket_no.ilike(like),Ticket.title.ilike(like),Ticket.description.ilike(like),
                Ticket.equipment_id.ilike(like),Ticket.owner.ilike(like),
            )).limit(max_each)):
                add("TICKET",row.ticket_no,f"{row.ticket_no} — {row.title}",f"{row.priority} · {row.status} · {row.equipment_id}",row.equipment_id)
            seen_lot_entities=set()
            for lot in s.scalars(select(EntityLotLink).where(
                EntityLotLink.lot_number.ilike(like)
            ).order_by(EntityLotLink.created_at.desc()).limit(max_each)):
                identity=(lot.entity_type,lot.entity_key)
                if identity in seen_lot_entities:continue
                seen_lot_entities.add(identity)
                if lot.entity_type=="TICKET":
                    ticket=s.scalar(select(Ticket).where(Ticket.ticket_no==lot.entity_key))
                    if ticket:
                        add("TICKET",ticket.ticket_no,f"{ticket.ticket_no} — {ticket.title}",f"Lot {lot.lot_number} · {ticket.status} · {ticket.equipment_id}",ticket.equipment_id)
                elif lot.entity_type=="EQUIPMENT":
                    add("EQUIPMENT",lot.entity_key,f"{lot.entity_key} — lot {lot.lot_number}",f"Lot context",lot.equipment_id or lot.entity_key)
            for row in s.scalars(select(PMTask).where(or_(
                PMTask.pm_id.ilike(like),PMTask.pm_name.ilike(like),PMTask.equipment_id.ilike(like),PMTask.assigned_to.ilike(like),
            )).limit(max_each)):
                add("PM_TASK",row.id,f"{row.pm_id} — {row.pm_name}",f"{row.status} · {row.equipment_id}",row.equipment_id)
            for row in s.scalars(select(EquipmentAlarmEvent).where(or_(
                EquipmentAlarmEvent.alarm_code.ilike(like),EquipmentAlarmEvent.message.ilike(like),EquipmentAlarmEvent.equipment_id.ilike(like),
            )).order_by(EquipmentAlarmEvent.occurred_at.desc()).limit(max_each)):
                add("ALARM",row.event_key,f"{row.alarm_code} — {row.message}",f"{row.state} · {row.equipment_id}",row.equipment_id)
            for row in s.scalars(select(WorkOrder).where(or_(
                WorkOrder.work_order_no.ilike(like),WorkOrder.title.ilike(like),WorkOrder.description.ilike(like),
                WorkOrder.equipment_id.ilike(like),WorkOrder.owner.ilike(like),
            )).limit(max_each)):
                add("WORK_ORDER",row.work_order_no,f"{row.work_order_no} — {row.title}",f"{row.status} · {row.equipment_id} · {row.owner}",row.equipment_id)
            for row in s.scalars(select(InventoryItem).where(or_(
                InventoryItem.part_number.ilike(like),InventoryItem.description.ilike(like),InventoryItem.location_code.ilike(like),
            )).limit(max_each)):
                add("PART",f"{row.part_number}@{row.location_code}",row.part_number,f"{row.description} · {row.location_code}")
            for row in s.scalars(select(ControlledDocument).where(or_(
                ControlledDocument.document_id.ilike(like),ControlledDocument.title.ilike(like),ControlledDocument.entity_key.ilike(like),
            )).limit(max_each)):
                equipment_id=row.entity_key if row.entity_type.upper()=="EQUIPMENT" else ""
                add("DOCUMENT",row.document_id,f"{row.document_id} — {row.title}",f"{row.status} · {row.entity_type}:{row.entity_key}",equipment_id)
            for row in s.scalars(select(EquipmentComponent).where(or_(
                EquipmentComponent.component_id.ilike(like),EquipmentComponent.name.ilike(like),EquipmentComponent.part_number.ilike(like),
                EquipmentComponent.serial_number.ilike(like),EquipmentComponent.equipment_id.ilike(like),
            )).limit(max_each)):
                add("COMPONENT",row.component_id,f"{row.component_id} — {row.name}",f"{row.status} · {row.part_number} · {row.equipment_id}",row.equipment_id)
            for row in s.scalars(select(QualificationRun).where(or_(
                QualificationRun.run_no.ilike(like),QualificationRun.protocol_id.ilike(like),QualificationRun.protocol_name.ilike(like),
                QualificationRun.equipment_id.ilike(like),QualificationRun.status.ilike(like),
            )).order_by(QualificationRun.started_at.desc()).limit(max_each)):
                add("QUALIFICATION",row.run_no,f"{row.run_no} — {row.protocol_name}",f"{row.status} · {row.equipment_id}",row.equipment_id)
            for row in s.scalars(select(Endorsement).where(or_(
                Endorsement.endorsement_no.ilike(like),Endorsement.equipment_id.ilike(like),Endorsement.current_condition.ilike(like),
                Endorsement.pending_work.ilike(like),Endorsement.next_owner.ilike(like),
            )).order_by(Endorsement.created_at.desc()).limit(max_each)):
                add("ENDORSEMENT",row.endorsement_no,f"{row.endorsement_no} — {row.equipment_id}",f"{row.status} · {row.pending_work}",row.equipment_id)
        return out[:limit]

    def my_work(self, username: str, limit: int = 200) -> list[dict[str, Any]]:
        username=(username or "").strip()
        if not username:return []
        rows=[]
        attention=self.operations_attention_queue(max(limit*2,200))
        for item in attention:
            if (item.get("owner") or "").strip().lower()==username.lower():
                rows.append(dict(item))
        with self.session() as s:
            for wo in s.scalars(select(WorkOrder).where(
                WorkOrder.owner==username,WorkOrder.status.notin_(["Completed","Cancelled"])
            ).order_by(WorkOrder.updated_at.desc())):
                rows.append({
                    "severity":"HIGH" if wo.priority in {"P1","Critical","High"} else "MEDIUM",
                    "kind":"WORK_ORDER","key":wo.work_order_no,"equipment_id":wo.equipment_id,
                    "summary":f"{wo.status} — {wo.title}","owner":wo.owner,"age_hours":0.0,
                })
            user=s.scalar(select(User).where(User.username==username))
            userctx={"username":username,"role":user.role} if user else {"username":username,"role":"Read Only"}
            if self.has_permission(userctx,"release.approve"):
                for rel in s.scalars(select(EquipmentRelease).where(EquipmentRelease.status=="Verified")):
                    rows.append({"severity":"HIGH","kind":"APPROVAL","key":str(rel.id),"equipment_id":rel.equipment_id,"summary":"Release approval required","owner":username,"age_hours":0.0})
            if self.has_permission(userctx,"qualification.verify"):
                for run in s.scalars(select(QualificationRun).where(QualificationRun.status=="Submitted")):
                    rows.append({"severity":"HIGH","kind":"VERIFY","key":run.run_no,"equipment_id":run.equipment_id,"summary":f"Qualification verification — {run.protocol_name}","owner":username,"age_hours":0.0})
            if self.has_permission(userctx,"qualification.approve"):
                for run in s.scalars(select(QualificationRun).where(QualificationRun.status=="Verified")):
                    rows.append({"severity":"HIGH","kind":"APPROVAL","key":run.run_no,"equipment_id":run.equipment_id,"summary":f"Qualification approval — {run.protocol_name}","owner":username,"age_hours":0.0})
        for mention,comment in self.list_unacknowledged_mentions(username,limit):
            rows.append({
                "severity":"MEDIUM","kind":"MENTION","key":str(mention.id),
                "equipment_id":comment.equipment_id,
                "summary":f"@mention on {comment.entity_type}:{comment.entity_key} — {comment.body[:120]}",
                "owner":username,"age_hours":max(0.0,(datetime.utcnow()-comment.created_at).total_seconds()/3600),
                "entity_type":comment.entity_type,"entity_key":comment.entity_key,
            })
        rank={"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3}
        dedup={}
        for row in rows:
            dedup[(row.get("kind"),row.get("key"),row.get("summary"))]=row
        result=list(dedup.values())
        result.sort(key=lambda x:(rank.get(x.get("severity"),9),-float(x.get("age_hours") or 0)))
        return result[:max(1,min(int(limit),1000))]

    def add_attachment(
        self,
        entity_type: str,
        entity_key: str,
        stored_path: str,
        *,
        original_name: str = "",
        media_type: str = "",
        category: str = "Evidence",
        caption: str = "",
        tags: str = "",
        equipment_id: str = "",
        created_by: str = "",
        copied_from_id: int | None = None,
    ):
        path=os.path.abspath(stored_path)
        if not os.path.isfile(path):raise FileNotFoundError(path)
        file_size=os.path.getsize(path)
        digest=self._file_sha256(path)
        with self.session() as s:
            row=EntityAttachment(
                entity_type=entity_type.strip().upper(),entity_key=str(entity_key),
                equipment_id=equipment_id.strip(),category=category.strip() or "Evidence",
                original_name=original_name.strip() or os.path.basename(path),stored_path=path,
                media_type=media_type.strip(),file_size=file_size,file_sha256=digest,
                caption=caption.strip(),tags=tags.strip(),created_by=created_by.strip(),
                copied_from_id=copied_from_id,
            )
            s.add(row);s.flush()
            s.add(AuditLog(
                user=created_by or "system",action="ATTACHMENT_ADD",entity_type=row.entity_type,
                entity_key=row.entity_key,detail=json.dumps({"attachment_key":row.attachment_key,"name":row.original_name,"sha256":digest},sort_keys=True),
            ))
            return row

    def list_attachments(self, entity_type: str, entity_key: str, active_only: bool = True):
        with self.session() as s:
            stmt=select(EntityAttachment).where(
                EntityAttachment.entity_type==entity_type.strip().upper(),
                EntityAttachment.entity_key==str(entity_key),
            ).order_by(EntityAttachment.created_at.desc(),EntityAttachment.id.desc())
            if active_only:stmt=stmt.where(EntityAttachment.active.is_(True))
            return list(s.scalars(stmt))

    def get_attachment(self, attachment_id: int):
        with self.session() as s:return s.get(EntityAttachment,attachment_id)

    def update_attachment_metadata(self, attachment_id: int, caption: str, tags: str, category: str, user: str = ""):
        with self.session() as s:
            row=s.get(EntityAttachment,attachment_id)
            if not row or not row.active:raise ValueError("Attachment not found")
            row.caption=caption.strip();row.tags=tags.strip();row.category=category.strip() or "Evidence"
            s.add(AuditLog(user=user or "system",action="ATTACHMENT_METADATA",entity_type=row.entity_type,entity_key=row.entity_key,detail=str(row.id)))
            s.flush();return row

    def remove_attachment(self, attachment_id: int, user: str = ""):
        with self.session() as s:
            row=s.get(EntityAttachment,attachment_id)
            if not row or not row.active:raise ValueError("Attachment not found")
            row.active=False
            s.add(AuditLog(user=user or "system",action="ATTACHMENT_REMOVE",entity_type=row.entity_type,entity_key=row.entity_key,detail=str(row.id)))
            s.flush();return row

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

    def save_equipment(
        self,
        data: dict[str, Any],
        expected_version: int | None = None,
        user: str = "",
        workstation: str = "",
    ):
        payload = dict(data)
        with self.session() as s:
            item = s.scalar(select(Equipment).where(Equipment.equipment_id == payload["equipment_id"]))
            if item:
                # Operational state and disposition are governed workflows, not editable master-data fields.
                payload.pop("status", None)
                payload.pop("disposition", None)
                self._update_versioned(item, payload, expected_version, "Equipment")
            else:
                payload["status"] = payload.get("status") or "Available"
                payload["disposition"] = payload.get("disposition") or "Released"
                if payload["status"] not in EQUIPMENT_STATES:
                    raise ValueError(f"Unknown equipment state: {payload['status']}")
                item = Equipment(**payload)
                s.add(item)
                s.add(EquipmentStateEvent(
                    equipment_id=payload["equipment_id"],
                    from_state="",
                    to_state=payload["status"],
                    state_class=STATE_CLASS[payload["status"]],
                    downtime=payload["status"] in DOWNTIME_STATES,
                    reason_code="INITIAL_STATE",
                    reason_text="Equipment record created",
                    owner=payload.get("owner", ""),
                    changed_by=user,
                    workstation=workstation,
                ))
            s.flush()
            return item

    def alarm_burst_policy(self) -> dict[str, Any]:
        defaults={"window_seconds":300,"threshold_count":3,"min_severity":"WARNING","auto_trigger":False}
        with self.session() as s:
            row=s.scalar(select(ConfigOption).where(
                ConfigOption.category=="ALARM_BURST_POLICY",
                ConfigOption.code=="DEFAULT",
                ConfigOption.active.is_(True),
            ))
            if not row:return defaults
            try:meta=json.loads(row.metadata_json or "{}")
            except Exception:meta={}
        result=dict(defaults);result.update({k:v for k,v in meta.items() if k in defaults})
        try:result["window_seconds"]=max(1,min(int(result["window_seconds"]),86400))
        except Exception:result["window_seconds"]=defaults["window_seconds"]
        try:result["threshold_count"]=max(2,min(int(result["threshold_count"]),1000))
        except Exception:result["threshold_count"]=defaults["threshold_count"]
        result["min_severity"]=str(result.get("min_severity") or "WARNING").upper()
        result["auto_trigger"]=bool(result.get("auto_trigger",False))
        return result

    def save_alarm_burst_policy(
        self,
        window_seconds: int,
        threshold_count: int,
        min_severity: str = "WARNING",
        auto_trigger: bool = False,
    ):
        window=max(1,min(int(window_seconds),86400))
        threshold=max(2,min(int(threshold_count),1000))
        severity=str(min_severity or "WARNING").upper()
        if severity not in {"INFO","LOW","WARNING","MEDIUM","HIGH","CRITICAL"}:
            raise ValueError("Unsupported minimum alarm severity.")
        existing=self.list_config_options("ALARM_BURST_POLICY",False)
        row=next((x for x in existing if x.code=="DEFAULT"),None)
        return self.save_config_option({
            "category":"ALARM_BURST_POLICY","code":"DEFAULT","label":"Default alarm burst policy",
            "sort_order":10,"active":True,"system_locked":False,
            "metadata_json":{
                "window_seconds":window,"threshold_count":threshold,
                "min_severity":severity,"auto_trigger":bool(auto_trigger),
            },
        },row.version if row else None)

    @staticmethod
    def _alarm_severity_rank(value: str) -> int:
        return {"INFO":0,"LOW":1,"WARNING":2,"MEDIUM":3,"HIGH":4,"CRITICAL":5}.get(str(value or "").upper(),0)

    def _evaluate_alarm_burst_in_session(self, s, row: EquipmentAlarmEvent, occurred_at: datetime):
        policy=self.alarm_burst_policy()
        if not policy["auto_trigger"]:return []
        if self._alarm_severity_rank(row.severity)<self._alarm_severity_rank(policy["min_severity"]):return []
        start=occurred_at-timedelta(seconds=policy["window_seconds"])
        alarms=list(s.scalars(select(EquipmentAlarmEvent).where(
            EquipmentAlarmEvent.equipment_id==row.equipment_id,
            EquipmentAlarmEvent.alarm_code==row.alarm_code,
            EquipmentAlarmEvent.occurred_at>=start,
            EquipmentAlarmEvent.occurred_at<=occurred_at,
        ).order_by(EquipmentAlarmEvent.occurred_at,EquipmentAlarmEvent.id)))
        if len(alarms)<policy["threshold_count"]:return []
        recent_exec=list(s.scalars(select(WorkflowAutomationExecution).where(
            WorkflowAutomationExecution.trigger=="ALARM_BURST",
            WorkflowAutomationExecution.equipment_id==row.equipment_id,
            WorkflowAutomationExecution.status=="Completed",
        ).order_by(WorkflowAutomationExecution.id.desc()).limit(100)))
        for execution in recent_exec:
            try:ctx=json.loads(execution.context_json or "{}")
            except Exception:ctx={}
            if str(ctx.get("alarm_code",""))!=row.alarm_code:continue
            # Use source-event time for burst continuity, not server execution time.
            # Plant/FDC timestamps may be offset from the application host clock.
            context_last=ctx.get("last_seen") or ctx.get("first_seen")
            in_window=False
            if context_last:
                try:
                    context_time=datetime.fromisoformat(str(context_last))
                    in_window=start<=context_time<=occurred_at
                except Exception:in_window=False
            else:
                in_window=start<=execution.executed_at<=occurred_at
            if not in_window:continue
            try:results=json.loads(execution.result_json or "[]")
            except Exception:results=[]
            ticket_no=next((str(x.get("ticket_no")) for x in results if isinstance(x,dict) and x.get("type")=="CREATE_INCIDENT" and x.get("ticket_no")),"")
            if ticket_no and not row.related_ticket:row.related_ticket=ticket_no
            return []
        first=alarms[0];last=alarms[-1]
        max_severity=max((x.severity for x in alarms),key=self._alarm_severity_rank)
        burst_key=f"{row.equipment_id}:{row.alarm_code}:{first.event_key}"
        context={
            "entity_type":"ALARM_BURST","entity_key":burst_key,"equipment_id":row.equipment_id,
            "alarm_code":row.alarm_code,"severity":max_severity,"message":row.message,"source":row.source,
            "count":len(alarms),"first_seen":first.occurred_at.isoformat(),"last_seen":last.occurred_at.isoformat(),
            "alarm_ids":[x.event_key for x in alarms],
            "summary":f"{len(alarms)}× {row.alarm_code} alarm burst on {row.equipment_id}",
            "detail":f"Alarm burst detected within {policy['window_seconds']} seconds; source events: "+", ".join(x.event_key for x in alarms),
        }
        return self._apply_workflow_automation_in_session(s,"ALARM_BURST",context)

    def ingest_alarm(
        self,
        equipment_id: str,
        alarm_code: str,
        *,
        state: str = "ACTIVE",
        severity: str = "Warning",
        message: str = "",
        source: str = "Manual",
        event_key: str = "",
        occurred_at: datetime | None = None,
        related_ticket: str = "",
        raw_payload: dict[str, Any] | None = None,
    ):
        state=state.strip().upper()
        if state not in {"ACTIVE","CLEARED"}:raise ValueError("Alarm state must be ACTIVE or CLEARED.")
        occurred_at=occurred_at or datetime.utcnow()
        event_key=event_key.strip() or secrets.token_hex(20)
        with self.session() as s:
            existing=s.scalar(select(EquipmentAlarmEvent).where(EquipmentAlarmEvent.event_key==event_key))
            if existing:return existing
            if not s.scalar(select(Equipment).where(Equipment.equipment_id==equipment_id)):
                raise ValueError("Equipment not found")
            if state=="CLEARED":
                active=s.scalar(select(EquipmentAlarmEvent).where(
                    EquipmentAlarmEvent.equipment_id==equipment_id,
                    EquipmentAlarmEvent.alarm_code==alarm_code,
                    EquipmentAlarmEvent.state=="ACTIVE",
                ).order_by(EquipmentAlarmEvent.occurred_at.desc(),EquipmentAlarmEvent.id.desc()))
                if active:
                    active.state="CLEARED";active.cleared_at=occurred_at
                    self._queue_integration_event(s,"equipment.alarm.cleared","ALARM",active.event_key,{
                        "equipment_id":equipment_id,"alarm_code":alarm_code,"severity":active.severity,
                        "message":active.message,"source":source,"cleared_at":occurred_at.isoformat(),
                    })
                    s.flush();return active
            row=EquipmentAlarmEvent(
                event_key=event_key,equipment_id=equipment_id,alarm_code=alarm_code,
                severity=severity,message=message,source=source,state=state,
                occurred_at=occurred_at,cleared_at=occurred_at if state=="CLEARED" else None,
                related_ticket=related_ticket,raw_payload_json=json.dumps(raw_payload or {},default=str,sort_keys=True),
            )
            s.add(row)
            self._queue_integration_event(s,"equipment.alarm.active" if state=="ACTIVE" else "equipment.alarm.cleared","ALARM",event_key,{
                "equipment_id":equipment_id,"alarm_code":alarm_code,"severity":severity,
                "message":message,"source":source,"state":state,"occurred_at":occurred_at.isoformat(),
                "related_ticket":related_ticket,
            })
            if state=="ACTIVE":
                self._apply_workflow_automation_in_session(s,"ALARM_ACTIVE",{
                    "entity_type":"ALARM","entity_key":event_key,"equipment_id":equipment_id,
                    "alarm_code":alarm_code,"severity":severity,"message":message,"source":source,
                    "ticket_no":related_ticket,"summary":f"{alarm_code} — {message}",
                    "detail":json.dumps(raw_payload or {},default=str,sort_keys=True),
                })
                self._evaluate_alarm_burst_in_session(s,row,occurred_at)
            s.flush();return row

    def link_alarm_to_ticket(self, event_key: str, ticket_no: str, user: str, workstation: str = ""):
        with self.session() as s:
            alarm=s.scalar(select(EquipmentAlarmEvent).where(EquipmentAlarmEvent.event_key==event_key))
            if not alarm:raise ValueError("Alarm event not found")
            self.assert_authorized(user,"ticket.edit",alarm.equipment_id)
            ticket=s.scalar(select(Ticket).where(Ticket.ticket_no==ticket_no))
            if not ticket:raise ValueError("Ticket not found")
            if ticket.equipment_id!=alarm.equipment_id:
                raise ValueError("Alarm and ticket must belong to the same equipment.")
            alarm.related_ticket=ticket.ticket_no
            s.add(AuditLog(
                user=user,action="ALARM_LINK_TICKET",entity_type="ALARM",entity_key=alarm.event_key,
                detail=json.dumps({"ticket_no":ticket.ticket_no,"equipment_id":alarm.equipment_id},sort_keys=True),
                workstation=workstation,
            ))
            self._queue_integration_event(s,"equipment.alarm.linked_incident","ALARM",alarm.event_key,{
                "equipment_id":alarm.equipment_id,"alarm_code":alarm.alarm_code,
                "ticket_no":ticket.ticket_no,"linked_by":user,
            })
            s.flush();return alarm,ticket

    def create_incident_from_alarm(
        self,
        event_key: str,
        user: str,
        *,
        owner: str = "",
        ticket_no: str = "",
        workstation: str = "",
    ):
        with self.session() as s:
            stmt=select(EquipmentAlarmEvent).where(EquipmentAlarmEvent.event_key==event_key)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            alarm=s.scalar(stmt)
            if not alarm:raise ValueError("Alarm event not found")
            self.assert_authorized(user,"ticket.edit",alarm.equipment_id)
            if alarm.related_ticket:
                existing=s.scalar(select(Ticket).where(Ticket.ticket_no==alarm.related_ticket))
                if existing:return existing
            eq=s.scalar(select(Equipment).where(Equipment.equipment_id==alarm.equipment_id))
            if not eq:raise ValueError("Equipment not found")
            if not ticket_no.strip():
                prefix="".join(ch if ch.isalnum() else "-" for ch in alarm.equipment_id.upper()).strip("-")[:28]
                base=f"ALM-{prefix}-{alarm.occurred_at:%y%m%d%H%M%S}-{alarm.event_key[:6].upper()}"
                ticket_no=base[:100]
                suffix=1
                while s.scalar(select(Ticket).where(Ticket.ticket_no==ticket_no)):
                    tail=f"-{suffix}"
                    ticket_no=(base[:100-len(tail)]+tail);suffix+=1
            elif s.scalar(select(Ticket).where(Ticket.ticket_no==ticket_no.strip())):
                raise ValueError("Ticket number already exists.")
            sev=(alarm.severity or "").strip().lower()
            priority="P1" if sev in {"critical","fatal","emergency"} else ("P2" if sev in {"warning","major","high"} else "P3")
            severity="S1" if priority=="P1" else ("S2" if priority=="P2" else "S3")
            assignee=(owner or user).strip()
            description=(
                f"Created from equipment alarm.\n\n"
                f"Alarm: {alarm.alarm_code}\n"
                f"Message: {alarm.message}\n"
                f"Source: {alarm.source}\n"
                f"Occurred: {alarm.occurred_at.isoformat()}\n"
                f"Alarm event key: {alarm.event_key}"
            )
            ticket=Ticket(
                ticket_no=ticket_no.strip(),equipment_id=alarm.equipment_id,
                title=f"Alarm {alarm.alarm_code} — {alarm.message or 'Equipment alarm'}"[:250],
                description=description,severity=severity,priority=priority,status="Open",
                owner=assignee,root_cause="",corrective_action="",verification="",created_by=user,
            )
            s.add(ticket)
            s.add(TicketStateEvent(
                ticket_no=ticket.ticket_no,from_state="",to_state="Open",
                reason_code="INITIAL_STATE",note=f"Created from alarm {alarm.alarm_code}",
                owner=assignee,changed_by=user,workstation=workstation,
            ))
            alarm.related_ticket=ticket.ticket_no
            s.add(AuditLog(
                user=user,action="ALARM_CREATE_INCIDENT",entity_type="ALARM",entity_key=alarm.event_key,
                detail=json.dumps({"ticket_no":ticket.ticket_no,"equipment_id":alarm.equipment_id},sort_keys=True),
                workstation=workstation,
            ))
            self._queue_integration_event(s,"incident.created.from_alarm","TICKET",ticket.ticket_no,{
                "ticket_no":ticket.ticket_no,"equipment_id":alarm.equipment_id,
                "alarm_event_key":alarm.event_key,"alarm_code":alarm.alarm_code,
                "priority":priority,"owner":assignee,"created_by":user,
            })
            s.flush();return ticket

    def create_incident_from_alarm_burst(
        self,
        event_keys: list[str],
        user: str,
        *,
        owner: str = "",
        workstation: str = "",
    ):
        """Create or reuse one incident and link all alarms in one burst.

        Every source alarm is checked to ensure it belongs to the same tool.
        The original individual alarm workflow remains the source of truth.
        """
        keys=list(dict.fromkeys(str(key).strip() for key in event_keys if str(key).strip()))
        if not keys: raise ValueError("Select at least one alarm for burst incident creation.")
        alarms=self.list_alarms_for_event_keys(keys)
        if len(alarms)!=len(keys): raise ValueError("One or more burst alarms no longer exist.")
        equipment_ids={alarm.equipment_id for alarm in alarms}
        if len(equipment_ids)!=1: raise ValueError("A burst incident can only contain one equipment ID.")
        existing={alarm.related_ticket for alarm in alarms if alarm.related_ticket}
        if len(existing)>1: raise ValueError("Burst alarms already link to different incidents.")
        rank={"critical":4,"fatal":4,"emergency":4,"high":3,"major":3,"warning":2,"medium":2,"low":1}
        primary=max(alarms,key=lambda alarm: rank.get((alarm.severity or "").strip().lower(),0))
        ticket=self.create_incident_from_alarm(primary.event_key,user,owner=owner,workstation=workstation)
        for key in keys:
            if key!=primary.event_key:
                self.link_alarm_to_ticket(key,ticket.ticket_no,user,workstation)
        return ticket

    def list_alarms_for_event_keys(self, event_keys: list[str]):
        keys=[str(key).strip() for key in event_keys if str(key).strip()]
        if not keys:return []
        with self.session() as s:
            return list(s.scalars(select(EquipmentAlarmEvent).where(EquipmentAlarmEvent.event_key.in_(keys))))

    def acknowledge_alarm(self, event_key: str, user: str):
        with self.session() as s:
            row=s.scalar(select(EquipmentAlarmEvent).where(EquipmentAlarmEvent.event_key==event_key))
            if not row:raise ValueError("Alarm event not found")
            self.assert_equipment_scope(user,row.equipment_id,"ticket.edit")
            if not row.acknowledged_at:
                row.acknowledged_by=user;row.acknowledged_at=datetime.utcnow()
            s.flush();return row

    def list_alarms(self, equipment_id: str = "", active_only: bool = False, limit: int = 1000):
        with self.session() as s:
            stmt=select(EquipmentAlarmEvent).order_by(EquipmentAlarmEvent.occurred_at.desc(),EquipmentAlarmEvent.id.desc())
            if equipment_id:stmt=stmt.where(EquipmentAlarmEvent.equipment_id==equipment_id)
            if active_only:stmt=stmt.where(EquipmentAlarmEvent.state=="ACTIVE")
            return list(s.scalars(stmt.limit(max(1,min(int(limit),5000)))))

    def alarm_pareto(self, days: int = 30, equipment_id: str = ""):
        cutoff=datetime.utcnow()-timedelta(days=max(1,int(days)))
        with self.session() as s:
            stmt=select(
                EquipmentAlarmEvent.alarm_code,
                EquipmentAlarmEvent.message,
                func.count(EquipmentAlarmEvent.id).label("count"),
            ).where(EquipmentAlarmEvent.occurred_at>=cutoff)
            if equipment_id:stmt=stmt.where(EquipmentAlarmEvent.equipment_id==equipment_id)
            stmt=stmt.group_by(EquipmentAlarmEvent.alarm_code,EquipmentAlarmEvent.message).order_by(func.count(EquipmentAlarmEvent.id).desc())
            return [dict(alarm_code=r[0],message=r[1],count=int(r[2])) for r in s.execute(stmt).all()]

    def list_equipment_state_events(self, equipment_id: str, limit: int = 250):
        with self.session() as s:
            stmt = (
                select(EquipmentStateEvent)
                .where(EquipmentStateEvent.equipment_id == equipment_id)
                .order_by(EquipmentStateEvent.changed_at.desc(), EquipmentStateEvent.id.desc())
                .limit(max(1, min(int(limit), 2000)))
            )
            return list(s.scalars(stmt))

    def list_components(self, equipment_id: str = "", active_only: bool = False):
        with self.session() as s:
            stmt=select(EquipmentComponent).order_by(EquipmentComponent.equipment_id,EquipmentComponent.parent_component_id,EquipmentComponent.component_id)
            if equipment_id:
                stmt=stmt.where(EquipmentComponent.equipment_id==equipment_id)
            if active_only:
                stmt=stmt.where(EquipmentComponent.status!="Removed")
            return list(s.scalars(stmt))

    def save_component(
        self,
        data: dict[str, Any],
        expected_version: int | None = None,
        user: str = "",
        workstation: str = "",
    ):
        self.assert_authorized(user,"equipment.component.edit",str(data.get("equipment_id","")))
        payload=dict(data)
        if not payload.get("component_id","").strip():
            raise ValueError("Component ID is required.")
        with self.session() as s:
            item=s.scalar(select(EquipmentComponent).where(EquipmentComponent.component_id==payload["component_id"]))
            if item:
                # Placement/lifecycle fields are governed; ordinary edits cannot move or reinstall a component.
                payload.pop("equipment_id",None)
                payload.pop("parent_component_id",None)
                payload.pop("status",None)
                payload.pop("installed_at",None)
                payload.pop("removed_at",None)
                self._update_versioned(item,payload,expected_version,"Equipment component")
                event_type="MASTER_UPDATE"
            else:
                eq=s.scalar(select(Equipment).where(Equipment.equipment_id==payload.get("equipment_id","")))
                if not eq:
                    raise ValueError("Parent equipment not found.")
                parent_id=(payload.get("parent_component_id") or "").strip()
                if parent_id:
                    if parent_id==payload["component_id"]:
                        raise ValueError("Component cannot be its own parent.")
                    parent=s.scalar(select(EquipmentComponent).where(EquipmentComponent.component_id==parent_id))
                    if not parent or parent.equipment_id!=payload["equipment_id"] or parent.status=="Removed":
                        raise ValueError("Parent component must be an installed component on the same equipment.")
                payload["status"]="Installed"
                payload["installed_at"]=datetime.utcnow()
                payload["removed_at"]=None
                item=EquipmentComponent(**payload)
                s.add(item)
                s.add(ComponentEvent(
                    component_id=item.component_id,
                    equipment_id=item.equipment_id,
                    event_type="INSTALLED",
                    parent_component_id=item.parent_component_id,
                    reason="Component record installed/commissioned",
                    user=user,
                    workstation=workstation,
                ))
                event_type="INSTALLED"
            s.add(AuditLog(
                user=user,
                action="COMPONENT_"+event_type,
                entity_type="EQUIPMENT_COMPONENT",
                entity_key=item.component_id,
                detail=json.dumps({"equipment_id":item.equipment_id,"parent_component_id":item.parent_component_id},sort_keys=True),
                workstation=workstation,
            ))
            s.flush()
            return item

    def remove_component(
        self,
        component_id: str,
        reason: str,
        user: str,
        related_ticket: str = "",
        related_pm_task_id: int | None = None,
        workstation: str = "",
        expected_version: int | None = None,
    ):
        if not reason.strip():
            raise ValueError("Removal reason is required.")
        with self.session() as s:
            stmt=select(EquipmentComponent).where(EquipmentComponent.component_id==component_id)
            if self.url.startswith("postgresql"):
                stmt=stmt.with_for_update()
            item=s.scalar(stmt)
            if not item:
                raise ValueError("Component not found")
            self.assert_authorized(user,"equipment.component.edit",item.equipment_id)
            if expected_version is not None and item.version!=expected_version:
                raise RuntimeError("CONFLICT: Component changed by another user. Refresh and retry.")
            if item.status=="Removed":
                raise ValueError("Component is already removed.")
            child_count=int(s.scalar(
                select(func.count()).select_from(EquipmentComponent).where(
                    EquipmentComponent.parent_component_id==component_id,
                    EquipmentComponent.status!="Removed",
                )
            ) or 0)
            if child_count:
                raise ValueError(f"Cannot remove component while {child_count} installed child component(s) remain.")
            now=datetime.utcnow()
            item.status="Removed"
            item.removed_at=now
            item.version+=1
            s.add(ComponentEvent(
                component_id=item.component_id,
                equipment_id=item.equipment_id,
                event_type="REMOVED",
                parent_component_id=item.parent_component_id,
                reason=reason.strip(),
                related_ticket=related_ticket.strip(),
                related_pm_task_id=related_pm_task_id,
                user=user,
                workstation=workstation,
                occurred_at=now,
            ))
            s.add(AuditLog(
                user=user,
                action="COMPONENT_REMOVED",
                entity_type="EQUIPMENT_COMPONENT",
                entity_key=item.component_id,
                detail=json.dumps({
                    "equipment_id":item.equipment_id,
                    "reason":reason.strip(),
                    "related_ticket":related_ticket.strip(),
                    "related_pm_task_id":related_pm_task_id,
                },sort_keys=True),
                workstation=workstation,
                created_at=now,
            ))
            s.flush()
            return item

    def list_component_events(self, component_id: str = "", equipment_id: str = ""):
        with self.session() as s:
            stmt=select(ComponentEvent).order_by(ComponentEvent.occurred_at.desc(),ComponentEvent.id.desc())
            if component_id:
                stmt=stmt.where(ComponentEvent.component_id==component_id)
            if equipment_id:
                stmt=stmt.where(ComponentEvent.equipment_id==equipment_id)
            return list(s.scalars(stmt))

    def list_meters(self, equipment_id: str = ""):
        with self.session() as s:
            stmt=select(EquipmentMeter).order_by(EquipmentMeter.equipment_id,EquipmentMeter.meter_code)
            if equipment_id:
                stmt=stmt.where(EquipmentMeter.equipment_id==equipment_id)
            return list(s.scalars(stmt))

    def save_meter(self, data: dict[str, Any], expected_version: int | None = None):
        payload=dict(data)
        mode=str(payload.pop("meter_mode","COUNTER")).upper()
        if mode not in {"COUNTER","GAUGE"}:raise ValueError("Meter mode must be COUNTER or GAUGE.")
        with self.session() as s:
            if not s.scalar(select(Equipment).where(Equipment.equipment_id==payload.get("equipment_id",""))):
                raise ValueError("Equipment not found")
            item=s.scalar(select(EquipmentMeter).where(
                EquipmentMeter.equipment_id==payload["equipment_id"],
                EquipmentMeter.meter_code==payload["meter_code"],
            ))
            if item:
                payload.pop("current_value",None)
                payload.pop("last_reading_at",None)
                self._update_versioned(item,payload,expected_version,"Equipment meter")
            else:
                item=EquipmentMeter(**payload)
                s.add(item);s.flush()
            behavior=s.scalar(select(EquipmentMeterBehavior).where(
                EquipmentMeterBehavior.equipment_id==item.equipment_id,
                EquipmentMeterBehavior.meter_code==item.meter_code,
            ))
            if behavior:
                if behavior.meter_mode!=mode:behavior.meter_mode=mode;behavior.version+=1
            else:s.add(EquipmentMeterBehavior(equipment_id=item.equipment_id,meter_code=item.meter_code,meter_mode=mode))
            s.flush()
            return item

    def meter_mode(self, equipment_id: str, meter_code: str) -> str:
        with self.session() as s:
            row=s.scalar(select(EquipmentMeterBehavior).where(
                EquipmentMeterBehavior.equipment_id==equipment_id,
                EquipmentMeterBehavior.meter_code==meter_code,
            ))
            return row.meter_mode if row else "COUNTER"

    def list_meter_readings(self, equipment_id: str, meter_code: str = "", limit: int = 500):
        with self.session() as s:
            stmt=select(MeterReading).where(MeterReading.equipment_id==equipment_id)
            if meter_code:
                stmt=stmt.where(MeterReading.meter_code==meter_code)
            stmt=stmt.order_by(MeterReading.recorded_at.desc(),MeterReading.id.desc()).limit(max(1,min(int(limit),5000)))
            return list(s.scalars(stmt))

    def _evaluate_usage_triggers_in_session(self, s, meter: EquipmentMeter, user: str = "", workstation: str = ""):
        created=[]
        stmt=select(PMUsageTrigger).where(
            PMUsageTrigger.equipment_id==meter.equipment_id,
            PMUsageTrigger.meter_code==meter.meter_code,
            PMUsageTrigger.active.is_(True),
        )
        if self.url.startswith("postgresql"):
            stmt=stmt.with_for_update()
        triggers=list(s.scalars(stmt))
        for trigger in triggers:
            if meter.current_value<trigger.next_trigger_value:
                continue
            open_task=s.scalar(select(PMTask).where(
                PMTask.equipment_id==meter.equipment_id,
                PMTask.pm_id==trigger.pm_id,
                PMTask.status.notin_(["Completed","Cancelled"]),
            ))
            if open_task:
                continue
            definition=s.scalar(select(PMDefinition).where(PMDefinition.pm_id==trigger.pm_id))
            now=datetime.utcnow()
            threshold=trigger.next_trigger_value
            task=PMTask(
                equipment_id=meter.equipment_id,
                pm_id=trigger.pm_id,
                pm_name=definition.name if definition else trigger.pm_id,
                original_due_date=now,
                scheduled_date=now,
                status="Pending",
                estimated_hours=definition.estimated_hours if definition else 0.0,
                priority="High",
                sop_path=definition.sop_path if definition else "",
            )
            s.add(task)
            s.flush()
            s.add(PMUsageOccurrence(
                trigger_id=trigger.trigger_id,
                task_id=task.id,
                equipment_id=meter.equipment_id,
                pm_id=trigger.pm_id,
                meter_code=meter.meter_code,
                trigger_value=threshold,
                reading_value=meter.current_value,
            ))
            trigger.last_trigger_value=threshold
            while trigger.next_trigger_value<=meter.current_value:
                trigger.next_trigger_value+=trigger.interval_value
            trigger.version+=1
            s.add(AuditLog(
                user=user,
                action="PM_USAGE_TRIGGER",
                entity_type="PM_TASK",
                entity_key=str(task.id),
                detail=json.dumps({
                    "trigger_id":trigger.trigger_id,
                    "equipment_id":meter.equipment_id,
                    "pm_id":trigger.pm_id,
                    "meter_code":meter.meter_code,
                    "trigger_value":threshold,
                    "reading_value":meter.current_value,
                },sort_keys=True),
                workstation=workstation,
            ))
            created.append(task)
        return created

    def record_meter_reading(
        self,
        equipment_id: str,
        meter_code: str,
        value: float,
        user: str,
        note: str = "",
        reset: bool = False,
        workstation: str = "",
        expected_version: int | None = None,
    ):
        self.assert_authorized(user,"equipment.meter.record",equipment_id)
        with self.session() as s:
            stmt=select(EquipmentMeter).where(
                EquipmentMeter.equipment_id==equipment_id,
                EquipmentMeter.meter_code==meter_code,
            )
            if self.url.startswith("postgresql"):
                stmt=stmt.with_for_update()
            meter=s.scalar(stmt)
            if not meter:
                raise ValueError("Equipment meter not found")
            if expected_version is not None and meter.version!=expected_version:
                raise RuntimeError("CONFLICT: Meter changed by another user. Refresh and retry.")
            value=float(value)
            if value<0:
                raise ValueError("Meter reading cannot be negative")
            behavior=s.scalar(select(EquipmentMeterBehavior).where(
                EquipmentMeterBehavior.equipment_id==equipment_id,
                EquipmentMeterBehavior.meter_code==meter_code,
            ))
            mode=behavior.meter_mode if behavior else "COUNTER"
            if mode=="COUNTER" and value<meter.current_value and not reset:
                raise ValueError("Counter reading cannot decrease unless an explicit reset is recorded.")
            if mode=="GAUGE" and reset:
                raise ValueError("Gauge meters do not use counter reset operations.")
            now=datetime.utcnow()
            reading=MeterReading(
                equipment_id=equipment_id,
                meter_code=meter_code,
                value=value,
                reading_type="Reset" if reset else "Reading",
                note=note.strip(),
                recorded_by=user,
                workstation=workstation,
                recorded_at=now,
            )
            s.add(reading)
            meter.current_value=value
            meter.last_reading_at=now
            meter.version+=1

            if reset:
                trigger_stmt=select(PMUsageTrigger).where(
                    PMUsageTrigger.equipment_id==equipment_id,
                    PMUsageTrigger.meter_code==meter_code,
                    PMUsageTrigger.active.is_(True),
                )
                if self.url.startswith("postgresql"):
                    trigger_stmt=trigger_stmt.with_for_update()
                for trigger in s.scalars(trigger_stmt):
                    trigger.last_trigger_value=value
                    trigger.next_trigger_value=value+trigger.interval_value
                    trigger.version+=1
                created=[]
            else:
                created=self._evaluate_usage_triggers_in_session(s,meter,user=user,workstation=workstation)
                created+=self._evaluate_condition_triggers_in_session(s,meter,user=user,workstation=workstation)

            s.add(AuditLog(
                user=user,
                action="METER_RESET" if reset else "METER_READING",
                entity_type="EQUIPMENT_METER",
                entity_key=f"{equipment_id}:{meter_code}",
                detail=json.dumps({"value":value,"unit":meter.unit,"note":note.strip(),"pm_tasks_created":[t.id for t in created]},sort_keys=True),
                workstation=workstation,
                created_at=now,
            ))
            s.flush()
            return reading,created

    def save_pm_usage_trigger(self, data: dict[str, Any], expected_version: int | None = None):
        payload=dict(data)
        interval=float(payload.get("interval_value") or 0)
        if interval<=0:
            raise ValueError("Usage trigger interval must be greater than zero.")
        with self.session() as s:
            meter=s.scalar(select(EquipmentMeter).where(
                EquipmentMeter.equipment_id==payload.get("equipment_id",""),
                EquipmentMeter.meter_code==payload.get("meter_code",""),
            ))
            if not meter:
                raise ValueError("Configured equipment meter not found")
            if not s.scalar(select(PMDefinition).where(PMDefinition.pm_id==payload.get("pm_id",""))):
                raise ValueError("PM definition not found")
            item=s.scalar(select(PMUsageTrigger).where(PMUsageTrigger.trigger_id==payload["trigger_id"]))
            if item:
                payload.pop("equipment_id",None)
                payload.pop("pm_id",None)
                payload.pop("meter_code",None)
                payload.pop("last_trigger_value",None)
                payload.pop("next_trigger_value",None)
                self._update_versioned(item,payload,expected_version,"PM usage trigger")
            else:
                base=float(payload.pop("start_value",meter.current_value) or 0.0)
                payload["last_trigger_value"]=base
                payload["next_trigger_value"]=base+interval
                item=PMUsageTrigger(**payload)
                s.add(item)
            s.flush()
            return item

    def list_pm_usage_triggers(self, equipment_id: str = ""):
        with self.session() as s:
            stmt=select(PMUsageTrigger).order_by(PMUsageTrigger.equipment_id,PMUsageTrigger.trigger_id)
            if equipment_id:
                stmt=stmt.where(PMUsageTrigger.equipment_id==equipment_id)
            return list(s.scalars(stmt))

    def save_pm_condition_trigger(self, data: dict[str, Any], expected_version: int | None = None):
        payload=dict(data)
        comp=str(payload.get("comparator","")).strip()
        if comp not in {">",">=","<","<="}:raise ValueError("Condition comparator must be >, >=, <, or <=.")
        with self.session() as s:
            meter=s.scalar(select(EquipmentMeter).where(
                EquipmentMeter.equipment_id==payload.get("equipment_id",""),
                EquipmentMeter.meter_code==payload.get("meter_code",""),
            ))
            if not meter:raise ValueError("Configured equipment meter not found")
            if not s.scalar(select(PMDefinition).where(PMDefinition.pm_id==payload.get("pm_id",""))):
                raise ValueError("PM definition not found")
            row=s.scalar(select(PMConditionTrigger).where(PMConditionTrigger.trigger_id==payload["trigger_id"]))
            if row:
                payload.pop("latched",None)
                self._update_versioned(row,payload,expected_version,"PM condition trigger")
            else:
                payload.setdefault("latched",False);row=PMConditionTrigger(**payload);s.add(row)
            s.flush();return row

    def list_pm_condition_triggers(self, equipment_id: str = ""):
        with self.session() as s:
            stmt=select(PMConditionTrigger).order_by(PMConditionTrigger.equipment_id,PMConditionTrigger.trigger_id)
            if equipment_id:stmt=stmt.where(PMConditionTrigger.equipment_id==equipment_id)
            return list(s.scalars(stmt))

    def list_pm_condition_occurrences(self, trigger_id: str = ""):
        with self.session() as s:
            stmt=select(PMConditionOccurrence).order_by(PMConditionOccurrence.created_at.desc())
            if trigger_id:stmt=stmt.where(PMConditionOccurrence.trigger_id==trigger_id)
            return list(s.scalars(stmt))

    @staticmethod
    def _condition_matches(value: float, comparator: str, threshold: float) -> bool:
        if comparator==">":return value>threshold
        if comparator==">=":return value>=threshold
        if comparator=="<":return value<threshold
        if comparator=="<=":return value<=threshold
        raise ValueError("Unsupported condition comparator")

    def _evaluate_condition_triggers_in_session(self, s, meter: EquipmentMeter, user: str = "", workstation: str = ""):
        created=[]
        stmt=select(PMConditionTrigger).where(
            PMConditionTrigger.equipment_id==meter.equipment_id,
            PMConditionTrigger.meter_code==meter.meter_code,
            PMConditionTrigger.active.is_(True),
        )
        if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
        for trigger in s.scalars(stmt):
            matched=self._condition_matches(meter.current_value,trigger.comparator,trigger.threshold)
            if trigger.latched:
                reset=False
                if trigger.reset_threshold is None:
                    reset=not matched
                elif trigger.comparator in {">",">="}:
                    reset=meter.current_value<=trigger.reset_threshold
                else:
                    reset=meter.current_value>=trigger.reset_threshold
                if reset:
                    trigger.latched=False;trigger.version+=1
                    s.add(PMConditionOccurrence(
                        trigger_id=trigger.trigger_id,task_id=None,equipment_id=meter.equipment_id,
                        pm_id=trigger.pm_id,meter_code=meter.meter_code,threshold=trigger.threshold,
                        reading_value=meter.current_value,event_type="RESET",
                    ))
                continue
            if not matched:continue
            open_task=s.scalar(select(PMTask).where(
                PMTask.equipment_id==meter.equipment_id,PMTask.pm_id==trigger.pm_id,
                PMTask.status.notin_(["Completed","Cancelled"]),
            ))
            task=None
            if not open_task:
                definition=s.scalar(select(PMDefinition).where(PMDefinition.pm_id==trigger.pm_id))
                now=datetime.utcnow()
                task=PMTask(
                    equipment_id=meter.equipment_id,pm_id=trigger.pm_id,
                    pm_name=definition.name if definition else trigger.pm_id,
                    original_due_date=now,scheduled_date=now,status="Pending",
                    estimated_hours=definition.estimated_hours if definition else 0.0,
                    priority="High",sop_path=definition.sop_path if definition else "",
                )
                s.add(task);s.flush();created.append(task)
            trigger.latched=True;trigger.version+=1
            s.add(PMConditionOccurrence(
                trigger_id=trigger.trigger_id,task_id=task.id if task else (open_task.id if open_task else None),
                equipment_id=meter.equipment_id,pm_id=trigger.pm_id,meter_code=meter.meter_code,
                threshold=trigger.threshold,reading_value=meter.current_value,event_type="TRIGGERED",
            ))
            s.add(AuditLog(
                user=user,action="PM_CONDITION_TRIGGER",entity_type="PM_TASK",
                entity_key=str(task.id if task else open_task.id),
                detail=json.dumps({"trigger_id":trigger.trigger_id,"meter_code":meter.meter_code,
                    "reading":meter.current_value,"comparator":trigger.comparator,"threshold":trigger.threshold},sort_keys=True),
                workstation=workstation,
            ))
        return created

    def list_pm_usage_occurrences(self, trigger_id: str = ""):
        with self.session() as s:
            stmt=select(PMUsageOccurrence).order_by(PMUsageOccurrence.created_at.desc())
            if trigger_id:
                stmt=stmt.where(PMUsageOccurrence.trigger_id==trigger_id)
            return list(s.scalars(stmt))

    def evaluate_usage_triggers(self, equipment_id: str, meter_code: str, user: str = "", workstation: str = ""):
        with self.session() as s:
            stmt=select(EquipmentMeter).where(
                EquipmentMeter.equipment_id==equipment_id,
                EquipmentMeter.meter_code==meter_code,
            )
            if self.url.startswith("postgresql"):
                stmt=stmt.with_for_update()
            meter=s.scalar(stmt)
            if not meter:
                return []
            created=self._evaluate_usage_triggers_in_session(s,meter,user=user,workstation=workstation)
            s.flush()
            return created

    def transition_equipment_state(
        self,
        equipment_id: str,
        target_state: str,
        *,
        reason_code: str,
        reason_text: str = "",
        related_ticket: str = "",
        related_pm_task_id: int | None = None,
        owner: str = "",
        user: str,
        workstation: str = "",
        expected_version: int | None = None,
        override: bool = False,
        override_reason: str = "",
    ):
        self.assert_authorized(user,"equipment.transition",equipment_id)
        if override:
            if not override_reason.strip():
                raise ValueError("Workflow override requires explicit justification.")
            self.assert_authorized(user,"workflow.override",equipment_id)
        with self.session() as s:
            stmt = select(Equipment).where(Equipment.equipment_id == equipment_id)
            if self.url.startswith("postgresql"):
                stmt = stmt.with_for_update()
            eq = s.scalar(stmt)
            if not eq:
                raise ValueError("Equipment not found")
            if expected_version is not None and eq.version != expected_version:
                raise RuntimeError("CONFLICT: Equipment changed by another user. Refresh and retry.")

            decision = validate_transition(
                eq.status,
                target_state,
                reason_code=reason_code,
                reason_text=reason_text,
                related_ticket=related_ticket,
                related_pm_task_id=related_pm_task_id,
                owner=owner,
                disposition=eq.disposition,
                override=override,
            )
            now = datetime.utcnow()
            event = EquipmentStateEvent(
                equipment_id=equipment_id,
                from_state=eq.status,
                to_state=target_state,
                state_class=decision.state_class,
                downtime=decision.downtime,
                reason_code=reason_code,
                reason_text=reason_text.strip(),
                related_ticket=related_ticket.strip(),
                related_pm_task_id=related_pm_task_id,
                owner=owner.strip(),
                changed_by=user,
                workstation=workstation,
                changed_at=now,
            )
            s.add(event)
            previous = eq.status
            eq.status = target_state
            eq.version += 1
            eq.updated_at = now
            self._queue_integration_event(s,"equipment.state.changed","EQUIPMENT",equipment_id,{
                "equipment_id":equipment_id,"from_state":previous,"to_state":target_state,
                "reason_code":reason_code,"reason_text":reason_text.strip(),"owner":owner.strip(),
                "related_ticket":related_ticket.strip(),"changed_by":user,"changed_at":now.isoformat(),
            })
            s.add(AuditLog(
                user=user,
                action="STATE_TRANSITION_OVERRIDE" if override else "STATE_TRANSITION",
                entity_type="EQUIPMENT",
                entity_key=equipment_id,
                detail=json.dumps({
                    "from": previous,
                    "to": target_state,
                    "state_class": STATE_CLASS[target_state],
                    "reason_code": reason_code,
                    "reason_text": reason_text.strip(),
                    "related_ticket": related_ticket.strip(),
                    "related_pm_task_id": related_pm_task_id,
                    "owner": owner.strip(),
                    "override": override,
                    "override_reason": override_reason.strip(),
                }, sort_keys=True),
                workstation=workstation,
                created_at=now,
            ))
            s.flush()
            return eq, event

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

    def apply_pm_template_bundle(
        self,
        definition: dict[str, Any],
        steps: list[dict[str, Any]],
        requirements: list[dict[str, Any]],
        user: str,
        workstation: str = "",
    ) -> dict[str,int]:
        """Apply one Excel-authored PM definition as an authoritative revision."""
        payload=dict(definition)
        pm_id=str(payload.get("pm_id","")).strip()
        equipment_id=str(payload.get("equipment_id","")).strip()
        if not pm_id:raise ValueError("PM ID is required.")
        if not steps:raise ValueError("A PM template must contain at least one valid step.")
        if equipment_id:self.assert_authorized(user,"pm.edit",equipment_id)
        imported_steps={int(x["step_no"]) for x in steps}
        imported_requirements={str(x["requirement_id"]).strip() for x in requirements}
        result={"definition_updated":0,"steps_revised":0,"steps_created":0,"steps_retired":0,
                "requirements_revised":0,"requirements_created":0,"requirements_retired":0}
        with self.session() as s:
            current_def=s.scalar(select(PMDefinition).where(PMDefinition.pm_id==pm_id))
            if current_def:
                if current_def.equipment_id and equipment_id and current_def.equipment_id!=equipment_id:
                    raise ValueError("Existing PM ID cannot be reassigned to a different equipment through template import.")
                self._update_versioned(current_def,payload,current_def.version,"PM definition")
                current_def.revision=(current_def.revision or 1)+1
                result["definition_updated"]=1
            else:
                payload.setdefault("revision",1);payload.setdefault("version",1)
                s.add(PMDefinition(**payload));result["definition_updated"]=1

            active_specs=list(s.scalars(select(PMSpec).where(PMSpec.pm_id==pm_id,PMSpec.active.is_(True))))
            current_by_step={int(x.step_no):x for x in active_specs}
            for spec_data in steps:
                data=dict(spec_data);data["pm_id"]=pm_id;step_no=int(data["step_no"])
                old=current_by_step.get(step_no)
                if old:
                    old.active=False;old.version+=1
                    data["revision"]=(old.revision or 1)+1;data["active"]=True
                    s.add(PMSpec(**data));result["steps_revised"]+=1
                else:
                    data.setdefault("revision",1);data["active"]=True
                    s.add(PMSpec(**data));result["steps_created"]+=1
            for old in active_specs:
                if int(old.step_no) not in imported_steps:
                    old.active=False;old.version+=1;result["steps_retired"]+=1

            active_reqs=list(s.scalars(select(PMRequirement).where(PMRequirement.pm_id==pm_id,PMRequirement.active.is_(True))))
            current_req={x.requirement_id:x for x in active_reqs}
            for req_data in requirements:
                data=dict(req_data);data["pm_id"]=pm_id
                rid=str(data["requirement_id"]).strip()
                old=current_req.get(rid)
                if old:
                    old.active=False;old.version+=1
                    data["revision"]=(old.revision or 1)+1;data["active"]=True
                    s.add(PMRequirement(**data));result["requirements_revised"]+=1
                else:
                    data.setdefault("revision",1);data["active"]=True
                    s.add(PMRequirement(**data));result["requirements_created"]+=1
            for old in active_reqs:
                if old.requirement_id not in imported_requirements:
                    old.active=False;old.version+=1;result["requirements_retired"]+=1

            s.add(AuditLog(
                user=user,action="PM_TEMPLATE_IMPORT",entity_type="PM_DEFINITION",entity_key=pm_id,
                detail=json.dumps(result,sort_keys=True),workstation=workstation,
            ))
            s.flush()
        return result

    def list_pm_definitions(self):
        with self.session() as s: return list(s.scalars(select(PMDefinition).order_by(PMDefinition.pm_id)))

    def upsert_pm_task(self, data: dict[str, Any]):
        with self.session() as s:
            item = s.scalar(select(PMTask).where(PMTask.equipment_id == data.get("equipment_id", ""), PMTask.pm_id == data.get("pm_id", ""), PMTask.original_due_date == data.get("original_due_date")))
            if item: self._update_versioned(item, data, None, "PM task")
            else: item = PMTask(**data); s.add(item)
            s.flush(); return item

    def list_pm_tasks(self, equipment_id: str = ""):
        with self.session() as s:
            stmt=select(PMTask)
            if equipment_id:stmt=stmt.where(PMTask.equipment_id==equipment_id)
            stmt=stmt.order_by(PMTask.original_due_date.asc().nullslast(),PMTask.equipment_id)
            return list(s.scalars(stmt))

    def get_pm_task(self, task_id: int):
        with self.session() as s: return s.get(PMTask, task_id)

    def plan_pm_task(
        self,
        task_id: int,
        user: str,
        *,
        scheduled_date: datetime | None = None,
        assigned_to: str | None = None,
        expected_version: int | None = None,
        workstation: str = "",
    ):
        with self.session() as s:
            stmt=select(PMTask).where(PMTask.id==task_id)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            task=s.scalar(stmt)
            if not task:raise ValueError("PM task not found")
            self.assert_authorized(user,"pm.edit",task.equipment_id)
            if expected_version is not None and task.version!=expected_version:
                raise RuntimeError("CONFLICT: PM task changed by another user. Refresh and retry.")
            if task.status in {"Completed","Cancelled","In Progress"}:
                raise ValueError(f"Cannot re-plan PM task in {task.status} state.")
            changes={}
            if scheduled_date is not None:
                definition=s.scalar(select(PMDefinition).where(PMDefinition.pm_id==task.pm_id))
                original=task.original_due_date
                if original and definition and task.status!="Deferred":
                    earliest=original-timedelta(days=max(0,definition.early_window_days or 0))
                    latest=original+timedelta(days=max(0,definition.grace_days or 0))
                    if scheduled_date<earliest:
                        raise ValueError(f"Scheduled date is before the controlled early-execution window ({earliest:%Y-%m-%d}).")
                    if scheduled_date>latest:
                        raise ValueError(f"Scheduled date exceeds the controlled grace window ({latest:%Y-%m-%d}). Use the PM deferral workflow.")
                if task.status=="Deferred" and task.scheduled_date and scheduled_date>task.scheduled_date:
                    raise ValueError("A deferred PM cannot be moved later than its approved deferred date without a new deferral.")
                task.scheduled_date=scheduled_date;changes["scheduled_date"]=scheduled_date.isoformat()
                if task.status in {"Pending","Overdue"}:task.status="Scheduled"
            if assigned_to is not None:
                task.assigned_to=assigned_to.strip();changes["assigned_to"]=task.assigned_to
            if not changes:return task
            task.version+=1
            task.updated_at=datetime.utcnow()
            s.add(AuditLog(
                user=user,action="PM_PLAN_UPDATE",entity_type="PM_TASK",entity_key=str(task.id),
                detail=json.dumps(changes,sort_keys=True),workstation=workstation,
            ))
            self._queue_integration_event(s,"maintenance.pm.planned","PM_TASK",str(task.id),{
                "task_id":task.id,"equipment_id":task.equipment_id,"pm_id":task.pm_id,
                "status":task.status,"scheduled_date":task.scheduled_date.isoformat() if task.scheduled_date else None,
                "assigned_to":task.assigned_to,"changed_by":user,
            })
            s.flush();return task

    def get_pm_task_schedule(self, task_id: int):
        with self.session() as s:
            return s.scalar(select(PMTaskSchedule).where(PMTaskSchedule.task_id==task_id))

    def list_pm_schedule_events(self, task_id: int):
        with self.session() as s:
            return list(s.scalars(
                select(PMTaskScheduleEvent).where(PMTaskScheduleEvent.task_id==task_id)
                .order_by(PMTaskScheduleEvent.changed_at.desc(),PMTaskScheduleEvent.id.desc())
            ))

    def schedule_pm_task(
        self,
        task_id: int,
        user: str,
        *,
        start_at: datetime,
        end_at: datetime | None = None,
        assigned_to: str | None = None,
        reason: str = "",
        expected_task_version: int | None = None,
        workstation: str = "",
    ) -> dict[str,Any]:
        """Move a PM calendar slot without changing its controlled due date.

        Calendar placement is operational planning. Moving outside the recommended
        early/grace window is allowed when a reason is supplied and remains
        visible in the audit trail; formal due-date extension is still handled by
        the deferral workflow.
        """
        if not start_at:raise ValueError("Scheduled start is required.")
        with self.session() as s:
            stmt=select(PMTask).where(PMTask.id==task_id)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            task=s.scalar(stmt)
            if not task:raise ValueError("PM task not found")
            self.assert_authorized(user,"pm.edit",task.equipment_id)
            if expected_task_version is not None and task.version!=expected_task_version:
                raise RuntimeError("CONFLICT: PM task changed by another user. Refresh and retry.")
            if task.status in {"Completed","Cancelled"}:
                raise ValueError(f"Cannot schedule PM task in {task.status} state.")
            hours=float(task.estimated_hours or 0)
            if end_at is None:end_at=start_at+timedelta(hours=max(hours,0.5))
            if end_at<=start_at:raise ValueError("Scheduled end must be after scheduled start.")

            definition=s.scalar(select(PMDefinition).where(PMDefinition.pm_id==task.pm_id))
            due=task.original_due_date
            early=(due-timedelta(days=max(0,definition.early_window_days or 0))) if due and definition else None
            latest=(due+timedelta(days=max(0,definition.grace_days or 0))) if due and definition else None
            outside=bool((early and start_at<early) or (latest and start_at>latest))
            if outside and not reason.strip():
                raise ValueError("This slot is outside the recommended PM window. Enter a scheduling reason to continue.")

            schedule=s.scalar(select(PMTaskSchedule).where(PMTaskSchedule.task_id==task.id))
            old_start=schedule.scheduled_start_at if schedule else task.scheduled_date
            old_end=schedule.scheduled_end_at if schedule else (
                old_start+timedelta(hours=max(hours,0.5)) if old_start else None
            )
            old_assignee=task.assigned_to or ""
            new_assignee=old_assignee if assigned_to is None else assigned_to.strip()
            if schedule is None:
                baseline=task.scheduled_date or task.original_due_date or start_at
                schedule=PMTaskSchedule(
                    task_id=task.id,baseline_start_at=baseline,
                    scheduled_start_at=start_at,scheduled_end_at=end_at,
                    planned_hours=max(0.0,(end_at-start_at).total_seconds()/3600),
                    updated_by=user,
                )
                s.add(schedule)
            else:
                schedule.scheduled_start_at=start_at;schedule.scheduled_end_at=end_at
                schedule.planned_hours=max(0.0,(end_at-start_at).total_seconds()/3600)
                schedule.updated_by=user;schedule.updated_at=datetime.utcnow();schedule.version+=1
            task.scheduled_date=start_at
            task.assigned_to=new_assignee
            if task.status in {"Pending","Overdue"}:task.status="Scheduled"
            task.version+=1;task.updated_at=datetime.utcnow()

            event=PMTaskScheduleEvent(
                task_id=task.id,old_start_at=old_start,old_end_at=old_end,
                new_start_at=start_at,new_end_at=end_at,
                old_assignee=old_assignee,new_assignee=new_assignee,
                reason=reason.strip(),outside_window=outside,changed_by=user,
            )
            s.add(event)
            s.add(AuditLog(
                user=user,action="PM_CALENDAR_MOVE",entity_type="PM_TASK",entity_key=str(task.id),
                detail=json.dumps({
                    "old_start":old_start.isoformat() if old_start else None,
                    "old_end":old_end.isoformat() if old_end else None,
                    "new_start":start_at.isoformat(),"new_end":end_at.isoformat(),
                    "old_assignee":old_assignee,"new_assignee":new_assignee,
                    "outside_window":outside,"reason":reason.strip(),
                    "controlled_due":due.isoformat() if due else None,
                },sort_keys=True),workstation=workstation,
            ))
            self._queue_integration_event(s,"maintenance.pm.calendar_moved","PM_TASK",str(task.id),{
                "task_id":task.id,"equipment_id":task.equipment_id,"pm_id":task.pm_id,
                "scheduled_start_at":start_at.isoformat(),"scheduled_end_at":end_at.isoformat(),
                "assigned_to":new_assignee,"outside_window":outside,"reason":reason.strip(),
                "changed_by":user,
            })
            s.flush()
            return {
                "task_id":task.id,"start_at":start_at,"end_at":end_at,
                "assigned_to":new_assignee,"outside_window":outside,
                "early_date":early,"latest_date":latest,
            }

    def pm_task_readiness(self, task_id: int) -> dict[str, Any]:
        now=datetime.utcnow()
        with self.session() as s:
            task=s.get(PMTask,task_id)
            if not task:raise ValueError("PM task not found")
            reqs=list(s.scalars(select(PMRequirement).where(
                PMRequirement.pm_id==task.pm_id,
                PMRequirement.active.is_(True),
                PMRequirement.mandatory.is_(True),
            )))
            definition=s.scalar(select(PMDefinition).where(PMDefinition.pm_id==task.pm_id))
            reservations=list(s.scalars(select(InventoryReservation).where(
                InventoryReservation.pm_task_id==task.id,
                InventoryReservation.status=="Reserved",
            )))
            reserved_by_part={}
            for r in reservations:reserved_by_part[r.part_number]=reserved_by_part.get(r.part_number,0.0)+float(r.quantity or 0)
            part_requirements={}
            cert_codes=[]
            for req in reqs:
                if req.requirement_type=="PART" and req.requirement_key:
                    part_requirements[req.requirement_key]=part_requirements.get(req.requirement_key,0.0)+float(req.quantity or 0)
                elif req.requirement_type=="CERTIFICATION" and req.requirement_key:
                    cert_codes.append(req.requirement_key.strip())
            if definition and (definition.required_skill or "").strip():
                cert_codes.append(definition.required_skill.strip())
            cert_codes=list(dict.fromkeys(x for x in cert_codes if x))
            assigned=(task.assigned_to or "").strip()
            cert_rows=list(s.scalars(select(TechnicianCertification).where(
                TechnicianCertification.username==assigned,
                TechnicianCertification.active.is_(True),
            ))) if assigned else []
            valid_certs={x.cert_code for x in cert_rows if x.expires_at is None or x.expires_at>now}
        parts=[];shortages=[]
        for part,qty in sorted(part_requirements.items()):
            reserved=float(reserved_by_part.get(part,0.0))
            unreserved_available=float(self.inventory_available(part))
            total_covered=reserved+unreserved_available
            short=max(0.0,qty-total_covered)
            row={"part_number":part,"required":qty,"reserved":reserved,"available_unreserved":unreserved_available,"shortage":short,"ready":short<=0}
            parts.append(row)
            if short>0:shortages.append(row)
        missing_certs=[code for code in cert_codes if code not in valid_certs]
        return {
            "task_id":task_id,
            "equipment_id":task.equipment_id,
            "assigned_to":assigned,
            "parts":parts,
            "parts_status":"NONE" if not parts else ("READY" if not shortages else "SHORT"),
            "part_shortages":shortages,
            "required_certifications":cert_codes,
            "missing_certifications":missing_certs,
            "certification_status":"NONE" if not cert_codes else ("UNASSIGNED" if not assigned else ("READY" if not missing_certs else "MISSING")),
        }

    def reserve_pm_required_parts(self, task_id: int, user: str, workstation: str = "") -> list[InventoryReservation]:
        with self.session() as s:
            task_stmt=select(PMTask).where(PMTask.id==task_id)
            if self.url.startswith("postgresql"):task_stmt=task_stmt.with_for_update()
            task=s.scalar(task_stmt)
            if not task:raise ValueError("PM task not found")
            self.assert_authorized(user,"inventory.reserve",task.equipment_id)
            reqs=list(s.scalars(select(PMRequirement).where(
                PMRequirement.pm_id==task.pm_id,
                PMRequirement.active.is_(True),
                PMRequirement.mandatory.is_(True),
                PMRequirement.requirement_type=="PART",
            )))
            required={}
            for req in reqs:
                if req.requirement_key:required[req.requirement_key]=required.get(req.requirement_key,0.0)+float(req.quantity or 0)
            current=list(s.scalars(select(InventoryReservation).where(
                InventoryReservation.pm_task_id==task.id,
                InventoryReservation.status=="Reserved",
            )))
            reserved={}
            for row in current:reserved[row.part_number]=reserved.get(row.part_number,0.0)+float(row.quantity or 0)
            planned=[]
            shortages=[]
            for part,qty in required.items():
                need=max(0.0,qty-reserved.get(part,0.0))
                if need<=0:continue
                stock_stmt=select(InventoryItem).where(InventoryItem.part_number==part,InventoryItem.condition=="Available")
                if self.url.startswith("postgresql"):stock_stmt=stock_stmt.with_for_update()
                stock=list(s.scalars(stock_stmt))
                total=sum(float(x.quantity or 0) for x in stock)
                global_reserved=float(s.scalar(select(func.sum(InventoryReservation.quantity)).where(
                    InventoryReservation.part_number==part,
                    InventoryReservation.status=="Reserved",
                )) or 0.0)
                available=max(0.0,total-global_reserved)
                if available<need:
                    shortages.append(f"{part}: need {need:g}, available {available:g}")
                    continue
                location=stock[0].location_code if len(stock)==1 else ""
                planned.append((part,location,need))
            if shortages:raise ValueError("Required parts cannot be fully reserved: "+"; ".join(shortages))
            created=[]
            for part,location,qty in planned:
                row=InventoryReservation(
                    part_number=part,location_code=location,quantity=qty,pm_task_id=task.id,
                    equipment_id=task.equipment_id,status="Reserved",reserved_by=user,
                    note=f"PM {task.pm_id} required part",
                )
                s.add(row);created.append(row)
            if planned:
                s.add(AuditLog(
                    user=user,action="PM_PARTS_RESERVE",entity_type="PM_TASK",entity_key=str(task.id),
                    detail=json.dumps([{"part":p,"location":loc,"quantity":q} for p,loc,q in planned],sort_keys=True),
                    workstation=workstation,
                ))
            s.flush();return created

    def consume_pm_reserved_parts(self, execution_id: int, user: str, workstation: str = "") -> list[InventoryTransaction]:
        with self.session() as s:
            ex=s.get(PMExecution,execution_id)
            if not ex:raise ValueError("PM execution not found")
            task=s.get(PMTask,ex.task_id)
            if not task:raise ValueError("PM task not found")
            self.assert_authorized(user,"inventory.consume",task.equipment_id)
            reservations=list(s.scalars(select(InventoryReservation).where(
                InventoryReservation.pm_task_id==task.id,
                InventoryReservation.status=="Reserved",
            )))
            if not reservations:return []
            allocations=[]
            for reservation in reservations:
                remaining=float(reservation.quantity or 0)
                stmt=select(InventoryItem).where(
                    InventoryItem.part_number==reservation.part_number,
                    InventoryItem.condition=="Available",
                )
                if reservation.location_code:stmt=stmt.where(InventoryItem.location_code==reservation.location_code)
                if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
                items=list(s.scalars(stmt.order_by(InventoryItem.location_code)))
                available=sum(float(x.quantity or 0) for x in items)
                if available<remaining:
                    raise ValueError(f"Cannot consume reserved {reservation.part_number}: reserved {remaining:g}, physical available {available:g}.")
                for item in items:
                    if remaining<=0:break
                    take=min(float(item.quantity or 0),remaining)
                    if take<=0:continue
                    allocations.append((reservation,item,take))
                    remaining-=take
            created=[]
            for reservation,item,qty in allocations:
                item.quantity-=qty;item.version+=1
                tx=InventoryTransaction(
                    part_number=item.part_number,location_code=item.location_code,
                    transaction_type="Consume",quantity=-qty,equipment_id=task.equipment_id,
                    related_ticket="",user=user,note=f"PM task {task.id} / execution {execution_id}",
                )
                s.add(tx);created.append(tx)
            for reservation in reservations:
                reservation.status="Consumed";reservation.released_at=datetime.utcnow();reservation.version+=1
            s.add(AuditLog(
                user=user,action="PM_PARTS_CONSUME",entity_type="PM_EXECUTION",entity_key=str(execution_id),
                detail=json.dumps([{"part":x.part_number,"location":x.location_code,"quantity":-x.quantity} for x in created],sort_keys=True),
                workstation=workstation,
            ))
            s.flush();return created

    def pm_planning_rows(self, days: int = 60, include_overdue: bool = True) -> list[dict[str, Any]]:
        horizon=max(1,min(int(days),730))
        now=datetime.utcnow();end=now+timedelta(days=horizon)
        with self.session() as s:
            tasks=list(s.scalars(select(PMTask).where(PMTask.status.notin_(["Completed","Cancelled"])).order_by(PMTask.scheduled_date,PMTask.original_due_date,PMTask.priority)))
            definitions={x.pm_id:x for x in s.scalars(select(PMDefinition))}
            schedules={x.task_id:x for x in s.scalars(select(PMTaskSchedule))}
        rows=[]
        for task in tasks:
            due=task.original_due_date
            schedule=schedules.get(task.id)
            planned=(schedule.scheduled_start_at if schedule else None) or task.scheduled_date or due
            planned_end=(schedule.scheduled_end_at if schedule else None)
            if planned and planned>end and not (include_overdue and due and due<now):continue
            definition=definitions.get(task.pm_id)
            early=(due-timedelta(days=max(0,definition.early_window_days or 0))) if due and definition else due
            latest=(due+timedelta(days=max(0,definition.grace_days or 0))) if due and definition else due
            if due and now>latest if latest else False:window="OVERDUE"
            elif planned and early and planned<early:window="TOO EARLY"
            elif planned and latest and planned>latest and task.status!="Deferred":window="OUTSIDE GRACE"
            elif task.status=="Deferred":window="DEFERRED"
            else:window="IN WINDOW"
            readiness=self.pm_task_readiness(task.id)
            rows.append({
                "id":task.id,"equipment_id":task.equipment_id,"pm_id":task.pm_id,"pm_name":task.pm_name,
                "original_due_date":due,"scheduled_date":planned,"scheduled_start_at":planned,
                "scheduled_end_at":planned_end,"baseline_start_at":schedule.baseline_start_at if schedule else task.scheduled_date,
                "planned_hours":float(schedule.planned_hours if schedule else (task.estimated_hours or 0)),
                "status":task.status,"assigned_to":task.assigned_to,
                "estimated_hours":float(task.estimated_hours or 0),"priority":task.priority,"window":window,
                "parts_status":readiness["parts_status"],"certification_status":readiness["certification_status"],
                "part_shortages":", ".join(f"{x['part_number']}:{x['shortage']:g}" for x in readiness["part_shortages"]),
                "missing_certifications":", ".join(readiness["missing_certifications"]),
                "early_date":early,"latest_date":latest,"version":task.version,
            })
        return rows

    def request_pm_deferral(
        self,
        task_id: int,
        requested_due_date: datetime,
        reason: str,
        risk_assessment: str,
        mitigation: str,
        user: str,
        workstation: str = "",
        expected_task_version: int | None = None,
    ):
        if not reason.strip() or not risk_assessment.strip() or not mitigation.strip():
            raise ValueError("Deferral reason, risk assessment, and mitigation are all required.")
        with self.session() as s:
            stmt=select(PMTask).where(PMTask.id==task_id)
            if self.url.startswith("postgresql"):
                stmt=stmt.with_for_update()
            task=s.scalar(stmt)
            if not task:
                raise ValueError("PM task not found")
            self.assert_authorized(user,"pm.defer",task.equipment_id)
            if expected_task_version is not None and task.version!=expected_task_version:
                raise RuntimeError("CONFLICT: PM task changed by another user. Refresh and retry.")
            if task.status in {"Completed","Cancelled","In Progress"}:
                raise ValueError(f"PM task in state '{task.status}' cannot be deferred.")
            if not task.original_due_date:
                raise ValueError("PM task has no controlled original due date.")
            if requested_due_date <= task.original_due_date:
                raise ValueError("Requested deferred due date must be later than the original due date.")
            pending=s.scalar(select(PMDeferral).where(PMDeferral.task_id==task_id,PMDeferral.status=="Pending"))
            if pending:
                raise ValueError("A PM deferral request is already pending for this task.")
            row=PMDeferral(
                task_id=task.id,
                equipment_id=task.equipment_id,
                pm_id=task.pm_id,
                original_due_date=task.original_due_date,
                requested_due_date=requested_due_date,
                reason=reason.strip(),
                risk_assessment=risk_assessment.strip(),
                mitigation=mitigation.strip(),
                requested_by=user,
            )
            s.add(row)
            s.flush()
            s.add(AuditLog(
                user=user,
                action="PM_DEFERRAL_REQUEST",
                entity_type="PM_DEFERRAL",
                entity_key=str(row.id),
                detail=json.dumps({
                    "task_id":task.id,
                    "equipment_id":task.equipment_id,
                    "pm_id":task.pm_id,
                    "original_due_date":task.original_due_date.isoformat(),
                    "requested_due_date":requested_due_date.isoformat(),
                },sort_keys=True),
                workstation=workstation,
            ))
            return row

    def list_pm_deferrals(self, pending_only: bool = False):
        with self.session() as s:
            stmt=select(PMDeferral).order_by(PMDeferral.requested_at.desc())
            if pending_only:
                stmt=stmt.where(PMDeferral.status=="Pending")
            return list(s.scalars(stmt))

    def review_pm_deferral(
        self,
        deferral_id: int,
        approve: bool,
        user: str,
        review_note: str = "",
        workstation: str = "",
        expected_version: int | None = None,
    ):
        with self.session() as s:
            stmt=select(PMDeferral).where(PMDeferral.id==deferral_id)
            if self.url.startswith("postgresql"):
                stmt=stmt.with_for_update()
            row=s.scalar(stmt)
            if not row:
                raise ValueError("PM deferral request not found")
            if expected_version is not None and row.version!=expected_version:
                raise RuntimeError("CONFLICT: PM deferral changed by another user. Refresh and retry.")
            if row.status!="Pending":
                raise ValueError("PM deferral request has already been reviewed.")
            if row.requested_by==user:
                raise ValueError("Independent review required: requester cannot approve/reject their own PM deferral.")
            task_stmt=select(PMTask).where(PMTask.id==row.task_id)
            if self.url.startswith("postgresql"):
                task_stmt=task_stmt.with_for_update()
            task=s.scalar(task_stmt)
            if not task:
                raise ValueError("Related PM task no longer exists")
            now=datetime.utcnow()
            row.status="Approved" if approve else "Rejected"
            row.reviewed_by=user
            row.reviewed_at=now
            row.review_note=review_note.strip()
            row.version+=1
            if approve:
                task.scheduled_date=row.requested_due_date
                task.status="Deferred"
                task.deferral_reason=row.reason
                task.version+=1
            s.add(AuditLog(
                user=user,
                action="PM_DEFERRAL_APPROVE" if approve else "PM_DEFERRAL_REJECT",
                entity_type="PM_DEFERRAL",
                entity_key=str(row.id),
                detail=json.dumps({
                    "task_id":row.task_id,
                    "equipment_id":row.equipment_id,
                    "requested_by":row.requested_by,
                    "requested_due_date":row.requested_due_date.isoformat(),
                    "review_note":row.review_note,
                },sort_keys=True),
                workstation=workstation,
            ))
            s.flush()
            return row

    def save_technician_certification(self, data: dict[str, Any], expected_version: int | None = None):
        payload=dict(data)
        with self.session() as s:
            if not s.scalar(select(User).where(User.username==payload.get("username",""))):
                raise ValueError("Certification user not found.")
            row=s.scalar(select(TechnicianCertification).where(
                TechnicianCertification.username==payload["username"],
                TechnicianCertification.cert_code==payload["cert_code"],
            ))
            if row:self._update_versioned(row,payload,expected_version,"Technician certification")
            else:row=TechnicianCertification(**payload);s.add(row)
            s.flush();return row

    def list_technician_certifications(self, username: str = ""):
        with self.session() as s:
            stmt=select(TechnicianCertification).order_by(TechnicianCertification.username,TechnicianCertification.cert_code)
            if username:stmt=stmt.where(TechnicianCertification.username==username)
            return list(s.scalars(stmt))

    def upsert_pm_requirement(self, data: dict[str, Any], create_revision: bool = False):
        payload=dict(data)
        rtype=str(payload.get("requirement_type","")).upper()
        if rtype not in {"CERTIFICATION","LOTO","SAFETY","TOOL","PART","DOCUMENT"}:
            raise ValueError("PM requirement type must be CERTIFICATION, LOTO, SAFETY, TOOL, PART, or DOCUMENT.")
        payload["requirement_type"]=rtype
        with self.session() as s:
            current=s.scalar(select(PMRequirement).where(
                PMRequirement.requirement_id==payload["requirement_id"],
                PMRequirement.active.is_(True),
            ).order_by(PMRequirement.revision.desc()))
            if current and create_revision:
                current.active=False;current.version+=1
                payload["revision"]=current.revision+1
                row=PMRequirement(**payload);s.add(row)
            elif current:
                self._update_versioned(current,payload,None,"PM requirement");row=current
            else:
                payload.setdefault("revision",1);row=PMRequirement(**payload);s.add(row)
            s.flush();return row

    def list_pm_requirements(self, pm_id: str = "", active_only: bool = True):
        with self.session() as s:
            stmt=select(PMRequirement).order_by(PMRequirement.pm_id,PMRequirement.requirement_id,PMRequirement.revision.desc())
            if pm_id:stmt=stmt.where(PMRequirement.pm_id==pm_id)
            if active_only:stmt=stmt.where(PMRequirement.active.is_(True))
            return list(s.scalars(stmt))

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

    @staticmethod
    def _classify_pm_snapshot_value(spec, value_text: str, value_numeric: float | None) -> str:
        if spec.input_type == "Numeric":
            if value_numeric is None:
                return "INVALID"
            v = float(value_numeric)
            if (spec.spec_low is not None and v < spec.spec_low) or (spec.spec_high is not None and v > spec.spec_high):
                return "SPECIFICATION FAILURE"
            if (spec.control_low is not None and v < spec.control_low) or (spec.control_high is not None and v > spec.control_high):
                return "CONTROL FAILURE"
            if (spec.warning_low is not None and v < spec.warning_low) or (spec.warning_high is not None and v > spec.warning_high):
                return "WARNING"
            return "PASS"
        if spec.input_type == "Pass / Fail":
            normalized = (value_text or "").strip().lower()
            return "PASS" if normalized in {"pass", "ok", "yes", "good", "acceptable"} else "FAIL"
        return "RECORDED" if (value_text or "").strip() else "INVALID"

    @staticmethod
    def _snapshot_pm_requirements(s, ex: PMExecution, task: PMTask):
        existing=int(s.scalar(select(func.count()).select_from(PMExecutionRequirementSnapshot).where(
            PMExecutionRequirementSnapshot.execution_id==ex.id
        )) or 0)
        if existing:return
        reqs=list(s.scalars(select(PMRequirement).where(
            PMRequirement.pm_id==task.pm_id,PMRequirement.active.is_(True)
        ).order_by(PMRequirement.requirement_id)))
        for req in reqs:
            s.add(PMExecutionRequirementSnapshot(
                execution_id=ex.id,source_requirement_id=req.id,requirement_id=req.requirement_id,
                requirement_type=req.requirement_type,requirement_key=req.requirement_key,
                description=req.description,quantity=req.quantity,mandatory=req.mandatory,
                source_revision=req.revision,
            ))

    def _validate_pm_certifications(self, s, execution_id: int, username: str):
        now=datetime.utcnow()
        reqs=list(s.scalars(select(PMExecutionRequirementSnapshot).where(
            PMExecutionRequirementSnapshot.execution_id==execution_id,
            PMExecutionRequirementSnapshot.requirement_type=="CERTIFICATION",
            PMExecutionRequirementSnapshot.mandatory.is_(True),
        )))
        missing=[]
        for req in reqs:
            cert=s.scalar(select(TechnicianCertification).where(
                TechnicianCertification.username==username,
                TechnicianCertification.cert_code==req.requirement_key,
                TechnicianCertification.active.is_(True),
                ((TechnicianCertification.expires_at.is_(None)) | (TechnicianCertification.expires_at>now)),
            ))
            if not cert:missing.append(req.requirement_key or req.description)
        if missing:
            raise PermissionError("Required active certification(s) missing: "+", ".join(missing))

    def list_pm_execution_requirements(self, execution_id: int):
        with self.session() as s:
            return list(s.scalars(select(PMExecutionRequirementSnapshot).where(
                PMExecutionRequirementSnapshot.execution_id==execution_id
            ).order_by(PMExecutionRequirementSnapshot.requirement_type,PMExecutionRequirementSnapshot.requirement_id)))

    def acknowledge_pm_requirement(
        self,
        execution_id: int,
        requirement_id: str,
        user: str,
        note: str = "",
        evidence_path: str = "",
    ):
        with self.session() as s:
            ex=s.get(PMExecution,execution_id)
            if not ex:raise ValueError("PM execution not found")
            if ex.status=="Completed":raise ValueError("Completed PM execution is read-only.")
            req=s.scalar(select(PMExecutionRequirementSnapshot).where(
                PMExecutionRequirementSnapshot.execution_id==execution_id,
                PMExecutionRequirementSnapshot.requirement_id==requirement_id,
            ))
            if not req:raise ValueError("PM execution requirement not found")
            if req.requirement_type=="CERTIFICATION":
                raise ValueError("Certification requirements are validated automatically at execution start.")
            row=s.scalar(select(PMExecutionRequirementAck).where(
                PMExecutionRequirementAck.execution_id==execution_id,
                PMExecutionRequirementAck.requirement_id==requirement_id,
            ))
            if row:raise ValueError("Requirement is already acknowledged.")
            row=PMExecutionRequirementAck(
                execution_id=execution_id,requirement_id=requirement_id,acknowledged_by=user,
                note=note.strip(),evidence_path=evidence_path.strip(),
            )
            s.add(row);s.flush();return row

    def list_pm_requirement_acks(self, execution_id: int):
        with self.session() as s:
            return list(s.scalars(select(PMExecutionRequirementAck).where(
                PMExecutionRequirementAck.execution_id==execution_id
            ).order_by(PMExecutionRequirementAck.acknowledged_at)))

    @staticmethod
    def _snapshot_pm_specs(s, ex: PMExecution, task: PMTask):
        existing = int(s.scalar(
            select(func.count()).select_from(PMExecutionStepSnapshot)
            .where(PMExecutionStepSnapshot.execution_id == ex.id)
        ) or 0)
        if existing:
            return
        specs = list(s.scalars(
            select(PMSpec)
            .where(PMSpec.pm_id == task.pm_id, PMSpec.active.is_(True))
            .order_by(PMSpec.step_no)
        ))
        if not specs:
            raise ValueError("PM cannot start because no active controlled checklist/specification steps exist.")
        for spec in specs:
            s.add(PMExecutionStepSnapshot(
                execution_id=ex.id,
                pm_id=spec.pm_id,
                source_spec_id=spec.id,
                source_revision=spec.revision,
                step_no=spec.step_no,
                activity=spec.activity,
                method=spec.method,
                input_type=spec.input_type,
                unit=spec.unit,
                target=spec.target,
                warning_low=spec.warning_low,
                warning_high=spec.warning_high,
                control_low=spec.control_low,
                control_high=spec.control_high,
                spec_low=spec.spec_low,
                spec_high=spec.spec_high,
                acceptance_text=spec.acceptance_text,
                reaction_plan=spec.reaction_plan,
                sop_path=spec.sop_path,
                sop_page=spec.sop_page,
                sop_section=spec.sop_section,
                screenshot_required=bool(spec.screenshot_required),
                comment_required=bool(spec.comment_required),
            ))

    def get_pm_execution_for_task(self, task_id: int):
        with self.session() as s:
            return s.scalar(select(PMExecution).where(PMExecution.task_id==task_id))

    def start_pm_execution(self, task_id: int, user: str):
        with self.session() as s:
            task_stmt = select(PMTask).where(PMTask.id == task_id)
            if self.url.startswith("postgresql"):
                task_stmt = task_stmt.with_for_update()
            task = s.scalar(task_stmt)
            if not task:
                raise ValueError("PM task not found")
            self.assert_authorized(user,"pm.execute",task.equipment_id)
            ex = s.scalar(select(PMExecution).where(PMExecution.task_id == task_id))
            if ex:
                if ex.status=="Completed":
                    return ex
                self._snapshot_pm_specs(s, ex, task)
                self._snapshot_pm_requirements(s, ex, task)
                s.flush()
                self._validate_pm_certifications(s,ex.id,user)
                if ex.status=="Paused":
                    pause=s.scalar(select(PMExecutionPauseEvent).where(
                        PMExecutionPauseEvent.execution_id==ex.id,
                        PMExecutionPauseEvent.resumed_at.is_(None),
                    ).order_by(PMExecutionPauseEvent.paused_at.desc(),PMExecutionPauseEvent.id.desc()))
                    if pause:
                        pause.resumed_by=user;pause.resumed_at=datetime.utcnow()
                    ex.status="In Progress";ex.version+=1
                    task.status="In Progress";task.version+=1
                    s.add(AuditLog(
                        user=user,action="PM_EXECUTION_RESUME",entity_type="PM_EXECUTION",
                        entity_key=str(ex.id),detail=json.dumps({"task_id":task.id},sort_keys=True),
                        workstation="PM-RUNNER",
                    ))
                    self._queue_integration_event(s,"maintenance.pm.resumed","PM_EXECUTION",str(ex.id),{
                        "execution_id":ex.id,"task_id":task.id,"equipment_id":task.equipment_id,
                        "pm_id":task.pm_id,"resumed_by":user,
                    })
                    s.flush()
                return ex
            ex = PMExecution(task_id=task_id, started_by=user)
            s.add(ex)
            s.flush()
            self._snapshot_pm_specs(s, ex, task)
            self._snapshot_pm_requirements(s, ex, task)
            s.flush()
            self._validate_pm_certifications(s,ex.id,user)
            task.status = "In Progress"
            task.version += 1
            s.flush()
            return ex

    def pause_pm_execution(
        self,
        execution_id: int,
        user: str,
        reason: str,
        note: str = "",
        workstation: str = "",
    ):
        allowed={
            "Production Request","Waiting Parts","Waiting Engineer","Waiting Vendor",
            "Tool Unavailable","Shift End","Safety Hold","Other",
        }
        reason=(reason or "").strip()
        if reason not in allowed:raise ValueError("Select a valid PM pause / carry-over reason.")
        with self.session() as s:
            stmt=select(PMExecution).where(PMExecution.id==execution_id)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            ex=s.scalar(stmt)
            if not ex:raise ValueError("PM execution not found")
            task=s.get(PMTask,ex.task_id)
            if not task:raise ValueError("PM task not found")
            self.assert_authorized(user,"pm.execute",task.equipment_id)
            if ex.status=="Completed":raise ValueError("Completed PM execution cannot be paused.")
            if ex.status=="Paused":return ex
            ex.status="Paused";ex.version+=1
            # Task remains operationally in progress; execution status carries
            # the interruption so PM compliance is not misrepresented.
            task.status="In Progress";task.version+=1
            s.add(PMExecutionPauseEvent(
                execution_id=ex.id,reason=reason,note=(note or "").strip(),
                paused_by=user,paused_at=datetime.utcnow(),
            ))
            s.add(AuditLog(
                user=user,action="PM_EXECUTION_PAUSE",entity_type="PM_EXECUTION",
                entity_key=str(ex.id),
                detail=json.dumps({"task_id":task.id,"reason":reason,"note":(note or "").strip()},sort_keys=True),
                workstation=workstation,
            ))
            self._queue_integration_event(s,"maintenance.pm.paused","PM_EXECUTION",str(ex.id),{
                "execution_id":ex.id,"task_id":task.id,"equipment_id":task.equipment_id,
                "pm_id":task.pm_id,"reason":reason,"note":(note or "").strip(),"paused_by":user,
            })
            s.flush();return ex

    def list_pm_execution_pauses(self, execution_id: int):
        with self.session() as s:
            return list(s.scalars(
                select(PMExecutionPauseEvent)
                .where(PMExecutionPauseEvent.execution_id==execution_id)
                .order_by(PMExecutionPauseEvent.paused_at.desc(),PMExecutionPauseEvent.id.desc())
            ))

    def list_pm_execution_specs(self, execution_id: int):
        with self.session() as s:
            return list(s.scalars(
                select(PMExecutionStepSnapshot)
                .where(PMExecutionStepSnapshot.execution_id == execution_id)
                .order_by(PMExecutionStepSnapshot.step_no)
            ))

    def save_pm_result(self, execution_id: int, step_no: int, data: dict[str, Any], expected_version: int | None = None):
        with self.session() as s:
            ex = s.get(PMExecution, execution_id)
            if not ex:
                raise ValueError("PM execution not found")
            if ex.status == "Completed":
                raise ValueError("Completed PM execution is read-only.")
            spec = s.scalar(select(PMExecutionStepSnapshot).where(
                PMExecutionStepSnapshot.execution_id == execution_id,
                PMExecutionStepSnapshot.step_no == step_no,
            ))
            if not spec:
                raise ValueError("PM step is not part of the frozen execution checklist.")
            item = s.scalar(select(PMResult).where(PMResult.execution_id == execution_id, PMResult.step_no == step_no))
            payload = dict(data)
            payload.update(execution_id=execution_id, step_no=step_no)
            payload["result"] = self._classify_pm_snapshot_value(
                spec,
                payload.get("value_text", ""),
                payload.get("value_numeric"),
            )
            if item:
                self._update_versioned(item, payload, expected_version, "PM result")
            else:
                item = PMResult(**payload)
                s.add(item)
            s.flush()
            if item.result in {"SPECIFICATION FAILURE","CONTROL FAILURE","FAIL","INVALID"}:
                task=s.get(PMTask,ex.task_id)
                if task:
                    self._apply_workflow_automation_in_session(s,"PM_ABNORMAL_RESULT",{
                        "entity_type":"PM_RESULT","entity_key":f"{execution_id}:{step_no}",
                        "equipment_id":task.equipment_id,"pm_task_id":task.id,"pm_id":task.pm_id,
                        "step_no":step_no,"result":item.result,
                        "summary":f"{task.pm_id} step {step_no} — {item.result}",
                        "detail":f"{spec.activity}; value={item.value_text or item.value_numeric}; reaction={spec.reaction_plan}",
                    })
            s.flush()
            return item

    def pm_step_history(
        self,
        equipment_id: str,
        pm_id: str,
        step_no: int,
        limit: int = 12,
        exclude_execution_id: int | None = None,
    ) -> list[dict[str, Any]]:
        with self.session() as s:
            tasks=list(s.scalars(select(PMTask).where(
                PMTask.equipment_id==equipment_id,
                PMTask.pm_id==pm_id,
            )))
            if not tasks:return []
            task_by_id={x.id:x for x in tasks}
            executions=list(s.scalars(select(PMExecution).where(
                PMExecution.task_id.in_(list(task_by_id))
            )))
            execution_by_id={x.id:x for x in executions if exclude_execution_id is None or x.id!=exclude_execution_id}
            if not execution_by_id:return []
            results=list(s.scalars(select(PMResult).where(
                PMResult.execution_id.in_(list(execution_by_id)),
                PMResult.step_no==int(step_no),
            ).order_by(PMResult.entered_at.desc(),PMResult.id.desc()).limit(max(1,min(int(limit),200)))))
            rows=[]
            for result in results:
                execution=execution_by_id.get(result.execution_id)
                if not execution:continue
                task=task_by_id.get(execution.task_id)
                rows.append({
                    "entered_at":result.entered_at,
                    "result":result.result,
                    "value_text":result.value_text,
                    "value_numeric":result.value_numeric,
                    "comment":result.comment,
                    "entered_by":result.entered_by,
                    "task_id":task.id if task else None,
                    "execution_id":execution.id,
                    "scheduled_date":task.scheduled_date if task else None,
                    "completed_at":execution.completed_at,
                })
            return rows

    def list_pm_results(self, execution_id: int):
        with self.session() as s:
            return list(s.scalars(
                select(PMResult)
                .where(PMResult.execution_id == execution_id)
                .order_by(PMResult.step_no)
            ))

    def complete_pm_execution(self, execution_id: int, user: str):
        with self.session() as s:
            ex_stmt = select(PMExecution).where(PMExecution.id == execution_id)
            if self.url.startswith("postgresql"):
                ex_stmt = ex_stmt.with_for_update()
            ex = s.scalar(ex_stmt)
            if not ex:
                raise ValueError("Execution not found")
            if ex.status == "Completed":
                return ex
            task = s.get(PMTask, ex.task_id)
            specs = list(s.scalars(
                select(PMExecutionStepSnapshot)
                .where(PMExecutionStepSnapshot.execution_id == execution_id)
                .order_by(PMExecutionStepSnapshot.step_no)
            ))
            if not specs:
                raise ValueError("PM execution has no frozen controlled checklist.")
            results = list(s.scalars(select(PMResult).where(PMResult.execution_id == execution_id)))
            by_step = {r.step_no: r for r in results}
            missing = [p.step_no for p in specs if p.step_no not in by_step]
            if missing:
                raise ValueError(f"Missing required PM steps: {missing}")
            hard_fail = [
                step_no for step_no, result in by_step.items()
                if result.result in {"SPECIFICATION FAILURE", "CONTROL FAILURE", "FAIL", "INVALID"}
            ]
            if hard_fail:
                raise ValueError(
                    f"Failed/invalid PM steps require correction, disposition, or engineering review: {hard_fail}"
                )
            missing_screenshot=[
                p.step_no for p in specs
                if p.screenshot_required and not (by_step[p.step_no].evidence_path or "").strip()
            ]
            if missing_screenshot:
                raise ValueError(f"Screenshot evidence required for PM step(s): {missing_screenshot}")
            missing_comment=[
                p.step_no for p in specs
                if p.comment_required and not (by_step[p.step_no].comment or "").strip()
            ]
            if missing_comment:
                raise ValueError(f"Comment required for PM step(s): {missing_comment}")
            requirements=list(s.scalars(select(PMExecutionRequirementSnapshot).where(
                PMExecutionRequirementSnapshot.execution_id==execution_id,
                PMExecutionRequirementSnapshot.mandatory.is_(True),
                PMExecutionRequirementSnapshot.requirement_type!="CERTIFICATION",
            )))
            acked={x.requirement_id for x in s.scalars(select(PMExecutionRequirementAck).where(
                PMExecutionRequirementAck.execution_id==execution_id
            ))}
            missing_req=[x.requirement_id for x in requirements if x.requirement_id not in acked]
            if missing_req:
                raise ValueError(f"Mandatory PM execution requirements not acknowledged: {missing_req}")
            now = datetime.utcnow()
            active_pause=s.scalar(select(PMExecutionPauseEvent).where(
                PMExecutionPauseEvent.execution_id==execution_id,
                PMExecutionPauseEvent.resumed_at.is_(None),
            ).order_by(PMExecutionPauseEvent.paused_at.desc(),PMExecutionPauseEvent.id.desc()))
            if active_pause:
                active_pause.resumed_by=user;active_pause.resumed_at=now
            ex.status = "Completed"
            ex.completed_by = user
            ex.completed_at = now
            ex.version += 1
            task.status = "Completed"
            task.last_completion_date = now
            task.version += 1
            self._queue_integration_event(s,"maintenance.pm.completed","PM_TASK",str(task.id),{
                "task_id":task.id,"equipment_id":task.equipment_id,"pm_id":task.pm_id,
                "completed_by":user,"completed_at":now.isoformat(),
            })
            s.flush()
            return ex

    def list_tickets(self, equipment_id: str = ""):
        with self.session() as s:
            stmt=select(Ticket)
            if equipment_id:stmt=stmt.where(Ticket.equipment_id==equipment_id)
            return list(s.scalars(stmt.order_by(Ticket.created_at.desc())))

    def save_ticket(
        self,
        data: dict[str, Any],
        expected_version: int | None = None,
        workstation: str = "",
    ):
        payload = dict(data)
        equipment_id=str(payload.get("equipment_id","")).strip()
        context={"priority":str(payload.get("priority","")).strip(),"severity":str(payload.get("severity","")).strip()}
        if not str(payload.get("owner","")).strip() and equipment_id:
            owner=self.resolve_default_owner("TICKET",equipment_id,context)
            if owner:payload["owner"]=owner
        sla=self.resolve_sla_policy(equipment_id,context) if equipment_id else {}
        with self.session() as s:
            ticket_no=str(payload.get("ticket_no","")).strip()
            if not ticket_no:
                ticket_no=self._next_configured_number_in_session(s,"TICKET",equipment_id,context)
                payload["ticket_no"]=ticket_no
            item = s.scalar(select(Ticket).where(Ticket.ticket_no == ticket_no))
            if item:
                # Lifecycle state is controlled by transition_ticket_state(), not generic editing.
                payload.pop("status", None)
                payload.pop("created_by", None)
                payload.pop("created_at", None)
                self._update_versioned(item, payload, expected_version, "Ticket")
            else:
                payload["status"] = "Open"
                if payload["status"] not in TICKET_STATES:
                    raise ValueError(f"Unknown ticket state: {payload['status']}")
                now=datetime.utcnow()
                item = Ticket(**payload)
                s.add(item)
                s.add(TicketStateEvent(
                    ticket_no=ticket_no,
                    from_state="",
                    to_state="Open",
                    reason_code="INITIAL_STATE",
                    note="Issue ticket created",
                    owner=payload.get("owner", ""),
                    changed_by=payload.get("created_by", ""),
                    workstation=workstation,
                    changed_at=now,
                ))
                if sla:
                    s.add(TicketOperationalControl(
                        ticket_no=ticket_no,
                        response_due_at=now+timedelta(minutes=sla["response_minutes"]) if sla.get("response_minutes") else None,
                        containment_due_at=now+timedelta(minutes=sla["containment_minutes"]) if sla.get("containment_minutes") else None,
                        resolution_due_at=now+timedelta(minutes=sla["resolution_minutes"]) if sla.get("resolution_minutes") else None,
                    ))
            s.flush()
            return item

    def list_incident_whys(self, ticket_no: str):
        with self.session() as s:
            return list(s.scalars(select(IncidentWhy).where(IncidentWhy.ticket_no==ticket_no).order_by(IncidentWhy.sequence)))

    def save_incident_why(
        self,
        ticket_no: str,
        sequence: int,
        question: str,
        answer: str,
        user: str,
        expected_version: int | None = None,
        workstation: str = "",
    ):
        if sequence<1 or sequence>10:raise ValueError("Why sequence must be between 1 and 10.")
        if not answer.strip():raise ValueError("Why analysis answer is required.")
        with self.session() as s:
            ticket=s.scalar(select(Ticket).where(Ticket.ticket_no==ticket_no))
            if not ticket:raise ValueError("Ticket not found")
            self.assert_authorized(user,"ticket.edit",ticket.equipment_id)
            row=s.scalar(select(IncidentWhy).where(IncidentWhy.ticket_no==ticket_no,IncidentWhy.sequence==sequence))
            if row:
                if expected_version is not None and row.version!=expected_version:raise RuntimeError("CONFLICT: Why analysis changed by another user.")
                row.question=question.strip();row.answer=answer.strip();row.updated_by=user;row.updated_at=datetime.utcnow();row.version+=1
            else:
                row=IncidentWhy(ticket_no=ticket_no,sequence=sequence,question=question.strip(),answer=answer.strip(),updated_by=user);s.add(row)
            s.add(AuditLog(user=user,action="INCIDENT_WHY_UPDATE",entity_type="TICKET",entity_key=ticket_no,detail=json.dumps({"sequence":sequence,"answer":answer.strip()},sort_keys=True),workstation=workstation))
            s.flush();return row

    def list_incident_causal_factors(self, ticket_no: str):
        with self.session() as s:
            return list(s.scalars(select(IncidentCausalFactor).where(IncidentCausalFactor.ticket_no==ticket_no).order_by(IncidentCausalFactor.id)))

    def save_incident_causal_factor(
        self,
        ticket_no: str,
        data: dict[str, Any],
        user: str,
        factor_id: int | None = None,
        expected_version: int | None = None,
        workstation: str = "",
    ):
        categories={"Man","Machine","Method","Material","Measurement","Environment","Software","Process","Other"}
        factor_types={"Suspected","Contributing","Verified Root Cause","Ruled Out"}
        category=str(data.get("category","Other")).strip() or "Other"
        factor_type=str(data.get("factor_type","Suspected")).strip() or "Suspected"
        description=str(data.get("description","")).strip()
        if category not in categories:raise ValueError("Unsupported causal-factor category.")
        if factor_type not in factor_types:raise ValueError("Unsupported causal-factor type.")
        if not description:raise ValueError("Causal-factor description is required.")
        with self.session() as s:
            ticket=s.scalar(select(Ticket).where(Ticket.ticket_no==ticket_no))
            if not ticket:raise ValueError("Ticket not found")
            self.assert_authorized(user,"ticket.edit",ticket.equipment_id)
            row=s.get(IncidentCausalFactor,factor_id) if factor_id else None
            if row:
                if row.ticket_no!=ticket_no:raise ValueError("Causal factor does not belong to this incident.")
                if expected_version is not None and row.version!=expected_version:raise RuntimeError("CONFLICT: Causal factor changed by another user.")
                row.category=category;row.factor_type=factor_type;row.description=description
                row.evidence=str(data.get("evidence","")).strip();row.status=str(data.get("status","Open")).strip() or "Open";row.version+=1
            else:
                row=IncidentCausalFactor(ticket_no=ticket_no,category=category,factor_type=factor_type,description=description,evidence=str(data.get("evidence","")).strip(),status=str(data.get("status","Open")).strip() or "Open",created_by=user);s.add(row)
            s.add(AuditLog(user=user,action="INCIDENT_CAUSAL_FACTOR",entity_type="TICKET",entity_key=ticket_no,detail=json.dumps({"category":category,"factor_type":factor_type,"description":description},sort_keys=True),workstation=workstation))
            s.flush();return row

    def list_incident_actions(self, ticket_no: str):
        with self.session() as s:
            return list(s.scalars(select(IncidentAction).where(IncidentAction.ticket_no==ticket_no).order_by(IncidentAction.status,IncidentAction.due_at,IncidentAction.id)))

    def save_incident_action(
        self,
        ticket_no: str,
        data: dict[str, Any],
        user: str,
        action_id: int | None = None,
        expected_version: int | None = None,
        workstation: str = "",
    ):
        action_type=str(data.get("action_type","Corrective")).strip()
        if action_type not in {"Containment","Corrective","Preventive","Follow-up"}:raise ValueError("Unsupported incident action type.")
        description=str(data.get("description","")).strip()
        if not description:raise ValueError("Action description is required.")
        with self.session() as s:
            ticket=s.scalar(select(Ticket).where(Ticket.ticket_no==ticket_no))
            if not ticket:raise ValueError("Ticket not found")
            self.assert_authorized(user,"ticket.edit",ticket.equipment_id)
            row=s.get(IncidentAction,action_id) if action_id else None
            if row:
                if row.ticket_no!=ticket_no:raise ValueError("Action does not belong to this incident.")
                if expected_version is not None and row.version!=expected_version:raise RuntimeError("CONFLICT: Incident action changed by another user.")
                if row.status in {"Completed","Verified"}:raise ValueError("Completed/verified actions cannot be edited.")
                row.action_type=action_type;row.description=description;row.owner=str(data.get("owner","")).strip()
                row.due_at=data.get("due_at");row.effectiveness_criteria=str(data.get("effectiveness_criteria","")).strip();row.version+=1
            else:
                row=IncidentAction(ticket_no=ticket_no,action_type=action_type,description=description,owner=str(data.get("owner","")).strip(),due_at=data.get("due_at"),effectiveness_criteria=str(data.get("effectiveness_criteria","")).strip());s.add(row)
            s.add(AuditLog(user=user,action="INCIDENT_ACTION_SAVE",entity_type="TICKET",entity_key=ticket_no,detail=description,workstation=workstation))
            s.flush();return row

    def complete_incident_action(self, action_id: int, user: str, note: str, expected_version: int | None = None, workstation: str = ""):
        if not note.strip():raise ValueError("Completion note is required.")
        with self.session() as s:
            stmt=select(IncidentAction).where(IncidentAction.id==action_id)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            row=s.scalar(stmt)
            if not row:raise ValueError("Incident action not found")
            ticket=s.scalar(select(Ticket).where(Ticket.ticket_no==row.ticket_no))
            self.assert_authorized(user,"ticket.edit",ticket.equipment_id if ticket else "")
            if expected_version is not None and row.version!=expected_version:raise RuntimeError("CONFLICT: Incident action changed by another user.")
            if row.status=="Verified":return row
            row.status="Completed";row.completion_note=note.strip();row.completed_by=user;row.completed_at=datetime.utcnow();row.version+=1
            s.add(AuditLog(user=user,action="INCIDENT_ACTION_COMPLETE",entity_type="TICKET",entity_key=row.ticket_no,detail=json.dumps({"action_id":row.id,"note":note.strip()}),workstation=workstation))
            s.flush();return row

    def verify_incident_action(self, action_id: int, user: str, note: str, expected_version: int | None = None, workstation: str = ""):
        if not note.strip():raise ValueError("Effectiveness verification note is required.")
        with self.session() as s:
            stmt=select(IncidentAction).where(IncidentAction.id==action_id)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            row=s.scalar(stmt)
            if not row:raise ValueError("Incident action not found")
            ticket=s.scalar(select(Ticket).where(Ticket.ticket_no==row.ticket_no))
            self.assert_authorized(user,"ticket.edit",ticket.equipment_id if ticket else "")
            if expected_version is not None and row.version!=expected_version:raise RuntimeError("CONFLICT: Incident action changed by another user.")
            if row.status!="Completed":raise ValueError("Action must be completed before effectiveness verification.")
            if row.completed_by==user:raise ValueError("Independent verification required: action completer cannot verify effectiveness.")
            row.status="Verified";row.verification_note=note.strip();row.verified_by=user;row.verified_at=datetime.utcnow();row.version+=1
            s.add(AuditLog(user=user,action="INCIDENT_ACTION_VERIFY",entity_type="TICKET",entity_key=row.ticket_no,detail=json.dumps({"action_id":row.id,"note":note.strip()}),workstation=workstation))
            s.flush();return row

    def search_troubleshooting_cases(
        self,
        query: str = "",
        equipment_id: str = "",
        limit: int = 200,
    ) -> list[dict[str,Any]]:
        """Search closed and open troubleshooting knowledge across tickets, checks, alarms and lots."""
        q=(query or "").strip();like=f"%{q}%";max_rows=max(1,min(int(limit),500))
        with self.session() as s:
            ticket_nos=set()
            if q:
                for value in s.scalars(select(Ticket.ticket_no).where(or_(
                    Ticket.ticket_no.ilike(like),Ticket.title.ilike(like),Ticket.description.ilike(like),
                    Ticket.root_cause.ilike(like),Ticket.corrective_action.ilike(like),
                    Ticket.equipment_id.ilike(like),
                )).limit(max_rows*2)):ticket_nos.add(value)
                for value in s.scalars(select(TicketInvestigation.ticket_no).where(or_(
                    TicketInvestigation.observation.ilike(like),TicketInvestigation.check_performed.ilike(like),
                    TicketInvestigation.result.ilike(like),TicketInvestigation.conclusion.ilike(like),
                    TicketInvestigation.action.ilike(like),
                )).limit(max_rows*2)):ticket_nos.add(value)
                for value in s.scalars(select(EquipmentAlarmEvent.related_ticket).where(
                    EquipmentAlarmEvent.related_ticket!="",
                    or_(EquipmentAlarmEvent.alarm_code.ilike(like),EquipmentAlarmEvent.message.ilike(like)),
                ).limit(max_rows*2)):
                    if value:ticket_nos.add(value)
                for value in s.scalars(select(EntityLotLink.entity_key).where(
                    EntityLotLink.entity_type=="TICKET",EntityLotLink.lot_number.ilike(like)
                ).limit(max_rows*2)):ticket_nos.add(value)
                stmt=select(Ticket).where(Ticket.ticket_no.in_(ticket_nos)) if ticket_nos else select(Ticket).where(False)
            else:
                stmt=select(Ticket)
            if equipment_id.strip():stmt=stmt.where(Ticket.equipment_id==equipment_id.strip())
            tickets=list(s.scalars(stmt.order_by(Ticket.updated_at.desc(),Ticket.created_at.desc()).limit(max_rows)))
            if not tickets:return []
            nos=[x.ticket_no for x in tickets]
            investigations=list(s.scalars(select(TicketInvestigation).where(
                TicketInvestigation.ticket_no.in_(nos)
            ).order_by(TicketInvestigation.ticket_no,TicketInvestigation.sequence.desc(),TicketInvestigation.entered_at.desc())))
            alarms=list(s.scalars(select(EquipmentAlarmEvent).where(
                EquipmentAlarmEvent.related_ticket.in_(nos)
            ).order_by(EquipmentAlarmEvent.occurred_at.desc())))
            lots=list(s.scalars(select(EntityLotLink).where(
                EntityLotLink.entity_type=="TICKET",EntityLotLink.entity_key.in_(nos)
            )))
            attachments=list(s.scalars(select(EntityAttachment).where(
                EntityAttachment.entity_type=="TICKET",EntityAttachment.entity_key.in_(nos),
                EntityAttachment.active.is_(True),
            )))
        latest_inv={};alarms_by={};lots_by={};images={}
        for x in investigations:
            if x.ticket_no not in latest_inv:latest_inv[x.ticket_no]=x
        for x in alarms:
            if x.alarm_code:
                arr=alarms_by.setdefault(x.related_ticket,[])
                if x.alarm_code not in arr:arr.append(x.alarm_code)
        for x in lots:
            arr=lots_by.setdefault(x.entity_key,[])
            if x.lot_number not in arr:arr.append(x.lot_number)
        for x in attachments:
            if (x.category or "").lower() in {"screenshot","photo"} or (x.media_type or "").lower().startswith("image/"):
                images[x.entity_key]=images.get(x.entity_key,0)+1
        rows=[]
        for t in tickets:
            inv=latest_inv.get(t.ticket_no)
            rows.append({
                "ticket_no":t.ticket_no,"equipment_id":t.equipment_id,"created_at":t.created_at,
                "updated_at":t.updated_at,"priority":t.priority,"status":t.status,"owner":t.owner,
                "title":t.title,"description":t.description,
                "lots":", ".join(lots_by.get(t.ticket_no,[])),
                "alarms":", ".join(alarms_by.get(t.ticket_no,[])[:8]),
                "last_observation":inv.observation if inv else "",
                "last_check":inv.check_performed if inv else "",
                "last_result":inv.result if inv else "",
                "last_conclusion":inv.conclusion if inv else "",
                "last_action":inv.action if inv else "",
                "root_cause":t.root_cause,"corrective_action":t.corrective_action,
                "screenshot_count":images.get(t.ticket_no,0),
            })
        return rows

    def incident_similar_history(self, ticket_no: str, limit: int = 50):
        """Rank prior troubleshooting cases and return technician-useful resolution detail."""
        stop={"the","and","for","with","from","this","that","tool","issue","problem","error","alarm","equipment"}
        def tokens(value):
            return {
                x for x in re.findall(r"[a-z0-9_-]{3,}",(value or "").lower())
                if x not in stop
            }
        with self.session() as s:
            current=s.scalar(select(Ticket).where(Ticket.ticket_no==ticket_no))
            if not current:return []
            candidates=list(s.scalars(
                select(Ticket).where(Ticket.ticket_no!=ticket_no)
                .order_by(Ticket.created_at.desc()).limit(600)
            ))
            ticket_nos=[current.ticket_no]+[x.ticket_no for x in candidates]
            lot_rows=list(s.scalars(select(EntityLotLink).where(
                EntityLotLink.entity_type=="TICKET",EntityLotLink.entity_key.in_(ticket_nos)
            )))
            alarm_rows=list(s.scalars(select(EquipmentAlarmEvent).where(
                EquipmentAlarmEvent.related_ticket.in_(ticket_nos)
            )))
            investigation_rows=list(s.scalars(select(TicketInvestigation).where(
                TicketInvestigation.ticket_no.in_(ticket_nos)
            ).order_by(TicketInvestigation.ticket_no,TicketInvestigation.sequence.desc(),TicketInvestigation.entered_at.desc())))
            attachment_rows=list(s.scalars(select(EntityAttachment).where(
                EntityAttachment.entity_type=="TICKET",
                EntityAttachment.entity_key.in_(ticket_nos),
                EntityAttachment.active.is_(True),
            )))

        lots_by_ticket={};alarms_by_ticket={};investigation_by_ticket={};image_count={}
        for x in lot_rows:lots_by_ticket.setdefault(x.entity_key,set()).add(x.lot_number.upper())
        for x in alarm_rows:
            if x.alarm_code:alarms_by_ticket.setdefault(x.related_ticket,set()).add(x.alarm_code.upper())
        for x in investigation_rows:
            if x.ticket_no not in investigation_by_ticket:investigation_by_ticket[x.ticket_no]=x
        for x in attachment_rows:
            is_image=(x.category or "").lower() in {"screenshot","photo"} or (x.media_type or "").lower().startswith("image/")
            if is_image:image_count[x.entity_key]=image_count.get(x.entity_key,0)+1

        current_lots=lots_by_ticket.get(current.ticket_no,set())
        current_alarms=alarms_by_ticket.get(current.ticket_no,set())
        current_tokens=tokens(" ".join([current.title or "",current.description or "",current.root_cause or ""]))
        rows=[]
        for row in candidates:
            row_lots=lots_by_ticket.get(row.ticket_no,set())
            row_alarms=alarms_by_ticket.get(row.ticket_no,set())
            investigation=investigation_by_ticket.get(row.ticket_no)
            investigation_text=""
            if investigation:
                investigation_text=" ".join([
                    investigation.observation or "",investigation.check_performed or "",
                    investigation.result or "",investigation.conclusion or "",investigation.action or "",
                ])
            overlap=current_tokens & tokens(" ".join([
                row.title or "",row.description or "",row.root_cause or "",
                row.corrective_action or "",investigation_text,
            ]))
            score=0;reasons=[]
            if row.equipment_id==current.equipment_id:
                score+=8;reasons.append("same tool")
            shared_lots=current_lots & row_lots
            if shared_lots:
                score+=6+min(3,len(shared_lots));reasons.append("same lot")
            shared_alarms=current_alarms & row_alarms
            if shared_alarms:
                score+=6+min(3,len(shared_alarms));reasons.append("same alarm")
            if overlap:
                score+=min(6,len(overlap)*2);reasons.append("similar symptom")
            if score<=0:continue
            rows.append({
                "ticket_no":row.ticket_no,"equipment_id":row.equipment_id,
                "title":row.title,"priority":row.priority,"status":row.status,"owner":row.owner,
                "lots":", ".join(sorted(row_lots)),"alarms":", ".join(sorted(row_alarms)),
                "last_observation":investigation.observation if investigation else "",
                "last_check":investigation.check_performed if investigation else "",
                "last_result":investigation.result if investigation else "",
                "last_conclusion":investigation.conclusion if investigation else "",
                "last_action":investigation.action if investigation else "",
                "root_cause":row.root_cause,"corrective_action":row.corrective_action,
                "screenshot_count":image_count.get(row.ticket_no,0),
                "score":score,"match_reason":", ".join(reasons),
                "created_at":row.created_at,"updated_at":row.updated_at,
            })
        rows.sort(key=lambda x:(-x["score"],-(x["updated_at"] or x["created_at"]).timestamp()))
        return rows[:max(1,min(int(limit),200))]

    def ticket_operational_control(self, ticket_no: str):
        with self.session() as s:
            return s.scalar(select(TicketOperationalControl).where(TicketOperationalControl.ticket_no==ticket_no))

    def save_ticket_operational_control(
        self,
        ticket_no: str,
        data: dict[str, Any],
        user: str,
        workstation: str = "",
        expected_version: int | None = None,
    ):
        with self.session() as s:
            ticket=s.scalar(select(Ticket).where(Ticket.ticket_no==ticket_no))
            if not ticket:raise ValueError("Ticket not found")
            self.assert_authorized(user,"ticket.edit",ticket.equipment_id)
            row=s.scalar(select(TicketOperationalControl).where(TicketOperationalControl.ticket_no==ticket_no))
            payload=dict(data)
            if row:
                self._update_versioned(row,payload,expected_version,"Ticket operational control")
            else:
                row=TicketOperationalControl(ticket_no=ticket_no,**payload);s.add(row)
            s.add(AuditLog(
                user=user,action="TICKET_OPERATIONAL_CONTROL",entity_type="TICKET",
                entity_key=ticket_no,detail=json.dumps(payload,default=str,sort_keys=True),
                workstation=workstation,
            ))
            s.flush();return row

    @staticmethod
    def _normalize_lot_numbers(values: Any) -> list[str]:
        if values is None:
            return []
        if isinstance(values,str):
            raw=re.split(r"[\n,;\t]+",values)
        else:
            raw=list(values)
        out=[]
        seen=set()
        for value in raw:
            lot=str(value or "").strip()
            if not lot:
                continue
            key=lot.upper()
            if key in seen:
                continue
            seen.add(key);out.append(lot)
        return out

    def list_entity_lots(self, entity_type: str, entity_key: str):
        with self.session() as s:
            return list(s.scalars(
                select(EntityLotLink)
                .where(
                    EntityLotLink.entity_type==(entity_type or "").upper(),
                    EntityLotLink.entity_key==str(entity_key),
                )
                .order_by(EntityLotLink.created_at,EntityLotLink.id)
            ))

    def replace_entity_lots(
        self,
        entity_type: str,
        entity_key: str,
        lot_numbers: Any,
        *,
        equipment_id: str = "",
        user: str = "",
        workstation: str = "",
    ):
        entity_type=(entity_type or "").upper().strip()
        entity_key=str(entity_key or "").strip()
        if not entity_type or not entity_key:
            raise ValueError("Entity type and key are required for lot context.")
        lots=self._normalize_lot_numbers(lot_numbers)
        with self.session() as s:
            existing=list(s.scalars(select(EntityLotLink).where(
                EntityLotLink.entity_type==entity_type,
                EntityLotLink.entity_key==entity_key,
            )))
            by_upper={x.lot_number.upper():x for x in existing}
            wanted={x.upper() for x in lots}
            for row in existing:
                if row.lot_number.upper() not in wanted:
                    s.delete(row)
            for lot in lots:
                if lot.upper() not in by_upper:
                    s.add(EntityLotLink(
                        entity_type=entity_type,entity_key=entity_key,
                        equipment_id=equipment_id.strip(),lot_number=lot,
                        created_by=user,
                    ))
            s.add(AuditLog(
                user=user or "system",action="LOT_CONTEXT_REPLACE",
                entity_type=entity_type,entity_key=entity_key,
                detail=json.dumps({"lots":lots,"equipment_id":equipment_id},sort_keys=True),
                workstation=workstation,
            ))
            s.flush()
        return self.list_entity_lots(entity_type,entity_key)

    def find_lot_history(self, lot_number: str, limit: int = 100):
        query=(lot_number or "").strip()
        if not query:
            return []
        with self.session() as s:
            stmt=(
                select(EntityLotLink)
                .where(func.lower(EntityLotLink.lot_number).contains(query.lower()))
                .order_by(EntityLotLink.created_at.desc(),EntityLotLink.id.desc())
                .limit(max(1,min(int(limit),500)))
            )
            return list(s.scalars(stmt))

    def create_manual_issue(
        self,
        data: dict[str, Any],
        user: str,
        workstation: str = "",
    ):
        equipment_id=str(data.get("equipment_id","")).strip()
        title=str(data.get("title","")).strip()
        if not equipment_id:
            raise ValueError("Equipment is required.")
        if not title:
            raise ValueError("Problem / symptom is required.")
        self.assert_authorized(user,"ticket.edit",equipment_id)
        impact=str(data.get("impact","Observation")).strip() or "Observation"
        impact_defaults={
            "Production Stop":("P1","S1"),
            "Degraded":("P2","S2"),
            "Observation":("P3","S3"),
        }
        default_priority,default_severity=impact_defaults.get(impact,("P3","S3"))
        priority=str(data.get("priority","")).strip() or default_priority
        severity=str(data.get("severity","")).strip() or default_severity
        context={"priority":priority,"severity":severity}
        owner=str(data.get("owner","")).strip() or self.resolve_default_owner("TICKET",equipment_id,context)
        sla=self.resolve_sla_policy(equipment_id,context)
        lots=self._normalize_lot_numbers(data.get("lot_numbers",[]))
        description=str(data.get("description","")).strip()
        alarm_code=str(data.get("alarm_code","")).strip()
        now=datetime.utcnow()
        with self.session() as s:
            if not s.scalar(select(Equipment).where(Equipment.equipment_id==equipment_id)):
                raise ValueError("Equipment not found")
            ticket_no=self._next_configured_number_in_session(s,"TICKET",equipment_id,context)
            ticket=Ticket(
                ticket_no=ticket_no,equipment_id=equipment_id,title=title,
                description=description,severity=severity,priority=priority,
                status="Open",owner=owner,root_cause="",corrective_action="",
                verification="",created_by=user,created_at=now,updated_at=now,
            )
            s.add(ticket);s.flush()
            s.add(TicketStateEvent(
                ticket_no=ticket_no,from_state="",to_state="Open",
                reason_code="MANUAL_REPORT",note=f"Manual issue reported; impact={impact}",
                owner=owner,changed_by=user,workstation=workstation,changed_at=now,
            ))
            s.add(TicketOperationalControl(
                ticket_no=ticket_no,
                production_impact=impact,
                affected_lots="; ".join(lots),
                response_due_at=now+timedelta(minutes=sla["response_minutes"]) if sla.get("response_minutes") else None,
                containment_due_at=now+timedelta(minutes=sla["containment_minutes"]) if sla.get("containment_minutes") else None,
                resolution_due_at=now+timedelta(minutes=sla["resolution_minutes"]) if sla.get("resolution_minutes") else None,
            ))
            for lot in lots:
                s.add(EntityLotLink(
                    entity_type="TICKET",entity_key=ticket_no,equipment_id=equipment_id,
                    lot_number=lot,created_by=user,created_at=now,
                ))
            alarm=None
            if alarm_code:
                alarm_severity=str(data.get("alarm_severity","")).strip() or (
                    "Critical" if impact=="Production Stop" else "Warning"
                )
                event_key=secrets.token_hex(20)
                alarm=EquipmentAlarmEvent(
                    event_key=event_key,equipment_id=equipment_id,alarm_code=alarm_code,
                    severity=alarm_severity,message=title,source="Manual Issue",
                    state="ACTIVE",occurred_at=now,related_ticket=ticket_no,
                    raw_payload_json=json.dumps({"manual_issue":True,"impact":impact,"lots":lots},sort_keys=True),
                )
                s.add(alarm)
                self._queue_integration_event(s,"equipment.alarm.active","ALARM",event_key,{
                    "equipment_id":equipment_id,"alarm_code":alarm_code,
                    "severity":alarm_severity,"message":title,"source":"Manual Issue",
                    "state":"ACTIVE","occurred_at":now.isoformat(),"related_ticket":ticket_no,
                })
                self._apply_workflow_automation_in_session(s,"ALARM_ACTIVE",{
                    "entity_type":"ALARM","entity_key":event_key,"equipment_id":equipment_id,
                    "alarm_code":alarm_code,"severity":alarm_severity,"message":title,
                    "source":"Manual Issue","ticket_no":ticket_no,
                    "summary":f"{alarm_code} — {title}","detail":description,
                })
            s.add(AuditLog(
                user=user,action="MANUAL_ISSUE_CREATE",entity_type="TICKET",
                entity_key=ticket_no,
                detail=json.dumps({
                    "equipment_id":equipment_id,"impact":impact,"lots":lots,
                    "alarm_code":alarm_code,
                },sort_keys=True),
                workstation=workstation,
            ))
            self._queue_integration_event(s,"incident.created","TICKET",ticket_no,{
                "ticket_no":ticket_no,"equipment_id":equipment_id,"title":title,
                "priority":priority,"severity":severity,"owner":owner,
                "created_by":user,"impact":impact,"lots":lots,
            })
            s.flush()
            return ticket,alarm

    def evaluate_ticket_escalations(self, now: datetime | None = None):
        now=now or datetime.utcnow()
        escalated=[]
        with self.session() as s:
            controls=list(s.scalars(select(TicketOperationalControl)))
            for control in controls:
                ticket=s.scalar(select(Ticket).where(Ticket.ticket_no==control.ticket_no))
                if not ticket or ticket.status in {"Closed","Cancelled"}:continue
                reasons=[]
                target=control.escalation_level
                if control.response_due_at and now>control.response_due_at and ticket.status=="Open":
                    target=max(target,1);reasons.append("Response SLA overdue")
                if control.containment_due_at and now>control.containment_due_at and not control.containment.strip():
                    target=max(target,2);reasons.append("Containment overdue")
                if control.resolution_due_at and now>control.resolution_due_at:
                    target=max(target,3);reasons.append("Resolution SLA overdue")
                if ticket.priority=="P1":
                    target=max(target,2);reasons.append("P1 critical incident")
                if target>control.escalation_level:
                    old=control.escalation_level
                    control.escalation_level=target
                    control.escalated_at=now
                    control.escalation_reason="; ".join(dict.fromkeys(reasons))
                    control.version+=1
                    s.add(TicketEscalationEvent(
                        ticket_no=ticket.ticket_no,from_level=old,to_level=target,
                        reason=control.escalation_reason,user="system",occurred_at=now,
                    ))
                    if ticket.owner:
                        self._add_notification_in_session(
                            s,ticket.owner,"INCIDENT_ESCALATION",
                            f"{ticket.ticket_no} escalated to L{target}",
                            f"{ticket.title}\n{control.escalation_reason}",
                            "CRITICAL" if target>=3 or ticket.priority=="P1" else "HIGH",
                            "TICKET",ticket.ticket_no,ticket.equipment_id,
                            f"incident-escalation:{ticket.ticket_no}:L{target}",
                        )
                    escalated.append(ticket.ticket_no)
            s.flush()
        return escalated

    def list_ticket_escalations(self, ticket_no: str = ""):
        with self.session() as s:
            stmt=select(TicketEscalationEvent).order_by(TicketEscalationEvent.occurred_at.desc())
            if ticket_no:stmt=stmt.where(TicketEscalationEvent.ticket_no==ticket_no)
            return list(s.scalars(stmt))

    def operations_attention_queue(self, limit: int = 200):
        self.evaluate_ticket_escalations()
        now=datetime.utcnow()
        rows=[]
        with self.session() as s:
            for alarm in s.scalars(select(EquipmentAlarmEvent).where(EquipmentAlarmEvent.state=="ACTIVE")):
                sev=(alarm.severity or "").upper()
                rows.append({"severity":"CRITICAL" if sev in {"CRITICAL","FATAL","S1"} else "HIGH","kind":"ALARM","key":alarm.event_key,"equipment_id":alarm.equipment_id,"summary":f"{alarm.alarm_code} — {alarm.message}","owner":alarm.acknowledged_by,"age_hours":(now-alarm.occurred_at).total_seconds()/3600})
            for eq in s.scalars(select(Equipment).where(Equipment.status.in_(["Down","Engineering","Waiting Parts","Waiting Vendor","Qualification","Hold"]))):
                rows.append({"severity":"CRITICAL" if eq.status=="Down" else "HIGH","kind":"EQUIPMENT","key":eq.equipment_id,"equipment_id":eq.equipment_id,"summary":f"{eq.status} — {eq.name}","owner":eq.owner,"age_hours":0.0})
            for task in s.scalars(select(PMTask).where(PMTask.status.in_(["Overdue","Deferred","Pending","Scheduled"]))):
                if task.status=="Overdue" or (task.scheduled_date and task.scheduled_date<now):
                    due=task.scheduled_date or task.original_due_date
                    age=(now-due).total_seconds()/3600 if due else 0
                    rows.append({"severity":"HIGH","kind":"PM","key":str(task.id),"equipment_id":task.equipment_id,"summary":f"{task.pm_id} {task.status}","owner":task.assigned_to,"age_hours":age})
            for ticket in s.scalars(select(Ticket).where(Ticket.status.notin_(["Closed","Cancelled"]))):
                control=s.scalar(select(TicketOperationalControl).where(TicketOperationalControl.ticket_no==ticket.ticket_no))
                level=control.escalation_level if control else 0
                if ticket.priority in {"P1","P2"} or level>0:
                    age=(now-ticket.created_at).total_seconds()/3600 if ticket.created_at else 0
                    rows.append({"severity":"CRITICAL" if ticket.priority=="P1" or level>=3 else "HIGH","kind":"INCIDENT","key":ticket.ticket_no,"equipment_id":ticket.equipment_id,"summary":f"{ticket.priority} {ticket.status} — {ticket.title}"+(f" [Esc L{level}]" if level else ""),"owner":ticket.owner,"age_hours":age})
            for q in s.scalars(select(QualificationRun).where(QualificationRun.status.in_(["Submitted","Verified"]))):
                rows.append({"severity":"MEDIUM","kind":"QUALIFICATION","key":q.run_no,"equipment_id":q.equipment_id,"summary":f"{q.status} — {q.protocol_name}","owner":q.verified_by or q.submitted_by,"age_hours":(now-q.started_at).total_seconds()/3600})
            for rel in s.scalars(select(EquipmentRelease).where(EquipmentRelease.status.in_(["Pending Verification","Verified","Verification Failed"]))):
                rows.append({"severity":"HIGH" if rel.status=="Verification Failed" else "MEDIUM","kind":"RELEASE","key":str(rel.id),"equipment_id":rel.equipment_id,"summary":rel.status,"owner":rel.verified_by or rel.requested_by,"age_hours":(now-rel.requested_at).total_seconds()/3600})
            for e in s.scalars(select(Endorsement).where(Endorsement.status.in_(["Open","Acknowledged"]))):
                rows.append({"severity":"MEDIUM","kind":"HANDOVER","key":e.endorsement_no,"equipment_id":e.equipment_id,"summary":e.next_action or e.pending_work or "Open handover","owner":e.next_owner,"age_hours":(now-e.created_at).total_seconds()/3600})
        rank={"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3}
        rows.sort(key=lambda x:(rank.get(x["severity"],9),-float(x.get("age_hours") or 0)))
        return rows[:max(1,min(int(limit),1000))]

    def list_ticket_state_events(self, ticket_no: str, limit: int = 250):
        with self.session() as s:
            stmt = (
                select(TicketStateEvent)
                .where(TicketStateEvent.ticket_no == ticket_no)
                .order_by(TicketStateEvent.changed_at.desc(), TicketStateEvent.id.desc())
                .limit(max(1, min(int(limit), 2000)))
            )
            return list(s.scalars(stmt))

    def transition_ticket_state(
        self,
        ticket_no: str,
        target_state: str,
        *,
        reason_code: str,
        note: str = "",
        owner: str = "",
        user: str,
        workstation: str = "",
        expected_version: int | None = None,
        override: bool = False,
        override_reason: str = "",
    ):
        if override and not override_reason.strip():
            raise ValueError("Workflow override requires explicit justification.")
        with self.session() as s:
            stmt = select(Ticket).where(Ticket.ticket_no == ticket_no)
            if self.url.startswith("postgresql"):
                stmt = stmt.with_for_update()
            item = s.scalar(stmt)
            if not item:
                raise ValueError("Ticket not found")
            self.assert_authorized(user,"ticket.edit",item.equipment_id)
            if override:self.assert_authorized(user,"workflow.override",item.equipment_id)
            if expected_version is not None and item.version != expected_version:
                raise RuntimeError("CONFLICT: Ticket changed by another user. Refresh and retry.")

            effective_owner = (owner or item.owner or "").strip()
            validate_ticket_transition(
                item.status,
                target_state,
                reason_code=reason_code,
                owner=effective_owner,
                note=note,
                override=override,
            )
            if target_state in {"Resolved", "Verification", "Closed"}:
                if not (item.root_cause or "").strip():
                    raise ValueError("Root cause must be documented before resolution/verification.")
                if not (item.corrective_action or "").strip():
                    raise ValueError("Corrective action must be documented before resolution/verification.")

            if target_state == "Verification":
                resolver = s.scalar(
                    select(TicketStateEvent)
                    .where(TicketStateEvent.ticket_no == ticket_no, TicketStateEvent.to_state == "Resolved")
                    .order_by(TicketStateEvent.changed_at.desc(), TicketStateEvent.id.desc())
                )
                if resolver and resolver.changed_by == user:
                    raise ValueError(
                        "Independent verification required: the resolver cannot verify their own corrective action."
                    )

            if target_state == "Closed":
                if not (item.verification or "").strip():
                    raise ValueError("Verification evidence/result must be documented before closure.")
                verifier = s.scalar(
                    select(TicketStateEvent)
                    .where(TicketStateEvent.ticket_no == ticket_no, TicketStateEvent.to_state == "Verification")
                    .order_by(TicketStateEvent.changed_at.desc(), TicketStateEvent.id.desc())
                )
                if not verifier:
                    raise ValueError("A verification lifecycle event is required before closure.")
                if verifier.changed_by != user:
                    raise ValueError(
                        "The engineer who performed independent verification must perform the closure transition."
                    )

            now = datetime.utcnow()
            previous = item.status
            item.status = target_state
            if effective_owner:
                item.owner = effective_owner
            item.updated_at = now
            item.version += 1
            event = TicketStateEvent(
                ticket_no=ticket_no,
                from_state=previous,
                to_state=target_state,
                reason_code=reason_code,
                note=note.strip(),
                owner=item.owner,
                changed_by=user,
                workstation=workstation,
                changed_at=now,
            )
            s.add(event)
            self._queue_integration_event(s,"incident.state.changed","TICKET",ticket_no,{
                "ticket_no":ticket_no,"equipment_id":item.equipment_id,"from_state":previous,
                "to_state":target_state,"reason_code":reason_code,"owner":item.owner,
                "changed_by":user,"changed_at":now.isoformat(),
            })
            if target_state in {"Resolved","Closed"}:
                linked_manual=list(s.scalars(select(EquipmentAlarmEvent).where(
                    EquipmentAlarmEvent.related_ticket==ticket_no,
                    EquipmentAlarmEvent.state=="ACTIVE",
                    EquipmentAlarmEvent.source=="Manual Issue",
                )))
                for alarm in linked_manual:
                    alarm.state="CLEARED";alarm.cleared_at=now
                    self._queue_integration_event(s,"equipment.alarm.cleared","ALARM",alarm.event_key,{
                        "equipment_id":alarm.equipment_id,"alarm_code":alarm.alarm_code,
                        "severity":alarm.severity,"message":alarm.message,"source":"Manual Issue",
                        "cleared_at":now.isoformat(),"related_ticket":ticket_no,
                        "cleared_by":user,
                    })
            s.add(AuditLog(
                user=user,
                action="TICKET_STATE_OVERRIDE" if override else "TICKET_STATE_TRANSITION",
                entity_type="TICKET",
                entity_key=ticket_no,
                detail=json.dumps({
                    "from": previous,
                    "to": target_state,
                    "reason_code": reason_code,
                    "note": note.strip(),
                    "owner": item.owner,
                    "override": override,
                    "override_reason": override_reason.strip(),
                }, sort_keys=True),
                workstation=workstation,
                created_at=now,
            ))
            s.flush()
            return item, event

    def add_ticket_investigation(self, ticket_no: str, data: dict[str, Any]):
        with self.session() as s:
            seq = (s.scalar(select(func.max(TicketInvestigation.sequence)).where(TicketInvestigation.ticket_no == ticket_no)) or 0) + 1
            item=TicketInvestigation(ticket_no=ticket_no,sequence=seq,**data); s.add(item); s.flush(); return item

    def list_ticket_investigations(self, ticket_no: str):
        with self.session() as s:
            return list(s.scalars(select(TicketInvestigation).where(TicketInvestigation.ticket_no==ticket_no).order_by(TicketInvestigation.sequence)))

    def set_disposition(self, data: dict[str, Any]):
        self.assert_authorized(str(data.get("created_by","")),"disposition.edit",str(data.get("equipment_id","")))
        with self.session() as s:
            stmt = select(Equipment).where(Equipment.equipment_id == data["equipment_id"])
            if not self.url.startswith("sqlite"): stmt = stmt.with_for_update()
            eq = s.scalar(stmt)
            if not eq: raise ValueError("Equipment not found")
            for d in s.scalars(select(Disposition).where(Disposition.equipment_id==data["equipment_id"],Disposition.active.is_(True))): d.active=False
            d=Disposition(**data); s.add(d); eq.disposition=d.state; eq.version += 1; s.flush(); return d

    def list_dispositions(self, active_only: bool = False, equipment_id: str = ""):
        with self.session() as s:
            stmt=select(Disposition)
            if active_only:stmt=stmt.where(Disposition.active.is_(True))
            if equipment_id:stmt=stmt.where(Disposition.equipment_id==equipment_id)
            return list(s.scalars(stmt.order_by(Disposition.effective_at.desc())))

    @staticmethod
    def _normalize_qualification_checks(checks: list[Any]) -> list[dict[str, Any]]:
        normalized=[]
        seen=set()
        for idx,item in enumerate(checks or [],start=1):
            if isinstance(item,str):
                check_id=f"Q{idx:02d}"
                label=item.strip()
                acceptance="Pass"
            elif isinstance(item,dict):
                check_id=str(item.get("check_id") or f"Q{idx:02d}").strip()
                label=str(item.get("label") or item.get("name") or "").strip()
                acceptance=str(item.get("acceptance") or "Pass").strip()
            else:
                raise ValueError("Qualification checks must be strings or objects.")
            if not check_id or not label:
                raise ValueError("Every qualification check needs an ID and label.")
            if check_id in seen:
                raise ValueError(f"Duplicate qualification check ID: {check_id}")
            seen.add(check_id)
            normalized.append({"check_id":check_id,"label":label,"acceptance":acceptance})
        if not normalized:
            raise ValueError("Qualification protocol requires at least one check.")
        return normalized

    def save_qualification_protocol(
        self,
        protocol_id: str,
        name: str,
        checks: list[Any],
        user: str,
        equipment_id: str = "",
        equipment_type: str = "",
        create_revision: bool = False,
        workstation: str = "",
    ):
        protocol_id=protocol_id.strip()
        name=name.strip()
        if not protocol_id or not name:
            raise ValueError("Protocol ID and name are required.")
        normalized=self._normalize_qualification_checks(checks)
        with self.session() as s:
            if equipment_id and not s.scalar(select(Equipment).where(Equipment.equipment_id==equipment_id)):
                raise ValueError("Qualification protocol equipment not found.")
            current=s.scalar(
                select(QualificationProtocol)
                .where(QualificationProtocol.protocol_id==protocol_id,QualificationProtocol.active.is_(True))
                .order_by(QualificationProtocol.revision.desc())
            )
            if current and not create_revision:
                raise ValueError("Active protocol exists. Create a controlled revision instead.")
            revision=1
            if current:
                current.active=False
                current.version+=1
                revision=current.revision+1
            row=QualificationProtocol(
                protocol_id=protocol_id,revision=revision,name=name,equipment_id=equipment_id.strip(),
                equipment_type=equipment_type.strip(),checks_json=json.dumps(normalized,sort_keys=True),
                active=True,created_by=user,
            )
            s.add(row)
            s.add(AuditLog(
                user=user,action="QUALIFICATION_PROTOCOL_REVISION",entity_type="QUALIFICATION_PROTOCOL",
                entity_key=f"{protocol_id}:R{revision}",
                detail=json.dumps({"equipment_id":equipment_id,"equipment_type":equipment_type,"checks":len(normalized)},sort_keys=True),
                workstation=workstation,
            ))
            s.flush()
            return row

    def list_qualification_protocols(self, active_only: bool = True):
        with self.session() as s:
            stmt=select(QualificationProtocol).order_by(QualificationProtocol.protocol_id,QualificationProtocol.revision.desc())
            if active_only:
                stmt=stmt.where(QualificationProtocol.active.is_(True))
            return list(s.scalars(stmt))

    def start_qualification_run(
        self,
        equipment_id: str,
        protocol_id: str,
        user: str,
        run_no: str = "",
        workstation: str = "",
    ):
        self.assert_authorized(user,"qualification.execute",equipment_id)
        with self.session() as s:
            eq=s.scalar(select(Equipment).where(Equipment.equipment_id==equipment_id))
            if not eq:
                raise ValueError("Equipment not found")
            protocol=s.scalar(
                select(QualificationProtocol)
                .where(QualificationProtocol.protocol_id==protocol_id,QualificationProtocol.active.is_(True))
                .order_by(QualificationProtocol.revision.desc())
            )
            if not protocol:
                raise ValueError("Active qualification protocol not found")
            if protocol.equipment_id and protocol.equipment_id!=equipment_id:
                raise ValueError("Protocol is controlled for another equipment.")
            if protocol.equipment_type and protocol.equipment_type!=eq.equipment_type:
                raise ValueError("Protocol equipment type does not match this equipment.")
            existing=s.scalar(select(QualificationRun).where(
                QualificationRun.equipment_id==equipment_id,
                QualificationRun.status.in_(["In Progress","Submitted","Verified"]),
            ))
            if existing:
                raise ValueError(f"Open qualification run already exists: {existing.run_no}")
            run_no=run_no.strip() or self._next_configured_number_in_session(
                s,"QUALIFICATION",equipment_id,{"protocol_id":protocol.protocol_id,"equipment_type":eq.equipment_type},
            )
            row=QualificationRun(
                run_no=run_no,equipment_id=equipment_id,protocol_id=protocol.protocol_id,
                protocol_revision=protocol.revision,protocol_name=protocol.name,
                frozen_checks_json=protocol.checks_json,results_json="{}",
                status="In Progress",started_by=user,
            )
            s.add(row);s.flush()
            s.add(QualificationEvent(run_no=row.run_no,action="START",user=user,detail=f"{protocol.protocol_id} R{protocol.revision}",workstation=workstation))
            return row

    def list_qualification_runs(self, equipment_id: str = ""):
        with self.session() as s:
            stmt=select(QualificationRun).order_by(QualificationRun.started_at.desc())
            if equipment_id:
                stmt=stmt.where(QualificationRun.equipment_id==equipment_id)
            return list(s.scalars(stmt))

    def qualification_run_checks(self, run_id: int) -> tuple[list[dict[str,Any]],dict[str,Any]]:
        with self.session() as s:
            row=s.get(QualificationRun,run_id)
            if not row:
                raise ValueError("Qualification run not found")
            return json.loads(row.frozen_checks_json or "[]"),json.loads(row.results_json or "{}")

    def save_qualification_result(
        self,
        run_id: int,
        check_id: str,
        result: str,
        comment: str,
        user: str,
        evidence_path: str = "",
        workstation: str = "",
        expected_version: int | None = None,
    ):
        result=result.strip().upper()
        if result not in {"PASS","FAIL","NA"}:
            raise ValueError("Qualification result must be PASS, FAIL, or NA.")
        with self.session() as s:
            stmt=select(QualificationRun).where(QualificationRun.id==run_id)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            row=s.scalar(stmt)
            if not row:raise ValueError("Qualification run not found")
            if expected_version is not None and row.version!=expected_version:
                raise RuntimeError("CONFLICT: Qualification run changed by another user.")
            if row.status!="In Progress":
                raise ValueError("Only In Progress qualification runs can be edited.")
            checks=json.loads(row.frozen_checks_json or "[]")
            valid_ids={str(x["check_id"]) for x in checks}
            if check_id not in valid_ids:
                raise ValueError("Check is not part of the frozen qualification protocol.")
            results=json.loads(row.results_json or "{}")
            results[check_id]={"result":result,"comment":comment.strip(),"evidence_path":evidence_path.strip(),"entered_by":user,"entered_at":datetime.utcnow().isoformat()}
            row.results_json=json.dumps(results,sort_keys=True)
            row.version+=1
            s.add(QualificationEvent(run_no=row.run_no,action="RESULT",user=user,detail=json.dumps({"check_id":check_id,"result":result},sort_keys=True),workstation=workstation))
            s.flush();return row

    def submit_qualification_run(
        self,
        run_id: int,
        user: str,
        conclusion: str = "",
        workstation: str = "",
        expected_version: int | None = None,
    ):
        with self.session() as s:
            stmt=select(QualificationRun).where(QualificationRun.id==run_id)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            row=s.scalar(stmt)
            if not row:raise ValueError("Qualification run not found")
            if expected_version is not None and row.version!=expected_version:raise RuntimeError("CONFLICT: Qualification run changed by another user.")
            if row.status!="In Progress":raise ValueError("Qualification run is not In Progress.")
            checks=json.loads(row.frozen_checks_json or "[]")
            results=json.loads(row.results_json or "{}")
            missing=[x["check_id"] for x in checks if x["check_id"] not in results]
            if missing:raise ValueError(f"Missing qualification results: {missing}")
            failed=[cid for cid,r in results.items() if r.get("result")=="FAIL"]
            if failed:raise ValueError(f"Qualification contains failed checks: {failed}")
            now=datetime.utcnow()
            row.status="Submitted";row.submitted_by=user;row.submitted_at=now;row.conclusion=conclusion.strip();row.version+=1
            s.add(QualificationEvent(run_no=row.run_no,action="SUBMIT",user=user,detail=row.conclusion,workstation=workstation,occurred_at=now))
            s.flush();return row

    def verify_qualification_run(
        self,
        run_id: int,
        user: str,
        note: str = "",
        workstation: str = "",
        expected_version: int | None = None,
    ):
        with self.session() as s:
            stmt=select(QualificationRun).where(QualificationRun.id==run_id)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            row=s.scalar(stmt)
            if not row:raise ValueError("Qualification run not found")
            if expected_version is not None and row.version!=expected_version:raise RuntimeError("CONFLICT: Qualification run changed by another user.")
            if row.status!="Submitted":raise ValueError("Only Submitted qualification runs can be verified.")
            if user in {row.started_by,row.submitted_by}:raise ValueError("Independent verification required.")
            now=datetime.utcnow();row.status="Verified";row.verified_by=user;row.verified_at=now;row.version+=1
            s.add(QualificationEvent(run_no=row.run_no,action="VERIFY",user=user,detail=note.strip(),workstation=workstation,occurred_at=now))
            s.flush();return row

    def approve_qualification_run(
        self,
        run_id: int,
        user: str,
        valid_days: int | None = None,
        note: str = "",
        workstation: str = "",
        expected_version: int | None = None,
    ):
        with self.session() as s:
            stmt=select(QualificationRun).where(QualificationRun.id==run_id)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            row=s.scalar(stmt)
            if not row:raise ValueError("Qualification run not found")
            if expected_version is not None and row.version!=expected_version:raise RuntimeError("CONFLICT: Qualification run changed by another user.")
            if row.status!="Verified":raise ValueError("Only Verified qualification runs can be approved.")
            if user in {row.started_by,row.submitted_by,row.verified_by}:raise ValueError("Independent final approval required.")
            now=datetime.utcnow();row.status="Approved";row.approved_by=user;row.approved_at=now;row.expires_at=(now+timedelta(days=int(valid_days))) if valid_days else None;row.version+=1
            s.add(QualificationEvent(run_no=row.run_no,action="APPROVE",user=user,detail=note.strip(),workstation=workstation,occurred_at=now))
            self._queue_integration_event(s,"qualification.approved","QUALIFICATION_RUN",row.run_no,{
                "run_no":row.run_no,"equipment_id":row.equipment_id,"protocol_id":row.protocol_id,
                "protocol_revision":row.protocol_revision,"approved_by":user,
                "approved_at":now.isoformat(),"expires_at":row.expires_at.isoformat() if row.expires_at else None,
            })
            self._apply_workflow_automation_in_session(s,"QUALIFICATION_APPROVED",{
                "entity_type":"QUALIFICATION","entity_key":row.run_no,"equipment_id":row.equipment_id,
                "protocol_id":row.protocol_id,"protocol_revision":row.protocol_revision,
                "approved_by":user,"summary":f"Qualification approved — {row.protocol_name}",
                "detail":note.strip(),
            })
            s.add(AuditLog(
                user=user,action="QUALIFICATION_APPROVE",entity_type="QUALIFICATION_RUN",entity_key=row.run_no,
                detail=json.dumps({"equipment_id":row.equipment_id,"protocol_id":row.protocol_id,"protocol_revision":row.protocol_revision,"expires_at":row.expires_at.isoformat() if row.expires_at else None},sort_keys=True),
                workstation=workstation,created_at=now,
            ))
            s.flush();return row

    def reject_qualification_run(
        self,
        run_id: int,
        user: str,
        reason: str,
        workstation: str = "",
        expected_version: int | None = None,
    ):
        if not reason.strip():raise ValueError("Rejection reason is required.")
        with self.session() as s:
            row=s.get(QualificationRun,run_id)
            if not row:raise ValueError("Qualification run not found")
            if expected_version is not None and row.version!=expected_version:raise RuntimeError("CONFLICT: Qualification run changed by another user.")
            if row.status not in {"Submitted","Verified"}:raise ValueError("Only Submitted or Verified runs can be rejected.")
            if user==row.started_by:raise ValueError("Independent rejection review required.")
            row.status="Rejected";row.conclusion=(row.conclusion+"\nREJECTED: "+reason.strip()).strip();row.version+=1
            s.add(QualificationEvent(run_no=row.run_no,action="REJECT",user=user,detail=reason.strip(),workstation=workstation))
            s.flush();return row

    def latest_valid_qualification(self, equipment_id: str):
        now=datetime.utcnow()
        with self.session() as s:
            return s.scalar(
                select(QualificationRun)
                .where(
                    QualificationRun.equipment_id==equipment_id,
                    QualificationRun.status=="Approved",
                    ((QualificationRun.expires_at.is_(None)) | (QualificationRun.expires_at>now)),
                )
                .order_by(QualificationRun.approved_at.desc(),QualificationRun.id.desc())
            )

    def release_precheck(self, equipment_id: str) -> dict[str, Any]:
        with self.session() as s:
            critical = int(s.scalar(select(func.count()).select_from(Ticket).where(Ticket.equipment_id==equipment_id,Ticket.priority.in_(["P1","P2"]),Ticket.status.notin_(["Closed","Cancelled"]))) or 0)
            overdue = int(s.scalar(select(func.count()).select_from(PMTask).where(PMTask.equipment_id==equipment_id,PMTask.status=="Overdue")) or 0)
            eq=s.scalar(select(Equipment).where(Equipment.equipment_id==equipment_id))
            qualification_required=bool(eq and (eq.status=="Qualification" or eq.disposition=="Qualification"))
            valid_qualification=None
            if qualification_required:
                now=datetime.utcnow()
                valid_qualification=s.scalar(
                    select(QualificationRun)
                    .where(
                        QualificationRun.equipment_id==equipment_id,
                        QualificationRun.status=="Approved",
                        ((QualificationRun.expires_at.is_(None)) | (QualificationRun.expires_at>now)),
                    )
                    .order_by(QualificationRun.approved_at.desc(),QualificationRun.id.desc())
                )
            return {
                "critical_tickets_open":critical,
                "overdue_pm":overdue,
                "qualification_required":qualification_required,
                "qualification_valid":bool(valid_qualification),
                "qualification_run_no":valid_qualification.run_no if valid_qualification else "",
            }

    def create_release_request(
        self,
        equipment_id: str,
        related_ticket: str,
        checks: dict[str, bool],
        notes: str,
        user: str,
        workstation: str = "",
    ):
        self.assert_authorized(user,"release.verify",equipment_id)
        with self.session() as s:
            if not s.scalar(select(Equipment).where(Equipment.equipment_id==equipment_id)):
                raise ValueError("Equipment not found")
            r=EquipmentRelease(
                equipment_id=equipment_id,
                related_ticket=related_ticket,
                checks_json=json.dumps(checks, sort_keys=True),
                notes=notes,
                requested_by=user,
            )
            s.add(r)
            s.flush()
            s.add(AuditLog(
                user=user,
                action="RELEASE_REQUEST",
                entity_type="EQUIPMENT_RELEASE",
                entity_key=str(r.id),
                detail=json.dumps({"equipment_id":equipment_id,"related_ticket":related_ticket}, sort_keys=True),
                workstation=workstation,
            ))
            return r

    def list_release_requests(self, equipment_id: str = ""):
        with self.session() as s:
            stmt=select(EquipmentRelease)
            if equipment_id:stmt=stmt.where(EquipmentRelease.equipment_id==equipment_id)
            return list(s.scalars(stmt.order_by(EquipmentRelease.requested_at.desc())))

    def verify_release(
        self,
        release_id: int,
        checks: dict[str, bool],
        user: str,
        expected_version: int | None=None,
        workstation: str = "",
    ):
        with self.session() as s:
            stmt=select(EquipmentRelease).where(EquipmentRelease.id==release_id)
            if self.url.startswith("postgresql"):
                stmt=stmt.with_for_update()
            r=s.scalar(stmt)
            if not r: raise ValueError("Release request not found")
            self.assert_authorized(user,"release.verify",r.equipment_id)
            if expected_version is not None and r.version!=expected_version:
                raise RuntimeError("CONFLICT: Release request changed by another user.")
            if r.status=="Approved / Released":
                raise ValueError("Release request is already approved and cannot be re-verified.")
            r.checks_json=json.dumps(checks, sort_keys=True)
            r.verified_by=user
            r.verified_at=datetime.utcnow()
            r.status="Verified" if checks and all(checks.values()) else "Verification Failed"
            r.version+=1
            s.add(AuditLog(
                user=user,
                action="RELEASE_VERIFY",
                entity_type="EQUIPMENT_RELEASE",
                entity_key=str(r.id),
                detail=json.dumps({"equipment_id":r.equipment_id,"status":r.status,"checks":checks}, sort_keys=True),
                workstation=workstation,
            ))
            s.flush()
            return r

    def approve_release(
        self,
        release_id: int,
        user: str,
        expected_version: int | None=None,
        workstation: str = "",
    ):
        with self.session() as s:
            stmt=select(EquipmentRelease).where(EquipmentRelease.id==release_id)
            if self.url.startswith("postgresql"):
                stmt=stmt.with_for_update()
            r=s.scalar(stmt)
            if not r: raise ValueError("Release request not found")
            self.assert_authorized(user,"release.approve",r.equipment_id)
            if expected_version is not None and r.version!=expected_version:
                raise RuntimeError("CONFLICT: Release request changed by another user.")
            checks=json.loads(r.checks_json or "{}")
            if r.status!="Verified" or not checks or not all(checks.values()):
                raise ValueError("Release must be fully verified before approval")
            if user in {r.requested_by, r.verified_by}:
                raise ValueError(
                    "Independent approval required: the release approver must differ from both requester and verifier."
                )
            critical = int(s.scalar(select(func.count()).select_from(Ticket).where(
                Ticket.equipment_id==r.equipment_id,
                Ticket.priority.in_(["P1","P2"]),
                Ticket.status.notin_(["Closed","Cancelled"]),
            )) or 0)
            if critical:
                raise ValueError(f"Cannot release equipment while {critical} P1/P2 ticket(s) remain open")
            eq_stmt=select(Equipment).where(Equipment.equipment_id==r.equipment_id)
            if self.url.startswith("postgresql"):
                eq_stmt=eq_stmt.with_for_update()
            eq=s.scalar(eq_stmt)
            if not eq:
                raise ValueError("Equipment not found")
            if eq.status=="Qualification" or eq.disposition=="Qualification":
                now=datetime.utcnow()
                valid_qualification=s.scalar(
                    select(QualificationRun)
                    .where(
                        QualificationRun.equipment_id==r.equipment_id,
                        QualificationRun.status=="Approved",
                        ((QualificationRun.expires_at.is_(None)) | (QualificationRun.expires_at>now)),
                    )
                    .order_by(QualificationRun.approved_at.desc(),QualificationRun.id.desc())
                )
                if not valid_qualification:
                    raise ValueError("Cannot release equipment from Qualification without an approved, non-expired qualification run.")
            for d in s.scalars(select(Disposition).where(Disposition.equipment_id==r.equipment_id,Disposition.active.is_(True))):
                d.active=False
            s.add(Disposition(
                equipment_id=r.equipment_id,
                state="Released",
                reason="Verified equipment release",
                related_ticket=r.related_ticket,
                created_by=r.requested_by,
                approved_by=user,
            ))
            eq.disposition="Released"
            eq.version+=1
            r.status="Approved / Released"
            r.approved_by=user
            r.approved_at=datetime.utcnow()
            r.version+=1
            self._queue_integration_event(s,"equipment.released","EQUIPMENT",r.equipment_id,{
                "equipment_id":r.equipment_id,"release_id":r.id,"approved_by":user,
                "approved_at":r.approved_at.isoformat(),"related_ticket":r.related_ticket,
            })
            self._apply_workflow_automation_in_session(s,"RELEASE_APPROVED",{
                "entity_type":"RELEASE","entity_key":str(r.id),"equipment_id":r.equipment_id,
                "ticket_no":r.related_ticket,"approved_by":user,
                "summary":"Equipment release approved","detail":r.notes or "",
            })
            s.add(AuditLog(
                user=user,
                action="RELEASE_APPROVE",
                entity_type="EQUIPMENT_RELEASE",
                entity_key=str(r.id),
                detail=json.dumps({
                    "equipment_id":r.equipment_id,
                    "requested_by":r.requested_by,
                    "verified_by":r.verified_by,
                    "approved_by":user,
                }, sort_keys=True),
                workstation=workstation,
            ))
            s.flush()
            return r

    WORK_ORDER_TRANSITIONS={
        "Open":{"Assigned","In Progress","Cancelled"},
        "Assigned":{"In Progress","Waiting Parts","Waiting Production","Cancelled"},
        "In Progress":{"Waiting Parts","Waiting Production","Ready for Qualification","Completed","Cancelled"},
        "Waiting Parts":{"In Progress","Cancelled"},
        "Waiting Production":{"In Progress","Cancelled"},
        "Ready for Qualification":{"Completed","In Progress","Cancelled"},
        "Completed":set(),
        "Cancelled":set(),
    }

    def create_work_order(self, data: dict[str, Any], user: str, workstation: str = ""):
        payload=dict(data)
        equipment_id=str(payload.get("equipment_id","")).strip()
        if not equipment_id:raise ValueError("Equipment ID is required.")
        self.assert_authorized(user,"worklog.edit",equipment_id)
        if not str(payload.get("owner","")).strip():
            owner=self.resolve_default_owner("WORK_ORDER",equipment_id,{"priority":str(payload.get("priority","Normal")),"source_type":str(payload.get("source_type","ENGINEERING")).upper()})
            if owner:payload["owner"]=owner
        with self.session() as s:
            if not s.scalar(select(Equipment).where(Equipment.equipment_id==equipment_id)):
                raise ValueError("Equipment not found")
            no=str(payload.get("work_order_no","")).strip()
            if not no:
                no=self._next_configured_number_in_session(
                    s,"WORK_ORDER",equipment_id,
                    {"priority":str(payload.get("priority","Normal")),"source_type":str(payload.get("source_type","ENGINEERING")).upper()},
                )
            if s.scalar(select(WorkOrder).where(WorkOrder.work_order_no==no)):
                raise ValueError("Work order number already exists.")
            row=WorkOrder(
                work_order_no=no,equipment_id=equipment_id,
                source_type=str(payload.get("source_type","ENGINEERING")).upper(),
                source_key=str(payload.get("source_key","")).strip(),
                title=str(payload.get("title","")).strip() or f"Engineering work on {equipment_id}",
                description=str(payload.get("description","")).strip(),
                priority=str(payload.get("priority","Normal")).strip() or "Normal",
                status="Open",owner=str(payload.get("owner","")).strip(),
                team=str(payload.get("team","")).strip(),
                planned_start=payload.get("planned_start"),planned_end=payload.get("planned_end"),
                qualification_required=bool(payload.get("qualification_required",False)),
                release_required=bool(payload.get("release_required",False)),
                created_by=user,
            )
            s.add(row);s.flush()
            s.add(WorkOrderEvent(
                work_order_no=no,from_state="",to_state="Open",reason="Work order created",
                owner=row.owner,changed_by=user,workstation=workstation,
            ))
            if row.source_key:
                s.add(WorkOrderLink(
                    work_order_no=no,entity_type=row.source_type,entity_key=row.source_key,
                    relation="SOURCE",created_by=user,
                ))
            s.add(AuditLog(
                user=user,action="WORK_ORDER_CREATE",entity_type="WORK_ORDER",entity_key=no,
                detail=json.dumps({"equipment_id":equipment_id,"source_type":row.source_type,"source_key":row.source_key},sort_keys=True),
                workstation=workstation,
            ))
            self._queue_integration_event(s,"work_order.created","WORK_ORDER",no,{
                "work_order_no":no,"equipment_id":equipment_id,"source_type":row.source_type,
                "source_key":row.source_key,"owner":row.owner,"created_by":user,
            })
            s.flush();return row

    def create_work_order_from_ticket(self, ticket_no: str, user: str, workstation: str = ""):
        with self.session() as s:
            ticket=s.scalar(select(Ticket).where(Ticket.ticket_no==ticket_no))
            if not ticket:raise ValueError("Ticket not found")
            existing=s.scalar(
                select(WorkOrder)
                .join(WorkOrderLink,WorkOrderLink.work_order_no==WorkOrder.work_order_no)
                .where(WorkOrderLink.entity_type=="TICKET",WorkOrderLink.entity_key==ticket_no,WorkOrderLink.relation=="SOURCE",
                       WorkOrder.status.notin_(["Completed","Cancelled"]))
                .order_by(WorkOrder.created_at.desc())
            )
            if existing:return existing
        return self.create_work_order({
            "equipment_id":ticket.equipment_id,"source_type":"TICKET","source_key":ticket.ticket_no,
            "title":f"Repair / investigation — {ticket.title}","description":ticket.description,
            "priority":ticket.priority,"owner":ticket.owner,
            "qualification_required":ticket.priority in {"P1","P2"},"release_required":ticket.priority in {"P1","P2"},
        },user,workstation)

    def create_work_order_from_pm(self, task_id: int, user: str, workstation: str = ""):
        with self.session() as s:
            task=s.get(PMTask,task_id)
            if not task:raise ValueError("PM task not found")
            existing=s.scalar(
                select(WorkOrder)
                .join(WorkOrderLink,WorkOrderLink.work_order_no==WorkOrder.work_order_no)
                .where(WorkOrderLink.entity_type=="PM_TASK",WorkOrderLink.entity_key==str(task_id),WorkOrderLink.relation=="SOURCE",
                       WorkOrder.status.notin_(["Completed","Cancelled"]))
                .order_by(WorkOrder.created_at.desc())
            )
            if existing:return existing
        return self.create_work_order({
            "equipment_id":task.equipment_id,"source_type":"PM_TASK","source_key":str(task.id),
            "title":f"{task.pm_id} — {task.pm_name}","description":"Controlled preventive-maintenance work order",
            "priority":task.priority,"owner":task.assigned_to,
        },user,workstation)

    def schedule_work_order(
        self,
        work_order_no: str,
        user: str,
        *,
        start_at: datetime,
        end_at: datetime,
        owner: str | None = None,
        reason: str = "",
        expected_version: int | None = None,
        workstation: str = "",
    ):
        if not start_at or not end_at or end_at<=start_at:
            raise ValueError("Work-order schedule requires an end after the start.")
        with self.session() as s:
            stmt=select(WorkOrder).where(WorkOrder.work_order_no==work_order_no)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            row=s.scalar(stmt)
            if not row:raise ValueError("Work order not found")
            self.assert_authorized(user,"worklog.edit",row.equipment_id)
            if expected_version is not None and row.version!=expected_version:
                raise RuntimeError("CONFLICT: Work order changed by another user. Refresh and retry.")
            if row.status in {"Completed","Cancelled"}:
                raise ValueError(f"Cannot schedule work order in {row.status} state.")
            old_start=row.planned_start;old_end=row.planned_end;old_owner=row.owner
            row.planned_start=start_at;row.planned_end=end_at
            if owner is not None:row.owner=owner.strip()
            row.updated_at=datetime.utcnow();row.version+=1
            detail={
                "old_start":old_start.isoformat() if old_start else None,
                "old_end":old_end.isoformat() if old_end else None,
                "new_start":start_at.isoformat(),"new_end":end_at.isoformat(),
                "old_owner":old_owner,"new_owner":row.owner,"reason":reason.strip(),
            }
            s.add(AuditLog(
                user=user,action="WORK_ORDER_SCHEDULE_UPDATE",entity_type="WORK_ORDER",
                entity_key=row.work_order_no,detail=json.dumps(detail,sort_keys=True),
                workstation=workstation,
            ))
            self._queue_integration_event(s,"work_order.schedule.changed","WORK_ORDER",row.work_order_no,{
                "work_order_no":row.work_order_no,"equipment_id":row.equipment_id,
                "planned_start":start_at.isoformat(),"planned_end":end_at.isoformat(),
                "owner":row.owner,"reason":reason.strip(),"changed_by":user,
            })
            s.flush();return row

    def operational_calendar_rows(
        self,
        start_at: datetime,
        end_at: datetime,
    ) -> list[dict[str,Any]]:
        """Merge PM and engineering work into one operational calendar view."""
        if end_at<=start_at:return []
        with self.session() as s:
            pm_tasks=list(s.scalars(select(PMTask).where(
                PMTask.status.notin_(["Completed","Cancelled"])
            )))
            task_ids=[x.id for x in pm_tasks]
            schedules={x.task_id:x for x in s.scalars(select(PMTaskSchedule).where(
                PMTaskSchedule.task_id.in_(task_ids)
            ))} if task_ids else {}
            definitions={x.pm_id:x for x in s.scalars(select(PMDefinition))}
            work_orders=list(s.scalars(select(WorkOrder).where(
                WorkOrder.status.notin_(["Completed","Cancelled"]),
                WorkOrder.planned_start.is_not(None),
                WorkOrder.planned_start<end_at,
                (WorkOrder.planned_end.is_(None) | (WorkOrder.planned_end>start_at)),
            )))
        rows=[]
        for task in pm_tasks:
            schedule=schedules.get(task.id)
            start=(schedule.scheduled_start_at if schedule else None) or task.scheduled_date or task.original_due_date
            if not start:continue
            hours=float(schedule.planned_hours if schedule else (task.estimated_hours or 0)) or 1.0
            end=(schedule.scheduled_end_at if schedule else None) or (start+timedelta(hours=max(.5,hours)))
            if start>=end_at or end<=start_at:continue
            definition=definitions.get(task.pm_id);due=task.original_due_date
            early=(due-timedelta(days=max(0,definition.early_window_days or 0))) if due and definition else due
            latest=(due+timedelta(days=max(0,definition.grace_days or 0))) if due and definition else due
            window="IN WINDOW"
            if latest and datetime.utcnow()>latest:window="OVERDUE"
            elif early and start<early:window="TOO EARLY"
            elif latest and start>latest and task.status!="Deferred":window="OUTSIDE GRACE"
            elif task.status=="Deferred":window="DEFERRED"
            rows.append({
                "entity_type":"PM_TASK","entity_key":str(task.id),"kind":"PM",
                "equipment_id":task.equipment_id,"title":f"{task.pm_id} — {task.pm_name}",
                "start_at":start,"end_at":end,"owner":task.assigned_to,"status":task.status,
                "priority":task.priority,"window":window,"version":task.version,
                "controlled_due":task.original_due_date,
            })
        for wo in work_orders:
            start=wo.planned_start
            end=wo.planned_end or (start+timedelta(hours=1))
            rows.append({
                "entity_type":"WORK_ORDER","entity_key":wo.work_order_no,"kind":"WO",
                "equipment_id":wo.equipment_id,"title":wo.title,
                "start_at":start,"end_at":end,"owner":wo.owner,"status":wo.status,
                "priority":wo.priority,"window":"","version":wo.version,
                "controlled_due":None,
            })
        rows.sort(key=lambda x:(x["start_at"],x["equipment_id"],x["kind"],x["entity_key"]))
        return rows

    def list_work_orders(self, equipment_id: str = "", open_only: bool = False):
        with self.session() as s:
            stmt=select(WorkOrder)
            if equipment_id:stmt=stmt.where(WorkOrder.equipment_id==equipment_id)
            if open_only:stmt=stmt.where(WorkOrder.status.notin_(["Completed","Cancelled"]))
            return list(s.scalars(stmt.order_by(WorkOrder.updated_at.desc(),WorkOrder.created_at.desc())))

    def get_work_order(self, work_order_no: str):
        with self.session() as s:return s.scalar(select(WorkOrder).where(WorkOrder.work_order_no==work_order_no))

    def list_work_order_events(self, work_order_no: str):
        with self.session() as s:return list(s.scalars(
            select(WorkOrderEvent).where(WorkOrderEvent.work_order_no==work_order_no)
            .order_by(WorkOrderEvent.occurred_at,WorkOrderEvent.id)
        ))

    def add_work_order_link(self, work_order_no: str, entity_type: str, entity_key: str, relation: str, user: str):
        with self.session() as s:
            wo=s.scalar(select(WorkOrder).where(WorkOrder.work_order_no==work_order_no))
            if not wo:raise ValueError("Work order not found")
            self.assert_authorized(user,"worklog.edit",wo.equipment_id)
            et=entity_type.strip().upper();ek=str(entity_key).strip();rel=relation.strip().upper() or "RELATED"
            existing=s.scalar(select(WorkOrderLink).where(
                WorkOrderLink.work_order_no==work_order_no,WorkOrderLink.entity_type==et,
                WorkOrderLink.entity_key==ek,WorkOrderLink.relation==rel,
            ))
            if existing:return existing
            row=WorkOrderLink(work_order_no=work_order_no,entity_type=et,entity_key=ek,relation=rel,created_by=user)
            s.add(row);s.flush();return row

    def list_work_order_links(self, work_order_no: str):
        with self.session() as s:return list(s.scalars(
            select(WorkOrderLink).where(WorkOrderLink.work_order_no==work_order_no)
            .order_by(WorkOrderLink.created_at,WorkOrderLink.id)
        ))

    def update_work_order_details(
        self,
        work_order_no: str,
        user: str,
        *,
        description: str | None = None,
        owner: str | None = None,
        team: str | None = None,
        expected_version: int | None = None,
        workstation: str = "",
    ):
        with self.session() as s:
            stmt=select(WorkOrder).where(WorkOrder.work_order_no==work_order_no)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            row=s.scalar(stmt)
            if not row:raise ValueError("Work order not found")
            self.assert_authorized(user,"worklog.edit",row.equipment_id)
            if expected_version is not None and row.version!=expected_version:
                raise RuntimeError("CONFLICT: Work order changed by another user.")
            if row.status=="Cancelled":raise ValueError("Cancelled work order details cannot be edited.")
            changes={}
            if description is not None and description!=row.description:
                changes["description"]={"old":row.description,"new":description};row.description=description
            if owner is not None and owner.strip()!=row.owner:
                changes["owner"]={"old":row.owner,"new":owner.strip()};row.owner=owner.strip()
            if team is not None and team.strip()!=row.team:
                changes["team"]={"old":row.team,"new":team.strip()};row.team=team.strip()
            if not changes:return row
            row.updated_at=datetime.utcnow();row.version+=1
            s.add(AuditLog(
                user=user,action="WORK_ORDER_DETAILS_UPDATE",entity_type="WORK_ORDER",entity_key=row.work_order_no,
                detail=json.dumps(changes,sort_keys=True),workstation=workstation,
            ))
            self._queue_integration_event(s,"work_order.details.changed","WORK_ORDER",row.work_order_no,{
                "work_order_no":row.work_order_no,"equipment_id":row.equipment_id,
                "changes":changes,"changed_by":user,
            })
            s.flush();return row

    def transition_work_order(
        self,work_order_no: str,target_state: str,user: str,reason: str="",
        owner: str="",expected_version: int | None=None,workstation: str="",
    ):
        with self.session() as s:
            stmt=select(WorkOrder).where(WorkOrder.work_order_no==work_order_no)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            row=s.scalar(stmt)
            if not row:raise ValueError("Work order not found")
            self.assert_authorized(user,"worklog.edit",row.equipment_id)
            if expected_version is not None and row.version!=expected_version:
                raise RuntimeError("CONFLICT: Work order changed by another user.")
            allowed=self.WORK_ORDER_TRANSITIONS.get(row.status,set())
            if target_state not in allowed:
                raise ValueError(f"Invalid work-order transition: {row.status} → {target_state}")
            if target_state in {"Waiting Parts","Waiting Production","Cancelled"} and not reason.strip():
                raise ValueError(f"{target_state} requires a reason.")
            previous=row.status;now=datetime.utcnow();row.status=target_state
            if owner.strip():row.owner=owner.strip()
            if target_state=="In Progress" and not row.started_at:row.started_at=now
            if target_state=="Completed":row.completed_at=now
            row.updated_at=now;row.version+=1
            s.add(WorkOrderEvent(
                work_order_no=row.work_order_no,from_state=previous,to_state=target_state,
                reason=reason.strip(),owner=row.owner,changed_by=user,workstation=workstation,occurred_at=now,
            ))
            s.add(AuditLog(
                user=user,action="WORK_ORDER_TRANSITION",entity_type="WORK_ORDER",entity_key=row.work_order_no,
                detail=json.dumps({"from":previous,"to":target_state,"reason":reason.strip(),"owner":row.owner},sort_keys=True),
                workstation=workstation,created_at=now,
            ))
            self._queue_integration_event(s,"work_order.state.changed","WORK_ORDER",row.work_order_no,{
                "work_order_no":row.work_order_no,"equipment_id":row.equipment_id,
                "from_state":previous,"to_state":target_state,"owner":row.owner,"changed_by":user,
            })
            if row.owner and row.owner!=user:
                self._add_notification_in_session(
                    s,row.owner,"WORK_ORDER",f"{row.work_order_no} · {target_state}",
                    f"{row.title}\nEquipment: {row.equipment_id}"+(f"\n{reason.strip()}" if reason.strip() else ""),
                    "HIGH" if target_state in {"Assigned","Waiting Parts","Ready for Qualification"} else "INFO",
                    "WORK_ORDER",row.work_order_no,row.equipment_id,
                    f"work-order:{row.work_order_no}:{target_state}:{row.version}",
                )
            s.flush();return row

    def applicable_qualification_protocols(self, equipment_id: str):
        with self.session() as s:
            eq=s.scalar(select(Equipment).where(Equipment.equipment_id==equipment_id))
            if not eq:raise ValueError("Equipment not found")
            rows=list(s.scalars(
                select(QualificationProtocol)
                .where(QualificationProtocol.active.is_(True))
                .order_by(QualificationProtocol.protocol_id,QualificationProtocol.revision.desc())
            ))
            latest={}
            for row in rows:
                if row.protocol_id in latest:continue
                if row.equipment_id and row.equipment_id!=equipment_id:continue
                if row.equipment_type and row.equipment_type!=eq.equipment_type:continue
                latest[row.protocol_id]=row
            return list(latest.values())

    def work_order_closeout_status(self, work_order_no: str) -> dict[str, Any]:
        with self.session() as s:
            wo=s.scalar(select(WorkOrder).where(WorkOrder.work_order_no==work_order_no))
            if not wo:raise ValueError("Work order not found")
            links=list(s.scalars(select(WorkOrderLink).where(WorkOrderLink.work_order_no==work_order_no)))
            logs=list(s.scalars(select(WorkLog).where(
                WorkLog.entity_type=="WORK_ORDER",WorkLog.entity_key==work_order_no
            ).order_by(WorkLog.started_at)))
            attachments=list(s.scalars(select(EntityAttachment).where(
                EntityAttachment.entity_type=="WORK_ORDER",EntityAttachment.entity_key==work_order_no,
                EntityAttachment.active.is_(True),
            )))
            qualification_keys={x.entity_key for x in links if x.entity_type=="QUALIFICATION"}
            release_keys={x.entity_key for x in links if x.entity_type=="RELEASE"}
            qualifications=list(s.scalars(select(QualificationRun).where(
                QualificationRun.run_no.in_(qualification_keys)
            ).order_by(QualificationRun.started_at.desc()))) if qualification_keys else []
            release_ids=[]
            for key in release_keys:
                try:
                    release_ids.append(int(key))
                except (TypeError,ValueError):
                    continue
            releases=list(s.scalars(select(EquipmentRelease).where(
                EquipmentRelease.id.in_(release_ids)
            ).order_by(EquipmentRelease.requested_at.desc()))) if release_ids else []
            related_ticket=""
            if wo.source_type=="TICKET" and wo.source_key:related_ticket=wo.source_key
            if not related_ticket:
                ticket_link=next((x for x in links if x.entity_type=="TICKET"),None)
                related_ticket=ticket_link.entity_key if ticket_link else ""
            source_pm_id=None
            if wo.source_type=="PM_TASK" and str(wo.source_key).isdigit():source_pm_id=int(wo.source_key)
            if source_pm_id is None:
                pm_link=next((x for x in links if x.entity_type=="PM_TASK" and str(x.entity_key).isdigit()),None)
                source_pm_id=int(pm_link.entity_key) if pm_link else None
            reservations=list(s.scalars(select(InventoryReservation).where(
                InventoryReservation.pm_task_id==source_pm_id
            ))) if source_pm_id else []
        precheck=self.release_precheck(wo.equipment_id)
        now=datetime.utcnow()
        valid_qualification=next((
            x for x in qualifications
            if x.status=="Approved" and (x.expires_at is None or x.expires_at>now)
        ),None)
        open_qualification=next((x for x in qualifications if x.status in {"In Progress","Submitted","Verified"}),None)
        active_release=next((x for x in releases if x.status!="Approved / Released"),None)
        approved_release=next((x for x in releases if x.status=="Approved / Released"),None)
        blockers=[]
        if wo.status not in {"Ready for Qualification","Completed"} and (wo.qualification_required or wo.release_required):
            blockers.append(f"Work order is still {wo.status}; finish repair/work before controlled closeout.")
        if precheck["critical_tickets_open"]:
            blockers.append(f"{precheck['critical_tickets_open']} open P1/P2 incident(s) remain.")
        if wo.qualification_required and not valid_qualification:
            blockers.append("Approved valid qualification is required.")
        if wo.release_required and not approved_release:
            blockers.append("Approved equipment release is required." if active_release else "Equipment release request is required.")
        if any(x.status=="Reserved" for x in reservations):
            blockers.append("PM part reservations remain active; consume or release them before closeout.")
        return {
            "work_order_no":wo.work_order_no,"equipment_id":wo.equipment_id,"status":wo.status,
            "qualification_required":wo.qualification_required,"release_required":wo.release_required,
            "related_ticket":related_ticket,"source_pm_task_id":source_pm_id,
            "labor_entries":len(logs),"active_labor":sum(1 for x in logs if x.status=="Active"),
            "attachment_count":len(attachments),"part_reservations":len(reservations),
            "active_part_reservations":sum(1 for x in reservations if x.status=="Reserved"),
            "critical_tickets_open":precheck["critical_tickets_open"],"overdue_pm":precheck["overdue_pm"],
            "valid_qualification_run":valid_qualification.run_no if valid_qualification else "",
            "open_qualification_run":open_qualification.run_no if open_qualification else "",
            "active_release_id":active_release.id if active_release else None,
            "active_release_status":active_release.status if active_release else "",
            "approved_release_id":approved_release.id if approved_release else None,
            "release_approved":bool(approved_release),
            "blockers":blockers,
            "can_start_qualification":bool(
                wo.qualification_required and wo.status in {"Ready for Qualification","Completed"}
                and not valid_qualification and not open_qualification
            ),
            "can_request_release":bool(
                wo.release_required and wo.status in {"Ready for Qualification","Completed"}
                and precheck["critical_tickets_open"]==0
                and (not wo.qualification_required or bool(valid_qualification))
                and not active_release and not approved_release
            ),
        }

    def start_work_order_qualification(
        self, work_order_no: str, user: str, protocol_id: str = "", workstation: str = ""
    ):
        wo=self.get_work_order(work_order_no)
        if not wo:raise ValueError("Work order not found")
        if not wo.qualification_required:raise ValueError("This work order does not require qualification.")
        if wo.status not in {"Ready for Qualification","Completed"}:
            raise ValueError("Work order must be Ready for Qualification before starting qualification.")
        linked_keys={x.entity_key for x in self.list_work_order_links(work_order_no) if x.entity_type=="QUALIFICATION"}
        linked_runs=[x for x in self.list_qualification_runs(wo.equipment_id) if x.run_no in linked_keys]
        now=datetime.utcnow()
        current=next((
            x for x in linked_runs
            if x.status=="Approved" and (x.expires_at is None or x.expires_at>now)
        ),None)
        if current:return current
        open_runs=[x for x in linked_runs if x.status in {"In Progress","Submitted","Verified"}]
        if open_runs:return open_runs[0]
        protocols=self.applicable_qualification_protocols(wo.equipment_id)
        if protocol_id:
            protocol=next((x for x in protocols if x.protocol_id==protocol_id),None)
            if not protocol:raise ValueError("Selected qualification protocol is not applicable to this equipment.")
        elif len(protocols)==1:
            protocol=protocols[0]
        elif not protocols:
            raise ValueError("No active qualification protocol is applicable to this equipment.")
        else:
            raise ValueError("Multiple qualification protocols are applicable; select one explicitly.")
        run=self.start_qualification_run(wo.equipment_id,protocol.protocol_id,user,workstation=workstation)
        self.add_work_order_link(work_order_no,"QUALIFICATION",run.run_no,"CLOSEOUT",user)
        return run

    def create_work_order_release_request(self, work_order_no: str, user: str, workstation: str = ""):
        wo=self.get_work_order(work_order_no)
        if not wo:raise ValueError("Work order not found")
        if not wo.release_required:raise ValueError("This work order does not require release verification.")
        status=self.work_order_closeout_status(work_order_no)
        if status["critical_tickets_open"]:
            raise ValueError("Cannot request release while P1/P2 incidents remain open.")
        if wo.qualification_required and not status["valid_qualification_run"]:
            raise ValueError("Approved valid qualification is required before release request.")
        if wo.status not in {"Ready for Qualification","Completed"}:
            raise ValueError("Work order must be ready for closeout before release request.")
        if status["active_release_id"]:
            return next(x for x in self.list_release_requests() if x.id==status["active_release_id"])
        checks={
            "maintenance_complete":False,
            "measurements_pass":False,
            "calibration_valid":False,
            "safety_check":False,
            "verification_run":False,
            "critical_tickets_cleared":False,
        }
        notes=f"Generated from work order {work_order_no}. Independent release verification remains required."
        release=self.create_release_request(
            wo.equipment_id,status["related_ticket"],checks,notes,user,workstation
        )
        self.add_work_order_link(work_order_no,"RELEASE",str(release.id),"CLOSEOUT",user)
        return release

    def start_work_log(
        self,
        entity_type: str,
        entity_key: str,
        equipment_id: str,
        user: str,
        work_type: str = "Engineering",
        note: str = "",
    ):
        if equipment_id:self.assert_authorized(user,"worklog.edit",equipment_id)
        with self.session() as s:
            active=s.scalar(select(WorkLog).where(
                WorkLog.username==user,WorkLog.entity_type==entity_type,
                WorkLog.entity_key==entity_key,WorkLog.status=="Active",
            ))
            if active:return active
            row=WorkLog(
                equipment_id=equipment_id,entity_type=entity_type,entity_key=str(entity_key),
                username=user,work_type=work_type,note=note.strip(),status="Active",
            )
            s.add(row);s.flush();return row

    def stop_work_log(self, work_log_id: int, user: str, note: str = ""):
        with self.session() as s:
            stmt=select(WorkLog).where(WorkLog.id==work_log_id)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            row=s.scalar(stmt)
            if not row:raise ValueError("Work log not found")
            if row.status!="Active":raise ValueError("Work log is already closed.")
            actor=s.scalar(select(User).where(User.username==user))
            if row.username!=user and not (actor and actor.role in {"Administrator","Manager","Supervisor"}):
                raise PermissionError("Only the worker or an authorized supervisor can close this work log.")
            now=datetime.utcnow();row.ended_at=now;row.duration_minutes=max(0.0,(now-row.started_at).total_seconds()/60.0);row.status="Completed";row.version+=1
            if note.strip():row.note=(row.note+"\n"+note.strip()).strip()
            self._queue_integration_event(s,"labor.work.completed","WORK_LOG",str(row.id),{
                "work_log_id":row.id,"equipment_id":row.equipment_id,"entity_type":row.entity_type,
                "entity_key":row.entity_key,"username":row.username,"work_type":row.work_type,
                "duration_minutes":row.duration_minutes,"ended_at":now.isoformat(),
            })
            s.flush();return row

    def list_work_logs(self, equipment_id: str = "", active_only: bool = False, limit: int = 1000):
        with self.session() as s:
            stmt=select(WorkLog).order_by(WorkLog.started_at.desc()).limit(max(1,min(int(limit),5000)))
            if equipment_id:stmt=stmt.where(WorkLog.equipment_id==equipment_id)
            if active_only:stmt=stmt.where(WorkLog.status=="Active")
            return list(s.scalars(stmt))

    def shift_handover_candidates(self) -> list[dict[str, Any]]:
        now=datetime.utcnow();rows=[]
        with self.session() as s:
            equipment=list(s.scalars(select(Equipment)))
            tickets=list(s.scalars(select(Ticket).where(Ticket.status.notin_(["Closed","Cancelled"]))))
            alarms=list(s.scalars(select(EquipmentAlarmEvent).where(EquipmentAlarmEvent.state=="ACTIVE")))
            pm=list(s.scalars(select(PMTask).where(PMTask.status.notin_(["Completed","Cancelled"]))))
            work_orders=list(s.scalars(select(WorkOrder).where(WorkOrder.status.notin_(["Completed","Cancelled"]))))
            qualification=list(s.scalars(select(QualificationRun).where(QualificationRun.status.notin_(["Approved","Rejected"]))))
            releases=list(s.scalars(select(EquipmentRelease).where(EquipmentRelease.status!="Approved / Released")))
            dispositions=list(s.scalars(select(Disposition).where(Disposition.active.is_(True))))
            existing=list(s.scalars(select(Endorsement).where(Endorsement.status.in_(["Open","Acknowledged"]))))
        by_ticket={};by_alarm={};by_pm={};by_wo={};by_q={};by_rel={};by_disp={}
        for x in tickets:by_ticket.setdefault(x.equipment_id,[]).append(x)
        for x in alarms:by_alarm.setdefault(x.equipment_id,[]).append(x)
        for x in pm:by_pm.setdefault(x.equipment_id,[]).append(x)
        for x in work_orders:by_wo.setdefault(x.equipment_id,[]).append(x)
        for x in qualification:by_q.setdefault(x.equipment_id,[]).append(x)
        for x in releases:by_rel.setdefault(x.equipment_id,[]).append(x)
        for x in dispositions:by_disp.setdefault(x.equipment_id,[]).append(x)
        existing_eq={x.equipment_id for x in existing}
        risk_states={"Down","Engineering","Waiting Parts","Waiting Vendor","Qualification","Hold","Restricted","Offline"}
        for eq in equipment:
            t=by_ticket.get(eq.equipment_id,[]);a=by_alarm.get(eq.equipment_id,[]);p=by_pm.get(eq.equipment_id,[]);wo=by_wo.get(eq.equipment_id,[]);q=by_q.get(eq.equipment_id,[]);rel=by_rel.get(eq.equipment_id,[]);disp=by_disp.get(eq.equipment_id,[])
            due_soon=[x for x in p if x.status in {"Overdue","In Progress"} or (x.scheduled_date and x.scheduled_date<=now+timedelta(hours=24))]
            critical=[x for x in t if x.priority in {"P1","P2"}]
            needs=eq.status in risk_states or bool(critical or a or due_soon or wo or q or rel)
            if not needs:continue
            pending=[]
            pending += [f"{x.ticket_no} {x.priority} {x.status}: {x.title}" for x in sorted(t,key=lambda x:(x.priority,x.created_at))[:5]]
            pending += [f"Alarm {x.alarm_code} {x.severity}: {x.message}" for x in a[:5]]
            pending += [f"PM {x.pm_id} {x.status} due {x.scheduled_date or x.original_due_date}" for x in due_soon[:5]]
            pending += [f"WO {x.work_order_no} {x.status}: {x.title}" for x in wo[:5]]
            pending += [f"Qualification {x.run_no} {x.status}" for x in q[:3]]
            pending += [f"Release #{x.id} {x.status}" for x in rel[:3]]
            restriction_parts=[]
            for d in disp[:3]:
                text="; ".join(x for x in [d.state,d.restrictions,d.release_criteria] if x)
                if text:restriction_parts.append(text)
            critical_alarm=any((x.severity or "").strip().lower() in {"critical","fatal","emergency"} for x in a)
            severity="CRITICAL" if eq.status=="Down" or any(x.priority=="P1" for x in t) or critical_alarm else ("HIGH" if eq.status in risk_states or critical or a else "MEDIUM")
            owner=next((x.owner for x in wo if x.owner),None) or next((x.owner for x in t if x.owner),None) or eq.owner
            next_action=(
                "Resolve active critical incident and restore controlled state." if critical else
                "Complete qualification / release sequence." if q or rel or eq.status=="Qualification" else
                "Continue active work order / maintenance." if wo or due_soon else
                "Investigate active alarm / abnormal equipment state."
            )
            rows.append({
                "severity":severity,"equipment_id":eq.equipment_id,"equipment_name":eq.name,
                "current_condition":f"{eq.status} / {eq.disposition}",
                "pending_work":"\n".join(pending),
                "restrictions":"\n".join(restriction_parts),
                "next_action":next_action,"next_owner":owner or "",
                "active_incidents":len(t),"active_alarms":len(a),"open_pm":len(due_soon),"open_work_orders":len(wo),
                "existing_open_handover":eq.equipment_id in existing_eq,
            })
        rank={"CRITICAL":0,"HIGH":1,"MEDIUM":2}
        rows.sort(key=lambda x:(rank.get(x["severity"],9),x["equipment_id"]))
        return rows

    def publish_shift_handover(self, equipment_id: str, user: str, next_owner: str = "", workstation: str = ""):
        candidate=next((x for x in self.shift_handover_candidates() if x["equipment_id"]==equipment_id),None)
        if not candidate:raise ValueError("Equipment no longer has a live handover candidate.")
        self.assert_authorized(user,"endorsement.edit",equipment_id)
        with self.session() as s:
            prefix="".join(ch if ch.isalnum() else "-" for ch in equipment_id.upper()).strip("-")[:30]
            base=f"HO-{datetime.utcnow():%y%m%d%H%M%S}-{prefix}"
            no=base[:100];suffix=1
            while s.scalar(select(Endorsement).where(Endorsement.endorsement_no==no)):
                tail=f"-{suffix}";no=base[:100-len(tail)]+tail;suffix+=1
            row=Endorsement(
                endorsement_no=no,equipment_id=equipment_id,
                current_condition=candidate["current_condition"],work_completed="",
                pending_work=candidate["pending_work"],restrictions=candidate["restrictions"],
                next_action=candidate["next_action"],next_owner=(next_owner or candidate["next_owner"]).strip(),
                status="Open",created_by=user,
            )
            s.add(row)
            s.add(AuditLog(
                user=user,action="SHIFT_HANDOVER_PUBLISH",entity_type="ENDORSEMENT",entity_key=no,
                detail=json.dumps({"equipment_id":equipment_id,"severity":candidate["severity"]},sort_keys=True),
                workstation=workstation,
            ))
            self._queue_integration_event(s,"shift.handover.published","ENDORSEMENT",no,{
                "endorsement_no":no,"equipment_id":equipment_id,"next_owner":row.next_owner,"created_by":user,
            })
            s.flush();return row

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

    def list_endorsements(self, equipment_id: str = ""):
        with self.session() as s:
            stmt=select(Endorsement)
            if equipment_id:stmt=stmt.where(Endorsement.equipment_id==equipment_id)
            return list(s.scalars(stmt.order_by(Endorsement.created_at.desc())))

    def save_storage_location(self, data: dict[str, Any], expected_version: int | None = None):
        with self.session() as s:
            item=s.scalar(select(StorageLocation).where(StorageLocation.location_code==data["location_code"]))
            if item: self._update_versioned(item,data,expected_version,"Storage location")
            else: item=StorageLocation(**data); s.add(item)
            s.flush(); return item

    def list_storage_locations(self):
        with self.session() as s: return list(s.scalars(select(StorageLocation).order_by(StorageLocation.location_code)))

    def save_supplier_order(self, data: dict[str, Any], user: str, expected_version: int | None = None):
        payload=dict(data);order_no=str(payload.get("order_no","")).strip();supplier=str(payload.get("supplier","")).strip()
        if not order_no or not supplier:raise ValueError("Order number and supplier are required.")
        payload["order_no"]=order_no;payload["supplier"]=supplier;payload.setdefault("created_by",user)
        with self.session() as s:
            row=s.scalar(select(SupplierOrder).where(SupplierOrder.order_no==order_no))
            if row:
                if row.status not in {"Draft","Submitted","Partially Received"}:raise ValueError(f"Cannot edit supplier order in {row.status} status.")
                for key in ["status","submitted_by","submitted_at","closed_at","created_by"]:payload.pop(key,None)
                self._update_versioned(row,payload,expected_version,"Supplier order")
            else:
                for key in ["status","submitted_by","submitted_at","closed_at"]:payload.pop(key,None)
                row=SupplierOrder(**payload);s.add(row)
            s.add(AuditLog(user=user,action="SUPPLIER_ORDER_SAVE",entity_type="SUPPLIER_ORDER",entity_key=order_no,detail=supplier))
            s.flush();return row

    def list_supplier_orders(self, status: str = ""):
        with self.session() as s:
            stmt=select(SupplierOrder).order_by(SupplierOrder.order_date.desc(),SupplierOrder.order_no.desc())
            if status:stmt=stmt.where(SupplierOrder.status==status)
            return list(s.scalars(stmt))

    def add_supplier_order_line(self, order_no: str, data: dict[str, Any], user: str, expected_version: int | None = None):
        payload=dict(data);part=str(payload.get("part_number","")).strip();qty=float(payload.get("ordered_qty") or 0)
        if not part or qty<=0:raise ValueError("Part number and positive ordered quantity are required.")
        with self.session() as s:
            order=s.scalar(select(SupplierOrder).where(SupplierOrder.order_no==order_no))
            if not order:raise ValueError("Supplier order not found")
            if order.status not in {"Draft","Submitted","Partially Received"}:raise ValueError(f"Cannot edit lines in {order.status} order.")
            line_no=int(payload.get("line_no") or 0)
            row=s.scalar(select(SupplierOrderLine).where(SupplierOrderLine.order_no==order_no,SupplierOrderLine.line_no==line_no)) if line_no else None
            if row:
                if float(row.received_qty or 0)>qty:raise ValueError("Ordered quantity cannot be reduced below received quantity.")
                self._update_versioned(row,payload,expected_version,"Supplier order line")
            else:
                line_no=int(s.scalar(select(func.max(SupplierOrderLine.line_no)).where(SupplierOrderLine.order_no==order_no)) or 0)+1
                payload["line_no"]=line_no;payload["order_no"]=order_no
                catalog=s.scalar(select(PartCatalog).where(PartCatalog.part_number==part))
                if catalog and not payload.get("supplier_part_number"):payload["supplier_part_number"]=catalog.supplier_part_number
                row=SupplierOrderLine(**payload);s.add(row)
            s.flush();return row

    def list_supplier_order_lines(self, order_no: str):
        with self.session() as s:
            return list(s.scalars(select(SupplierOrderLine).where(SupplierOrderLine.order_no==order_no).order_by(SupplierOrderLine.line_no)))

    def submit_supplier_order(self, order_no: str, user: str, expected_version: int | None = None):
        with self.session() as s:
            stmt=select(SupplierOrder).where(SupplierOrder.order_no==order_no)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            order=s.scalar(stmt)
            if not order:raise ValueError("Supplier order not found")
            if expected_version is not None and order.version!=expected_version:raise RuntimeError("CONFLICT: Supplier order changed.")
            if order.status!="Draft":raise ValueError("Only Draft supplier orders can be submitted.")
            count=int(s.scalar(select(func.count()).select_from(SupplierOrderLine).where(SupplierOrderLine.order_no==order_no)) or 0)
            if not count:raise ValueError("Supplier order requires at least one line.")
            order.status="Submitted";order.submitted_by=user;order.submitted_at=datetime.utcnow();order.version+=1
            s.add(AuditLog(user=user,action="SUPPLIER_ORDER_SUBMIT",entity_type="SUPPLIER_ORDER",entity_key=order_no,detail=f"{count} line(s)"))
            s.flush();return order

    def receive_supplier_order_line(self, line_id: int, qty: float, user: str, reference: str = "", note: str = ""):
        if qty<=0:raise ValueError("Receipt quantity must be positive.")
        self.assert_authorized(user,"inventory.edit")
        with self.session() as s:
            stmt=select(SupplierOrderLine).where(SupplierOrderLine.id==line_id)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            line=s.scalar(stmt)
            if not line:raise ValueError("Supplier order line not found")
            order_stmt=select(SupplierOrder).where(SupplierOrder.order_no==line.order_no)
            if self.url.startswith("postgresql"):order_stmt=order_stmt.with_for_update()
            order=s.scalar(order_stmt)
            if not order or order.status not in {"Submitted","Partially Received"}:raise ValueError("Order must be Submitted before receipt.")
            remaining=float(line.ordered_qty or 0)-float(line.received_qty or 0)
            if qty>remaining+1e-9:raise ValueError(f"Receipt exceeds remaining ordered quantity ({remaining:g}).")
            location=(line.destination_location or "").strip()
            if not location:raise ValueError("Destination location is required before receipt.")
            item_stmt=select(InventoryItem).where(InventoryItem.part_number==line.part_number,InventoryItem.location_code==location)
            if self.url.startswith("postgresql"):item_stmt=item_stmt.with_for_update()
            item=s.scalar(item_stmt)
            if not item:
                catalog=s.scalar(select(PartCatalog).where(PartCatalog.part_number==line.part_number))
                item=InventoryItem(part_number=line.part_number,description=catalog.description if catalog else "",category=catalog.category if catalog else "",manufacturer=catalog.manufacturer if catalog else "",quantity=0.0,min_quantity=0.0,unit="ea",condition="Available",location_code=location)
                s.add(item);s.flush()
            item.quantity=float(item.quantity or 0)+qty;item.version+=1
            line.received_qty=float(line.received_qty or 0)+qty
            line.status="Received" if line.received_qty>=float(line.ordered_qty or 0)-1e-9 else "Partial";line.version+=1
            tx=InventoryTransaction(part_number=line.part_number,location_code=location,transaction_type="PO Receive",quantity=qty,user=user,note=" | ".join(x for x in [line.order_no,reference.strip(),note.strip()] if x))
            s.add(tx)
            lines=list(s.scalars(select(SupplierOrderLine).where(SupplierOrderLine.order_no==order.order_no)))
            statuses=[("Received" if x.id==line.id and line.status=="Received" else x.status) for x in lines]
            if all(x=="Received" for x in statuses):
                order.status="Received";order.closed_at=datetime.utcnow()
            else:order.status="Partially Received"
            order.version+=1
            s.add(AuditLog(user=user,action="SUPPLIER_ORDER_RECEIVE",entity_type="SUPPLIER_ORDER",entity_key=order.order_no,detail=json.dumps({"line_id":line.id,"part_number":line.part_number,"qty":qty,"location":location,"reference":reference},sort_keys=True)))
            s.flush();return line,order,tx

    def cancel_supplier_order(self, order_no: str, user: str, reason: str = ""):
        with self.session() as s:
            order=s.scalar(select(SupplierOrder).where(SupplierOrder.order_no==order_no))
            if not order:raise ValueError("Supplier order not found")
            if order.status=="Received":raise ValueError("Received supplier order cannot be cancelled.")
            if s.scalar(select(func.count()).select_from(SupplierOrderLine).where(SupplierOrderLine.order_no==order_no,SupplierOrderLine.received_qty>0)):
                raise ValueError("Order with received quantity cannot be cancelled.")
            order.status="Cancelled";order.closed_at=datetime.utcnow();order.version+=1
            for line in s.scalars(select(SupplierOrderLine).where(SupplierOrderLine.order_no==order_no)):line.status="Cancelled";line.version+=1
            s.add(AuditLog(user=user,action="SUPPLIER_ORDER_CANCEL",entity_type="SUPPLIER_ORDER",entity_key=order_no,detail=reason.strip()))
            s.flush();return order

    def register_rotable(self, data: dict[str, Any], user: str, expected_version: int | None = None):
        payload=dict(data);asset_id=str(payload.get("asset_id","")).strip();part=str(payload.get("part_number","")).strip()
        if not asset_id or not part:raise ValueError("Rotable asset ID and part number are required.")
        with self.session() as s:
            row=s.scalar(select(RotableAsset).where(RotableAsset.asset_id==asset_id))
            lifecycle_fields={"status","condition","equipment_id","component_id","vendor","repair_reference","repair_count","installed_at","removed_at","sent_for_repair_at","returned_at"}
            if row:
                for key in lifecycle_fields:payload.pop(key,None)
                self._update_versioned(row,payload,expected_version,"Rotable asset")
            else:
                for key in lifecycle_fields:payload.pop(key,None)
                row=RotableAsset(**payload);s.add(row);s.flush()
                s.add(RotableEvent(asset_id=asset_id,event_type="REGISTER",from_status="",to_status=row.status,location_code=row.current_location,user=user,note=row.notes))
            s.flush();return row

    def list_rotables(self, search_text: str = "", status: str = ""):
        with self.session() as s:
            stmt=select(RotableAsset).order_by(RotableAsset.part_number,RotableAsset.asset_id)
            if search_text:
                q=f"%{search_text}%";stmt=stmt.where(or_(RotableAsset.asset_id.ilike(q),RotableAsset.part_number.ilike(q),RotableAsset.serial_number.ilike(q),RotableAsset.equipment_id.ilike(q),RotableAsset.vendor.ilike(q)))
            if status:stmt=stmt.where(RotableAsset.status==status)
            return list(s.scalars(stmt))

    def list_rotable_events(self, asset_id: str):
        with self.session() as s:
            return list(s.scalars(select(RotableEvent).where(RotableEvent.asset_id==asset_id).order_by(RotableEvent.occurred_at.desc(),RotableEvent.id.desc())))

    def transition_rotable(self, asset_id: str, target_status: str, user: str, *, location_code: str = "", equipment_id: str = "", component_id: str = "", vendor: str = "", reference: str = "", note: str = "", expected_version: int | None = None):
        target_status=target_status.strip()
        allowed={
            "Stock":{"Installed","In Repair","Quarantine","Scrapped"},
            "Installed":{"Stock","In Repair","Quarantine","Scrapped"},
            "In Repair":{"Stock","Quarantine","Scrapped"},
            "Quarantine":{"Stock","In Repair","Scrapped"},
            "Scrapped":set(),
        }
        if target_status not in {"Stock","Installed","In Repair","Quarantine","Scrapped"}:raise ValueError("Invalid rotable lifecycle status.")
        with self.session() as s:
            stmt=select(RotableAsset).where(RotableAsset.asset_id==asset_id)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            row=s.scalar(stmt)
            if not row:raise ValueError("Rotable asset not found")
            if expected_version is not None and row.version!=expected_version:raise RuntimeError("CONFLICT: Rotable asset changed.")
            if target_status==row.status:return row
            if target_status not in allowed.get(row.status,set()):raise ValueError(f"Invalid rotable transition {row.status} → {target_status}.")
            if target_status=="Installed" and not equipment_id.strip():raise ValueError("Equipment ID is required when installing a rotable.")
            if target_status=="In Repair" and not vendor.strip():raise ValueError("Vendor is required when sending a rotable for repair.")
            previous=row.status;now=datetime.utcnow()
            row.status=target_status;row.version+=1
            if target_status=="Installed":
                row.equipment_id=equipment_id.strip();row.component_id=component_id.strip();row.current_location="";row.installed_at=now
            elif target_status=="In Repair":
                row.vendor=vendor.strip();row.repair_reference=reference.strip();row.sent_for_repair_at=now;row.equipment_id="";row.component_id=""
            elif target_status=="Stock":
                row.current_location=location_code.strip() or row.current_location;row.equipment_id="";row.component_id="";row.condition="Serviceable"
                if previous=="Installed":row.removed_at=now
                if previous=="In Repair":row.returned_at=now;row.repair_count+=1
            elif target_status=="Quarantine":
                row.current_location=location_code.strip() or row.current_location;row.equipment_id="";row.component_id="";row.condition="Quarantine"
            elif target_status=="Scrapped":
                row.equipment_id="";row.component_id="";row.condition="Scrapped"
            row.notes=note.strip() or row.notes
            s.add(RotableEvent(asset_id=asset_id,event_type="STATUS",from_status=previous,to_status=target_status,location_code=row.current_location,equipment_id=row.equipment_id,reference=reference.strip(),note=note.strip(),user=user,occurred_at=now))
            s.add(AuditLog(user=user,action="ROTABLE_TRANSITION",entity_type="ROTABLE",entity_key=asset_id,detail=json.dumps({"from":previous,"to":target_status,"equipment_id":equipment_id,"vendor":vendor,"reference":reference},sort_keys=True)))
            s.flush();return row

    def pm_kit_stage(self, task_id: int):
        with self.session() as s:return s.scalar(select(PMKitStage).where(PMKitStage.task_id==task_id))

    def set_pm_kit_stage(self, task_id: int, status: str, user: str, staging_location: str = "", note: str = "", expected_version: int | None = None):
        status=status.strip()
        if status not in {"Reserved","Staged","Issued","Returned","Completed"}:raise ValueError("Invalid PM kit stage status.")
        with self.session() as s:
            task=s.get(PMTask,task_id)
            if not task:raise ValueError("PM task not found")
            row=s.scalar(select(PMKitStage).where(PMKitStage.task_id==task_id))
            if row and expected_version is not None and row.version!=expected_version:raise RuntimeError("CONFLICT: PM kit stage changed.")
            if status in {"Staged","Issued"}:
                reservations=list(s.scalars(select(InventoryReservation).where(InventoryReservation.pm_task_id==task_id,InventoryReservation.status=="Reserved")))
                readiness=self.pm_task_readiness(task_id)
                if readiness["parts_status"]!="READY":raise ValueError("PM kit cannot be staged while required parts are short.")
                if not reservations and readiness["parts"]:raise ValueError("Reserve required parts before staging the PM kit.")
            now=datetime.utcnow()
            if not row:
                row=PMKitStage(task_id=task_id,status=status,staging_location=staging_location.strip(),note=note.strip());s.add(row)
            else:
                row.status=status;row.staging_location=staging_location.strip() or row.staging_location;row.note=note.strip() or row.note;row.version+=1
            if status=="Staged":row.staged_by=user;row.staged_at=now
            if status=="Issued":row.issued_by=user;row.issued_at=now
            s.add(AuditLog(user=user,action="PM_KIT_STAGE",entity_type="PM_TASK",entity_key=str(task_id),detail=json.dumps({"status":status,"location":row.staging_location,"note":note},sort_keys=True)))
            s.flush();return row

    def save_part_catalog(self, data: dict[str, Any], expected_version: int | None = None):
        payload=dict(data);part=str(payload.get("part_number","")).strip()
        if not part:raise ValueError("Part number is required.")
        payload["part_number"]=part
        with self.session() as s:
            row=s.scalar(select(PartCatalog).where(PartCatalog.part_number==part))
            if row:self._update_versioned(row,payload,expected_version,"Part catalog")
            else:row=PartCatalog(**payload);s.add(row)
            s.flush();return row

    def list_part_catalog(self, search_text: str = "", active_only: bool = False):
        with self.session() as s:
            stmt=select(PartCatalog).order_by(PartCatalog.part_number)
            if search_text:
                q=f"%{search_text}%"
                stmt=stmt.where(or_(
                    PartCatalog.part_number.ilike(q),PartCatalog.description.ilike(q),
                    PartCatalog.supplier.ilike(q),PartCatalog.supplier_part_number.ilike(q),
                    PartCatalog.barcode.ilike(q),
                ))
            if active_only:stmt=stmt.where(PartCatalog.active.is_(True))
            return list(s.scalars(stmt))

    def resolve_part_scan(self, value: str):
        code=(value or "").strip()
        if not code:return None
        with self.session() as s:
            catalog=s.scalar(select(PartCatalog).where(or_(
                PartCatalog.part_number==code,PartCatalog.barcode==code,PartCatalog.supplier_part_number==code
            )))
            if catalog:return catalog.part_number
            item=s.scalar(select(InventoryItem).where(InventoryItem.part_number==code))
            return item.part_number if item else None

    def save_part_alternate(self, part_number: str, alternate_part_number: str, user: str, approved: bool=True, note: str=""):
        part_number=part_number.strip();alternate_part_number=alternate_part_number.strip()
        if not part_number or not alternate_part_number:raise ValueError("Primary and alternate part numbers are required.")
        if part_number==alternate_part_number:raise ValueError("Alternate part must differ from the primary part.")
        with self.session() as s:
            row=s.scalar(select(PartAlternate).where(
                PartAlternate.part_number==part_number,PartAlternate.alternate_part_number==alternate_part_number
            ))
            if row:row.approved=bool(approved);row.note=note.strip()
            else:
                row=PartAlternate(part_number=part_number,alternate_part_number=alternate_part_number,approved=bool(approved),note=note.strip(),created_by=user)
                s.add(row)
            s.flush();return row

    def list_part_alternates(self, part_number: str = "", approved_only: bool = False):
        with self.session() as s:
            stmt=select(PartAlternate).order_by(PartAlternate.part_number,PartAlternate.alternate_part_number)
            if part_number:stmt=stmt.where(PartAlternate.part_number==part_number)
            if approved_only:stmt=stmt.where(PartAlternate.approved.is_(True))
            return list(s.scalars(stmt))

    def receive_inventory(self, part_number: str, location_code: str, qty: float, user: str, reference: str="", note: str=""):
        if qty<=0:raise ValueError("Received quantity must be positive.")
        self.assert_authorized(user,"inventory.edit")
        with self.session() as s:
            stmt=select(InventoryItem).where(InventoryItem.part_number==part_number,InventoryItem.location_code==location_code)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            item=s.scalar(stmt)
            if not item:
                catalog=s.scalar(select(PartCatalog).where(PartCatalog.part_number==part_number))
                item=InventoryItem(
                    part_number=part_number,description=catalog.description if catalog else "",
                    category=catalog.category if catalog else "",manufacturer=catalog.manufacturer if catalog else "",
                    quantity=0.0,min_quantity=0.0,unit="ea",condition="Available",location_code=location_code,
                );s.add(item);s.flush()
            item.quantity=float(item.quantity or 0)+float(qty);item.version+=1
            tx=InventoryTransaction(
                part_number=part_number,location_code=location_code,transaction_type="Receive",
                quantity=float(qty),user=user,note=" | ".join(x for x in [reference.strip(),note.strip()] if x),
            )
            s.add(tx);s.add(AuditLog(user=user,action="INVENTORY_RECEIVE",entity_type="PART",entity_key=f"{part_number}@{location_code}",detail=f"{qty:g} {reference}".strip()))
            s.flush();return item,tx

    def transfer_inventory(self, part_number: str, from_location: str, to_location: str, qty: float, user: str, note: str=""):
        if qty<=0:raise ValueError("Transfer quantity must be positive.")
        if from_location==to_location:raise ValueError("Source and destination must differ.")
        self.assert_authorized(user,"inventory.edit")
        with self.session() as s:
            stmt=select(InventoryItem).where(InventoryItem.part_number==part_number,InventoryItem.location_code==from_location)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            source=s.scalar(stmt)
            if not source or float(source.quantity or 0)<qty:raise ValueError("Insufficient source stock.")
            dest_stmt=select(InventoryItem).where(InventoryItem.part_number==part_number,InventoryItem.location_code==to_location)
            if self.url.startswith("postgresql"):dest_stmt=dest_stmt.with_for_update()
            dest=s.scalar(dest_stmt)
            if not dest:
                dest=InventoryItem(
                    part_number=part_number,description=source.description,category=source.category,
                    manufacturer=source.manufacturer,model=source.model,compatible_equipment=source.compatible_equipment,
                    quantity=0.0,min_quantity=0.0,unit=source.unit,condition=source.condition,
                    location_code=to_location,image_path=source.image_path,notes=source.notes,
                );s.add(dest);s.flush()
            source.quantity-=qty;source.version+=1;dest.quantity+=qty;dest.version+=1
            transfer_key=secrets.token_hex(6)
            out=InventoryTransaction(part_number=part_number,location_code=from_location,transaction_type="Transfer Out",quantity=-qty,user=user,note=f"{transfer_key} → {to_location} {note}".strip())
            inc=InventoryTransaction(part_number=part_number,location_code=to_location,transaction_type="Transfer In",quantity=qty,user=user,note=f"{transfer_key} ← {from_location} {note}".strip())
            s.add_all([out,inc]);s.flush();return source,dest

    def cycle_count_inventory(self, part_number: str, location_code: str, counted_qty: float, user: str, reason: str=""):
        if counted_qty<0:raise ValueError("Counted quantity cannot be negative.")
        self.assert_authorized(user,"inventory.edit")
        with self.session() as s:
            stmt=select(InventoryItem).where(InventoryItem.part_number==part_number,InventoryItem.location_code==location_code)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            item=s.scalar(stmt)
            if not item:raise ValueError("Inventory item not found.")
            previous=float(item.quantity or 0);delta=float(counted_qty)-previous
            item.quantity=float(counted_qty);item.version+=1
            tx=InventoryTransaction(
                part_number=part_number,location_code=location_code,transaction_type="Cycle Count",
                quantity=delta,user=user,note=f"Count {previous:g} → {counted_qty:g}. {reason}".strip(),
            )
            s.add(tx);s.add(AuditLog(user=user,action="INVENTORY_CYCLE_COUNT",entity_type="PART",entity_key=f"{part_number}@{location_code}",detail=tx.note))
            s.flush();return item,tx

    def inventory_reorder_queue(self) -> list[dict[str, Any]]:
        with self.session() as s:
            items=list(s.scalars(select(InventoryItem).where(InventoryItem.condition=="Available")))
            reservations=list(s.scalars(select(InventoryReservation).where(InventoryReservation.status=="Reserved")))
            catalog={x.part_number:x for x in s.scalars(select(PartCatalog))}
        reserved={}
        for row in reservations:
            reserved[(row.part_number,row.location_code)]=reserved.get((row.part_number,row.location_code),0.0)+float(row.quantity or 0)
            if not row.location_code:reserved[(row.part_number,"*")]=reserved.get((row.part_number,"*"),0.0)+float(row.quantity or 0)
        rows=[]
        for item in items:
            on_hand=float(item.quantity or 0);res=reserved.get((item.part_number,item.location_code),0.0)+reserved.get((item.part_number,"*"),0.0)
            available=max(0.0,on_hand-res);minimum=float(item.min_quantity or 0)
            if available>minimum:continue
            cat=catalog.get(item.part_number)
            rows.append({
                "part_number":item.part_number,"description":item.description,"location_code":item.location_code,
                "on_hand":on_hand,"reserved":res,"available":available,"min_quantity":minimum,
                "shortage_to_min":max(0.0,minimum-available),
                "suggested_order_qty":float(cat.reorder_qty or 0) if cat else 0.0,
                "supplier":cat.supplier if cat else "","supplier_part_number":cat.supplier_part_number if cat else "",
                "lead_time_days":cat.lead_time_days if cat else 0,
            })
        rows.sort(key=lambda x:(-x["shortage_to_min"],x["part_number"],x["location_code"]))
        return rows

    def pm_kit_status(self, task_id: int) -> dict[str, Any]:
        readiness=self.pm_task_readiness(task_id)
        reservations=[x for x in self.list_reservations() if x.pm_task_id==task_id]
        for part in readiness["parts"]:
            part["alternates"]=[x.alternate_part_number for x in self.list_part_alternates(part["part_number"],True)]
        readiness["reservations"]=[{
            "id":x.id,"part_number":x.part_number,"location_code":x.location_code,
            "quantity":x.quantity,"status":x.status,"reserved_by":x.reserved_by,
        } for x in reservations]
        return readiness

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

    def list_inventory_transactions(self, limit: int=500, equipment_id: str = ""):
        with self.session() as s:
            stmt=select(InventoryTransaction)
            if equipment_id:stmt=stmt.where(InventoryTransaction.equipment_id==equipment_id)
            return list(s.scalars(stmt.order_by(InventoryTransaction.created_at.desc()).limit(limit)))

    @staticmethod
    def _file_sha256(path: str) -> str:
        h=hashlib.sha256()
        with open(path,"rb") as fh:
            for chunk in iter(lambda:fh.read(1024*1024),b""):
                h.update(chunk)
        return h.hexdigest()

    def create_controlled_document(self, data: dict[str, Any], user: str, workstation: str = ""):
        payload=dict(data)
        payload["document_id"]=payload.get("document_id","").strip()
        payload["title"]=payload.get("title","").strip()
        if not payload["document_id"] or not payload["title"]:
            raise ValueError("Document ID and title are required.")
        with self.session() as s:
            if s.scalar(select(ControlledDocument).where(ControlledDocument.document_id==payload["document_id"])):
                raise ValueError("Controlled document ID already exists.")
            payload["created_by"]=user
            payload["status"]="Draft"
            payload["current_revision"]=""
            doc=ControlledDocument(**payload)
            s.add(doc)
            s.add(AuditLog(user=user,action="CONTROLLED_DOCUMENT_CREATE",entity_type="CONTROLLED_DOCUMENT",entity_key=payload["document_id"],workstation=workstation))
            s.flush()
            return doc

    def list_controlled_documents(self, entity_type: str = "", entity_key: str = ""):
        with self.session() as s:
            stmt=select(ControlledDocument).order_by(ControlledDocument.document_id)
            if entity_type:stmt=stmt.where(ControlledDocument.entity_type==entity_type)
            if entity_key:stmt=stmt.where(ControlledDocument.entity_key==entity_key)
            return list(s.scalars(stmt))

    def add_controlled_revision(
        self,
        document_id: str,
        revision: str,
        path: str,
        change_summary: str,
        user: str,
        workstation: str = "",
    ):
        revision=revision.strip()
        if not revision:
            raise ValueError("Revision is required.")
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        digest=self._file_sha256(path)
        with self.session() as s:
            doc=s.scalar(select(ControlledDocument).where(ControlledDocument.document_id==document_id))
            if not doc:raise ValueError("Controlled document not found")
            if s.scalar(select(ControlledDocumentRevision).where(ControlledDocumentRevision.document_id==document_id,ControlledDocumentRevision.revision==revision)):
                raise ValueError("That controlled document revision already exists.")
            row=ControlledDocumentRevision(
                document_id=document_id,revision=revision,path=path,file_sha256=digest,
                change_summary=change_summary.strip(),created_by=user,status="Draft",
            )
            s.add(row);s.flush()
            s.add(AuditLog(
                user=user,action="CONTROLLED_REVISION_CREATE",entity_type="CONTROLLED_DOCUMENT",
                entity_key=f"{document_id}:{revision}",
                detail=json.dumps({"sha256":digest,"path":path},sort_keys=True),workstation=workstation,
            ))
            return row

    def list_controlled_revisions(self, document_id: str):
        with self.session() as s:
            return list(s.scalars(
                select(ControlledDocumentRevision)
                .where(ControlledDocumentRevision.document_id==document_id)
                .order_by(ControlledDocumentRevision.created_at.desc(),ControlledDocumentRevision.id.desc())
            ))

    def approve_controlled_revision(
        self,
        revision_id: int,
        user: str,
        effective_at: datetime | None = None,
        expires_at: datetime | None = None,
        workstation: str = "",
        expected_version: int | None = None,
    ):
        now=datetime.utcnow()
        effective_at=effective_at or now
        if expires_at and expires_at<=effective_at:
            raise ValueError("Document expiry must be after its effective date.")
        with self.session() as s:
            stmt=select(ControlledDocumentRevision).where(ControlledDocumentRevision.id==revision_id)
            if self.url.startswith("postgresql"):stmt=stmt.with_for_update()
            row=s.scalar(stmt)
            if not row:raise ValueError("Controlled revision not found")
            if expected_version is not None and row.version!=expected_version:
                raise RuntimeError("CONFLICT: Controlled revision changed by another user.")
            if row.status!="Draft":raise ValueError("Only Draft revisions can be approved.")
            if row.created_by==user:raise ValueError("Independent approval required: revision author cannot approve their own revision.")
            if not os.path.isfile(row.path):raise FileNotFoundError(row.path)
            current_hash=self._file_sha256(row.path)
            if current_hash!=row.file_sha256:
                raise ValueError("Controlled file content changed after revision registration; create a new revision.")
            doc=s.scalar(select(ControlledDocument).where(ControlledDocument.document_id==row.document_id))
            if not doc:raise ValueError("Controlled document not found")
            for old in s.scalars(select(ControlledDocumentRevision).where(ControlledDocumentRevision.document_id==row.document_id,ControlledDocumentRevision.status=="Effective")):
                old.status="Superseded";old.version+=1
            row.status="Effective";row.approved_by=user;row.approved_at=now;row.effective_at=effective_at;row.expires_at=expires_at;row.version+=1
            doc.status="Effective";doc.current_revision=row.revision;doc.version+=1
            s.add(AuditLog(
                user=user,action="CONTROLLED_REVISION_APPROVE",entity_type="CONTROLLED_DOCUMENT",
                entity_key=f"{row.document_id}:{row.revision}",
                detail=json.dumps({"effective_at":effective_at.isoformat(),"expires_at":expires_at.isoformat() if expires_at else None,"sha256":row.file_sha256},sort_keys=True),
                workstation=workstation,
            ))
            s.flush();return row

    def reject_controlled_revision(self, revision_id: int, user: str, reason: str, workstation: str = "", expected_version: int | None = None):
        if not reason.strip():raise ValueError("Rejection reason is required.")
        with self.session() as s:
            row=s.get(ControlledDocumentRevision,revision_id)
            if not row:raise ValueError("Controlled revision not found")
            if expected_version is not None and row.version!=expected_version:raise RuntimeError("CONFLICT: Controlled revision changed by another user.")
            if row.status!="Draft":raise ValueError("Only Draft revisions can be rejected.")
            if row.created_by==user:raise ValueError("Independent review required.")
            row.status="Rejected";row.approved_by=user;row.approved_at=datetime.utcnow();row.change_summary=(row.change_summary+"\nREJECTED: "+reason.strip()).strip();row.version+=1
            s.add(AuditLog(user=user,action="CONTROLLED_REVISION_REJECT",entity_type="CONTROLLED_DOCUMENT",entity_key=f"{row.document_id}:{row.revision}",detail=reason.strip(),workstation=workstation))
            s.flush();return row

    def effective_controlled_revision(self, document_id: str):
        now=datetime.utcnow()
        with self.session() as s:
            return s.scalar(
                select(ControlledDocumentRevision)
                .where(
                    ControlledDocumentRevision.document_id==document_id,
                    ControlledDocumentRevision.status=="Effective",
                    ControlledDocumentRevision.effective_at<=now,
                    (ControlledDocumentRevision.expires_at.is_(None) | (ControlledDocumentRevision.expires_at>now)),
                )
                .order_by(ControlledDocumentRevision.effective_at.desc(),ControlledDocumentRevision.id.desc())
            )

    def verify_controlled_revision_file(self, revision_id: int) -> tuple[bool,str]:
        with self.session() as s:
            row=s.get(ControlledDocumentRevision,revision_id)
            if not row:return False,"Revision not found"
            if not os.path.isfile(row.path):return False,"File missing"
            digest=self._file_sha256(row.path)
            return digest==row.file_sha256,digest

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

    def equipment_activity_timeline(self, equipment_id: str, limit: int = 500) -> list[dict[str, Any]]:
        """Return the newest cross-domain equipment events without scanning full history.

        Each source query is independently ordered and bounded before the results
        are merged. This keeps Equipment 360 responsive even when a tool has
        100k+ alarms/events while preserving the existing unified timeline API.
        """
        cap=max(1,min(int(limit),5000))
        rows=[]
        def add(when,kind,key,summary,user="",status="",source=""):
            if when is None:return
            rows.append({
                "occurred_at":when,"kind":kind,"key":str(key),"summary":summary,
                "user":user or "","status":status or "","source":source or "",
            })
        with self.session() as s:
            state_events=list(s.scalars(
                select(EquipmentStateEvent)
                .where(EquipmentStateEvent.equipment_id==equipment_id)
                .order_by(EquipmentStateEvent.changed_at.desc(),EquipmentStateEvent.id.desc())
                .limit(cap)
            ))
            for e in state_events:
                add(e.changed_at,"STATE",e.event_key,f"{e.from_state or '—'} → {e.to_state} · {e.reason_code}: {e.reason_text}",e.changed_by,e.to_state,"Equipment state")

            tickets=list(s.scalars(
                select(Ticket)
                .where(Ticket.equipment_id==equipment_id)
                .order_by(Ticket.created_at.desc(),Ticket.id.desc())
                .limit(cap)
            ))
            for t in tickets:
                add(t.created_at,"INCIDENT",t.ticket_no,f"Created {t.priority} incident — {t.title}",t.created_by,t.status,"Ticket")
            ticket_events=s.execute(
                select(TicketStateEvent,Ticket)
                .join(Ticket,Ticket.ticket_no==TicketStateEvent.ticket_no)
                .where(Ticket.equipment_id==equipment_id)
                .order_by(TicketStateEvent.changed_at.desc(),TicketStateEvent.id.desc())
                .limit(cap)
            ).all()
            for e,_ticket in ticket_events:
                add(e.changed_at,"INCIDENT",e.ticket_no,f"{e.from_state or '—'} → {e.to_state} · {e.reason_code}: {e.note}",e.changed_by,e.to_state,"Ticket lifecycle")

            alarms=list(s.scalars(
                select(EquipmentAlarmEvent)
                .where(EquipmentAlarmEvent.equipment_id==equipment_id)
                .order_by(EquipmentAlarmEvent.occurred_at.desc(),EquipmentAlarmEvent.id.desc())
                .limit(cap)
            ))
            for a in alarms:
                add(a.occurred_at,"ALARM",a.event_key,f"{a.alarm_code} — {a.message}",a.acknowledged_by,a.state,a.source)
                if a.cleared_at:add(a.cleared_at,"ALARM",a.event_key,f"{a.alarm_code} cleared",a.acknowledged_by,"CLEARED",a.source)

            tasks=list(s.scalars(
                select(PMTask)
                .where(PMTask.equipment_id==equipment_id)
                .order_by(PMTask.scheduled_date.desc(),PMTask.id.desc())
                .limit(cap)
            ))
            for t in tasks:
                add(t.updated_at or t.scheduled_date or t.original_due_date,"PM",t.id,f"{t.pm_id} — {t.pm_name}",t.assigned_to,t.status,"PM task")
            executions=s.execute(
                select(PMExecution,PMTask)
                .join(PMTask,PMTask.id==PMExecution.task_id)
                .where(PMTask.equipment_id==equipment_id)
                .order_by(PMExecution.started_at.desc(),PMExecution.id.desc())
                .limit(cap)
            ).all()
            for ex,task in executions:
                label=f"{task.pm_id} — {task.pm_name}"
                add(ex.started_at,"PM",ex.task_id,f"Execution started: {label}",ex.started_by,ex.status,"PM execution")
                if ex.completed_at:add(ex.completed_at,"PM",ex.task_id,f"Execution completed: {label}",ex.completed_by,"Completed","PM execution")

            work_orders=list(s.scalars(
                select(WorkOrder)
                .where(WorkOrder.equipment_id==equipment_id)
                .order_by(WorkOrder.created_at.desc(),WorkOrder.id.desc())
                .limit(cap)
            ))
            for wo in work_orders:
                add(wo.created_at,"WORK_ORDER",wo.work_order_no,f"{wo.title}",wo.created_by,wo.status,"Work order")
            work_order_events=s.execute(
                select(WorkOrderEvent,WorkOrder)
                .join(WorkOrder,WorkOrder.work_order_no==WorkOrderEvent.work_order_no)
                .where(WorkOrder.equipment_id==equipment_id)
                .order_by(WorkOrderEvent.occurred_at.desc(),WorkOrderEvent.id.desc())
                .limit(cap)
            ).all()
            for ev,_wo in work_order_events:
                add(ev.occurred_at,"WORK_ORDER",ev.work_order_no,f"{ev.from_state or '—'} → {ev.to_state}: {ev.reason}",ev.changed_by,ev.to_state,"Work order lifecycle")

            work_logs=list(s.scalars(
                select(WorkLog)
                .where(WorkLog.equipment_id==equipment_id)
                .order_by(WorkLog.started_at.desc(),WorkLog.id.desc())
                .limit(cap)
            ))
            for w in work_logs:
                add(w.started_at,"WORK",w.id,f"{w.work_type} started · {w.entity_type}:{w.entity_key}",w.username,w.status,"Labor")
                if w.ended_at:add(w.ended_at,"WORK",w.id,f"{w.work_type} completed · {w.duration_minutes:.1f} min",w.username,"Completed","Labor")

            qualifications=list(s.scalars(
                select(QualificationRun)
                .where(QualificationRun.equipment_id==equipment_id)
                .order_by(QualificationRun.started_at.desc(),QualificationRun.id.desc())
                .limit(cap)
            ))
            for q in qualifications:
                add(q.started_at,"QUALIFICATION",q.run_no,f"{q.protocol_id} R{q.protocol_revision} qualification started",q.started_by,q.status,"Qualification")
                if q.submitted_at:add(q.submitted_at,"QUALIFICATION",q.run_no,"Qualification submitted",q.submitted_by,"Submitted","Qualification")
                if q.verified_at:add(q.verified_at,"QUALIFICATION",q.run_no,"Qualification verified",q.verified_by,"Verified","Qualification")
                if q.approved_at:add(q.approved_at,"QUALIFICATION",q.run_no,"Qualification approved",q.approved_by,"Approved","Qualification")

            releases=list(s.scalars(
                select(EquipmentRelease)
                .where(EquipmentRelease.equipment_id==equipment_id)
                .order_by(EquipmentRelease.requested_at.desc(),EquipmentRelease.id.desc())
                .limit(cap)
            ))
            for r in releases:
                add(r.requested_at,"RELEASE",r.id,"Release requested",r.requested_by,r.status,"Release")
                if r.verified_at:add(r.verified_at,"RELEASE",r.id,"Release verified",r.verified_by,"Verified","Release")
                if r.approved_at:add(r.approved_at,"RELEASE",r.id,"Equipment released",r.approved_by,"Approved / Released","Release")

            transactions=list(s.scalars(
                select(InventoryTransaction)
                .where(InventoryTransaction.equipment_id==equipment_id)
                .order_by(InventoryTransaction.created_at.desc(),InventoryTransaction.id.desc())
                .limit(cap)
            ))
            for tx in transactions:
                add(tx.created_at,"PART",tx.id,f"{tx.transaction_type} {tx.quantity:g} × {tx.part_number} @ {tx.location_code}",tx.user,tx.transaction_type,"Inventory")

            attachments=list(s.scalars(
                select(EntityAttachment)
                .where(EntityAttachment.equipment_id==equipment_id,EntityAttachment.active.is_(True))
                .order_by(EntityAttachment.created_at.desc(),EntityAttachment.id.desc())
                .limit(cap)
            ))
            for att in attachments:
                add(att.created_at,"EVIDENCE",att.attachment_key,f"{att.category}: {att.original_name} — {att.caption}".strip(" —"),att.created_by,"Attached",f"{att.entity_type}:{att.entity_key}")

        rows.sort(key=lambda x:x["occurred_at"],reverse=True)
        return rows[:cap]

    def reliability_summary(
        self,
        equipment_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict[str, Any]:
        end=end or datetime.utcnow()
        start=start or (end-timedelta(days=30))
        if end<=start:
            raise ValueError("Reliability period end must be after start.")
        with self.session() as s:
            eq=s.scalar(select(Equipment).where(Equipment.equipment_id==equipment_id))
            if not eq:
                raise ValueError("Equipment not found")
            before=s.scalar(
                select(EquipmentStateEvent)
                .where(EquipmentStateEvent.equipment_id==equipment_id,EquipmentStateEvent.changed_at<=start)
                .order_by(EquipmentStateEvent.changed_at.desc(),EquipmentStateEvent.id.desc())
            )
            events=list(s.scalars(
                select(EquipmentStateEvent)
                .where(
                    EquipmentStateEvent.equipment_id==equipment_id,
                    EquipmentStateEvent.changed_at>start,
                    EquipmentStateEvent.changed_at<=end,
                )
                .order_by(EquipmentStateEvent.changed_at,EquipmentStateEvent.id)
            ))
            if before:
                state=before.to_state
                effective_start=start
            elif events and events[0].reason_code=="INITIAL_STATE":
                state=events[0].to_state
                effective_start=events[0].changed_at
                events=events[1:]
            else:
                state="Available"
                effective_start=start

        cursor=effective_start
        total_downtime=0.0
        unplanned=0.0
        planned=0.0
        failure_count=0
        in_unplanned=STATE_CLASS.get(state)=="UNPLANNED_DOWNTIME"

        for event in events:
            seconds=max(0.0,(event.changed_at-cursor).total_seconds())
            cls=STATE_CLASS.get(state,"")
            if state in DOWNTIME_STATES:
                total_downtime+=seconds
                if cls=="UNPLANNED_DOWNTIME":
                    unplanned+=seconds
                elif cls=="PLANNED_DOWNTIME":
                    planned+=seconds

            new_unplanned=STATE_CLASS.get(event.to_state)=="UNPLANNED_DOWNTIME"
            if new_unplanned and not in_unplanned:
                failure_count+=1
            in_unplanned=new_unplanned
            state=event.to_state
            cursor=event.changed_at

        seconds=max(0.0,(end-cursor).total_seconds())
        cls=STATE_CLASS.get(state,"")
        if state in DOWNTIME_STATES:
            total_downtime+=seconds
            if cls=="UNPLANNED_DOWNTIME":
                unplanned+=seconds
            elif cls=="PLANNED_DOWNTIME":
                planned+=seconds

        period=max(0.0,(end-effective_start).total_seconds())
        uptime=max(0.0,period-total_downtime)
        hours=lambda sec: sec/3600.0
        availability=(uptime/period*100.0) if period else 100.0
        mttr=(hours(unplanned)/failure_count) if failure_count else 0.0
        mtbf=(hours(uptime)/failure_count) if failure_count else 0.0
        return {
            "equipment_id":equipment_id,
            "start":start,
            "end":end,
            "period_hours":hours(period),
            "downtime_hours":hours(total_downtime),
            "unplanned_downtime_hours":hours(unplanned),
            "planned_downtime_hours":hours(planned),
            "failure_count":failure_count,
            "mttr_hours":mttr,
            "mtbf_hours":mtbf,
            "availability_pct":availability,
            "current_state":eq.status,
        }

    def reliability_report(self, days: int = 30) -> list[dict[str, Any]]:
        days=max(1,min(int(days),3650))
        end=datetime.utcnow()
        start=end-timedelta(days=days)
        return [self.reliability_summary(eq.equipment_id,start,end) for eq in self.list_equipment()]

    def fleet_reliability_trend(self, days: int = 90, bucket_days: int = 7, equipment_ids: list[str] | None = None) -> list[dict[str,Any]]:
        days=max(1,min(int(days),3650));bucket_days=max(1,min(int(bucket_days),365))
        end=datetime.utcnow();start=end-timedelta(days=days)
        ids=list(equipment_ids or [x.equipment_id for x in self.list_equipment()])
        if not ids:return []
        rows=[];cursor=start
        while cursor<end:
            bucket_end=min(end,cursor+timedelta(days=bucket_days))
            metrics=[]
            for equipment_id in ids:
                try:metrics.append(self.reliability_summary(equipment_id,cursor,bucket_end))
                except Exception:continue
            if metrics:
                rows.append({
                    "start":cursor,"end":bucket_end,
                    "availability_pct":sum(float(x["availability_pct"]) for x in metrics)/len(metrics),
                    "unplanned_downtime_hours":sum(float(x["unplanned_downtime_hours"]) for x in metrics),
                    "planned_downtime_hours":sum(float(x["planned_downtime_hours"]) for x in metrics),
                    "failure_count":sum(int(x["failure_count"]) for x in metrics),
                    "equipment_count":len(metrics),
                })
            cursor=bucket_end
        return rows

    def compare_equipment(self, equipment_ids: list[str], days: int = 30) -> list[dict[str,Any]]:
        ids=[str(x).strip() for x in equipment_ids if str(x).strip()]
        if not ids:return []
        days=max(1,min(int(days),3650));end=datetime.utcnow();start=end-timedelta(days=days)
        rows=[]
        with self.session() as s:
            for equipment_id in ids:
                eq=s.scalar(select(Equipment).where(Equipment.equipment_id==equipment_id))
                if not eq:continue
                rel=self.reliability_summary(equipment_id,start,end)
                incidents=int(s.scalar(select(func.count()).select_from(Ticket).where(
                    Ticket.equipment_id==equipment_id,Ticket.created_at>=start
                )) or 0)
                active_alarms=int(s.scalar(select(func.count()).select_from(EquipmentAlarmEvent).where(
                    EquipmentAlarmEvent.equipment_id==equipment_id,EquipmentAlarmEvent.state=="ACTIVE"
                )) or 0)
                overdue_pm=int(s.scalar(select(func.count()).select_from(PMTask).where(
                    PMTask.equipment_id==equipment_id,
                    ((PMTask.status=="Overdue") | (
                        PMTask.status.notin_(["Completed","Cancelled"]) &
                        PMTask.original_due_date.is_not(None) &
                        (PMTask.original_due_date<end)
                    ))
                )) or 0)
                rows.append({
                    "equipment_id":equipment_id,"name":eq.name,"equipment_type":eq.equipment_type,"area":eq.area,
                    "current_state":eq.status,"availability_pct":rel["availability_pct"],"failure_count":rel["failure_count"],
                    "unplanned_downtime_hours":rel["unplanned_downtime_hours"],"planned_downtime_hours":rel["planned_downtime_hours"],
                    "mttr_hours":rel["mttr_hours"],"mtbf_hours":rel["mtbf_hours"],"incidents":incidents,
                    "active_alarms":active_alarms,"overdue_pm":overdue_pm,
                })
        return rows

    def meter_trend(self, equipment_id: str, meter_code: str, days: int = 30, limit: int = 5000) -> list[dict[str,Any]]:
        days=max(1,min(int(days),3650));start=datetime.utcnow()-timedelta(days=days)
        with self.session() as s:
            rows=list(s.scalars(
                select(MeterReading)
                .where(
                    MeterReading.equipment_id==equipment_id,
                    MeterReading.meter_code==meter_code,
                    MeterReading.recorded_at>=start,
                )
                .order_by(MeterReading.recorded_at,MeterReading.id)
                .limit(max(1,min(int(limit),10000)))
            ))
        return [{"recorded_at":x.recorded_at,"value":float(x.value),"reading_type":x.reading_type,"note":x.note,"recorded_by":x.recorded_by} for x in rows]

    def engineering_analytics(self, days: int = 30) -> dict[str, Any]:
        days=max(1,min(int(days),3650))
        end=datetime.utcnow();start=end-timedelta(days=days)
        reliability=self.reliability_report(days)
        alarm_pareto=self.alarm_pareto(days)
        with self.session() as s:
            tickets=list(s.scalars(select(Ticket).where(Ticket.created_at>=start)))
            open_tickets=list(s.scalars(select(Ticket).where(Ticket.status.notin_(["Closed","Cancelled"]))))
            active_alarms=list(s.scalars(select(EquipmentAlarmEvent).where(EquipmentAlarmEvent.state=="ACTIVE")))
            pm_tasks=list(s.scalars(select(PMTask).where(
                PMTask.original_due_date.is_not(None),
                PMTask.original_due_date>=start,
                PMTask.original_due_date<=end,
            )))
        ticket_count={};open_count={};critical_open={}
        for row in tickets:ticket_count[row.equipment_id]=ticket_count.get(row.equipment_id,0)+1
        for row in open_tickets:
            open_count[row.equipment_id]=open_count.get(row.equipment_id,0)+1
            if row.priority in {"P1","P2"}:critical_open[row.equipment_id]=critical_open.get(row.equipment_id,0)+1
        alarm_active={}
        for row in active_alarms:alarm_active[row.equipment_id]=alarm_active.get(row.equipment_id,0)+1
        tool_matrix=[]
        for rel in reliability:
            equipment_id=rel["equipment_id"]
            tool_matrix.append({
                "equipment_id":equipment_id,
                "availability_pct":rel["availability_pct"],
                "failure_count":rel["failure_count"],
                "unplanned_downtime_hours":rel["unplanned_downtime_hours"],
                "planned_downtime_hours":rel["planned_downtime_hours"],
                "mttr_hours":rel["mttr_hours"],
                "mtbf_hours":rel["mtbf_hours"],
                "incidents_period":ticket_count.get(equipment_id,0),
                "open_incidents":open_count.get(equipment_id,0),
                "critical_open":critical_open.get(equipment_id,0),
                "active_alarms":alarm_active.get(equipment_id,0),
                "current_state":rel["current_state"],
            })
        tool_matrix.sort(key=lambda x:(-x["unplanned_downtime_hours"],-x["failure_count"],x["availability_pct"],x["equipment_id"]))
        due=len(pm_tasks);completed=sum(1 for x in pm_tasks if x.status=="Completed")
        overdue=sum(1 for x in pm_tasks if x.status=="Overdue" or (x.status not in {"Completed","Cancelled"} and x.original_due_date and x.original_due_date<end))
        deferred=sum(1 for x in pm_tasks if x.status=="Deferred")
        compliance_pct=(completed/due*100.0) if due else 100.0
        incident_by_equipment={}
        for row in tickets:incident_by_equipment[row.equipment_id]=incident_by_equipment.get(row.equipment_id,0)+1
        incident_pareto=[
            {"equipment_id":key,"count":value}
            for key,value in sorted(incident_by_equipment.items(),key=lambda kv:(-kv[1],kv[0]))
        ]
        return {
            "days":days,"start":start,"end":end,
            "reliability":reliability,"tool_matrix":tool_matrix,
            "alarm_pareto":alarm_pareto,"incident_pareto":incident_pareto,
            "pm":{"due":due,"completed":completed,"overdue":overdue,"deferred":deferred,"compliance_pct":compliance_pct},
        }

    def fab_shift_activity(
        self,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        *,
        building: str = "",
        floor: str = "",
        area: str = "",
    ) -> dict[str,Any]:
        """Return work completed/recovered during a reporting window for shift handoff."""
        end_at=end_at or datetime.utcnow()
        start_at=start_at or end_at.replace(hour=0,minute=0,second=0,microsecond=0)
        with self.session() as s:
            eq_stmt=select(Equipment)
            if building:eq_stmt=eq_stmt.where(Equipment.building==building)
            if floor:eq_stmt=eq_stmt.where(Equipment.floor==floor)
            if area:eq_stmt=eq_stmt.where(Equipment.area==area)
            equipment=list(s.scalars(eq_stmt))
            ids={x.equipment_id for x in equipment}
            if not ids:return {"start_at":start_at,"end_at":end_at,"recovered_tickets":[],"completed_pm":[],"completed_work_orders":[]}

            ticket_events=s.execute(
                select(TicketStateEvent,Ticket)
                .join(Ticket,Ticket.ticket_no==TicketStateEvent.ticket_no)
                .where(
                    Ticket.equipment_id.in_(ids),
                    TicketStateEvent.changed_at>=start_at,
                    TicketStateEvent.changed_at<=end_at,
                    TicketStateEvent.to_state.in_(["Resolved","Closed"]),
                )
                .order_by(TicketStateEvent.changed_at.desc())
            ).all()
            pm_rows=s.execute(
                select(PMExecution,PMTask)
                .join(PMTask,PMTask.id==PMExecution.task_id)
                .where(
                    PMTask.equipment_id.in_(ids),
                    PMExecution.completed_at.is_not(None),
                    PMExecution.completed_at>=start_at,
                    PMExecution.completed_at<=end_at,
                )
                .order_by(PMExecution.completed_at.desc())
            ).all()
            wo_rows=list(s.scalars(select(WorkOrder).where(
                WorkOrder.equipment_id.in_(ids),
                WorkOrder.completed_at.is_not(None),
                WorkOrder.completed_at>=start_at,
                WorkOrder.completed_at<=end_at,
            ).order_by(WorkOrder.completed_at.desc())))
        return {
            "start_at":start_at,"end_at":end_at,
            "recovered_tickets":[{
                "ticket_no":ticket.ticket_no,"equipment_id":ticket.equipment_id,"title":ticket.title,
                "priority":ticket.priority,"owner":event.owner or ticket.owner,
                "completed_at":event.changed_at,"note":event.note,
                "final_fix":ticket.corrective_action or ticket.root_cause,
            } for event,ticket in ticket_events],
            "completed_pm":[{
                "task_id":task.id,"equipment_id":task.equipment_id,"pm_id":task.pm_id,
                "pm_name":task.pm_name,"completed_at":execution.completed_at,
                "completed_by":execution.completed_by,
            } for execution,task in pm_rows],
            "completed_work_orders":[{
                "work_order_no":wo.work_order_no,"equipment_id":wo.equipment_id,"title":wo.title,
                "completed_at":wo.completed_at,"owner":wo.owner,
            } for wo in wo_rows],
        }

    def fab_health_snapshot(
        self,
        building: str = "",
        floor: str = "",
        area: str = "",
    ) -> list[dict[str,Any]]:
        """Return one batched management snapshot for the plant/floor map."""
        now=datetime.utcnow()
        with self.session() as s:
            stmt=select(Equipment)
            if building:stmt=stmt.where(Equipment.building==building)
            if floor:stmt=stmt.where(Equipment.floor==floor)
            if area:stmt=stmt.where(Equipment.area==area)
            equipment=list(s.scalars(stmt.order_by(Equipment.area,Equipment.line_cell,Equipment.equipment_id)))
            ids=[x.equipment_id for x in equipment]
            if not ids:return []

            tickets=list(s.scalars(select(Ticket).where(
                Ticket.equipment_id.in_(ids),Ticket.status.notin_(["Closed","Cancelled"])
            )))
            alarms=list(s.scalars(select(EquipmentAlarmEvent).where(
                EquipmentAlarmEvent.equipment_id.in_(ids),EquipmentAlarmEvent.state=="ACTIVE"
            )))
            pm=list(s.scalars(select(PMTask).where(
                PMTask.equipment_id.in_(ids),PMTask.status.notin_(["Completed","Cancelled"])
            )))
            work_orders=list(s.scalars(select(WorkOrder).where(
                WorkOrder.equipment_id.in_(ids),WorkOrder.status.notin_(["Completed","Cancelled"])
            )))
            task_ids=[x.id for x in pm]
            schedules={x.task_id:x for x in s.scalars(select(PMTaskSchedule).where(
                PMTaskSchedule.task_id.in_(task_ids)
            ))} if task_ids else {}
            ticket_nos=[x.ticket_no for x in tickets]
            lot_links=list(s.scalars(select(EntityLotLink).where(
                EntityLotLink.entity_type=="TICKET",EntityLotLink.entity_key.in_(ticket_nos)
            ))) if ticket_nos else []
            actions=list(s.scalars(select(IncidentAction).where(
                IncidentAction.ticket_no.in_(ticket_nos),
                IncidentAction.status.notin_(["Completed","Verified","Closed","Cancelled"]),
            ).order_by(IncidentAction.due_at.asc().nullslast(),IncidentAction.id))) if ticket_nos else []
            active_executions=list(s.scalars(select(PMExecution).where(
                PMExecution.task_id.in_(task_ids),PMExecution.status!="Completed"
            ))) if task_ids else []
            execution_ids=[x.id for x in active_executions]
            abnormal_results=list(s.scalars(select(PMResult).where(
                PMResult.execution_id.in_(execution_ids),
                PMResult.result.in_(["SPECIFICATION FAILURE","CONTROL FAILURE","FAIL","INVALID"]),
            ))) if execution_ids else []

        by_ticket={};by_alarm={};by_pm={};by_wo={};lots_by_ticket={};actions_by_ticket={}
        for x in tickets:by_ticket.setdefault(x.equipment_id,[]).append(x)
        for x in alarms:by_alarm.setdefault(x.equipment_id,[]).append(x)
        for x in pm:by_pm.setdefault(x.equipment_id,[]).append(x)
        for x in work_orders:by_wo.setdefault(x.equipment_id,[]).append(x)
        for x in lot_links:lots_by_ticket.setdefault(x.entity_key,[]).append(x.lot_number)
        for x in actions:actions_by_ticket.setdefault(x.ticket_no,[]).append(x)
        task_by_execution={x.id:x.task_id for x in active_executions}
        abnormal_task_ids={task_by_execution.get(x.execution_id) for x in abnormal_results}
        abnormal_task_ids.discard(None)

        priority_rank={"P1":0,"P2":1,"P3":2,"P4":3}
        rows=[]
        for eq in equipment:
            eq_tickets=by_ticket.get(eq.equipment_id,[])
            eq_tickets.sort(key=lambda x:(priority_rank.get((x.priority or "").upper(),9),-(x.created_at.timestamp() if x.created_at else 0)))
            eq_alarms=by_alarm.get(eq.equipment_id,[])
            eq_pm=by_pm.get(eq.equipment_id,[])
            eq_wo=by_wo.get(eq.equipment_id,[])
            active_pm=next((x for x in eq_pm if x.status=="In Progress"),None)
            effective_status="PM" if active_pm and eq.status not in {"Down","Hold","Waiting Parts","Waiting Vendor","Restricted","Offline","Decommissioned"} else eq.status
            health=classify_health(
                effective_status,
                ticket_priorities=[x.priority for x in eq_tickets],
                alarm_severities=[x.severity for x in eq_alarms],
                abnormal_pm=any(x.id in abnormal_task_ids for x in eq_pm),
            )
            current_issue=eq_tickets[0] if eq_tickets else None
            lots=[]
            for ticket in eq_tickets:
                for lot in lots_by_ticket.get(ticket.ticket_no,[]):
                    if lot not in lots:lots.append(lot)
            current_action=""
            if current_issue:
                acts=actions_by_ticket.get(current_issue.ticket_no,[])
                if acts:current_action=acts[0].description
                elif current_issue.corrective_action:current_action=current_issue.corrective_action
                else:current_action=current_issue.description
            next_pm=None;next_pm_at=None
            for task in eq_pm:
                schedule=schedules.get(task.id)
                when=(schedule.scheduled_start_at if schedule else None) or task.scheduled_date or task.original_due_date
                if when and (next_pm_at is None or when<next_pm_at):
                    next_pm=task;next_pm_at=when
            owner=(current_issue.owner if current_issue and current_issue.owner else "") or (active_pm.assigned_to if active_pm and active_pm.assigned_to else "") or eq.owner
            rows.append({
                "equipment_id":eq.equipment_id,"name":eq.name,"equipment_type":eq.equipment_type,
                "building":eq.building,"floor":eq.floor,"area":eq.area,"line_cell":eq.line_cell,
                "map_x":eq.map_x,"map_y":eq.map_y,"equipment_status":eq.status,
                "disposition":eq.disposition,"criticality":eq.criticality,"owner":owner,
                "health":health,"health_rank":health_rank(health),
                "active_alarm_count":len(eq_alarms),"open_ticket_count":len(eq_tickets),
                "open_work_order_count":len(eq_wo),"open_pm_count":len(eq_pm),
                "active_pm_task_id":active_pm.id if active_pm else None,
                "active_pm_id":active_pm.pm_id if active_pm else "",
                "current_issue_no":current_issue.ticket_no if current_issue else "",
                "current_issue_title":current_issue.title if current_issue else "",
                "current_issue_priority":current_issue.priority if current_issue else "",
                "current_action":current_action or "",
                "lots":lots,
                "next_pm_task_id":next_pm.id if next_pm else None,
                "next_pm_id":next_pm.pm_id if next_pm else "",
                "next_pm_at":next_pm_at,
                "next_pm_within_24h":bool(next_pm_at and now<=next_pm_at<=now+timedelta(hours=24)),
                "alarm_codes":[x.alarm_code for x in eq_alarms[:5]],
                "ticket_numbers":[x.ticket_no for x in eq_tickets[:5]],
                "version":eq.version,
            })
        return rows

    def dashboard_counts(self):
        with self.session() as s:
            c=lambda model,*w: int(s.scalar(select(func.count()).select_from(model).where(*w)) or 0)
            return {
                "equipment_total":c(Equipment), "equipment_down":c(Equipment,Equipment.status=="Down"),
                "equipment_hold":c(Equipment,Equipment.disposition.ilike("%Hold%")),
                "pm_open":c(PMTask,PMTask.status.in_(["Pending","Scheduled","In Progress","Overdue"])),
                "pm_overdue":c(PMTask,PMTask.status=="Overdue"),
                "tickets_open":c(Ticket,Ticket.status.notin_(["Closed","Cancelled"])),
                "alarms_active":c(EquipmentAlarmEvent,EquipmentAlarmEvent.state=="ACTIVE"),
                "tickets_critical":c(Ticket,Ticket.priority.in_(["P1","P2"]),Ticket.status.notin_(["Closed","Cancelled"])),
                "inventory_low":c(InventoryItem,InventoryItem.quantity<=InventoryItem.min_quantity),
                "endorsements_open":c(Endorsement,Endorsement.status.in_(["Open","Acknowledged"])),
                "dispositions_active":c(Disposition,Disposition.active.is_(True)),
                "release_pending":c(EquipmentRelease,EquipmentRelease.status.in_(["Pending Verification","Verified","Verification Failed"])),
                "reservations_active":c(InventoryReservation,InventoryReservation.status=="Reserved"),
            }
