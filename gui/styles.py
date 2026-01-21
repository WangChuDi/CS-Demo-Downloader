"""
GUI 样式定义
"""

STYLESHEET = """
QMainWindow {
    background-color: #1a1a2e;
}

QWidget {
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
    color: #eaeaea;
}

QGroupBox {
    border: 1px solid #3d3d5c;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 10px;
    background-color: #16213e;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 15px;
    padding: 0 8px;
    color: #00d9ff;
    font-weight: bold;
}

QPushButton {
    background-color: #0f3460;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    min-width: 80px;
}

QPushButton:hover {
    background-color: #1a4a7a;
}

QPushButton:pressed {
    background-color: #0a2540;
}

QPushButton:disabled {
    background-color: #2d2d4a;
    color: #666;
}

QPushButton#primaryButton {
    background-color: #00d9ff;
    color: #1a1a2e;
    font-weight: bold;
}

QPushButton#primaryButton:hover {
    background-color: #33e0ff;
}

QPushButton#addButton {
    background-color: #4ecca3;
    color: #1a1a2e;
    font-weight: bold;
    min-width: 60px;
}

QPushButton#addButton:hover {
    background-color: #6fd9b8;
}

QPushButton#deleteButton {
    background-color: #e94560;
    min-width: 60px;
}

QPushButton#deleteButton:hover {
    background-color: #ff6b83;
}

QLineEdit {
    background-color: #0f3460;
    border: 1px solid #3d3d5c;
    border-radius: 6px;
    padding: 8px 12px;
    color: #eaeaea;
}

QLineEdit:focus {
    border-color: #00d9ff;
}

QTableWidget {
    background-color: #16213e;
    border: 1px solid #3d3d5c;
    border-radius: 8px;
    gridline-color: #2d2d4a;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #2d2d4a;
}

QTableWidget::item:selected {
    background-color: #0f3460;
}

QHeaderView::section {
    background-color: #1a1a2e;
    color: #00d9ff;
    padding: 10px;
    border: none;
    border-bottom: 2px solid #00d9ff;
    font-weight: bold;
}

QTabWidget::pane {
    border: 1px solid #3d3d5c;
    border-radius: 8px;
    background-color: #16213e;
    top: -1px;
}

QTabBar::tab {
    background-color: #1a1a2e;
    color: #888;
    padding: 10px 20px;
    border: 1px solid #3d3d5c;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #16213e;
    color: #00d9ff;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background-color: #0f3460;
}

QProgressBar {
    border: none;
    border-radius: 6px;
    background-color: #0f3460;
    height: 20px;
    text-align: center;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #00d9ff, stop:1 #4ecca3);
    border-radius: 6px;
}

QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid #3d3d5c;
    background-color: #0f3460;
}

QCheckBox::indicator:checked {
    background-color: #00d9ff;
    border-color: #00d9ff;
}

QScrollBar:vertical {
    background-color: #1a1a2e;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #3d3d5c;
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #00d9ff;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QLabel#titleLabel {
    font-size: 18px;
    font-weight: bold;
    color: #00d9ff;
}

QLabel#statusLabel {
    color: #4ecca3;
}
"""
