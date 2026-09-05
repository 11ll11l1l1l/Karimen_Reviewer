from __future__ import annotations

import os
import socket
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QBrush, QColor, QPen
from PySide6.QtWidgets import (QApplication,QComboBox,QDialog,QDialogButtonBox,QDoubleSpinBox,QFileDialog,QFormLayout,QGraphicsRectItem,QGraphicsScene,QGraphicsTextItem,QGraphicsView,QGridLayout,QHBoxLayout,QHeaderView,QInputDialog,QLabel,QLineEdit,QListWidget,QMainWindow,QMessageBox,QPushButton,QSpinBox,QStackedWidget,QTableWidget,QTableWidgetItem,QTabWidget,QTextEdit,QVBoxLayout,QWidget)

from database import Database
from services import auto_mapping,calculate_next_due,copy_clipboard_image,dataframe_to_pm_backlog,dataframe_to_pm_specs,evaluate_measurement,read_table,readonly_open_copy,workbook_sheets,workload_by_day

APP_TITLE='Equipment Management System'; WORKSTATION=socket.gethostname(); FILE_ROOT=os.getenv('EMS_FILE_ROOT',str(Path.home()/'EquipmentManagementFiles'))
STYLE='''QWidget{font-size:10.5pt} QMainWindow,QDialog{background:#f4f6f8} QLineEdit,QComboBox,QDoubleSpinBox,QSpinBox,QTextEdit{background:white;border:1px solid #c8ced6;border-radius:4px;padding:6px} QPushButton{background:#1f5f8b;color:white;border:0;border-radius:4px;padding:7px 12px} QPushButton:disabled{background:#aeb7bf} QTableWidget{background:white;border:1px solid #d9dee3;gridline-color:#e7eaed} QHeaderView::section{background:#e9edf1;padding:6px;border:0;border-right:1px solid #d0d6dc;font-weight:600} QListWidget{background:#172431;color:white;border:0;padding:8px} QListWidget::item{padding:11px;border-radius:4px} QListWidget::item:selected{background:#2a6f9e}'''

def ti(v):
    if isinstance(v,datetime): return QTableWidgetItem(v.strftime('%Y-%m-%d %H:%M'))
    return QTableWidgetItem('' if v is None else str(v))

def setup_table(headers):
    t=QTableWidget(); t.setColumnCount(len(headers)); t.setHorizontalHeaderLabels(headers); t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); t.setSelectionBehavior(QTableWidget.SelectRows); return t

class FirstAdminDialog(QDialog):
    def __init__(self,db):
        super().__init__(); self.db=db; self.setWindowTitle('Create first administrator'); f=QFormLayout(self); self.u=QLineEdit('admin'); self.n=QLineEdit(); self.p=QLineEdit(); self.p.setEchoMode(QLineEdit.Password); self.c=QLineEdit(); self.c.setEchoMode(QLineEdit.Password)
        for label,w in [('Username',self.u),('Display name',self.n),('Password',self.p),('Confirm',self.c)]: f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.save); b.rejected.connect(self.reject); f.addRow(b)
    def save(self):
        if self.p.text()!=self.c.text(): QMessageBox.warning(self,'Password','Passwords do not match.'); return
        try:self.db.create_user(self.u.text(),self.n.text(),self.p.text()); self.accept()
        except Exception as e: QMessageBox.critical(self,'Create user',str(e))

class LoginDialog(QDialog):
    def __init__(self,db):
        super().__init__(); self.db=db; self.user=None; self.setWindowTitle(APP_TITLE+' - Login'); self.setMinimumWidth(420); l=QVBoxLayout(self); title=QLabel('EQUIPMENT MANAGEMENT'); title.setStyleSheet('font-size:20pt;font-weight:700;color:#16354b'); l.addWidget(title); ok,status=db.health(); h=QLabel(f"Database: {'Connected' if ok else 'Offline'} — {status}"); h.setStyleSheet('color:#26734d' if ok else 'color:#a62b2b'); l.addWidget(h)
        f=QFormLayout(); self.u=QLineEdit(); self.p=QLineEdit(); self.p.setEchoMode(QLineEdit.Password); f.addRow('Username',self.u); f.addRow('Password',self.p); l.addLayout(f); b=QPushButton('Login'); b.clicked.connect(self.login); l.addWidget(b); self.p.returnPressed.connect(self.login)
    def login(self):
        self.user=self.db.authenticate(self.u.text(),self.p.text())
        if not self.user: QMessageBox.warning(self,'Login','Invalid username/password or inactive account.'); return
        self.db.audit(self.user['username'],'LOGIN','SESSION',WORKSTATION,workstation=WORKSTATION); self.accept()

