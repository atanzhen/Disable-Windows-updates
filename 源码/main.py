# -*- coding: utf-8 -*-
"""
禁止自动重启工具  v1.1.0
禁止 Windows 自动更新 / 自动安装 / 自动重启，并把设置固化到系统。
永久免费 · 开放源码    出品：atusu.cn
"""
import os
import sys
import time
import shutil
import subprocess
import winreg

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer
from PySide6.QtGui import QFont, QIcon, QPixmap, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QDialog, QTextBrowser, QSizePolicy,
)

APP_NAME = "禁止自动重启工具"
APP_VER = "1.1.0"
BUILD_DATE = "2026-11"
SITE = "atusu.cn"
URL = "https://atusu.cn"
BASE = r"C:\ProgramData\NoAutoRestart"
TASK = "NoAutoRestartGuard"
NO_WIN = 0x08000000

AU = r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
CC = r"SYSTEM\CurrentControlSet\Control\CrashControl"
SVC = r"SYSTEM\CurrentControlSet\Services\wuauserv"

EDITION = {
    "Core": "家庭版", "CoreSingleLanguage": "家庭单语言版", "CoreCountrySpecific": "家庭中文版",
    "Professional": "专业版", "ProfessionalN": "专业版 N", "ProfessionalWorkstation": "专业工作站版",
    "ProfessionalEducation": "专业教育版", "Enterprise": "企业版", "EnterpriseN": "企业版 N",
    "EnterpriseS": "企业版 LTSC", "EnterpriseSN": "企业版 LTSC N",
    "Education": "教育版", "EducationN": "教育版 N", "IoTEnterprise": "IoT 企业版",
    "ServerStandard": "Server 标准版", "ServerDatacenter": "Server 数据中心版",
    "Ultimate": "旗舰版", "Starter": "简易版",
}


# --------------------------------------------------------------------------- utils
def res(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def reg(path, name, default=None):
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return default


def windows_info():
    build, disp, ed = 0, "", ""
    try:
        build = int(reg(r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "CurrentBuildNumber", "0"))
    except Exception:
        build = 0
    try:
        disp = str(reg(r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "DisplayVersion", "") or "")
    except Exception:
        disp = ""
    try:
        ed = str(reg(r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "EditionID", "") or "")
    except Exception:
        ed = ""
    if build >= 22000:
        fam = "Windows 11"
    elif build >= 10240:
        fam = "Windows 10"
    elif build > 0:
        fam = "旧版 Windows"
    else:
        fam = "Windows"
    return {
        "build": build,
        "display": disp,
        "edition": EDITION.get(ed, ed or "未知版本"),
        "family": fam,
        "ok": build >= 10240,
    }


def task_exists():
    """直接查任务文件（不调用 schtasks，兼容性最好、无进程开销）。"""
    p = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                     "System32", "Tasks", TASK)
    return os.path.exists(p)


def deployed_ver():
    p = os.path.join(BASE, "guard-version.txt")
    try:
        with open(p, "r", encoding="ascii", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        return ""


def deployed_marker():
    return os.path.exists(os.path.join(BASE, "deployed.txt"))


def last_run_age():
    """返回守护任务最近一次巡检距今的秒数，没有记录返回 None。"""
    try:
        return time.time() - os.path.getmtime(os.path.join(BASE, "last-run.txt"))
    except Exception:
        return None


def ensure_scripts():
    pkg = os.path.join(BASE, "pkg")
    try:
        os.makedirs(pkg, exist_ok=True)
        for f in ("guard.ps1", "deploy.ps1", "restore.ps1"):
            shutil.copyfile(res(os.path.join("scripts", f)), os.path.join(pkg, f))
    except Exception:
        pass
    return pkg


class PsRunner(QThread):
    line = Signal(str)
    done = Signal(int)

    def __init__(self, script, parent=None):
        super().__init__(parent)
        self.script = script

    def run(self):
        try:
            p = subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-File", self.script],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=NO_WIN,
            )
            for ln in p.stdout:
                self.line.emit(ln.rstrip())
            self.done.emit(p.wait())
        except Exception as e:  # pragma: no cover
            self.line.emit("错误：%s" % e)
            self.done.emit(-1)


# --------------------------------------------------------------------------- UI parts
class LinkLabel(QLabel):
    """无下划线、可点击的文字链接。"""

    def __init__(self, text, url=None, color="#94A3B8", hover="#2F6BFF", size=9,
                 bold=False, on_click=None):
        super().__init__(text)
        self._url = url
        self._on_click = on_click
        self._size = size
        self._bold = bold
        self._color = color
        self._hover = hover
        self._paint(color)
        if url or on_click:
            self.setCursor(Qt.PointingHandCursor)
        if url:
            self.setToolTip("点击打开 " + url)

    def _paint(self, color):
        w = "600" if self._bold else "400"
        self.setStyleSheet(
            "color:%s;font-size:%spt;font-weight:%s;background:transparent;"
            "text-decoration:none;" % (color, self._size, w)
        )

    def enterEvent(self, e):
        if self._url or self._on_click:
            self._paint(self._hover)

    def leaveEvent(self, e):
        self._paint(self._color)

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        if self._on_click:
            self._on_click()
        elif self._url:
            QDesktopServices.openUrl(QUrl(self._url))


class HeaderBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(104)
        self.setStyleSheet(
            "QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #16307A, stop:0.55 #2453C8, stop:1 #3B7BFF);}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(26, 0, 26, 0)
        lay.setSpacing(16)

        logo = QLabel()
        logo.setStyleSheet("background:transparent;border:none;")
        pm = QPixmap(res("icon_preview.png"))
        if not pm.isNull():
            logo.setPixmap(pm.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(logo)

        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(APP_NAME)
        f = QFont("Microsoft YaHei UI", 17)
        f.setBold(True)
        t.setFont(f)
        t.setStyleSheet("color:white;background:transparent;border:none;")
        s = QLabel("永久免费   ·   开放源码   ·   无需常驻后台   ·   v%s" % APP_VER)
        s.setStyleSheet("color:#BBD2FF;background:transparent;border:none;"
                        "font-family:'Microsoft YaHei UI';font-size:9.5pt;")
        col.addStretch()
        col.addWidget(t)
        col.addWidget(s)
        col.addStretch()
        lay.addLayout(col)
        lay.addStretch()


class StatusRow(QWidget):
    def __init__(self, name, hint):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.dot = QLabel()
        self.dot.setFixedSize(9, 9)
        lay.addWidget(self.dot)

        self.name = QLabel(name)
        self.name.setFixedWidth(72)
        self.name.setStyleSheet("color:#3C4A63;font-size:10pt;")
        lay.addWidget(self.name)

        self.value = QLabel("-")
        self.value.setStyleSheet("color:#0F172A;font-size:10pt;font-weight:600;")
        lay.addWidget(self.value)

        lay.addStretch()

        self.hint = QLabel(hint)
        self.hint.setStyleSheet("color:#93A0B5;font-size:9pt;")
        lay.addWidget(self.hint)

    def set(self, ok, text, hint_text=None):
        color = "#16A34A" if ok else "#DC2626"
        self.dot.setStyleSheet("background:%s;border-radius:4px;" % color)
        self.value.setText(text)
        if hint_text is not None:
            self.hint.setText(hint_text)


PRIMARY = (
    "QPushButton{background:#2F6BFF;color:white;border:none;border-radius:9px;"
    "font-size:11pt;font-weight:600;font-family:'Microsoft YaHei UI';}"
    "QPushButton:hover{background:#2557DB;}"
    "QPushButton:pressed{background:#1D47BA;}"
    "QPushButton:disabled{background:#A9C0F0;color:#EDF2FF;}"
)
NORMAL = (
    "QPushButton{background:white;color:#33415C;border:1px solid #D6DEEA;"
    "border-radius:9px;font-size:11pt;font-weight:600;font-family:'Microsoft YaHei UI';}"
    "QPushButton:hover{background:#F1F5FD;border-color:#B9C8E4;}"
    "QPushButton:pressed{background:#E7EEFB;}"
    "QPushButton:disabled{color:#A9B4C6;}"
)
DANGER = (
    "QPushButton{background:white;color:#B4443C;border:1px solid #E4CFCC;"
    "border-radius:9px;font-size:11pt;font-weight:600;font-family:'Microsoft YaHei UI';}"
    "QPushButton:hover{background:#FDF3F2;border-color:#D8B2AD;}"
    "QPushButton:pressed{background:#FAE7E5;}"
    "QPushButton:disabled{color:#B9C0CD;border-color:#E6EAF2;background:white;}"
)
DONE = (
    "QPushButton{background:#E9F8EF;color:#15803D;border:1px solid #B4E3C6;"
    "border-radius:9px;font-size:11pt;font-weight:600;font-family:'Microsoft YaHei UI';}"
    "QPushButton:disabled{background:#E9F8EF;color:#15803D;border:1px solid #B4E3C6;}"
)
GHOST = (
    "QPushButton{background:transparent;color:#5B6B85;border:1px solid #DCE3EF;"
    "border-radius:8px;font-size:10pt;font-weight:600;font-family:'Microsoft YaHei UI';}"
    "QPushButton:hover{background:white;border-color:#BFCBE0;color:#2F6BFF;}"
    "QPushButton:pressed{background:#EEF3FC;}"
)

CAPTION = "color:#8A97AC;font-size:8.5pt;background:transparent;"
CAPTION_OFF = "color:#B6BECC;font-size:8.5pt;background:transparent;"

# 主按钮在不同状态下的文案
LOCK_TEXT = "一键禁用更新和重启"
DONE_TEXT = "已配置完成锁定"
STALE_TEXT = "升级守护并重新锁定"

CAP_LOCK_OFF = "禁止自动更新与自动重启\n并写入系统长期生效"
CAP_LOCK_ON = "本机已处于保护状态\n如需打补丁请用「临时恢复更新」"
CAP_LOCK_STALE = "守护任务版本较旧\n点此升级并重新锁定"

CAP_RESTORE_OFF = "需先启用锁定才能操作\n未启用时无更新可恢复"
CAP_RESTORE_ON = "只放开更新，自动重启仍禁止\n装完补丁再点上方主按钮重新锁定"
CAP_RESTORE_FLAG = "当前已处于更新模式\n装完补丁请点「一键禁用更新和重启」重新锁定"

CAP_RESET_OFF = "需先启用锁定才能操作\n未启用时没有配置可恢复"
CAP_RESET_ON = "取消全部设置，恢复系统默认\n更新与自动重启都会恢复"

# 统一美化所有滚动条（去掉系统默认的灰色方块样式）
SCROLLBAR = """
QScrollBar:vertical{background:transparent;width:12px;margin:4px 2px 4px 2px;}
QScrollBar::handle:vertical{background:#B7C7DC;border:none;border-radius:4px;min-height:36px;}
QScrollBar::handle:vertical:hover{background:#97ADC9;}
QScrollBar::handle:vertical:pressed{background:#8098B8;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{
    height:0;width:0;background:transparent;border:none;subcontrol-position:top;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent;}
QScrollBar:horizontal{background:transparent;height:12px;margin:2px 4px 2px 4px;}
QScrollBar::handle:horizontal{background:#CCD6E6;border-radius:4px;min-width:36px;}
QScrollBar::handle:horizontal:hover{background:#A9BBD7;}
QScrollBar::handle:horizontal:pressed{background:#8CA2C6;}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{
    height:0;width:0;background:transparent;border:none;subcontrol-position:left;}
QScrollBar::add-page:horizontal,QScrollBar::sub-page:horizontal{background:transparent;}
"""

DLG_CSS = (
    "QTextEdit,QTextBrowser{border:1px solid #E2E8F2;border-radius:8px;padding:10px;"
    "font-family:'Microsoft YaHei UI';font-size:10pt;color:#243049;background:white;}"
)


def style_scroll(w):
    """给任意滚动区域套用统一的美化滚动条。"""
    try:
        w.verticalScrollBar().setStyleSheet(SCROLLBAR)
        w.horizontalScrollBar().setStyleSheet(SCROLLBAR)
    except Exception:
        pass


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.busy = False
        self.thread = None
        self._locked = False
        self._flag = False
        self._stale = False
        self.setWindowTitle("%s  v%s" % (APP_NAME, APP_VER))
        self.resize(820, 840)
        self.setMinimumSize(760, 780)
        self.setStyleSheet("background:#F4F6FB;font-family:'Microsoft YaHei UI';")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(HeaderBar())

        body = QVBoxLayout()
        body.setContentsMargins(24, 16, 24, 10)
        body.setSpacing(12)

        # ---- 状态卡片 ----
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(
            "QFrame#card{background:white;border:1px solid #E2E8F2;border-radius:10px;}"
            "QFrame#card QLabel{border:none;background:transparent;}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 12, 18, 12)
        cl.setSpacing(9)
        head = QLabel("系统当前状态")
        head.setStyleSheet("color:#8895AB;font-size:9pt;border:none;background:transparent;")
        cl.addWidget(head)
        self.row_upd = StatusRow("自动更新", "永不检查 / 下载 / 安装")
        self.row_rst = StatusRow("自动重启", "更新 + 蓝屏 + 计划任务")
        self.row_svc = StatusRow("更新服务", "wuauserv 引擎")
        self.row_tsk = StatusRow("守护任务", "开机 + 每 30 分钟")
        self.row_sys = StatusRow("系统环境", "Win10 / Win11")
        for w in (self.row_upd, self.row_rst, self.row_svc, self.row_tsk, self.row_sys):
            cl.addWidget(w)
        body.addWidget(card)

        # ---- 三个主操作按钮 + 每个按钮的说明 ----
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(7)

        self.b_lock = QPushButton(LOCK_TEXT)
        self.b_restore = QPushButton("临时恢复更新")
        self.b_reset = QPushButton("恢复配置")
        self.b_lock.setStyleSheet(PRIMARY)
        self.b_restore.setStyleSheet(NORMAL)
        self.b_reset.setStyleSheet(DANGER)

        self.b_lock.clicked.connect(lambda: self.run_op("lock"))
        self.b_restore.clicked.connect(lambda: self.run_op("restore"))
        self.b_reset.clicked.connect(lambda: self.run_op("reset"))

        caps = ["", "", ""]
        self.cap_lock = QLabel(caps[0])
        self.cap_restore = QLabel(caps[1])
        self.cap_reset = QLabel(caps[2])
        for i, (btn, cap) in enumerate(zip((self.b_lock, self.b_restore, self.b_reset),
                                           (self.cap_lock, self.cap_restore, self.cap_reset))):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(46)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            cap.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            cap.setWordWrap(True)
            cap.setMinimumHeight(30)
            cap.setStyleSheet(CAPTION)
            grid.addWidget(btn, 0, i)
            grid.addWidget(cap, 1, i)
            grid.setColumnStretch(i, 1)
        body.addLayout(grid)

        # ---- 次要操作 ----
        sub = QHBoxLayout()
        sub.setSpacing(10)
        self.b_log = QPushButton("查看日志")
        self.b_help = QPushButton("使用说明")
        for b in (self.b_log, self.b_help):
            b.setStyleSheet(GHOST)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(34)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.b_log.clicked.connect(self.show_log)
        self.b_help.clicked.connect(self.show_help)
        sub.addWidget(self.b_log)
        sub.addWidget(self.b_help)
        body.addLayout(sub)

        # ---- 输出区 ----
        lbl = QLabel("运行输出")
        lbl.setStyleSheet("color:#8895AB;font-size:9pt;")
        body.addWidget(lbl)
        self.out = QTextEdit()
        self.out.setReadOnly(True)
        self.out.setFont(QFont("Consolas", 9))
        self.out.setStyleSheet(
            "QTextEdit{background:white;border:1px solid #E2E8F2;border-radius:9px;"
            "padding:10px;color:#33415C;selection-background-color:#CBD9FF;}"
        )
        style_scroll(self.out)
        body.addWidget(self.out, 1)

        # ---- 页脚（版权 + 链接，无下划线）----
        foot = QHBoxLayout()
        foot.setSpacing(3)
        foot.setContentsMargins(0, 2, 0, 2)
        foot.addStretch(1)
        c1 = QLabel("© 2026")
        c1.setStyleSheet("color:#94A3B8;font-size:9pt;")
        foot.addWidget(c1)
        foot.addWidget(LinkLabel(SITE, URL))
        for txt in ("·", "永久免费", "·", "开放源码", "·"):
            x = QLabel(txt)
            x.setStyleSheet("color:#94A3B8;font-size:9pt;")
            foot.addWidget(x)
        foot.addWidget(LinkLabel("关于软件", on_click=self.show_about,
                                 color="#94A3B8", hover="#2F6BFF"))
        sep = QLabel("·")
        sep.setStyleSheet("color:#94A3B8;font-size:9pt;")
        foot.addWidget(sep)
        foot.addWidget(LinkLabel("开源说明", on_click=self.show_oss,
                                 color="#94A3B8", hover="#2F6BFF"))
        foot.addStretch(1)
        body.addLayout(foot)

        root.addLayout(body)

        self.refresh()
        for ln in self.welcome_text():
            self.say(ln)
        if not is_admin():
            self.say("")
            self.say("提示：当前没有管理员权限，锁死操作可能无法生效，请右键选择「以管理员身份运行」。")
        QTimer.singleShot(120, lambda: self.out.verticalScrollBar().setValue(0))

    # ------------------------------------------------------------------ helpers
    def welcome_text(self):
        i = windows_info()
        return [
            "欢迎使用  %s  v%s          永久免费 · 开放源码" % (APP_NAME, APP_VER),
            "",
            "【支持系统】",
            "  Windows 10 / Windows 11 全部版本（家庭版、专业版、企业版、教育版、LTSC）",
            "  当前系统：%s %s  Build %s%s" % (
                i["family"], i["edition"], i["build"],
                "" if i["ok"] else "   （版本过低，仅应用可用部分策略）"),
            "",
            "【功能说明】",
            "  ·  关闭 Windows 自动更新：自动检查、自动下载、自动安装 全部禁止",
            "  ·  禁止一切自动重启：更新装完、蓝屏崩溃、计划任务、开机续装 都不会重启",
            "  ·  取消全部更新与重启计划任务（20 多个）",
            "  ·  部署自愈守护任务：开机 + 每 30 分钟巡检，被系统改回来自动修复",
            "  ·  不影响安装软件、启用 Windows 功能、安装驱动、日常使用",
            "",
            "【使用方法】",
            "  1. 「一键禁用更新和重启」：禁止自动更新与自动重启，写入系统长期生效",
            "     启用成功后，按钮会变成绿色的「已配置完成锁定」，不需要再点",
            "  2. 「临时恢复更新」：需要打补丁时点它，只放开更新，装完再锁回去",
            "  3. 「恢复配置」：取消全部设置，让系统回到 Windows 默认状态",
            "     第 2、3 个按钮只有在已启用锁定后才可用，未启用时是灰色的",
            "",
            "【设置会一直有效】",
            "  锁死后的设置直接写进系统（注册表 + 服务 + 计划任务），",
            "  关掉本程序、甚至删掉本程序都不影响，电脑照常使用。",
            "  以后想改设置，重新下载运行本程序即可，它会识别当前状态。",
            "",
            "  只有你自己手动点「重启」，电脑才会重启。",
        ]

    def say(self, text):
        self.out.append(text)
        self.out.verticalScrollBar().setValue(self.out.verticalScrollBar().maximum())

    def set_busy(self, busy):
        self.busy = busy
        if busy:
            for b in (self.b_lock, self.b_restore, self.b_reset):
                b.setEnabled(False)
        else:
            self.apply_button_state()

    def lock_state(self):
        """返回 (是否已启用保护, 是否处于更新模式, 守护版本是否过期)。"""
        no_auto = reg(AU, "NoAutoUpdate", 0) == 1 and reg(AU, "AUOptions", 0) == 1
        no_rst = (reg(AU, "NoAutoRebootWithLoggedOnUsers", 0) == 1
                  and reg(CC, "AutoReboot", 1) == 0)
        svc_off = reg(SVC, "Start", 3) == 4
        flag = os.path.exists(os.path.join(BASE, "UPDATE_MODE.flag"))
        deployed = task_exists() or deployed_marker()
        dv = deployed_ver()
        stale = bool(dv) and dv != APP_VER
        locked = bool(no_auto and no_rst and svc_off and deployed and not flag)
        return locked, flag, stale

    def set_cap(self, lbl, text, on):
        lbl.setText(text)
        lbl.setStyleSheet(CAPTION if on else CAPTION_OFF)

    def apply_button_state(self):
        """按当前是否已启用保护，切换按钮文案与可用状态。"""
        locked, flag, stale = self.lock_state()
        self._locked, self._flag, self._stale = locked, flag, stale
        busy = self.busy
        need = "请先点「%s」启用保护后再操作" % LOCK_TEXT

        # ---- 主按钮：未启用 = 一键禁用更新和重启；已启用 = 已配置完成锁定 ----
        if locked and not stale:
            self.b_lock.setText(DONE_TEXT)
            self.b_lock.setStyleSheet(DONE)
            self.b_lock.setEnabled(False)
            self.b_lock.setCursor(Qt.ArrowCursor)
            self.b_lock.setToolTip("本机已处于保护状态：自动更新已禁用，"
                                   "任何情况下都不会自动重启。")
            self.set_cap(self.cap_lock, CAP_LOCK_ON, True)
        else:
            self.b_lock.setText(STALE_TEXT if (locked and stale) else LOCK_TEXT)
            self.b_lock.setStyleSheet(PRIMARY)
            self.b_lock.setEnabled(not busy)
            self.b_lock.setCursor(Qt.PointingHandCursor)
            if locked and stale:
                self.b_lock.setToolTip("守护任务还是旧版本，点一下升级并重新锁定。")
                self.set_cap(self.cap_lock, CAP_LOCK_STALE, True)
            else:
                self.b_lock.setToolTip("禁止 Windows 自动更新与自动重启，写入系统长期生效。")
                self.set_cap(self.cap_lock, CAP_LOCK_OFF, True)

        # ---- 另外两个：只有已启用锁定后才允许操作 ----
        usable = locked and not busy
        if usable:
            self.b_restore.setEnabled(True)
            self.b_restore.setCursor(Qt.PointingHandCursor)
            self.b_restore.setToolTip("")
            self.set_cap(self.cap_restore,
                         CAP_RESTORE_FLAG if flag else CAP_RESTORE_ON, not flag)
            self.b_reset.setEnabled(True)
            self.b_reset.setCursor(Qt.PointingHandCursor)
            self.b_reset.setToolTip("")
            self.set_cap(self.cap_reset, CAP_RESET_ON, True)
        else:
            for b in (self.b_restore, self.b_reset):
                b.setEnabled(False)
                b.setCursor(Qt.ArrowCursor)
                b.setToolTip("" if busy else need)
            self.set_cap(self.cap_restore,
                         CAP_RESTORE_FLAG if flag else CAP_RESTORE_OFF, False)
            self.set_cap(self.cap_reset, CAP_RESET_OFF, False)

    def refresh(self):
        no_auto = reg(AU, "NoAutoUpdate", 0) == 1 and reg(AU, "AUOptions", 0) == 1
        self.row_upd.set(no_auto,
                         "已禁用" if no_auto else "未禁用",
                         "永不自动更新" if no_auto else "存在自动更新风险")

        no_rst = reg(AU, "NoAutoRebootWithLoggedOnUsers", 0) == 1 and reg(CC, "AutoReboot", 1) == 0
        self.row_rst.set(no_rst,
                         "已锁定" if no_rst else "未锁定",
                         "不会自动重启" if no_rst else "可能被系统重启")

        svc_off = reg(SVC, "Start", 3) == 4
        self.row_svc.set(svc_off, "已禁用" if svc_off else "运行中",
                         "wuauserv" if svc_off else "仍可自动下载")

        flag = os.path.exists(os.path.join(BASE, "UPDATE_MODE.flag"))
        dv = deployed_ver()
        age = last_run_age()
        if flag:
            self.row_tsk.set(False, "已暂停（更新模式）", "装完请再点「一键禁用更新和重启」")
        elif dv and dv != APP_VER:
            self.row_tsk.set(False, "版本过期", "请重新点「一键禁用更新和重启」")
        elif age is not None and age <= 4500:
            m = int(age // 60)
            self.row_tsk.set(True, "运行中", ("%d 分钟前自检" % m) if m >= 1 else "刚刚自检")
        elif task_exists() or deployed_marker():
            self.row_tsk.set(True, "已部署", "等待下次巡检")
        else:
            self.row_tsk.set(False, "未部署", "点「一键禁用更新和重启」启用")

        i = windows_info()
        self.row_sys.set(
            i["ok"],
            "%s %s" % (i["family"], i["edition"]),
            ("Build " + str(i["build"])) if i["ok"] else "系统版本过低")

        self.apply_button_state()

    # ------------------------------------------------------------------ actions
    def run_op(self, kind):
        if self.busy:
            return
        if kind in ("restore", "reset") and not self._locked:
            self.show_msg("请先启用锁定",
                          NEED_LOCK_HTML % {"btn": LOCK_TEXT})
            return
        if kind == "reset":
            if not self.confirm_reset():
                return
            script = self.prepare_temp("reset.ps1")
        else:
            pkg = ensure_scripts()
            script = os.path.join(pkg, "deploy.ps1" if kind == "lock" else "restore.ps1")
        if not script or not os.path.exists(script):
            self.show_msg("文件缺失", "<p>内置脚本释放失败，无法继续。</p><p>%s</p>" % script)
            return
        self.out.clear()
        self.say(">>> %s，请稍候…" % {
            "lock": "正在锁死系统（禁止自动更新与自动重启）",
            "restore": "正在切换到更新模式（只放开更新，仍禁止自动重启）",
            "reset": "正在恢复系统默认配置（取消全部设置）",
        }.get(kind, "正在执行"))
        self.say("")
        self.set_busy(True)
        self.thread = PsRunner(script)
        self.thread.line.connect(self.say)
        self.thread.done.connect(lambda rc: self.on_done(kind, rc))
        self.thread.start()

    def prepare_temp(self, name):
        """把脚本释放到临时目录再执行（恢复配置要删掉 ProgramData 目录）。"""
        tmp = os.path.join(os.environ.get("TEMP", BASE), "NoAutoRestartRun")
        try:
            os.makedirs(tmp, exist_ok=True)
            dst = os.path.join(tmp, name)
            shutil.copyfile(res(os.path.join("scripts", name)), dst)
            return dst
        except Exception:
            return ""

    def confirm_reset(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("恢复配置")
        dlg.resize(580, 352)
        dlg.setStyleSheet("background:#F4F6FB;font-family:'Microsoft YaHei UI';")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 14)
        lay.setSpacing(12)
        b = QTextBrowser()
        b.setStyleSheet(DLG_CSS)
        style_scroll(b)
        b.setHtml(RESET_CONFIRM_HTML)
        lay.addWidget(b, 1)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)
        c = QPushButton("取消")
        c.setStyleSheet(NORMAL)
        c.clicked.connect(dlg.reject)
        d = QPushButton("确认恢复")
        d.setStyleSheet(DANGER)
        d.clicked.connect(dlg.accept)
        for x in (c, d):
            x.setFixedHeight(38)
            x.setFixedWidth(130)
            x.setCursor(Qt.PointingHandCursor)
        row.addWidget(c)
        row.addWidget(d)
        lay.addLayout(row)
        return dlg.exec() == QDialog.Accepted

    def on_done(self, kind, rc):
        self.set_busy(False)
        self.refresh()
        self.say("")
        if rc != 0:
            self.say("执行失败（返回码 %s），请查看上方输出。若提示需要管理员权限，请右键程序选择「以管理员身份运行」。" % rc)
            self.show_msg("执行失败", LOCK_FAIL_HTML % {"rc": rc})
            return

        if kind == "lock":
            self.say("【完成】自动更新已关闭，任何情况下都不会自动重启。")
            self.say("       设置已固化到系统：关闭本程序、删除本程序都不影响。")
            self.say("")
            self.say("【提示】现在打开 设置 → Windows 更新 会显示：")
            self.say("       “出现错误，请尝试稍后重新打开设置。”")
            self.say("       这是正常现象——更新引擎已被停用，不是系统故障。")
            self.say("")
            self.say("       要打补丁时点「临时恢复更新」，装完再点「一键禁用更新和重启」。")
            self.show_msg("已成功禁用自动更新与自动重启", LOCK_OK_HTML)
        elif kind == "restore":
            self.say("【完成】已切换到更新模式，可以手动检查并安装更新。")
            self.say("       自动重启依然是禁止的，装完更新不会自己重启。")
            self.say("")
            self.say("       装完后请再点一次「一键禁用更新和重启」重新锁定。")
            self.show_msg("更新模式已开启", RESTORE_OK_HTML)
        else:
            self.say("【完成】已取消全部设置，系统回到 Windows 默认状态。")
            self.say("       更新会重新自动检查安装，自动重启也会恢复系统默认。")
            self.say("       守护任务与程序数据已删除；本程序仍在，可随时重新锁死。")
            self.show_msg("已恢复系统默认配置", RESET_OK_HTML)

    def show_msg(self, title, html, w=620, h=470):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(w, h)
        dlg.setStyleSheet("background:#F4F6FB;font-family:'Microsoft YaHei UI';")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 14)
        lay.setSpacing(12)
        b = QTextBrowser()
        b.setOpenExternalLinks(True)
        b.setStyleSheet(DLG_CSS)
        style_scroll(b)
        b.setHtml(html)
        lay.addWidget(b, 1)
        btn = QPushButton("我知道了")
        btn.setStyleSheet(PRIMARY)
        btn.setFixedHeight(38)
        btn.setFixedWidth(140)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(dlg.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn)
        lay.addLayout(row)
        dlg.exec()

    def show_log(self):
        path = os.path.join(BASE, "guard.log")
        dlg = QDialog(self)
        dlg.setWindowTitle("守护日志  ·  %s" % path)
        dlg.resize(760, 540)
        dlg.setStyleSheet("background:#F4F6FB;font-family:'Microsoft YaHei UI';")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(14, 14, 14, 14)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setFont(QFont("Consolas", 9))
        te.setStyleSheet(DLG_CSS)
        style_scroll(te)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    te.setPlainText(f.read()[-200000:])
            except Exception as e:
                te.setPlainText("读取失败：%s" % e)
        else:
            te.setPlainText(
                "还没有日志。\n\n"
                "守护任务只在「发现设置被系统改回并按原样修复」时才写记录，\n"
                "所以一切正常时这里是空的——这是好事。\n\n"
                "最近一次巡检时间见：%s" % os.path.join(BASE, "last-run.txt"))
        lay.addWidget(te)
        dlg.exec()

    def show_help(self):
        self.show_msg("使用说明", HELP_HTML, 680, 620)

    def show_about(self):
        self.show_msg("关于软件", ABOUT_HTML, 620, 520)

    def show_oss(self):
        self.show_msg("开源说明  ·  README", OSS_HTML, 720, 660)


# --------------------------------------------------------------------------- 文案
LOCK_OK_HTML = """
<html><body style="line-height:165%;font-family:'Microsoft YaHei UI';">
<h2 style="color:#15803D;">已成功禁用自动更新与自动重启</h2>
<p>设置已经写入系统，从现在起：</p>
<ul>
<li>更新不会自动检查、下载、安装；</li>
<li>更新装完、蓝屏崩溃、计划任务、开机续装，<b>任何情况都不会自己重启</b>；</li>
<li>只有你自己手动点「重启 / 关机」，电脑才会重启。</li>
</ul>

<div style="background:#FFF7E6;border:1px solid #FFD8A8;border-radius:8px;padding:12px 14px;">
<b style="color:#B45309;">重要：设置里会显示一条错误，这是正常的</b><br>
现在打开 <b>设置 → Windows 更新</b>，会看到：<br>
<span style="color:#B45309;font-weight:600;">“出现错误，请尝试稍后重新打开设置。”</span><br>
这是因为 Windows 更新引擎已被停用，<b>不是系统故障</b>，不影响电脑正常使用。
</div>

<h3 style="color:#1E40AF;">为什么可以随便关掉 / 删掉本软件</h3>
<p>所有设置直接写进系统：注册表策略、服务启动方式、计划任务。
程序本身不常驻、不开机自启，删掉它设置照样有效。
以后重新下载本程序运行，它会识别当前状态，接着用。</p>

<h3 style="color:#1E40AF;">以后想装补丁</h3>
<p>点「临时恢复更新」→ 打开设置检查更新 → 装完再点「一键禁用更新和重启」。
装更新期间自动重启依然是禁止的。</p>
</body></html>
"""

LOCK_FAIL_HTML = """
<html><body style="line-height:165%;font-family:'Microsoft YaHei UI';">
<h2 style="color:#B91C1C;">部署未完成（返回码 %(rc)s）</h2>
<p>常见原因与处理：</p>
<ol>
<li><b>没有管理员权限</b>：右键程序 → 「以管理员身份运行」。程序已声明需要管理员权限，正常情况下会自动弹出授权窗口。</li>
<li><b>安全软件拦截</b>：某些安全软件会拦截修改服务与计划任务，请暂时允许。</li>
<li>若提示计划任务注册失败，把「运行输出」里的内容反馈给作者。</li>
</ol>
<p style="color:#64748B;">系统当前仍是原状态，可以放心重试。</p>
</body></html>
"""

RESTORE_OK_HTML = """
<html><body style="line-height:165%;font-family:'Microsoft YaHei UI';">
<h2 style="color:#B45309;">已进入更新模式</h2>
<p>现在可以打开：<b>设置 → Windows 更新 → 检查更新</b>，正常下载安装。</p>
<ul>
<li>守护任务已暂停，不会再把你刚放开的更新关掉；</li>
<li><b>自动重启依然是禁止的</b>，更新装完也不会自己重启；</li>
<li>装完更新后，请再点一次「一键禁用更新和重启」重新锁定。</li>
</ul>
<p style="color:#64748B;font-size:9pt;">更新模式下设置页可能仍显示部分错误，属正常现象。</p>
</body></html>
"""

RESET_CONFIRM_HTML = """
<html><body style="line-height:165%;font-family:'Microsoft YaHei UI';">
<h2 style="color:#B91C1C;">恢复配置会取消全部保护</h2>
<p>这一步会把<b>本程序做过的所有改动</b>还原成 Windows 默认状态：</p>
<ul>
<li>删除本程序创建的守护计划任务与程序数据；</li>
<li>本程序修改过的更新服务恢复默认，<b>Windows 会重新自动检查、下载、安装更新</b>；</li>
<li>删除本程序写入的注册表策略（<b>只删本工具自己添加的项，系统其它注册表设置一律不动</b>）；</li>
<li>本程序关掉的自动重启恢复系统默认——更新装完可能自动重启电脑；</li>
<li>蓝屏后的自动重启恢复系统默认。</li>
</ul>
<p style="background:#FFF1F0;border:1px solid #F5C4C0;border-radius:8px;padding:10px 12px;color:#B91C1C;">
确认前请先把正在编辑的文件保存好。恢复后可以随时再点「一键禁用更新和重启」重新启用保护。
</p>
</body></html>
"""

NEED_LOCK_HTML = """
<html><body style="line-height:165%;font-family:'Microsoft YaHei UI';">
<h2 style="color:#B45309;">当前没有启用保护</h2>
<p>「临时恢复更新」与「恢复配置」只有在<b>已启用锁定</b>之后才有意义，
未启用时这两个按钮是灰的，不需要操作。</p>
<p>请先点主按钮 <b>「%(btn)s」</b>，等上方状态全部变绿后，
这两个按钮会自动变为可用。</p>
</body></html>
"""

RESET_OK_HTML = """
<html><body style="line-height:165%;font-family:'Microsoft YaHei UI';">
<h2 style="color:#15803D;">已恢复系统默认配置</h2>
<p>本程序做过的改动已全部撤销：</p>
<ul>
<li>更新服务恢复默认，Windows 重新自动检查 / 下载 / 安装更新；</li>
<li>注册表策略已删除，设置页恢复正常；</li>
<li>更新与重启相关计划任务已重新启用；</li>
<li>守护任务与 <code>C:\\ProgramData\\NoAutoRestart</code> 已删除；</li>
<li>自动重启恢复系统默认：<b>更新装完可能自动重启</b>。</li>
</ul>
<p style="color:#64748B;">本程序还在，随时可以再点「一键禁用更新和重启」把保护加回来。</p>
</body></html>
"""

HELP_HTML = """
<html><body style="line-height:165%;font-family:'Microsoft YaHei UI';">
<h2 style="color:#1E40AF;">禁止自动重启工具 v1.1.0</h2>
<p style="color:#64748B;">永久免费 · 开放源码 · 出品：atusu.cn</p>

<h3 style="color:#1E40AF;">支持的系统</h3>
<ul>
<li><b>Windows 11</b>：21H2 / 22H2 / 23H2 / 24H2 及后续版本，家庭版、专业版、企业版、教育版全支持。</li>
<li><b>Windows 10</b>：1507 起的全部版本（含 1809 / 1909 / 21H2 / 22H2），家庭版、专业版、企业版、教育版、LTSC 全支持。</li>
<li>Windows Server 2016 / 2019 / 2022 亦可用（策略同上）。</li>
<li>系统里不存在对应服务或任务时会自动跳过，不会报错、不会影响系统。</li>
</ul>

<h3 style="color:#1E40AF;">这个软件做什么</h3>
<p>彻底禁止 Windows 的自动更新、自动安装和自动重启。电脑什么时候重启、关机，只有你说了算。</p>

<h3 style="color:#1E40AF;">主要功能</h3>
<ul>
<li><b>禁止自动更新</b>：关闭自动检查、自动下载、自动安装；更新引擎（Windows Update / 更新协调器 / 更新修复服务）全部停用。</li>
<li><b>禁止自动重启</b>：更新装完、蓝屏崩溃、计划任务、开机续装，四条路径全部堵死。</li>
<li><b>自愈守护</b>：注册一个 SYSTEM 权限的守护任务，开机时 + 每 30 分钟巡检，系统把设置改回去会自动修回来。</li>
<li><b>取消更新计划</b>：更新与重启相关的 20 多个计划任务全部禁用。</li>
<li><b>设置固化</b>：全部写入系统，不常驻后台，关掉或删除本软件都不影响。</li>
</ul>

<h3 style="color:#1E40AF;">三个按钮分别是做什么的</h3>
<p style="color:#64748B;font-size:9.5pt;">按钮会跟着当前状态变化：<b>未启用</b>时主按钮是「一键禁用更新和重启」，
下面两个按钮是灰的、点不动；<b>启用后</b>主按钮变成绿色的「已配置完成锁定」，
下面两个按钮才可以使用。</p>
<table cellpadding="7" style="font-size:10pt;border-collapse:collapse;">
<tr style="background:#F1F5FD;">
  <td><b>一键禁用更新和重启</b><br><span style="color:#64748B;font-size:9pt;">（已启用后显示为「已配置完成锁定」）</span></td>
  <td>禁止自动更新与自动重启，并把设置写进系统长期生效。第一次使用点它；
      上方的五项状态全部变绿、按钮变成绿色「已配置完成锁定」就说明配置完成，不需要再点。</td>
</tr>
<tr>
  <td><b>临时恢复更新</b><br><span style="color:#64748B;font-size:9pt;">（需先启用锁定）</span></td>
  <td>需要打补丁时点它：只放开更新，<b>自动重启仍然禁止</b>。装完更新后再点一次主按钮锁回去。
      未启用锁定时此按钮为灰色不可用。</td>
</tr>
<tr style="background:#F1F5FD;">
  <td><b>恢复配置</b><br><span style="color:#64748B;font-size:9pt;">（需先启用锁定）</span></td>
  <td>取消本程序的全部设置，让系统回到 Windows 默认状态：删除守护任务与程序数据、
      恢复更新服务、删除<b>本工具自己写入的</b>注册表策略（系统其它注册表项不动）。
      <b style="color:#B91C1C;">自动重启也会恢复系统默认</b>。未启用锁定时此按钮为灰色不可用。</td>
</tr>
</table>

<h3 style="color:#1E40AF;">怎么用</h3>
<ol>
<li>双击本程序（会自动请求管理员权限，点「是」）。</li>
<li>点 <b>一键禁用更新和重启</b>，等五项状态全部变绿、按钮变成绿色「已配置完成锁定」。</li>
<li>此时 <b>临时恢复更新</b> 与 <b>恢复配置</b> 自动变为可用，按需使用。</li>
<li>需要装更新时点 <b>临时恢复更新</b>，装完再点一次主按钮重新锁定。</li>
<li>想彻底还原系统时点 <b>恢复配置</b>（会二次确认）。</li>
</ol>

<h3 style="color:#1E40AF;">锁死成功后会看到什么</h3>
<p>打开 <b>设置 → Windows 更新</b>，会显示
<span style="color:#B45309;font-weight:600;">“出现错误，请尝试稍后重新打开设置。”</span><br>
这是<b>预期现象</b>：更新引擎已被停用，系统读不到更新状态。
它不是故障，不影响系统运行、不影响装软件、不影响日常使用。</p>

<h3 style="color:#1E40AF;">不影响什么</h3>
<ul>
<li>安装 / 卸载 .exe、.msi 软件，安装驱动，完全正常；</li>
<li>启用或关闭 Windows 功能（需要组件服务，本次未改动）；</li>
<li>系统服务、网络、显卡、声音、打印、Office、游戏，全部不受影响；</li>
<li>电脑不会变慢：程序不常驻，守护任务空闲时 1 秒内退出。</li>
</ul>

<h3 style="color:#1E40AF;">需要你知道的副作用</h3>
<ul>
<li>Microsoft Store 应用更新、Defender 病毒库自动更新会一并停止，需要时点「临时恢复更新」。</li>
<li>系统不会自动获得安全补丁，建议每 1～2 个月手动恢复一次更新。</li>
<li>装完补丁后系统会提示需要重启，需要你自己点重启（这正是本工具的目的）。</li>
</ul>

<h3 style="color:#1E40AF;">关于收费与开源源码</h3>
<p><b>本软件永久免费</b>，源码公开，可自由查看、修改、自行编译。
禁止把本软件当作商品出售或捆绑收费。详见「开源说明」。</p>

<h3 style="color:#1E40AF;">免责声明</h3>
<p style="color:#64748B;font-size:9pt;">
关闭自动更新意味着系统不会自动获得安全补丁。使用本工具属个人选择，
因关闭更新导致的系统安全问题由使用者自行承担。
</p>

<hr style="border:none;border-top:1px solid #E2E8F2;">
<p style="color:#94A3B8;font-size:9pt;">© 2026 atusu.cn　·　永久免费　·　开放源码</p>
</body></html>
"""

ABOUT_HTML = """
<html><body style="line-height:165%;font-family:'Microsoft YaHei UI';">
<h2 style="color:#1E40AF;">%NAME%</h2>
<p style="color:#64748B;">版本 v%VER%　·　构建 %DATE%</p>

<table cellpadding="6" style="font-size:10pt;">
<tr><td style="color:#64748B;">软件名称</td><td><b>%NAME%</b></td></tr>
<tr><td style="color:#64748B;">版本号</td><td>v%VER%</td></tr>
<tr><td style="color:#64748B;">出品</td>
    <td><a href="%URL%" style="color:#2F6BFF;text-decoration:none;">atusu.cn</a></td></tr>
<tr><td style="color:#64748B;">授权方式</td><td>永久免费 · 开放源码</td></tr>
<tr><td style="color:#64748B;">适用系统</td><td>Windows 10 / Windows 11 全版本</td></tr>
</table>

<h3 style="color:#1E40AF;">一句话说明</h3>
<p>Windows 更新会在你工作、开会、渲染、挂机的时候强制重启，丢掉没保存的东西。
这个工具把「什么时候重启」的决定权交回给你自己。</p>

<h3 style="color:#1E40AF;">许可</h3>
<p>本软件永久免费，源码公开。可自由使用、复制、分发、修改、自行编译；
再分发须保留版权与出处；<b>禁止将本软件作为商品出售或捆绑收费</b>。</p>

<h3 style="color:#1E40AF;">免责</h3>
<p style="color:#64748B;font-size:9pt;">本软件按「现状」提供，不附带任何明示或暗示担保。
关闭自动更新后系统不再自动获得安全补丁，请定期手动恢复更新打补丁。</p>

<hr style="border:none;border-top:1px solid #E2E8F2;">
<p style="color:#94A3B8;font-size:9pt;">Copyright (C) 2026 atusu.cn　·　永久免费　·　禁止转售</p>
</body></html>
""".replace("%NAME%", APP_NAME).replace("%VER%", APP_VER) \
   .replace("%DATE%", BUILD_DATE).replace("%URL%", URL)

OSS_HTML = """
<html><body style="line-height:170%;font-family:'Microsoft YaHei UI';">

<h2 style="color:#0F172A;margin-bottom:2px;">禁止自动重启工具</h2>
<p style="color:#64748B;margin-top:0;">
一款把「什么时候重启、什么时候关机」的决定权交还给你的 Windows 小工具。
完全禁止自动更新与自动重启，设置写入系统后长期生效。
</p>
<p style="color:#64748B;font-size:9.5pt;">
版本 v1.1.0 &nbsp;·&nbsp; Windows 10 / 11 全版本 &nbsp;·&nbsp; 永久免费 &nbsp;·&nbsp; 开放源码
</p>

<hr style="border:none;border-top:1px solid #E2E8F2;">

<h3 style="color:#1E40AF;">功能特性</h3>
<ul>
<li><b>禁止自动更新</b>：关闭自动检查、自动下载、自动安装；更新引擎三个服务全部停用。</li>
<li><b>禁止自动重启</b>：更新装完、蓝屏崩溃、计划任务、开机续装，四条路径全部堵死。</li>
<li><b>自愈守护</b>：SYSTEM 权限计划任务，开机 + 每 30 分钟巡检，被系统改回来自动修复。</li>
<li><b>取消更新计划</b>：20 多个更新 / 重启相关计划任务全部禁用。</li>
<li><b>设置固化</b>：写入注册表 + 服务 + 计划任务，不常驻后台，删掉程序也有效。</li>
<li><b>随时还原</b>：「恢复配置」一键取消全部改动，回到 Windows 默认状态。</li>
<li><b>零依赖</b>：不联网、不上传数据、无遥测、无开机自启。</li>
</ul>

<h3 style="color:#1E40AF;">支持系统</h3>
<ul>
<li>Windows 11：21H2 / 22H2 / 23H2 / 24H2 及后续</li>
<li>Windows 10：1507 起全部版本（含 1809 / 1909 / 21H2 / 22H2）</li>
<li>版本：家庭版、专业版、企业版、教育版、企业版 LTSC、IoT 企业版</li>
<li>Windows Server 2016 / 2019 / 2022 同样可用</li>
<li>架构：x86 / x64 / ARM64</li>
</ul>

<h3 style="color:#1E40AF;">快速开始</h3>
<pre style="background:#F8FAFC;border:1px solid #E2E8F2;border-radius:6px;padding:10px;font-size:9pt;">
1. 双击 禁止自动重启工具.exe   → UAC 弹窗点「是」
2. 点「一键禁用更新和重启」               → 五项状态全部变绿
3. 之后不用管它，程序无需常驻
</pre>

<table cellpadding="7" style="font-size:10pt;">
<tr style="background:#F1F5FD;">
  <td><b>一键禁用更新和重启</b></td>
  <td>禁止自动更新与自动重启，写入系统长期生效。第一次使用点它。</td>
</tr>
<tr>
  <td><b>临时恢复更新</b></td>
  <td>只放开更新，自动重启仍然禁止；装完补丁再点「一键禁用更新和重启」。</td>
</tr>
<tr style="background:#F1F5FD;">
  <td><b>恢复配置</b></td>
  <td>取消全部设置，回到 Windows 默认状态（自动重启也会恢复默认）。</td>
</tr>
<tr>
  <td><b>查看日志</b></td>
  <td>守护任务只在修复了被篡改的设置时才写记录，空日志＝一切正常。</td>
</tr>
</table>

<h3 style="color:#1E40AF;">锁死后的效果</h3>
<p>打开 <b>设置 → Windows 更新</b> 会显示
<span style="color:#B45309;">“出现错误，请尝试稍后重新打开设置。”</span>
——更新引擎已被停用，属预期现象，不是系统故障。</p>

<h3 style="color:#1E40AF;">目录结构</h3>
<pre style="background:#F8FAFC;border:1px solid #E2E8F2;border-radius:6px;padding:10px;font-size:9pt;">
禁止自动重启工具 v1.1.0/
├─ 禁止自动重启工具.exe     主程序（单文件，无需安装）
├─ 使用说明.txt             用户手册
├─ README.md                本文件（开源说明 / 构建说明）
└─ 源码/
   ├─ main.py               图形界面（PySide6）
   ├─ build.bat             一键打包
   ├─ ensure_bom.py         修正 ps1 编码
   ├─ make_icon.py          生成图标
   ├─ version.txt           exe 版本资源
   └─ scripts/
      ├─ guard.ps1          加固核心（守护任务执行）
      ├─ deploy.ps1         部署 + 校验
      ├─ restore.ps1        临时恢复更新
      └─ reset.ps1          恢复配置（彻底还原）
</pre>

<h3 style="color:#1E40AF;">从源码构建</h3>
<pre style="background:#F8FAFC;border:1px solid #E2E8F2;border-radius:6px;padding:10px;font-size:9pt;">
pip install PySide6 pyinstaller pillow
python ensure_bom.py
python make_icon.py
python -m PyInstaller --nofollow-import-to tkinter ^
  --onefile --windowed --uac-admin ^
  --name NoAutoRestartTool --icon app.ico ^
  --version-file version.txt ^
  --add-data "scripts;scripts" ^
  --add-data "icon_preview.png;." --add-data "app.ico;." main.py
</pre>
<p style="font-size:9pt;color:#64748B;">注：scripts 下的 .ps1 必须为 UTF-8 带 BOM，否则 PowerShell 5.1 按 ANSI 解析会中文乱码。</p>

<h3 style="color:#1E40AF;">技术原理</h3>
<table cellpadding="6" style="font-size:10pt;">
<tr><td style="color:#64748B;width:70px;">注册表</td>
    <td>WindowsUpdate\\AU 下 NoAutoUpdate / AUOptions / NoAutoRebootWithLoggedOnUsers 等 7 项策略</td></tr>
<tr><td style="color:#64748B;">服务</td>
    <td>wuauserv / UsoSvc / WaaSMedicSvc 禁用，DoSvc 降为手动</td></tr>
<tr><td style="color:#64748B;">计划任务</td>
    <td>UpdateOrchestrator / WindowsUpdate / InstallService / WaaSMedic 下全部任务禁用</td></tr>
<tr><td style="color:#64748B;">蓝屏 / 登录</td>
    <td>CrashControl.AutoReboot = 0，DisableAutomaticRestartSignOn = 1</td></tr>
</table>
<p style="font-size:9.5pt;color:#64748B;">
刻意不触碰 CBS、TrustedInstaller、Windows Installer、BITS、驱动与系统还原，
保证安装软件、启用 Windows 功能、日常使用完全正常。
</p>

<h3 style="color:#1E40AF;">开源许可</h3>
<ol>
<li><b>源码公开</b>：可查看、学习、修改、自行编译，个人与公司电脑均可使用。</li>
<li><b>自由分发</b>：原版或修改版都可转发、放到自己网站上。</li>
<li><b>保留署名</b>：再分发须保留版权声明与出处，并附本说明全文。</li>
<li><b>标明改动</b>：发布修改版需注明「基于 atusu.cn 的禁止自动重启工具修改」。</li>
<li><b>禁止售卖</b>：不得将本软件作为商品出售、付费下载或捆绑收费。</li>
</ol>

<h3 style="color:#1E40AF;">免责声明</h3>
<p style="color:#64748B;font-size:9pt;">
本软件按「现状」提供，不附带任何明示或暗示担保。
关闭自动更新意味着系统不再自动获得安全补丁，建议每 1～2 个月手动恢复一次更新。
使用本工具属个人选择，由此产生的安全风险由使用者自行承担。
</p>

<hr style="border:none;border-top:1px solid #E2E8F2;">
<p style="color:#94A3B8;font-size:9pt;">Copyright (C) 2026 atusu.cn　·　永久免费　·　开放源码　·　禁止售卖</p>
</body></html>
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VER)
    app.setOrganizationName(SITE)
    app.setStyleSheet(SCROLLBAR)
    ico = res("app.ico")
    if os.path.exists(ico):
        app.setWindowIcon(QIcon(ico))
    w = MainWindow()
    if os.path.exists(ico):
        w.setWindowIcon(QIcon(ico))
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
