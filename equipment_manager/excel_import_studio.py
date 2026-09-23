from __future__ import annotations

from typing import Any

import pandas as pd
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)


class ExcelImportStudioDialog(QDialog):
    def __init__(
        self,
        df: pd.DataFrame,
        fields: list[tuple[str,str]],
        *,
        initial_mapping: dict[str,str] | None = None,
        required_fields: set[str] | None = None,
        title: str = "Excel Import Studio",
        parent=None,
    ):
        super().__init__(parent)
        self.df=df.copy();self.fields=fields;self.required_fields=required_fields or set();self.combos={}
        self.setWindowTitle(title);self.resize(1050,700)
        root=QVBoxLayout(self)
        note=QLabel("Preview the source data and confirm how Excel columns map into EMS fields. Required fields are marked with *.")
        note.setWordWrap(True);root.addWidget(note)
        tabs=QTabWidget();root.addWidget(tabs,1)

        preview=QWidget();pv=QVBoxLayout(preview)
        self.preview=QTableWidget();columns=[str(x) for x in self.df.columns];self.preview.setColumnCount(len(columns));self.preview.setHorizontalHeaderLabels(columns)
        sample=self.df.head(30);self.preview.setRowCount(len(sample))
        for r,(_,row) in enumerate(sample.iterrows()):
            for c,col in enumerate(self.df.columns):
                value=row[col]
                self.preview.setItem(r,c,QTableWidgetItem("" if pd.isna(value) else str(value)))
        pv.addWidget(self.preview);tabs.addTab(preview,"Source preview")

        mapping=QWidget();form=QFormLayout(mapping)
        choices=["<not mapped>"]+columns
        initial=initial_mapping or {}
        for field,label in fields:
            combo=QComboBox();combo.addItems(choices)
            mapped=initial.get(field,"")
            if mapped in columns:combo.setCurrentText(mapped)
            self.combos[field]=combo
            form.addRow(f"{label}{' *' if field in self.required_fields else ''}",combo)
        tabs.addTab(mapping,"Column mapping")

        self.save_mapping=QCheckBox("Save this mapping for my next import");self.save_mapping.setChecked(True);root.addWidget(self.save_mapping)
        self.validation=QLabel();self.validation.setWordWrap(True);root.addWidget(self.validation)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_if_valid);buttons.rejected.connect(self.reject);root.addWidget(buttons)
        for combo in self.combos.values():combo.currentTextChanged.connect(self._validate)
        self._validate()

    def mapping(self) -> dict[str,str]:
        return {field:combo.currentText() for field,combo in self.combos.items() if combo.currentText()!="<not mapped>"}

    def _validate(self):
        current=self.mapping();missing=[label for field,label in self.fields if field in self.required_fields and not current.get(field)]
        used=[x for x in current.values() if x]
        duplicates=sorted({x for x in used if used.count(x)>1})
        messages=[]
        if missing:messages.append("Missing required mapping: "+", ".join(missing))
        if duplicates:messages.append("One source column is mapped more than once: "+", ".join(duplicates))
        self.validation.setText("Ready to import." if not messages else " | ".join(messages))
        return not messages

    def _accept_if_valid(self):
        if self._validate():self.accept()


def run_mapping_studio(
    parent,
    db,
    username: str,
    preference_key: str,
    df: pd.DataFrame,
    fields: list[tuple[str,str]],
    auto_mapping: dict[str,str],
    required_fields: set[str] | None = None,
    title: str = "Excel Import Studio",
):
    saved=db.get_user_preference(username,preference_key,{}) if db and username else {}
    initial=dict(auto_mapping or {})
    if isinstance(saved,dict):
        for key,value in saved.items():
            if value in [str(x) for x in df.columns]:initial[key]=value
    dialog=ExcelImportStudioDialog(
        df,fields,initial_mapping=initial,required_fields=required_fields or set(),title=title,parent=parent,
    )
    if dialog.exec()!=QDialog.DialogCode.Accepted:return None
    mapping=dialog.mapping()
    if dialog.save_mapping.isChecked() and db and username:
        db.set_user_preference(username,preference_key,mapping)
    return mapping
