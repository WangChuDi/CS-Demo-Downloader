#!/usr/bin/env python3
"""
CS Demo Downloader - GUI 入口
"""
import sys

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from .gui.main_window import MainWindow


def main():
    # 高 DPI 支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setApplicationName("CS Demo Downloader")
    
    window = MainWindow()
    window.show()

    return app.exec_()


if __name__ == '__main__':
    main()
