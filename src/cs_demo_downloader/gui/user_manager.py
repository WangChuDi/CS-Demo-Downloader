"""
用户管理对话框
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox
)
from PyQt5.QtCore import Qt


class Add5EUserDialog(QDialog):
    """添加 5E 用户对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加 5E 用户")
        self.setMinimumWidth(400)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 表单
        form = QFormLayout()
        form.setSpacing(10)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("用于显示的别名")
        form.addRow("用户别名:", self.name_edit)
        
        self.userid_edit = QLineEdit()
        self.userid_edit.setPlaceholderText("例如: 11814738gjdwn7")
        form.addRow("5E User ID:", self.userid_edit)
        
        layout.addLayout(form)
        
        # 说明
        hint = QLabel("提示: User ID 可在 5E 个人主页 URL 中找到")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("添加")
        ok_btn.setObjectName("primaryButton")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
    
    def get_data(self):
        return {
            'name': self.name_edit.text().strip(),
            'userid': self.userid_edit.text().strip()
        }
    
    def accept(self):
        data = self.get_data()
        if not data['name']:
            QMessageBox.warning(self, "错误", "请输入用户别名")
            return
        if not data['userid']:
            QMessageBox.warning(self, "错误", "请输入 5E User ID")
            return
        super().accept()


class AddPWAUserDialog(QDialog):
    """添加完美世界用户对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加完美世界用户")
        self.setMinimumWidth(450)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 表单
        form = QFormLayout()
        form.setSpacing(10)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("用于显示的别名")
        form.addRow("用户别名:", self.name_edit)
        
        self.steamid_edit = QLineEdit()
        self.steamid_edit.setPlaceholderText("例如: 76561198159976336")
        form.addRow("Steam ID:", self.steamid_edit)
        
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("从完美世界客户端获取")
        form.addRow("Access Token:", self.token_edit)
        
        layout.addLayout(form)
        
        # 说明
        hint = QLabel("提示: Access Token 可通过浏览器开发者工具在完美世界网页登录后获取")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("添加")
        ok_btn.setObjectName("primaryButton")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
    
    def get_data(self):
        return {
            'name': self.name_edit.text().strip(),
            'steamid': self.steamid_edit.text().strip(),
            'access_token': self.token_edit.text().strip()
        }
    
    def accept(self):
        data = self.get_data()
        if not data['name']:
            QMessageBox.warning(self, "错误", "请输入用户别名")
            return
        if not data['steamid']:
            QMessageBox.warning(self, "错误", "请输入 Steam ID")
            return
        if not data['access_token']:
            QMessageBox.warning(self, "错误", "请输入 Access Token")
            return
        super().accept()



class AddSteamUserDialog(QDialog):
    """添加 Steam 官匹用户对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加 Steam 官匹用户")
        self.setMinimumWidth(500)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        form = QFormLayout()
        form.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("用于显示的别名")
        form.addRow("用户别名:", self.name_edit)

        self.steamid_edit = QLineEdit()
        self.steamid_edit.setPlaceholderText("例如: 76561198159976336")
        form.addRow("Steam ID64:", self.steamid_edit)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("Steam Web API Key")
        form.addRow("API Key:", self.api_key_edit)

        self.steamidkey_edit = QLineEdit()
        self.steamidkey_edit.setPlaceholderText("从 CS2 比赛分享代码设置中获取")
        form.addRow("Steam ID Key:", self.steamidkey_edit)

        self.knowncode_edit = QLineEdit()
        self.knowncode_edit.setPlaceholderText("CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx")
        form.addRow("Known Share Code:", self.knowncode_edit)


        layout.addLayout(form)

        hint = QLabel("提示: Steam Web API 只能获取 share code 游标；真实 Demo URL 还需要 Steam GC full match info。当前版本会获取 share code，但未配置 GC 解析器时不会返回假下载地址。")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("添加")
        ok_btn.setObjectName("primaryButton")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

    def get_data(self):
        return {
            'name': self.name_edit.text().strip(),
            'steamid': self.steamid_edit.text().strip(),
            'api_key': self.api_key_edit.text().strip(),
            'steamidkey': self.steamidkey_edit.text().strip(),
            'knowncode': self.knowncode_edit.text().strip()
        }

    def accept(self):
        data = self.get_data()
        required_fields = [
            ('name', "请输入用户别名"),
            ('steamid', "请输入 Steam ID64"),
            ('api_key', "请输入 Steam Web API Key"),
            ('steamidkey', "请输入 Steam ID Key"),
            ('knowncode', "请输入 Known Share Code"),
        ]
        for field, message in required_fields:
            if not data[field]:
                QMessageBox.warning(self, "错误", message)
                return
        super().accept()
