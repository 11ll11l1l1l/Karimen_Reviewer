from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class InstructionSource:
    kind: str
    label: str
    path: str = ""
    locator: str = ""
    document_id: str = ""
    revision: str = ""

    @property
    def available(self) -> bool:
        return bool(self.path and Path(self.path).exists())


def _locator(page: str="", section: str="") -> str:
    bits=[]
    if page:bits.append(f"Page/slide {page}")
    if section:bits.append(f"Section/sheet {section}")
    return " · ".join(bits)


def resolve_pm_instruction(db, task, spec=None) -> list[InstructionSource]:
    """Resolve PM instructions in operator-first priority order.

    The structured EMS step is always first. External files are fallbacks and
    are opened read-only by the UI.
    """
    sources=[]
    if spec and (getattr(spec,"activity","") or "").strip():
        sources.append(InstructionSource(
            "STRUCTURED","EMS controlled checklist instruction",
            locator=_locator(getattr(spec,"sop_page",""),getattr(spec,"sop_section","")),
        ))

    # A step-specific reference imported from the EMS PM workbook is the most
    # precise external document for the current step.
    if spec and (getattr(spec,"sop_path","") or "").strip():
        path=str(spec.sop_path).strip()
        sources.append(InstructionSource(
            "STEP_REFERENCE",f"Step reference · {Path(path).name}",path,
            _locator(getattr(spec,"sop_page",""),getattr(spec,"sop_section","")),
        ))

    # Effective controlled documents may be attached at task, PM-definition,
    # or equipment scope. Prefer work instructions/SOPs before generic refs.
    docs=[]
    for entity_type,entity_key in [
        ("PM_TASK",str(task.id)),
        ("PM_DEFINITION",task.pm_id),
        ("EQUIPMENT",task.equipment_id),
    ]:
        try:docs.extend(db.list_controlled_documents(entity_type,entity_key))
        except Exception:pass
    doc_priority={"WORK INSTRUCTION":0,"WI":0,"SOP":1,"PROCEDURE":2,"REFERENCE":3}
    docs.sort(key=lambda d:(doc_priority.get((d.document_type or "").upper(),5),d.document_id))
    seen=set()
    for doc in docs:
        if doc.document_id in seen:continue
        seen.add(doc.document_id)
        try:rev=db.effective_controlled_revision(doc.document_id)
        except Exception:rev=None
        if not rev:continue
        sources.append(InstructionSource(
            "CONTROLLED_DOCUMENT",
            f"{doc.document_type or 'Document'} · {doc.title} · Rev {rev.revision}",
            rev.path,"",doc.document_id,rev.revision,
        ))

    # Legacy / direct PM paths remain supported so existing sites do not need
    # to migrate every reference before using the new runner.
    direct=[]
    if (getattr(task,"sop_path","") or "").strip():direct.append(("Task reference",task.sop_path))
    try:
        definition=next((x for x in db.list_pm_definitions() if x.pm_id==task.pm_id),None)
    except Exception:
        definition=None
    if definition and (definition.sop_path or "").strip():direct.append(("PM definition reference",definition.sop_path))
    existing_paths={x.path for x in sources if x.path}
    for label,path in direct:
        path=str(path).strip()
        if path and path not in existing_paths:
            sources.append(InstructionSource("REFERENCE",f"{label} · {Path(path).name}",path))
            existing_paths.add(path)
    return sources


def preferred_openable_instruction(db, task, spec=None) -> InstructionSource | None:
    for source in resolve_pm_instruction(db,task,spec):
        if source.kind!="STRUCTURED" and source.available:
            return source
    return None
