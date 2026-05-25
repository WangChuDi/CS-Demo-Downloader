"""
主窗口
"""
import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QProgressBar, QFileDialog, QMessageBox, QHeaderView,
    QCheckBox, QFrame
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon

from cs_demo_downloader.core.config import Config, load_config, save_config
from cs_demo_downloader.core.utils import get_demo_filename_from_url
from .styles import STYLESHEET
from .user_manager import Add5EUserDialog, AddPWAUserDialog, AddSteamUserDialog
from .download_worker import FetchDemosWorker, DownloadWorker


class UserTagWidget(QFrame):
    """用户标签组件"""
    
    def __init__(self, name: str, on_delete=None, parent=None):
        super().__init__(parent)
        self.name = name
        self.on_delete = on_delete
        self.setup_ui()
    
    def setup_ui(self):
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #0f3460;
                border-radius: 4px;
                padding: 2px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(4)
        
        label = QLabel(self.name)
        label.setStyleSheet("color: #eaeaea;")
        layout.addWidget(label)
        
        delete_btn = QPushButton("×")
        delete_btn.setFixedSize(20, 20)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #e94560;
                border: none;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #ff6b83;
            }
        """)
        delete_btn.clicked.connect(self._on_delete)
        layout.addWidget(delete_btn)
    
    def _on_delete(self):
        if self.on_delete:
            self.on_delete(self.name)


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.demos_5e = []  # [(match_id, demo_url, user_name, platform_or_steamid), ...]
        self.demos_pwa = []
        self.demos_steam = []
        self.fetch_worker = None
        self.download_worker = None
        
        self.setup_ui()
        self.load_users()
    
    def setup_ui(self):
        self.setWindowTitle("CS Demo Downloader")
        self.setMinimumSize(800, 700)
        self.setStyleSheet(STYLESHEET)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title = QLabel("CS Demo Downloader")
        title.setObjectName("titleLabel")
        layout.addWidget(title)
        
        # 下载路径
        path_group = QGroupBox("下载路径")
        path_layout = QHBoxLayout(path_group)
        
        self.path_edit = QLineEdit()
        self.path_edit.setText(self.config.download_path)
        self.path_edit.setPlaceholderText("选择 Demo 保存目录...")
        path_layout.addWidget(self.path_edit)
        
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_path)
        path_layout.addWidget(browse_btn)
        
        layout.addWidget(path_group)
        
        # 用户管理区域
        users_layout = QHBoxLayout()
        
        # 5E 用户
        self.users_5e_group = QGroupBox("5E 用户")
        users_5e_layout = QHBoxLayout(self.users_5e_group)
        users_5e_layout.setAlignment(Qt.AlignLeft)
        
        self.users_5e_container = QHBoxLayout()
        users_5e_layout.addLayout(self.users_5e_container)
        
        add_5e_btn = QPushButton("+ 添加")
        add_5e_btn.setObjectName("addButton")
        add_5e_btn.clicked.connect(self.add_5e_user)
        users_5e_layout.addWidget(add_5e_btn)
        users_5e_layout.addStretch()
        
        users_layout.addWidget(self.users_5e_group)
        
        # 完美世界用户
        self.users_pwa_group = QGroupBox("完美世界用户")
        users_pwa_layout = QHBoxLayout(self.users_pwa_group)
        users_pwa_layout.setAlignment(Qt.AlignLeft)
        
        self.users_pwa_container = QHBoxLayout()
        users_pwa_layout.addLayout(self.users_pwa_container)
        
        add_pwa_btn = QPushButton("+ 添加")
        add_pwa_btn.setObjectName("addButton")
        add_pwa_btn.clicked.connect(self.add_pwa_user)
        users_pwa_layout.addWidget(add_pwa_btn)
        users_pwa_layout.addStretch()
        
        users_layout.addWidget(self.users_pwa_group)

        # Steam 官匹用户
        self.users_steam_group = QGroupBox("Steam 官匹用户")
        users_steam_layout = QHBoxLayout(self.users_steam_group)
        users_steam_layout.setAlignment(Qt.AlignLeft)

        self.users_steam_container = QHBoxLayout()
        users_steam_layout.addLayout(self.users_steam_container)

        add_steam_btn = QPushButton("+ 添加")
        add_steam_btn.setObjectName("addButton")
        add_steam_btn.clicked.connect(self.add_steam_user)
        users_steam_layout.addWidget(add_steam_btn)
        users_steam_layout.addStretch()

        users_layout.addWidget(self.users_steam_group)
        
        layout.addLayout(users_layout)
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新 Demo 列表")
        refresh_btn.setObjectName("primaryButton")
        refresh_btn.clicked.connect(self.refresh_demos)
        layout.addWidget(refresh_btn)
        
        # Demo 列表标签页
        self.tab_widget = QTabWidget()
        
        # 5E Demo 标签页
        self.table_5e = self.create_demo_table()
        self.tab_widget.addTab(self.table_5e, "5E Demo")
        
        # 完美世界 Demo 标签页
        self.table_pwa = self.create_demo_table()
        self.tab_widget.addTab(self.table_pwa, "完美世界 Demo")

        # Steam 官匹 Demo 标签页
        self.table_steam = self.create_demo_table()
        self.tab_widget.addTab(self.table_steam, "Steam 官匹 Demo")
        
        layout.addWidget(self.tab_widget)
        
        # 底部控制区
        bottom_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("下载选中")
        self.download_btn.setObjectName("primaryButton")
        self.download_btn.clicked.connect(self.download_selected)
        bottom_layout.addWidget(self.download_btn)
        
        bottom_layout.addStretch()
        
        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("statusLabel")
        bottom_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(300)
        self.progress_bar.setValue(0)
        bottom_layout.addWidget(self.progress_bar)
        
        layout.addLayout(bottom_layout)
    
    def create_demo_table(self) -> QTableWidget:
        """创建 Demo 列表表格"""
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["选择", "用户", "Match ID", "状态"])
        
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        
        table.setColumnWidth(0, 50)
        table.setColumnWidth(3, 100)
        
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setAlternatingRowColors(True)
        
        return table
    
    def load_users(self):
        """加载用户标签"""
        # 清空现有标签
        self.clear_layout(self.users_5e_container)
        self.clear_layout(self.users_pwa_container)
        self.clear_layout(self.users_steam_container)
        
        # 添加 5E 用户
        for i, user in enumerate(self.config.get_users_5e()):
            tag = UserTagWidget(user.name, lambda name, idx=i: self.delete_5e_user(idx))
            self.users_5e_container.addWidget(tag)
        
        # 添加完美世界用户
        for i, user in enumerate(self.config.get_users_pwa()):
            tag = UserTagWidget(user.name, lambda name, idx=i: self.delete_pwa_user(idx))
            self.users_pwa_container.addWidget(tag)

        # 添加 Steam 官匹用户
        for i, user in enumerate(self.config.get_users_steam()):
            tag = UserTagWidget(user.name, lambda name, idx=i: self.delete_steam_user(idx))
            self.users_steam_container.addWidget(tag)
    
    def clear_layout(self, layout):
        """清空布局中的所有组件"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def browse_path(self):
        """选择下载目录"""
        path = QFileDialog.getExistingDirectory(self, "选择下载目录")
        if path:
            self.path_edit.setText(path)
            self.config.download_path = path
            save_config(self.config)
    
    def add_5e_user(self):
        """添加 5E 用户"""
        dialog = Add5EUserDialog(self)
        if dialog.exec_():
            data = dialog.get_data()
            self.config.add_user_5e(data['name'], data['userid'])
            save_config(self.config)
            self.load_users()
    
    def add_pwa_user(self):
        """添加完美世界用户"""
        dialog = AddPWAUserDialog(self)
        if dialog.exec_():
            data = dialog.get_data()
            self.config.add_user_pwa(data['name'], data['steamid'], data['access_token'])
            save_config(self.config)
            self.load_users()
    
    def add_steam_user(self):
        """添加 Steam 官匹用户"""
        dialog = AddSteamUserDialog(self)
        if dialog.exec_():
            data = dialog.get_data()
            self.config.add_user_steam(
                data['name'],
                data['steamid'],
                data['api_key'],
                data['steamidkey'],
                data['knowncode'],
            )
            save_config(self.config)
            self.load_users()

    def delete_5e_user(self, index: int):
        """删除 5E 用户"""
        reply = QMessageBox.question(
            self, "确认删除", 
            "确定要删除这个用户吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.config.remove_user_5e(index)
            save_config(self.config)
            self.load_users()
    
    def delete_pwa_user(self, index: int):
        """删除完美世界用户"""
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除这个用户吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.config.remove_user_pwa(index)
            save_config(self.config)
            self.load_users()
    
    def delete_steam_user(self, index: int):
        """删除 Steam 官匹用户"""
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除这个用户吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.config.remove_user_steam(index)
            save_config(self.config)
            self.load_users()

    def refresh_demos(self):
        """刷新 Demo 列表"""
        if self.fetch_worker and self.fetch_worker.isRunning():
            return
        
        # 清空列表
        self.table_5e.setRowCount(0)
        self.table_pwa.setRowCount(0)
        self.table_steam.setRowCount(0)
        self.demos_5e.clear()
        self.demos_pwa.clear()
        self.demos_steam.clear()
        
        self.status_label.setText("正在获取 Demo 列表...")
        
        self.fetch_worker = FetchDemosWorker(self.config)
        self.fetch_worker.demo_found.connect(self.on_demo_found)
        self.fetch_worker.status_update.connect(lambda msg: self.status_label.setText(msg))
        self.fetch_worker.finished_signal.connect(self.on_fetch_complete)
        self.fetch_worker.start()
    
    def on_demo_found(self, platform: str, user_name: str, match_id: str, demo_url: str, platform_or_steamid: str):
        """发现新 Demo"""
        if platform == '5e':
            table = self.table_5e
            self.demos_5e.append((match_id, demo_url, user_name, platform_or_steamid))
        elif platform == 'pwa':
            table = self.table_pwa
            self.demos_pwa.append((match_id, demo_url, user_name, platform_or_steamid))
        else:
            table = self.table_steam
            self.demos_steam.append((match_id, demo_url, user_name, platform_or_steamid))
        
        row = table.rowCount()
        table.insertRow(row)
        
        # 复选框
        checkbox = QCheckBox()
        checkbox.setChecked(True)
        table.setCellWidget(row, 0, checkbox)
        
        # 用户
        table.setItem(row, 1, QTableWidgetItem(user_name))
        
        # Match ID
        table.setItem(row, 2, QTableWidgetItem(match_id))
        
        # 状态
        status = self.check_demo_exists(demo_url)
        table.setItem(row, 3, QTableWidgetItem(status))
    
    def check_demo_exists(self, demo_url: str) -> str:
        """检查 Demo 是否已存在"""
        if not self.config.download_path:
            return "待下载"
        
        dem_filename = get_demo_filename_from_url(demo_url)
        dem_path = os.path.join(self.config.download_path, dem_filename)
        if os.path.exists(dem_path):
            return "已存在"
        
        return "待下载"
    
    def on_fetch_complete(self):
        """获取 Demo 列表完成"""
        total = len(self.demos_5e) + len(self.demos_pwa) + len(self.demos_steam)
        self.status_label.setText(f"找到 {total} 个 Demo")
    
    def download_selected(self):
        """下载选中的 Demo"""
        if not self.config.download_path:
            QMessageBox.warning(self, "错误", "请先选择下载目录")
            return
        
        if self.download_worker and self.download_worker.isRunning():
            return
        
        # 收集选中的 Demo
        demos_to_download = []
        
        # 5E Demo
        for row in range(self.table_5e.rowCount()):
            checkbox = self.table_5e.cellWidget(row, 0)
            status_item = self.table_5e.item(row, 3)
            if checkbox and checkbox.isChecked() and status_item.text() != "已存在":
                demos_to_download.append(self.demos_5e[row])
        
        # 完美世界 Demo
        for row in range(self.table_pwa.rowCount()):
            checkbox = self.table_pwa.cellWidget(row, 0)
            status_item = self.table_pwa.item(row, 3)
            if checkbox and checkbox.isChecked() and status_item.text() != "已存在":
                demos_to_download.append(self.demos_pwa[row])

        # Steam 官匹 Demo
        for row in range(self.table_steam.rowCount()):
            checkbox = self.table_steam.cellWidget(row, 0)
            status_item = self.table_steam.item(row, 3)
            if checkbox and checkbox.isChecked() and status_item.text() != "已存在":
                demos_to_download.append(self.demos_steam[row])
        
        if not demos_to_download:
            QMessageBox.information(self, "提示", "没有需要下载的 Demo")
            return
        
        self.download_btn.setEnabled(False)
        self.progress_bar.setMaximum(len(demos_to_download))
        self.progress_bar.setValue(0)
        
        self.download_worker = DownloadWorker(demos_to_download, self.config.download_path)
        self.download_worker.progress_update.connect(self.on_download_progress)
        self.download_worker.download_complete.connect(self.on_single_download_complete)
        self.download_worker.all_complete.connect(self.on_all_download_complete)
        self.download_worker.start()
    
    def on_download_progress(self, current: int, total: int, match_id: str, status: str):
        """下载进度更新"""
        self.progress_bar.setValue(current)
        self.status_label.setText(f"正在下载 {current}/{total}: {match_id} - {status}")
    
    def on_single_download_complete(self, match_id: str, success: bool):
        """单个下载完成"""
        status = "已完成" if success else "失败"
        
        # 更新表格状态
        for table in [self.table_5e, self.table_pwa, self.table_steam]:
            for row in range(table.rowCount()):
                item = table.item(row, 2)
                if item and item.text() == match_id:
                    table.setItem(row, 3, QTableWidgetItem(status))
                    break
    
    def on_all_download_complete(self):
        """全部下载完成"""
        self.download_btn.setEnabled(True)
        self.status_label.setText("下载完成")
        QMessageBox.information(self, "完成", "所有 Demo 下载完成！")
    
    def closeEvent(self, event):
        """关闭窗口时保存配置"""
        self.config.download_path = self.path_edit.text()
        save_config(self.config)
        
        # 停止工作线程
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.fetch_worker.terminate()
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.stop()
            self.download_worker.wait()
        
        event.accept()
