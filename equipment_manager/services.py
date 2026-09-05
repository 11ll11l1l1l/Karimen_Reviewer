from __future__ import annotations

import math
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


ALIASES = {
    "equipment_id": ["equipment id", "equipment_id", "eq id", "tool id", "machine id", "asset id"],
    "pm_id": ["pm id", "pm_id", "pm code", "maintenance id"],
    "pm_name": ["pm name", "pm", "maintenance", "activity name"],
    "original_due_date": ["original due date", "due date", "due", "pm due"],
    "scheduled_date": ["scheduled date", "schedule date", "planned date"],
    "last_completion_date": ["last completion date", "last pm", "last completed", "completion date"],
    "status": ["status", "pm status"],
    "assigned_to": ["assigned", "assigned to", "owner", "technician"],
    "estimated_hours": ["estimated hours", "hours", "duration hr", "duration hours"],
    "priority": ["priority"],
    "deferral_reason": ["deferral reason", "reason", "remarks", "comments"],
    "sop_path": ["sop", "sop path", "procedure path"],
    "report_path": ["report", "report path"],
    "step_no": ["step", "step no", "step number", "item", "no"],
    "activity": ["activity", "step activity", "check item", "procedure", "description"],
    "method": ["method", "measurement method", "check method"],
    "spec": ["spec", "specification", "criteria", "acceptance", "control spec"],
    "unit": ["unit", "units"],
    "target": ["target", "nominal"],
    "warning_low": ["warning low", "wl", "warn low"],
    "warning_high": ["warning high", "wh", "warn high"],
    "control_low": ["control low", "cl", "lcl", "control lower"],
    "control_high": ["control high", "ch", "ucl", "control upper"],
    "spec_low": ["spec low", "lsl", "lower spec", "minimum"],
    "spec_high": ["spec high", "usl", "upper spec", "maximum"],
    "reaction_plan": ["reaction plan", "reaction", "out of spec action"],
    "sop_page": ["sop page", "page"],
    "sop_section": ["sop section", "section"],
}


def normalize_col(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower().replace("_", " "))


def auto_mapping(columns: list[str]) -> dict[str, str]:
    normalized = {normalize_col(c): c for c in columns}
    result: dict[str, str] = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            if normalize_col(alias) in normalized:
                result[target] = normalized[normalize_col(alias)]
                break
    return result


def read_table(path: str, sheet_name: str | int | None = 0) -> pd.DataFrame:
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    return pd.read_excel(path, sheet_name=sheet_name)


def workbook_sheets(path: str) -> list[str]:
    if Path(path).suffix.lower() == ".csv":
        return ["CSV"]
    return list(pd.ExcelFile(path).sheet_names)


def clean_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def parse_date(value: Any) -> datetime | None:
    if value is None or clean_text(value) == "":
        return None
    try:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except Exception:
        return None


def parse_float(value: Any) -> float | None:
    if value is None or clean_text(value) == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


@dataclass
class ParsedSpec:
    input_type: str = "Text"
    target: float | None = None
    spec_low: float | None = None
    spec_high: float | None = None
    acceptance_text: str = ""
    ambiguous: bool = False


def parse_specification(text: Any) -> ParsedSpec:
    raw = clean_text(text)
    if not raw:
        return ParsedSpec()
    s = raw.replace("−", "-").replace("–", "-").replace("—", "-").replace("＋", "+").strip()
    lowered = s.lower()

    if lowered in {"ok", "pass", "no damage", "no leak", "good", "acceptable"} or any(
        token in lowered for token in ["no damage", "no leak", "visual"]
    ):
        return ParsedSpec(input_type="Pass/Fail", acceptance_text=raw)

    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*(?:±|\+/-)\s*(\d+(?:\.\d+)?)\s*", s)
    if m:
        target = float(m.group(1)); tol = float(m.group(2))
        return ParsedSpec(input_type="Numeric", target=target, spec_low=target - tol, spec_high=target + tol)

    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*(?:-|~|to)\s*(-?\d+(?:\.\d+)?)\s*", lowered)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        return ParsedSpec(input_type="Numeric", spec_low=min(lo, hi), spec_high=max(lo, hi))

    m = re.fullmatch(r"\s*(?:<=|≤)\s*(-?\d+(?:\.\d+)?)\s*", s)
    if m:
        return ParsedSpec(input_type="Numeric", spec_high=float(m.group(1)))
    m = re.fullmatch(r"\s*(?:>=|≥)\s*(-?\d+(?:\.\d+)?)\s*", s)
    if m:
        return ParsedSpec(input_type="Numeric", spec_low=float(m.group(1)))
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*(?:max|maximum)\s*", lowered)
    if m:
        return ParsedSpec(input_type="Numeric", spec_high=float(m.group(1)))
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*(?:min|minimum)\s*", lowered)
    if m:
        return ParsedSpec(input_type="Numeric", spec_low=float(m.group(1)))
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*", s)
    if m:
        val = float(m.group(1))
        return ParsedSpec(input_type="Numeric", target=val)

    if any(word in lowered for word in ["approx", "about", "around", "typ", "reference"]):
        return ParsedSpec(input_type="Text", acceptance_text=raw, ambiguous=True)
    return ParsedSpec(input_type="Text", acceptance_text=raw)


