from __future__ import annotations

import hashlib
import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, create_engine, func, inspect, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from domain import (
    DOWNTIME_STATES, EQUIPMENT_STATES, STATE_CLASS, TICKET_STATES,
    validate_ticket_transition, validate_transition,
)


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


class TicketEscalationEvent(Base):
    __tablename__ = "ticket_escalation_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(100), index=True)
    from_level: Mapped[int] = mapped_column(Integer, default=0)
    to_level: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    user: Mapped[str] = mapped_column(String(120), default="system")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


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
    "Manager": {"view", "workflow.override", "worklog.edit", "qualification.edit", "qualification.execute", "qualification.verify", "qualification.approve", "equipment.meter.record", "equipment.edit", "equipment.transition", "equipment.component.edit", "pm.edit", "pm.execute", "pm.approve", "pm.defer", "pm.defer.approve", "ticket.edit", "disposition.edit", "release.approve", "endorsement.edit", "inventory.edit", "inventory.reserve", "document.link", "report.view"},
    "Supervisor": {"view", "worklog.edit", "qualification.execute", "qualification.verify", "qualification.approve", "equipment.meter.record", "equipment.edit", "equipment.transition", "equipment.component.edit", "pm.edit", "pm.execute", "pm.defer", "pm.defer.approve", "ticket.edit", "disposition.edit", "release.verify", "endorsement.edit", "inventory.edit", "inventory.reserve", "document.link", "report.view"},
    "Equipment Engineer": {"view", "worklog.edit", "qualification.edit", "qualification.execute", "qualification.verify", "equipment.meter.record", "equipment.edit", "equipment.transition", "equipment.component.edit", "pm.edit", "pm.execute", "pm.defer", "ticket.edit", "disposition.edit", "release.verify", "endorsement.edit", "inventory.edit", "inventory.reserve", "document.link", "report.view"},
    "Maintenance": {"view", "worklog.edit", "qualification.execute", "equipment.meter.record", "equipment.component.edit", "pm.execute", "pm.defer", "ticket.edit", "endorsement.edit", "inventory.consume", "inventory.reserve", "document.link"},
    "Technician": {"view", "worklog.edit", "equipment.meter.record", "pm.execute", "ticket.edit", "inventory.consume", "document.link"},
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

    @staticmethod
    def _migration_checksum(revision: str, description: str) -> str:
        return hashlib.sha256(f"{revision}|{description}".encode("utf-8")).hexdigest()

    def _migration_plan(self):
        return [
            ("20260923_001","Create additive production-core tables",lambda: [
                table.create(self.engine,checkfirst=True) for table in Base.metadata.sorted_tables
            ]),
            ("20260923_002","Create operational event and lookup indexes",self._migration_indexes),
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
            s.flush();return row

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
            ))

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
                self._snapshot_pm_specs(s, ex, task)
                self._snapshot_pm_requirements(s, ex, task)
                s.flush()
                self._validate_pm_certifications(s,ex.id,user)
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
            return item

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

    def list_tickets(self):
        with self.session() as s: return list(s.scalars(select(Ticket).order_by(Ticket.created_at.desc())))

    def save_ticket(
        self,
        data: dict[str, Any],
        expected_version: int | None = None,
        workstation: str = "",
    ):
        payload = dict(data)
        with self.session() as s:
            item = s.scalar(select(Ticket).where(Ticket.ticket_no == payload["ticket_no"]))
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
                item = Ticket(**payload)
                s.add(item)
                s.add(TicketStateEvent(
                    ticket_no=payload["ticket_no"],
                    from_state="",
                    to_state="Open",
                    reason_code="INITIAL_STATE",
                    note="Issue ticket created",
                    owner=payload.get("owner", ""),
                    changed_by=payload.get("created_by", ""),
                    workstation=workstation,
                ))
            s.flush()
            return item

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

    def list_dispositions(self, active_only: bool = False):
        with self.session() as s:
            stmt=select(Disposition).order_by(Disposition.effective_at.desc())
            if active_only: stmt=stmt.where(Disposition.active.is_(True))
            return list(s.scalars(stmt))

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
            run_no=run_no.strip() or f"QUAL-{equipment_id}-{datetime.utcnow():%Y%m%d%H%M%S%f}"
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

    def list_release_requests(self):
        with self.session() as s: return list(s.scalars(select(EquipmentRelease).order_by(EquipmentRelease.requested_at.desc())))

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