class DashboardPage(QWidget):
    def __init__(self,db):
        super().__init__(); self.db=db; l=QVBoxLayout(self); x=QLabel('Operational Dashboard'); x.setStyleSheet('font-size:18pt;font-weight:700'); l.addWidget(x); self.grid=QGridLayout(); l.addLayout(self.grid); self.cards={}; labels=[('equipment_total','Equipment'),('equipment_down','Down'),('equipment_hold','On Hold'),('pm_open','Open PM'),('pm_overdue','PM Overdue'),('tickets_open','Open Tickets'),('inventory_low','Low Stock'),('endorsements_open','Open Endorsements')]
        for i,(k,name) in enumerate(labels): w=QWidget(); w.setStyleSheet('background:white;border:1px solid #d9dee3;border-radius:6px'); q=QVBoxLayout(w); v=QLabel('0'); v.setStyleSheet('font-size:24pt;font-weight:700;color:#16354b;border:0'); q.addWidget(v); q.addWidget(QLabel(name)); self.cards[k]=v; self.grid.addWidget(w,i//4,i%4)
        self.note=QLabel(); l.addWidget(self.note); l.addStretch(); self.refresh()
    def refresh(self):
        d=self.db.dashboard_counts()
        for k,w in self.cards.items(): w.setText(str(d.get(k,0)))
        self.note.setText('Updated '+datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

class EquipmentDialog(QDialog):
    def __init__(self,row=None):
        super().__init__(); self.setWindowTitle('Equipment'); f=QFormLayout(self); self.fields={}
        for k,n in [('equipment_id','Equipment ID'),('name','Name'),('equipment_type','Type'),('manufacturer','Manufacturer'),('model','Model'),('serial_number','Serial'),('asset_number','Asset Number'),('site','Site'),('building','Building'),('floor','Floor'),('area','Area'),('line_cell','Line / Bay / Cell'),('owner','Owner')]: self.fields[k]=QLineEdit(); f.addRow(n,self.fields[k])
        self.status=QComboBox(); self.status.addItems(['Available','Production','Down','PM','Engineering','Standby','Waiting Parts','Waiting Vendor','Qualification','Hold','Restricted','Offline','Decommissioned']); self.disp=QComboBox(); self.disp.addItems(['Released','Released With Conditions','Restricted Use','Engineering Use','Monitoring','Hold','PM Hold','Quality Hold','Safety Hold','Waiting Parts','Waiting Vendor','Qualification','Decommission','Scrap']); self.crit=QComboBox(); self.crit.addItems(['Low','Normal','High','Critical']); self.x=QDoubleSpinBox(); self.y=QDoubleSpinBox(); self.x.setRange(-100000,100000); self.y.setRange(-100000,100000)
        for n,w in [('Status',self.status),('Disposition',self.disp),('Criticality',self.crit),('Map X',self.x),('Map Y',self.y)]: f.addRow(n,w)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
        if row:
            for k,w in self.fields.items(): w.setText(str(getattr(row,k,'') or ''))
            self.status.setCurrentText(row.status); self.disp.setCurrentText(row.disposition); self.crit.setCurrentText(row.criticality); self.x.setValue(row.map_x); self.y.setValue(row.map_y); self.fields['equipment_id'].setReadOnly(True)
    def data(self):
        d={k:w.text().strip() for k,w in self.fields.items()}; d.update(status=self.status.currentText(),disposition=self.disp.currentText(),criticality=self.crit.currentText(),map_x=self.x.value(),map_y=self.y.value()); return d

class EquipmentPage(QWidget):
    def __init__(self,db,user):
        super().__init__(); self.db=db; self.user=user; self.rows=[]; l=QVBoxLayout(self); top=QHBoxLayout(); self.q=QLineEdit(); self.q.setPlaceholderText('Search equipment...'); self.q.textChanged.connect(self.refresh); a=QPushButton('Add'); a.clicked.connect(self.add); e=QPushButton('Edit'); e.clicked.connect(self.edit); top.addWidget(self.q,1); top.addWidget(a); top.addWidget(e); l.addLayout(top); self.t=setup_table(['ID','Name','Type','Area','Line/Cell','Status','Disposition','Owner','Criticality','Version']); self.t.doubleClicked.connect(self.edit); l.addWidget(self.t); self.refresh()
    def refresh(self):
        self.rows=self.db.list_equipment(self.q.text()); self.t.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            for c,v in enumerate([x.equipment_id,x.name,x.equipment_type,x.area,x.line_cell,x.status,x.disposition,x.owner,x.criticality,x.version]): self.t.setItem(r,c,ti(v))
    def selected(self): r=self.t.currentRow(); return self.rows[r] if 0<=r<len(self.rows) else None
    def add(self):
        d=EquipmentDialog()
        if d.exec()==QDialog.Accepted:
            try:self.db.save_equipment(d.data()); self.db.audit(self.user['username'],'CREATE','EQUIPMENT',d.data()['equipment_id'],workstation=WORKSTATION); self.refresh()
            except Exception as e: QMessageBox.critical(self,'Save',str(e))
    def edit(self):
        row=self.selected()
        if not row:return
        d=EquipmentDialog(row)
        if d.exec()==QDialog.Accepted:
            try:self.db.save_equipment(d.data(),row.version); self.db.audit(self.user['username'],'UPDATE','EQUIPMENT',row.equipment_id,workstation=WORKSTATION); self.refresh()
            except Exception as e: QMessageBox.critical(self,'Conflict',str(e))

class PMDefinitionDialog(QDialog):
    def __init__(self):
        super().__init__(); self.setWindowTitle('PM Definition / Scheduling Rule'); f=QFormLayout(self); self.pm=QLineEdit(); self.name=QLineEdit(); self.eq=QLineEdit(); self.typ=QComboBox(); self.typ.addItems(['Interval','One Time','Event Triggered']); self.freq=QDoubleSpinBox(); self.freq.setRange(0,1e9); self.freq.setValue(30); self.unit=QComboBox(); self.unit.addItems(['days','weeks','months','years','hours']); self.anchor=QComboBox(); self.anchor.addItems(['Original Due','Last Completion']); self.early=QSpinBox(); self.early.setRange(0,3650); self.grace=QSpinBox(); self.grace.setRange(0,3650); self.hours=QDoubleSpinBox(); self.hours.setRange(0,1e6); self.people=QSpinBox(); self.people.setRange(1,100); self.skill=QLineEdit(); self.parts=QLineEdit(); self.sop=QLineEdit()
        for n,w in [('PM ID',self.pm),('Name',self.name),('Equipment ID',self.eq),('Schedule Type',self.typ),('Frequency',self.freq),('Unit',self.unit),('Next due anchored to',self.anchor),('Early window days',self.early),('Grace days',self.grace),('Estimated hours',self.hours),('Required people',self.people),('Required skill',self.skill),('Required parts',self.parts),('SOP path',self.sop)]: f.addRow(n,w)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
    def data(self): return {'pm_id':self.pm.text().strip(),'name':self.name.text().strip(),'equipment_id':self.eq.text().strip(),'schedule_type':self.typ.currentText(),'frequency_value':self.freq.value(),'frequency_unit':self.unit.currentText(),'anchor_mode':self.anchor.currentText(),'early_window_days':self.early.value(),'grace_days':self.grace.value(),'estimated_hours':self.hours.value(),'required_people':self.people.value(),'required_skill':self.skill.text().strip(),'required_parts':self.parts.text().strip(),'sop_path':self.sop.text().strip()}

class PMExecutionDialog(QDialog):
    def __init__(self,db,user,task):
        super().__init__(); self.db=db; self.user=user; self.task=task; self.ex=db.start_pm_execution(task.id,user['username']); self.specs=db.list_pm_specs(task.pm_id); self.results={r.step_no:r for r in db.list_pm_results(self.ex.id)}; self.setWindowTitle(f'Execute PM — {task.equipment_id} / {task.pm_name}'); self.resize(1000,600); l=QVBoxLayout(self); l.addWidget(QLabel(f'PM {task.pm_id} | Equipment {task.equipment_id} | Due {task.original_due_date}'))
        self.t=setup_table(['Step','Activity','Method','Spec / Acceptance','Value','Result','Evidence']); self.t.setRowCount(len(self.specs)); l.addWidget(self.t); a=QHBoxLayout(); enter=QPushButton('Enter Result'); enter.clicked.connect(self.enter_result); paste=QPushButton('Paste Clipboard Image'); paste.clicked.connect(self.paste_image); complete=QPushButton('Complete PM'); complete.clicked.connect(self.complete); a.addWidget(enter); a.addWidget(paste); a.addStretch(); a.addWidget(complete); l.addLayout(a); self.refresh()
    def spec_text(self,s):
        if s.input_type=='Numeric': return f"Target {s.target if s.target is not None else ''} | Control {s.control_low if s.control_low is not None else ''}..{s.control_high if s.control_high is not None else ''} | Spec {s.spec_low if s.spec_low is not None else ''}..{s.spec_high if s.spec_high is not None else ''} {s.unit}"
        return s.acceptance_text
    def refresh(self):
        self.results={r.step_no:r for r in self.db.list_pm_results(self.ex.id)}
        for r,s in enumerate(self.specs):
            rr=self.results.get(s.step_no); vals=[s.step_no,s.activity,s.method,self.spec_text(s),rr.value_numeric if rr and rr.value_numeric is not None else (rr.value_text if rr else ''),rr.result if rr else '',rr.evidence_path if rr else '']
            for c,v in enumerate(vals): self.t.setItem(r,c,ti(v))
    def current_spec(self):
        r=self.t.currentRow(); return self.specs[r] if 0<=r<len(self.specs) else None
    def enter_result(self):
        s=self.current_spec()
        if not s:return
        if s.input_type=='Numeric':
            val,ok=QInputDialog.getDouble(self,'Measurement',f'{s.activity} ({s.unit})',0,-1e12,1e12,6)
            if not ok:return
            text=''; num=val
        else:
            text,ok=QInputDialog.getText(self,'Result',f'{s.activity}')
            if not ok:return
            num=None
        result=evaluate_measurement(s,text,num); old=self.results.get(s.step_no)
        try:self.db.save_pm_result(self.ex.id,s.step_no,{'value_text':text,'value_numeric':num,'result':result,'entered_by':self.user['username']},old.version if old else None); self.refresh()
        except Exception as e: QMessageBox.critical(self,'Save result',str(e))
    def paste_image(self):
        s=self.current_spec()
        if not s:return
        img=QApplication.clipboard().image()
        if img.isNull(): QMessageBox.information(self,'Clipboard','No image is currently in the clipboard.'); return
        try:
            path=copy_clipboard_image(img,FILE_ROOT,'PM',f'{self.task.equipment_id}_{self.task.pm_id}'); old=self.results.get(s.step_no); data={'value_text':old.value_text if old else '','value_numeric':old.value_numeric if old else None,'result':old.result if old else 'RECORDED','comment':old.comment if old else '','evidence_path':path,'entered_by':self.user['username']}; self.db.save_pm_result(self.ex.id,s.step_no,data,old.version if old else None); self.refresh()
        except Exception as e: QMessageBox.critical(self,'Paste image',str(e))
    def complete(self):
        try:self.db.complete_pm_execution(self.ex.id,self.user['username']); QMessageBox.information(self,'PM','PM completed.'); self.accept()
        except Exception as e: QMessageBox.warning(self,'Cannot complete',str(e))

class PMPage(QWidget):
    def __init__(self,db,user):
        super().__init__(); self.db=db; self.user=user; self.rows=[]; self.defrows=[]; l=QVBoxLayout(self); bar=QHBoxLayout(); adddef=QPushButton('Add PM Definition'); adddef.clicked.connect(self.add_definition); nextb=QPushButton('Generate Next PM'); nextb.clicked.connect(self.generate_next); b1=QPushButton('Import Backlog Excel'); b1.clicked.connect(self.import_backlog); b2=QPushButton('Import Steps / Specs Excel'); b2.clicked.connect(self.import_specs); run=QPushButton('Execute Selected PM'); run.clicked.connect(self.execute); bar.addWidget(adddef); bar.addWidget(nextb); bar.addWidget(b1); bar.addWidget(b2); bar.addWidget(run); bar.addStretch(); l.addLayout(bar); tabs=QTabWidget(); l.addWidget(tabs); self.defs=setup_table(['PM ID','Name','Equipment','Type','Frequency','Unit','Anchor','Early','Grace','Hours','Skill','Revision']); self.back=setup_table(['Equipment','PM ID','PM Name','Original Due','Scheduled','Status','Assigned','Hours','Priority','Version']); self.spec=setup_table(['PM ID','Step','Activity','Method','Type','Unit','Target','Control Low','Control High','Spec Low','Spec High','Revision']); self.load=setup_table(['Date','Planned Hours']); tabs.addTab(self.defs,'PM Definitions'); tabs.addTab(self.back,'Backlog / Schedule'); tabs.addTab(self.spec,'Checklist / Specs'); tabs.addTab(self.load,'Workload Forecast'); self.refresh()
    def refresh(self):
        self.defrows=self.db.list_pm_definitions(); self.defs.setRowCount(len(self.defrows))
        for r,x in enumerate(self.defrows):
            for c,v in enumerate([x.pm_id,x.name,x.equipment_id,x.schedule_type,x.frequency_value,x.frequency_unit,x.anchor_mode,x.early_window_days,x.grace_days,x.estimated_hours,x.required_skill,x.revision]): self.defs.setItem(r,c,ti(v))
        self.rows=self.db.list_pm_tasks(); self.back.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            for c,v in enumerate([x.equipment_id,x.pm_id,x.pm_name,x.original_due_date,x.scheduled_date,x.status,x.assigned_to,x.estimated_hours,x.priority,x.version]): self.back.setItem(r,c,ti(v))
        sp=self.db.list_pm_specs(); self.spec.setRowCount(len(sp))
        for r,x in enumerate(sp):
            for c,v in enumerate([x.pm_id,x.step_no,x.activity,x.method,x.input_type,x.unit,x.target,x.control_low,x.control_high,x.spec_low,x.spec_high,x.revision]): self.spec.setItem(r,c,ti(v))
        w=workload_by_day(self.rows); self.load.setRowCount(len(w))
        for r,(d,h) in enumerate(sorted(w.items())): self.load.setItem(r,0,ti(d)); self.load.setItem(r,1,ti(round(h,2)))
    def choose(self,path):
        ss=workbook_sheets(path)
        if len(ss)==1:return 0
        x,ok=QInputDialog.getItem(self,'Worksheet','Choose worksheet',ss,0,False); return x if ok else None
    def add_definition(self):
        d=PMDefinitionDialog()
        if d.exec()==QDialog.Accepted:
            try:
                data=d.data(); self.db.save_pm_definition(data); self.db.audit(self.user['username'],'CREATE','PM_DEFINITION',data['pm_id'],workstation=WORKSTATION); self.refresh()
            except Exception as e: QMessageBox.critical(self,'PM definition',str(e))
    def generate_next(self):
        r=self.defs.currentRow()
        if not (0<=r<len(self.defrows)): QMessageBox.information(self,'Scheduler','Select a PM definition first.'); return
        d=self.defrows[r]; prior=[x for x in self.db.list_pm_tasks() if x.pm_id==d.pm_id and x.equipment_id==d.equipment_id]
        prior.sort(key=lambda x:(x.original_due_date or datetime.min), reverse=True)
        if prior:
            p=prior[0]; due=calculate_next_due(d.schedule_type,d.frequency_value,d.frequency_unit,d.anchor_mode,p.original_due_date,p.last_completion_date)
        else:
            text,ok=QInputDialog.getText(self,'First Due Date','No prior task exists. Enter first due date YYYY-MM-DD:')
            if not ok:return
            try: due=datetime.strptime(text.strip(),'%Y-%m-%d')
            except ValueError: QMessageBox.warning(self,'Date','Use YYYY-MM-DD.'); return
        if not due: QMessageBox.warning(self,'Scheduler','Could not calculate the next due date.'); return
        data={'equipment_id':d.equipment_id,'pm_id':d.pm_id,'pm_name':d.name,'original_due_date':due,'scheduled_date':due,'status':'Scheduled','estimated_hours':d.estimated_hours,'sop_path':d.sop_path}
        try:self.db.upsert_pm_task(data); self.db.audit(self.user['username'],'SCHEDULE','PM_TASK',d.pm_id,f'Due={due.isoformat()}',WORKSTATION); self.refresh()
        except Exception as e: QMessageBox.critical(self,'Scheduler',str(e))
    def import_backlog(self):
        p,_=QFileDialog.getOpenFileName(self,'Import PM Backlog','','Excel/CSV (*.xlsx *.xlsm *.csv)')
        if not p:return
        try:
            sh=self.choose(p); df=read_table(p,sh); m=auto_mapping(list(df.columns)); rows,err=dataframe_to_pm_backlog(df,m)
            if QMessageBox.question(self,'Import',f'{len(rows)} valid rows; {len(err)} warnings/errors. Import?')!=QMessageBox.Yes:return
            for row in rows:self.db.upsert_pm_task(row)
            self.db.audit(self.user['username'],'IMPORT','PM_BACKLOG',Path(p).name,f'Rows={len(rows)} Errors={len(err)}',WORKSTATION); self.refresh()
        except Exception as e: QMessageBox.critical(self,'Import',str(e))
    def import_specs(self):
        p,_=QFileDialog.getOpenFileName(self,'Import PM Steps / Specs','','Excel/CSV (*.xlsx *.xlsm *.csv)')
        if not p:return
        try:
            sh=self.choose(p); df=read_table(p,sh); m=auto_mapping(list(df.columns)); default=''
            if 'pm_id' not in m: default,ok=QInputDialog.getText(self,'PM ID','PM ID for this sheet:')
            else: ok=True
            if not ok:return
            rows,warn=dataframe_to_pm_specs(df,m,default)
            if QMessageBox.question(self,'Import',f'{len(rows)} valid steps; {len(warn)} warnings. Import as controlled records?')!=QMessageBox.Yes:return
            for row in rows:self.db.upsert_pm_spec(row,create_revision=True)
            self.db.audit(self.user['username'],'IMPORT','PM_SPEC',Path(p).name,f'Rows={len(rows)} Warnings={len(warn)}',WORKSTATION); self.refresh()
        except Exception as e: QMessageBox.critical(self,'Import',str(e))
    def execute(self):
        r=self.back.currentRow()
        if not (0<=r<len(self.rows)):return
        PMExecutionDialog(self.db,self.user,self.rows[r]).exec(); self.refresh()

class TicketDialog(QDialog):
    def __init__(self,user):
        super().__init__(); self.setWindowTitle('Issue Ticket'); f=QFormLayout(self); self.no=QLineEdit('EQI-'+datetime.now().strftime('%Y%m%d-%H%M%S')); self.eq=QLineEdit(); self.title=QLineEdit(); self.desc=QTextEdit(); self.sev=QComboBox(); self.sev.addItems(['S1','S2','S3','S4']); self.pr=QComboBox(); self.pr.addItems(['P1','P2','P3','P4']); self.owner=QLineEdit(user['display_name'])
        for n,w in [('Ticket',self.no),('Equipment',self.eq),('Title',self.title),('Description',self.desc),('Severity',self.sev),('Priority',self.pr),('Owner',self.owner)]:f.addRow(n,w)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
    def data(self,user):return {'ticket_no':self.no.text().strip(),'equipment_id':self.eq.text().strip(),'title':self.title.text().strip(),'description':self.desc.toPlainText(),'severity':self.sev.currentText(),'priority':self.pr.currentText(),'owner':self.owner.text().strip(),'created_by':user['username']}

class TicketPage(QWidget):
    def __init__(self,db,user):
        super().__init__(); self.db=db; self.user=user; self.rows=[]; l=QVBoxLayout(self); b=QPushButton('New Issue Ticket'); b.clicked.connect(self.add); l.addWidget(b,alignment=Qt.AlignLeft); self.t=setup_table(['Ticket','Equipment','Title','Severity','Priority','Status','Owner','Created','Version']); l.addWidget(self.t); self.refresh()
    def refresh(self):
        self.rows=self.db.list_tickets(); self.t.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            for c,v in enumerate([x.ticket_no,x.equipment_id,x.title,x.severity,x.priority,x.status,x.owner,x.created_at,x.version]):self.t.setItem(r,c,ti(v))
    def add(self):
        d=TicketDialog(self.user)
        if d.exec()==QDialog.Accepted:
            try:data=d.data(self.user); self.db.save_ticket(data); self.db.audit(self.user['username'],'CREATE','TICKET',data['ticket_no'],workstation=WORKSTATION); self.refresh()
            except Exception as e:QMessageBox.critical(self,'Ticket',str(e))

class DispositionDialog(QDialog):
    def __init__(self,user):
        super().__init__(); self.setWindowTitle('Equipment Disposition'); f=QFormLayout(self); self.eq=QLineEdit(); self.state=QComboBox(); self.state.addItems(['Released','Released With Conditions','Restricted Use','Engineering Use','Monitoring','Hold','PM Hold','Quality Hold','Safety Hold','Waiting Parts','Waiting Vendor','Qualification','Decommission','Scrap']); self.reason=QTextEdit(); self.rest=QTextEdit(); self.criteria=QTextEdit(); self.ticket=QLineEdit(); self.approver=QLineEdit()
        for n,w in [('Equipment',self.eq),('Disposition',self.state),('Reason',self.reason),('Restrictions',self.rest),('Release criteria',self.criteria),('Related ticket',self.ticket),('Approved by',self.approver)]:f.addRow(n,w)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b); self.user=user
    def data(self):return {'equipment_id':self.eq.text().strip(),'state':self.state.currentText(),'reason':self.reason.toPlainText(),'restrictions':self.rest.toPlainText(),'release_criteria':self.criteria.toPlainText(),'related_ticket':self.ticket.text().strip(),'created_by':self.user['username'],'approved_by':self.approver.text().strip()}

class DispositionPage(QWidget):
    def __init__(self,db,user):
        super().__init__(); self.db=db; self.user=user; l=QVBoxLayout(self); b=QPushButton('Set Equipment Disposition'); b.clicked.connect(self.add); l.addWidget(b,alignment=Qt.AlignLeft); self.t=setup_table(['Equipment','State','Reason','Restrictions','Release Criteria','Ticket','By','Approved','Effective','Active']); l.addWidget(self.t); self.refresh()
    def refresh(self):
        rows=self.db.list_dispositions(); self.t.setRowCount(len(rows))
        for r,x in enumerate(rows):
            for c,v in enumerate([x.equipment_id,x.state,x.reason,x.restrictions,x.release_criteria,x.related_ticket,x.created_by,x.approved_by,x.effective_at,x.active]):self.t.setItem(r,c,ti(v))
    def add(self):
        d=DispositionDialog(self.user)
        if d.exec()==QDialog.Accepted:
            try:data=d.data(); self.db.set_disposition(data); self.db.audit(self.user['username'],'DISPOSITION','EQUIPMENT',data['equipment_id'],data['state'],WORKSTATION); self.refresh()
            except Exception as e: QMessageBox.critical(self,'Disposition',str(e))

class EndorsementDialog(QDialog):
    def __init__(self,user):
        super().__init__(); self.user=user; self.setWindowTitle('Endorsement / Handover'); f=QFormLayout(self); self.no=QLineEdit('END-'+datetime.now().strftime('%Y%m%d-%H%M%S')); self.eq=QLineEdit(); self.condition=QTextEdit(); self.done=QTextEdit(); self.pending=QTextEdit(); self.rest=QTextEdit(); self.next=QTextEdit(); self.owner=QLineEdit()
        for n,w in [('Endorsement',self.no),('Equipment',self.eq),('Current condition',self.condition),('Work completed',self.done),('Pending work',self.pending),('Restrictions',self.rest),('Next action',self.next),('Next owner',self.owner)]:f.addRow(n,w)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
    def data(self):return {'endorsement_no':self.no.text().strip(),'equipment_id':self.eq.text().strip(),'current_condition':self.condition.toPlainText(),'work_completed':self.done.toPlainText(),'pending_work':self.pending.toPlainText(),'restrictions':self.rest.toPlainText(),'next_action':self.next.toPlainText(),'next_owner':self.owner.text().strip(),'created_by':self.user['username']}

class EndorsementPage(QWidget):
    def __init__(self,db,user):
        super().__init__(); self.db=db; self.user=user; self.rows=[]; l=QVBoxLayout(self); bar=QHBoxLayout(); a=QPushButton('New Endorsement'); a.clicked.connect(self.add); ack=QPushButton('Acknowledge Selected'); ack.clicked.connect(self.ack); bar.addWidget(a); bar.addWidget(ack); bar.addStretch(); l.addLayout(bar); self.t=setup_table(['No.','Equipment','Condition','Pending','Restrictions','Next Action','Next Owner','Status','Created By','Acknowledged By']); l.addWidget(self.t); self.refresh()
    def refresh(self):
        self.rows=self.db.list_endorsements(); self.t.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            for c,v in enumerate([x.endorsement_no,x.equipment_id,x.current_condition,x.pending_work,x.restrictions,x.next_action,x.next_owner,x.status,x.created_by,x.acknowledged_by]):self.t.setItem(r,c,ti(v))
    def add(self):
        d=EndorsementDialog(self.user)
        if d.exec()==QDialog.Accepted:
            try:data=d.data(); self.db.save_endorsement(data); self.db.audit(self.user['username'],'CREATE','ENDORSEMENT',data['endorsement_no'],workstation=WORKSTATION); self.refresh()
            except Exception as e:QMessageBox.critical(self,'Endorsement',str(e))
    def ack(self):
        r=self.t.currentRow()
        if not (0<=r<len(self.rows)):return
        try:self.db.acknowledge_endorsement(self.rows[r].endorsement_no,self.user['username']); self.refresh()
        except Exception as e:QMessageBox.critical(self,'Acknowledge',str(e))

class LocationDialog(QDialog):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Storage Location'); f=QFormLayout(self); self.fields={}
        for k,n in [('location_code','Location Code'),('name','Name'),('site','Site'),('building','Building'),('floor','Floor'),('area','Area'),('cabinet','Cabinet'),('shelf','Shelf'),('drawer_bin','Drawer / Bin'),('image_path','Location Image')]: self.fields[k]=QLineEdit(); f.addRow(n,self.fields[k])
        self.x=QDoubleSpinBox();self.y=QDoubleSpinBox();self.x.setRange(-100000,100000);self.y.setRange(-100000,100000);f.addRow('Map X',self.x);f.addRow('Map Y',self.y);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
    def data(self):d={k:w.text().strip() for k,w in self.fields.items()};d.update(map_x=self.x.value(),map_y=self.y.value());return d

class InventoryDialog(QDialog):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Inventory Item'); f=QFormLayout(self); self.part=QLineEdit();self.desc=QLineEdit();self.loc=QLineEdit();self.qty=QDoubleSpinBox();self.qty.setRange(0,1e9);self.min=QDoubleSpinBox();self.min.setRange(0,1e9);self.unit=QLineEdit('pcs');self.condition=QComboBox();self.condition.addItems(['Available','Reserved','Installed','In Use','Repair','Quarantine','Inspection Required','Expired','Obsolete','Scrap','Vendor']);self.image=QLineEdit()
        for n,w in [('Part Number',self.part),('Description',self.desc),('Location Code',self.loc),('Quantity',self.qty),('Minimum',self.min),('Unit',self.unit),('Condition',self.condition),('Image',self.image)]:f.addRow(n,w)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
    def data(self):return {'part_number':self.part.text().strip(),'description':self.desc.text().strip(),'location_code':self.loc.text().strip(),'quantity':self.qty.value(),'min_quantity':self.min.value(),'unit':self.unit.text().strip(),'condition':self.condition.currentText(),'image_path':self.image.text().strip()}

class InventoryPage(QWidget):
    def __init__(self,db,user):
        super().__init__(); self.db=db; self.user=user; self.rows=[]; l=QVBoxLayout(self); bar=QHBoxLayout(); self.q=QLineEdit(); self.q.setPlaceholderText('Search part or location'); self.q.textChanged.connect(self.refresh); add=QPushButton('Add Inventory'); add.clicked.connect(self.add); loc=QPushButton('Add Storage Location');loc.clicked.connect(self.add_loc); use=QPushButton('Consume Selected');use.clicked.connect(self.consume);bar.addWidget(self.q,1);bar.addWidget(add);bar.addWidget(loc);bar.addWidget(use);l.addLayout(bar); self.t=setup_table(['Part','Description','Qty','Min','Unit','Condition','Location','Image','Version']);l.addWidget(self.t);self.refresh()
    def refresh(self):
        self.rows=self.db.list_inventory(self.q.text());self.t.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            for c,v in enumerate([x.part_number,x.description,x.quantity,x.min_quantity,x.unit,x.condition,x.location_code,x.image_path,x.version]):self.t.setItem(r,c,ti(v))
    def add(self):
        d=InventoryDialog()
        if d.exec()==QDialog.Accepted:
            try:self.db.save_inventory_item(d.data());self.refresh()
            except Exception as e:QMessageBox.critical(self,'Inventory',str(e))
    def add_loc(self):
        d=LocationDialog()
        if d.exec()==QDialog.Accepted:
            try:self.db.save_storage_location(d.data())
            except Exception as e:QMessageBox.critical(self,'Location',str(e))
    def consume(self):
        r=self.t.currentRow()
        if not (0<=r<len(self.rows)):return
        x=self.rows[r];qty,ok=QInputDialog.getDouble(self,'Consume',f'Quantity from {x.location_code}',1,0.000001,1e9,3)
        if ok:
            success,left=self.db.consume_inventory(x.part_number,x.location_code,qty,self.user['username'])
            if not success:QMessageBox.warning(self,'Inventory',f'Insufficient stock. Current quantity: {left}')
            self.refresh()

class LayoutPage(QWidget):
    def __init__(self,db):
        super().__init__();self.db=db;l=QVBoxLayout(self);bar=QHBoxLayout();self.q=QLineEdit();self.q.setPlaceholderText('Part number to highlight storage locations');self.q.returnPressed.connect(self.refresh);b=QPushButton('Refresh / Highlight');b.clicked.connect(self.refresh);bar.addWidget(self.q,1);bar.addWidget(b);l.addLayout(bar);self.scene=QGraphicsScene();self.view=QGraphicsView(self.scene);l.addWidget(self.view);self.refresh()
    def refresh(self):
        self.scene.clear(); eq=self.db.list_equipment(); locs=self.db.list_storage_locations(); target={x.location_code for x in self.db.list_inventory(self.q.text())} if self.q.text().strip() else set()
        for e in eq:
            rect=QGraphicsRectItem(e.map_x,e.map_y,120,55);rect.setPen(QPen(QColor('#444')));rect.setBrush(QBrush(QColor('#f7d6d6') if e.status=='Down' else '#dcebdc'));self.scene.addItem(rect);txt=QGraphicsTextItem(f'{e.equipment_id}\n{e.status}');txt.setPos(e.map_x+5,e.map_y+4);self.scene.addItem(txt)
        for x in locs:
            rect=QGraphicsRectItem(x.map_x,x.map_y,110,45);rect.setPen(QPen(QColor('#8a6d1d'),3 if x.location_code in target else 1));rect.setBrush(QBrush(QColor('#fff1a8') if x.location_code in target else '#eef0f2'));self.scene.addItem(rect);txt=QGraphicsTextItem('STORAGE\n'+x.location_code);txt.setPos(x.map_x+4,x.map_y+2);self.scene.addItem(txt)
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-50,-50,50,50))