def dataframe_to_pm_backlog(df: pd.DataFrame, mapping: dict[str, str]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for idx, row in df.iterrows():
        eq = clean_text(row.get(mapping.get("equipment_id", "")))
        pm_id = clean_text(row.get(mapping.get("pm_id", ""))) or clean_text(row.get(mapping.get("pm_name", "")))
        pm_name = clean_text(row.get(mapping.get("pm_name", ""))) or pm_id
        if not eq or not pm_id:
            errors.append(f"Row {idx + 2}: missing Equipment ID or PM ID/Name")
            continue
        data = {
            "equipment_id": eq,
            "pm_id": pm_id,
            "pm_name": pm_name,
            "original_due_date": parse_date(row.get(mapping.get("original_due_date", ""))),
            "scheduled_date": parse_date(row.get(mapping.get("scheduled_date", ""))),
            "last_completion_date": parse_date(row.get(mapping.get("last_completion_date", ""))),
            "status": clean_text(row.get(mapping.get("status", ""))) or "Pending",
            "assigned_to": clean_text(row.get(mapping.get("assigned_to", ""))),
            "estimated_hours": parse_float(row.get(mapping.get("estimated_hours", ""))) or 0.0,
            "priority": clean_text(row.get(mapping.get("priority", ""))) or "Normal",
            "deferral_reason": clean_text(row.get(mapping.get("deferral_reason", ""))),
            "sop_path": clean_text(row.get(mapping.get("sop_path", ""))),
            "report_path": clean_text(row.get(mapping.get("report_path", ""))),
        }
        if data["status"].lower() in {"open", "pending"} and data["original_due_date"] and data["original_due_date"] < datetime.now():
            data["status"] = "Overdue"
        rows.append(data)
    return rows, errors


def dataframe_to_pm_specs(df: pd.DataFrame, mapping: dict[str, str], default_pm_id: str = "") -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for idx, row in df.iterrows():
        pm_id = clean_text(row.get(mapping.get("pm_id", ""))) or default_pm_id
        step_val = row.get(mapping.get("step_no", ""))
        try:
            step_no = int(float(step_val)) if clean_text(step_val) else idx + 1
        except Exception:
            step_no = idx + 1
        activity = clean_text(row.get(mapping.get("activity", "")))
        if not pm_id or not activity:
            warnings.append(f"Row {idx + 2}: missing PM ID or activity")
            continue

        parsed = parse_specification(row.get(mapping.get("spec", ""))) if mapping.get("spec") else ParsedSpec()
        if parsed.ambiguous:
            warnings.append(f"Row {idx + 2}: ambiguous specification kept as text: {parsed.acceptance_text}")

        def mapped_float(key: str, fallback: float | None = None) -> float | None:
            if mapping.get(key):
                val = parse_float(row.get(mapping[key]))
                return fallback if val is None else val
            return fallback

        data = {
            "pm_id": pm_id,
            "step_no": step_no,
            "activity": activity,
            "method": clean_text(row.get(mapping.get("method", ""))),
            "input_type": parsed.input_type,
            "unit": clean_text(row.get(mapping.get("unit", ""))),
            "target": mapped_float("target", parsed.target),
            "warning_low": mapped_float("warning_low"),
            "warning_high": mapped_float("warning_high"),
            "control_low": mapped_float("control_low"),
            "control_high": mapped_float("control_high"),
            "spec_low": mapped_float("spec_low", parsed.spec_low),
            "spec_high": mapped_float("spec_high", parsed.spec_high),
            "acceptance_text": parsed.acceptance_text,
            "reaction_plan": clean_text(row.get(mapping.get("reaction_plan", ""))),
            "sop_path": clean_text(row.get(mapping.get("sop_path", ""))),
            "sop_page": clean_text(row.get(mapping.get("sop_page", ""))),
            "sop_section": clean_text(row.get(mapping.get("sop_section", ""))),
        }
        if data["control_low"] is not None and data["control_high"] is not None and data["control_low"] > data["control_high"]:
            warnings.append(f"Row {idx + 2}: control low is above control high")
        if data["spec_low"] is not None and data["spec_high"] is not None and data["spec_low"] > data["spec_high"]:
            warnings.append(f"Row {idx + 2}: spec low is above spec high")
        rows.append(data)
    return rows, warnings


def evaluate_measurement(value: float, spec: dict[str, float | None]) -> str:
    sl, sh = spec.get("spec_low"), spec.get("spec_high")
    cl, ch = spec.get("control_low"), spec.get("control_high")
    wl, wh = spec.get("warning_low"), spec.get("warning_high")
    if sl is not None and value < sl or sh is not None and value > sh:
        return "SPEC FAILURE"
    if cl is not None and value < cl or ch is not None and value > ch:
        return "CONTROL FAILURE"
    if wl is not None and value < wl or wh is not None and value > wh:
        return "WARNING"
    return "NORMAL"


def calculate_next_due(last_due: datetime, completion: datetime, value: float, unit: str, basis: str = "original") -> datetime:
    start = last_due if basis.lower().startswith("original") else completion
    unit = unit.lower()
    if unit.startswith("day"):
        return start + timedelta(days=value)
    if unit.startswith("week"):
        return start + timedelta(weeks=value)
    if unit.startswith("month"):
        return (pd.Timestamp(start) + pd.DateOffset(months=int(value))).to_pydatetime()
    if unit.startswith("year"):
        return start.replace(year=start.year + int(value))
    return start + timedelta(days=value)


def readonly_open_copy(path: str) -> str:
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(path)
    temp_dir = Path(tempfile.gettempdir()) / "EquipmentManager" / "readonly"
    temp_dir.mkdir(parents=True, exist_ok=True)
    dest = temp_dir / src.name
    if dest.exists():
        try:
            dest.chmod(stat.S_IWRITE | stat.S_IREAD)
            dest.unlink()
        except Exception:
            dest = temp_dir / f"{src.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{src.suffix}"
    shutil.copy2(src, dest)
    dest.chmod(stat.S_IREAD)
    os.startfile(str(dest))
    return str(dest)


def safe_path_exists(path: str) -> bool:
    try:
        return bool(path) and Path(path).exists()
    except Exception:
        return False
