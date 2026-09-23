from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QMessageBox, QPushButton, QRadioButton, QScrollArea, QVBoxLayout, QWidget,
)


class AnnotationCanvas(QWidget):
    def __init__(self,path: str,parent=None):
        super().__init__(parent)
        self.image=QImage(path)
        if self.image.isNull():raise ValueError("Image could not be loaded.")
        self.setFixedSize(self.image.size())
        self.mode="Rectangle";self.items=[];self.start=None;self.current=None
        self.setMouseTracking(True)

    def set_mode(self,mode: str):
        self.mode=mode

    def undo(self):
        if self.items:self.items.pop();self.update()

    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        p=event.position().toPoint()
        if self.mode=="Text":
            text,ok=QInputDialog.getText(self,"Annotation text","Text")
            if ok and text.strip():self.items.append(("Text",p,p,text.strip()));self.update()
            return
        self.start=p;self.current=p;self.update()

    def mouseMoveEvent(self,event):
        if self.start is not None:self.current=event.position().toPoint();self.update()

    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton or self.start is None:return
        end=event.position().toPoint()
        if (end-self.start).manhattanLength()>3:self.items.append((self.mode,self.start,end,""))
        self.start=None;self.current=None;self.update()

    @staticmethod
    def _arrow_head(start: QPoint,end: QPoint):
        dx=end.x()-start.x();dy=end.y()-start.y();angle=math.atan2(dy,dx);length=14
        a1=angle+math.pi*0.82;a2=angle-math.pi*0.82
        p1=QPoint(int(end.x()+length*math.cos(a1)),int(end.y()+length*math.sin(a1)))
        p2=QPoint(int(end.x()+length*math.cos(a2)),int(end.y()+length*math.sin(a2)))
        return QPolygon([end,p1,p2])

    def _draw_item(self,painter: QPainter,item):
        mode,start,end,text=item
        if mode=="Rectangle":painter.drawRect(start.x(),start.y(),end.x()-start.x(),end.y()-start.y())
        elif mode=="Ellipse":painter.drawEllipse(start.x(),start.y(),end.x()-start.x(),end.y()-start.y())
        elif mode=="Arrow":
            painter.drawLine(start,end);painter.drawPolygon(self._arrow_head(start,end))
        elif mode=="Text":
            painter.setFont(QFont("Segoe UI",16,QFont.Weight.Bold));painter.drawText(start,text)

    def paintEvent(self,_event):
        painter=QPainter(self);painter.drawImage(0,0,self.image)
        pen=QPen(QColor("#e32020"),4);pen.setCapStyle(Qt.PenCapStyle.RoundCap);painter.setPen(pen);painter.setBrush(Qt.BrushStyle.NoBrush)
        for item in self.items:self._draw_item(painter,item)
        if self.start is not None and self.current is not None:self._draw_item(painter,(self.mode,self.start,self.current,""))
        painter.end()

    def render_image(self) -> QImage:
        result=self.image.copy();painter=QPainter(result)
        pen=QPen(QColor("#e32020"),4);pen.setCapStyle(Qt.PenCapStyle.RoundCap);painter.setPen(pen);painter.setBrush(Qt.BrushStyle.NoBrush)
        for item in self.items:self._draw_item(painter,item)
        painter.end();return result


class ImageAnnotationDialog(QDialog):
    def __init__(self,path: str,parent=None):
        super().__init__(parent);self.source=Path(path);self.output_path=""
        self.setWindowTitle(f"Annotate evidence — {self.source.name}");self.resize(1200,820)
        root=QVBoxLayout(self);toolbar=QHBoxLayout();group=QButtonGroup(self)
        self.canvas=AnnotationCanvas(str(self.source),self)
        for i,mode in enumerate(["Rectangle","Ellipse","Arrow","Text"]):
            button=QRadioButton(mode);button.setChecked(i==0);button.toggled.connect(lambda checked,m=mode: checked and self.canvas.set_mode(m));group.addButton(button);toolbar.addWidget(button)
        undo=QPushButton("Undo");undo.clicked.connect(self.canvas.undo);save=QPushButton("Save annotated copy");save.clicked.connect(self.save_copy);cancel=QPushButton("Cancel");cancel.clicked.connect(self.reject)
        toolbar.addStretch(1);toolbar.addWidget(undo);toolbar.addWidget(save);toolbar.addWidget(cancel);root.addLayout(toolbar)
        hint=QLabel("Annotations are non-destructive. Saving creates a new evidence file and leaves the original unchanged.");hint.setStyleSheet("color:#647581;");root.addWidget(hint)
        scroll=QScrollArea();scroll.setWidget(self.canvas);scroll.setWidgetResizable(False);root.addWidget(scroll,1)

    def save_copy(self):
        suffix=self.source.suffix.lower()
        if suffix not in {".png",".jpg",".jpeg",".bmp",".webp"}:suffix=".png"
        suggested=self.source.with_name(f"{self.source.stem}_annotated_{datetime.now():%Y%m%d_%H%M%S}.png")
        path,_=QFileDialog.getSaveFileName(self,"Save annotated evidence",str(suggested),"PNG Image (*.png)")
        if not path:return
        if not path.lower().endswith(".png"):path+=".png"
        image=self.canvas.render_image()
        if not image.save(path,"PNG"):
            QMessageBox.critical(self,"Annotation","Could not save annotated image.");return
        self.output_path=path;self.accept()