class DocumentsPage(QWidget):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.rows=[];l=QVBoxLayout(self);bar=QHBoxLayout();add=QPushButton('Link File');add.clicked.connect(self.add);op=QPushButton('Open Selected Read-Only');op.clicked.connect(self.open);bar.addWidget(add);bar.addWidget(op);bar.addStretch();l.addLayout(bar);self.t=setup_table(['Entity Type','Entity Key','Type','Title','Revision','Path','Status','Added By']);l.addWidget(self.t);self.refresh()
    def refresh(self):
        self.rows=self.db.list_documents();self.t.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            for c,v in enumerate([x.entity_type,x.entity_key,x.document_type,x.title,x.revision,x.path,x.status,x.added_by]):self.t.setItem(r,c,ti(v))
    def add(self):
        p,_=QFileDialog.getOpenFileName(self,'Link document')
        if not p:return
        et,ok=QInputDialog.getItem(self,'Entity','Link to',['EQUIPMENT','PM','TICKET','INVENTORY','GENERAL'],0,False)
        if not ok:return
        key,ok=QInputDialog.getText(self,'Entity Key','Equipment ID / PM ID / ticket / part number:')
        if not ok:return
        data={'entity_type':et,'entity_key':key.strip(),'document_type':'Document','title':Path(p).name,'path':p,'added_by':self.user['username']};self.db.add_document(data);self.refresh()
    def open(self):
        r=self.t.currentRow()
        if not (0<=r<len(self.rows)):return
        try:readonly_open_copy(self.rows[r].path)
        except Exception as e:QMessageBox.critical(self,'Open file',str(e))

