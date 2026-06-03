# spinner_demo.py
# Демонстрация спиннеров для вкладок

import sys
import random
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QLabel, QPushButton, QHBoxLayout
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap, QIcon, QColor


class SpinnerIcon:
    """Генератор анимированной иконки-спиннера."""
    _cache: dict[tuple, QIcon] = {}

    @classmethod
    def get(cls, size: int = 16, angle: int = 0, style: str = "dots") -> QIcon:
        key = (size, angle, style)
        if key not in cls._cache:
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            if style == "dots":
                cls._draw_dots(painter, size, angle)
            elif style == "circle":
                cls._draw_circle(painter, size, angle)
            elif style == "pie":
                cls._draw_pie(painter, size, angle)
            elif style == "bars":
                cls._draw_bars(painter, size, angle)
            
            painter.end()
            cls._cache[key] = QIcon(pixmap)
        return cls._cache[key]

    @classmethod
    def _draw_dots(cls, painter: QPainter, size: int, angle: int):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.translate(size / 2, size / 2)
        painter.rotate(angle)
        for i in range(8):
            alpha = 255 - i * 25
            painter.setBrush(QColor(100, 100, 100, alpha))
            painter.drawEllipse(-2, -size/2 + 4, 4, 4)
            painter.rotate(45)

    @classmethod
    def _draw_circle(cls, painter: QPainter, size: int, angle: int):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.translate(size / 2, size / 2)
        painter.rotate(angle)
        for i in range(12):
            alpha = 255 - i * 20
            painter.setBrush(QColor(70, 130, 200, alpha))
            painter.drawRoundedRect(-1, -size/2 + 3, 2, 5, 1, 1)
            painter.rotate(30)

    @classmethod
    def _draw_pie(cls, painter: QPainter, size: int, angle: int):
        from PySide6.QtCore import QRectF
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(200, 100, 50))
        painter.translate(size / 2, size / 2)
        painter.rotate(angle)
        rect = QRectF(-size/2 + 2, -size/2 + 2, size - 4, size - 4)
        painter.drawPie(rect, 0, 90 * 16)

    @classmethod
    def _draw_bars(cls, painter: QPainter, size: int, angle: int):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.translate(size / 2, size / 2)
        painter.rotate(angle)
        for i in range(5):
            progress = (angle % 360) / 360.0
            height = 4 + int(8 * (0.5 + 0.5 * ((i + progress) % 1.0)))
            alpha = 100 + int(155 * (0.5 + 0.5 * ((i + progress) % 1.0)))
            painter.setBrush(QColor(60, 180, 75, alpha))
            painter.drawRoundedRect(-1 + i*3 - 6, -height/2, 2, height, 1, 1)


class SpinnerTab(QWidget):
    def __init__(self, name: str, style: str):
        super().__init__()
        self.name = name
        self.style = style
        self.angle = 0
        self.loading = False
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_spinner)
        self.timer.setInterval(80)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel(f"Стиль: {self.style}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        preview = QLabel()
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setMinimumHeight(50)
        layout.addWidget(preview)
        self.preview_label = preview
        
        btn_layout = QHBoxLayout()
        self.toggle_btn = QPushButton("Запустить")
        self.toggle_btn.clicked.connect(self.toggle_loading)
        btn_layout.addWidget(self.toggle_btn)
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        
        self._update_preview()
    
    def _update_spinner(self):
        self.angle = (self.angle + 30) % 360
        self._update_preview()
    
    def _update_preview(self):
        icon = SpinnerIcon.get(32, self.angle, self.style)
        self.preview_label.setPixmap(icon.pixmap(32, 32))
    
    def toggle_loading(self):
        self.loading = not self.loading
        if self.loading:
            self.timer.start()
            self.toggle_btn.setText("Остановить")
        else:
            self.timer.stop()
            self.toggle_btn.setText("Запустить")
    
    def get_icon(self) -> QIcon:
        return SpinnerIcon.get(16, self.angle, self.style)


class DemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Демо спиннеров для вкладок")
        self.resize(400, 300)
        
        self._tab_widget = QTabWidget()
        self.setCentralWidget(self._tab_widget)
        
        self._tabs: list[SpinnerTab] = []
        self._styles = ["dots", "circle", "pie", "bars"]
        
        for style in self._styles:
            tab = SpinnerTab(style.capitalize(), style)
            self._tabs.append(tab)
            self._tab_widget.addTab(tab, style.capitalize())
        
        self._global_timer = QTimer(self)
        self._global_timer.timeout.connect(self._update_tab_icons)
        self._global_timer.start(80)
    
    def _update_tab_icons(self):
        for i, tab in enumerate(self._tabs):
            if tab.loading:
                self._tab_widget.setTabIcon(i, tab.get_icon())
            else:
                self._tab_widget.setTabIcon(i, QIcon())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DemoWindow()
    window.show()
    sys.exit(app.exec())