class MainWindow(QMainWindow):
    def __init__(self,db,user):
        super().__init__();self.db=db;self.user=user;self.setWindowTitle(APP_TITLE);self.resize(1500,850);root=QWidget();self.setCentralWidget(root);l=QHBoxLayout(root);self.nav=QListWidget();self.nav.setFixedWidth(210);self.stack=QStackedWidget();l.addWidget(self.nav);l.addWidget(self.stack,1);self.pages=[]
        for name,page in [('Dashboard',DashboardPage(db)),('Equipment',EquipmentPage(db,user)),('PM Control',PMPage(db,user)),('Issues',TicketPage(db,user)),('Disposition',DispositionPage(db,user)),('Endorsement',EndorsementPage(db,user)),('Inventory',InventoryPage(db,user)),('Layout / Map',LayoutPage(db)),('Documents',DocumentsPage(db,user))]:self.nav.addItem(name);self.stack.addWidget(page);self.pages.append(page)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex);self.nav.setCurrentRow(0);refresh=QAction('Refresh',self);refresh.setShortcut('F5');refresh.triggered.connect(self.refresh);self.addAction(refresh);self.statusBar().showMessage(f"{user['display_name']} | {user['role']} | {WORKSTATION}");self.timer=QTimer(self);self.timer.timeout.connect(self.refresh_dashboard);self.timer.start(30000)
    def refresh(self):
        p=self.stack.currentWidget()
        if hasattr(p,'refresh'):p.refresh()
    def refresh_dashboard(self):
        if hasattr(self.pages[0],'refresh'):self.pages[0].refresh()

def main():
    app=QApplication(sys.argv);app.setApplicationName(APP_TITLE);app.setStyleSheet(STYLE);db=Database()
    if not db.has_users():
        if FirstAdminDialog(db).exec()!=QDialog.Accepted:return 0
    login=LoginDialog(db)
    if login.exec()!=QDialog.Accepted:return 0
    w=MainWindow(db,login.user);w.show();return app.exec()

if __name__=='__main__':raise SystemExit(main())
