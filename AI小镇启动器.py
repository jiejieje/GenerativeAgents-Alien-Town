import os
import sys
import re
import json
import shutil
import datetime
import webbrowser
import threading
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

try:
    from PySide6.QtCore import Qt, QTimer, QSize, QProcess, QByteArray, Signal, QObject, QProcessEnvironment
    from PySide6.QtGui import QFont, QIcon, QPixmap, QAction, QImage, QColor, QTextOption
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
        QGridLayout, QLineEdit, QTextEdit, QComboBox, QFileDialog, QMessageBox, QStackedWidget,
        QCheckBox, QScrollArea, QFrame, QSplitter, QProgressBar,
        QToolButton, QDialog, QFormLayout, QSpinBox, QStyleFactory, QGraphicsDropShadowEffect,
        QButtonGroup
    )
except Exception as e:
    print("错误：需要安装 PySide6。请先运行: pip install PySide6")
    raise

from PIL import Image


# 强制 UTF-8 日志与 I/O，避免 Windows 控制台 GBK 导致编码异常
try:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 目录常量
def _get_base_dir():
    if getattr(sys, "frozen", False):
        # PyInstaller 冻结模式：使用可执行文件所在目录
        try:
            return os.path.dirname(sys.executable)
        except Exception:
            pass
    return os.path.dirname(os.path.abspath(__file__))

def _get_resource_root(base_dir: str) -> str:
    """返回运行时资源根目录（frontend/static 与 data 同时存在）。
    兼容以下布局：
    - 与可执行文件同级：<base>/frontend/static
    - One-folder：<base>/_internal/frontend/static
    - 顶层 dist 启动，资源在子目录：<base>/AI-Town/_internal/frontend/static
    - 其他：尝试父目录组合
    """
    candidates = [
        base_dir,
        os.path.join(base_dir, "_internal"),
        os.path.join(base_dir, "AI-Town"),
        os.path.join(base_dir, "AI-Town", "_internal"),
        os.path.join(os.path.dirname(base_dir), "_internal"),
        os.path.join(os.path.dirname(base_dir), "AI-Town", "_internal"),
    ]
    for root in candidates:
        if os.path.isdir(os.path.join(root, "frontend", "static")) and os.path.isdir(os.path.join(root, "data")):
            return root
    # 最后回退：使用 base_dir（可能导致错误，但便于弹窗提示路径）
    return base_dir

SCRIPT_DIR = _get_base_dir()
RESOURCE_ROOT = _get_resource_root(SCRIPT_DIR)
BASE_AGENT_PATH = os.path.join(RESOURCE_ROOT, "frontend", "static", "assets", "village", "agents")
START_PY_PATH = os.path.join(SCRIPT_DIR, "start.py")
DEFAULT_TEMPLATE_AGENT = "光谱艺术家"
VISUAL_TEMPLATE_DIR = os.path.join(RESOURCE_ROOT, "角色模板", "agents")

# 预设角色列表
DEFAULT_PERSONAS_LIST = [
     "光谱艺术家",
     "原子分析师",
     "味觉调和师",
     "徐畅",
     "星辰诗者",
     "晶核分析师",
     "植物生命体",
     "生命研究者",
     "硅基植物体",
     "跨界组织者",
     "音乐与绘画家",
     "音乐与艺术家",
     "频率音乐家",
     "恒星音乐家",
]

# 雪碧图参数
SPRITE_COLS = 5
SPRITE_ROWS = 5
IDLE_ANIM_FRAME_INDICES = list(range(12, 18))
ANIMATION_DELAY_MS = 150


# 多巴胺紫系配色（像素风倾向）
class Palette:
    # 黑金主题（像素风强化）
    BG = "#0B0B0C"          # 深黑
    BG_SOFT = "#131315"     # 柔和黑
    BG_CARD = "#1A1A1E"     # 卡片底
    BORDER = "#3D3D45"      # 暗边框
    TEXT = "#F2F2F2"        # 微白
    TEXT_DIM = "#C8C8CC"     # 次级
    ACCENT = "#FFD166"      # 金色高亮
    ACCENT_2 = "#FFC14D"    # 次金
    OK = "#28C76F"
    WARN = "#FF9F43"
    ERR = "#EA5455"
    CYAN = "#23BFD8"
    LIME = "#A8E063"
    ORANGE = "#FFB86B"


def load_pixel_font() -> QFont:
    candidates = ["Press Start 2P", "Pixel Operator", "Pixeled", "VT323", "Courier New"]
    font = QFont()
    for name in candidates:
        font.setFamily(name)
        if QFont(name).exactMatch():
            break
    font.setPointSize(15)
    font.setBold(True)
    return font


def ensure_dirs():
    if not os.path.isdir(BASE_AGENT_PATH):
        QMessageBox.critical(None, "错误", f"基础角色路径 '{BASE_AGENT_PATH}' 不存在或不是目录！")
        sys.exit(1)
    # 冻结模式下校验 start.exe，开发模式下校验 start.py
    if getattr(sys, "frozen", False):
        start_exe = os.path.join(SCRIPT_DIR, "start.exe")
        if not os.path.isfile(start_exe):
            QMessageBox.critical(None, "错误", f"启动程序 '{start_exe}' 不存在！")
            sys.exit(1)
    else:
        if not os.path.isfile(START_PY_PATH):
            QMessageBox.critical(None, "错误", f"启动脚本 '{START_PY_PATH}' 不存在！")
            sys.exit(1)


# 读取配置并准备需要注入到子进程的环境变量（确保冻结环境也能获取到密钥）
def _load_service_env_from_config() -> dict:
    env_map = {}
    try:
        cfg_path = os.path.join(RESOURCE_ROOT, "data", "config.json")
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        services = (cfg or {}).get('services', {}) or {}
        # LiblibAI
        liblib = services.get('liblibai', {}) or {}
        if liblib.get('access_key'):
            env_map['LIBLIBAI_ACCESS_KEY'] = str(liblib.get('access_key'))
        if liblib.get('secret_key'):
            env_map['LIBLIBAI_SECRET_KEY'] = str(liblib.get('secret_key'))
        if liblib.get('base_url'):
            env_map['LIBLIBAI_BASE_URL'] = str(liblib.get('base_url'))
        # Suno
        suno = services.get('suno', {}) or {}
        if suno.get('api_key'):
            env_map['SUNO_API_KEY'] = str(suno.get('api_key'))
        if suno.get('base_url'):
            env_map['SUNO_BASE_URL'] = str(suno.get('base_url'))
        # Gemini
        gem = services.get('gemini', {}) or {}
        if gem.get('api_key'):
            env_map['GEMINI_API_KEY'] = str(gem.get('api_key'))
        if gem.get('base_url'):
            env_map['GEMINI_BASE_URL'] = str(gem.get('base_url'))
    except Exception:
        pass
    return env_map

LAUNCHER_SERVICE_ENV = _load_service_env_from_config()


def pil_to_qpixmap(pil_image: Image.Image) -> QPixmap:
    if pil_image.mode != "RGBA":
        pil_image = pil_image.convert("RGBA")
    data = pil_image.tobytes("raw", "RGBA")
    qimage = QImage(data, pil_image.size[0], pil_image.size[1], QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimage)


def slice_sprite_frames(image_path: str, cols: int, rows: int, target_indices: List[int]) -> List[QPixmap]:
    frames: List[QPixmap] = []
    try:
        sheet = Image.open(image_path).convert("RGBA")
        sw, sh = sheet.size
        fw, fh = sw // cols, sh // rows
        for idx in target_indices:
            if not (0 <= idx < cols * rows):
                continue
            c, r = idx % cols, idx // cols
            x0, y0 = c * fw, r * fh
            crop = sheet.crop((x0, y0, x0 + fw, y0 + fh))
            frames.append(pil_to_qpixmap(crop))
        return frames
    except Exception:
        return []


class LogBus(QObject):
    message = Signal(str, str)  # text, tag


class ProcessTask(QObject):
    finished = Signal(bool)  # success

    def __init__(self, parent: Optional[QObject] = None, enable_buffer: bool = False):
        super().__init__(parent)
        self.proc = QProcess(self)
        self.stderr_buffer = QByteArray()
        self.stdout_buffer = QByteArray()
        self.on_success: Optional[callable] = None
        self.on_failure: Optional[callable] = None
        if enable_buffer:
            self.proc.readyReadStandardError.connect(self._read_err)
            self.proc.readyReadStandardOutput.connect(self._read_out)
        self.proc.finished.connect(self._done)

    def start(self, program: str, arguments: List[str]):
        self.proc.setProcessChannelMode(QProcess.SeparateChannels)
        self.proc.start(program, arguments)

    def _read_err(self):
        data = self.proc.readAllStandardError()
        self.stderr_buffer += data

    def _read_out(self):
        data = self.proc.readAllStandardOutput()
        self.stdout_buffer += data

    def _done(self, code: int, status):
        success = code == 0
        self.finished.emit(success)
        if success and self.on_success:
            self.on_success()
        if not success and self.on_failure:
            self.on_failure()


class AnimatedLabel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.label = QLabel("", self)
        self.label.setAlignment(Qt.AlignCenter)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.label)
        self.frames: List[QPixmap] = []
        self.index = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def set_frames(self, frames: List[QPixmap]):
        self.frames = frames or []
        self.index = 0
        if len(self.frames) > 1:
            self.timer.start(ANIMATION_DELAY_MS)
        else:
            self.timer.stop()
        self._render()

    def _tick(self):
        if not self.frames:
            return
        self.index = (self.index + 1) % len(self.frames)
        self._render()

    def _render(self):
        if not self.frames:
            self.label.clear()
            return
        self.label.setPixmap(self.frames[self.index].scaled(384, 384, Qt.KeepAspectRatio, Qt.FastTransformation))


class PersonaItem(QWidget):
    def __init__(self, name: str, checked: bool, on_modify, on_toggle, on_delete, parent=None):
        super().__init__(parent)
        self.name = name
        self.setObjectName("PersonaRow")
        self.on_toggle = on_toggle
        self.on_delete = on_delete
        self.cb = QCheckBox()
        self.cb.setChecked(checked)
        # 隐藏原复选框，保留状态逻辑
        self.cb.setVisible(False)
        self.cb.stateChanged.connect(self._on_state_changed)
        self.lbl = QLabel(name)
        self.lbl.setObjectName("PersonaName")
        self.btn = QToolButton(); self.btn.setText("修改")
        self.btn_del = QToolButton(); self.btn_del.setText("删除"); self.btn_del.setObjectName("Danger")
        self.btn.clicked.connect(lambda: on_modify(self.name))
        self.btn_del.clicked.connect(lambda: on_delete(self.name))
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 4, 8, 4)
        h.addWidget(self.cb)
        h.addWidget(self.lbl, 1)
        h.addWidget(self.btn)
        h.addWidget(self.btn_del)
        # 行可点击提示
        try:
            self.setCursor(Qt.PointingHandCursor)
        except Exception:
            pass
        self._apply_selected_style()

    def _on_state_changed(self):
        try:
            self.on_toggle(self.name, self.cb.isChecked())
        finally:
            self._apply_selected_style()

    def _apply_selected_style(self):
        self.setProperty("selected", True if self.cb.isChecked() else False)
        # 触发样式刷新
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        # 同步名字的样式属性
        try:
            self.lbl.setProperty("selected", True if self.cb.isChecked() else False)
            self.lbl.style().unpolish(self.lbl)
            self.lbl.style().polish(self.lbl)
            self.lbl.update()
        except Exception:
            pass


class SettingsDialog(QDialog):
    def __init__(self, parent=None, step_value: int = 50, font_size: int = 11):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)
        form = QFormLayout(self)
        self.spin_steps = QSpinBox()
        self.spin_steps.setRange(1, 100000)
        self.spin_steps.setValue(step_value)
        self.spin_font = QSpinBox()
        self.spin_font.setRange(8, 48)
        self.spin_font.setValue(font_size)
        form.addRow("模拟总步数", self.spin_steps)
        form.addRow("字体大小", self.spin_font)
        btns = QHBoxLayout()
        ok = QPushButton("确定")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        form.addRow(btns)


class Step1Widget(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        right = QWidget()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 5)

        # 左侧：形象轮播 + 居中大箭头切换
        self.animated = AnimatedLabel()
        self.lbl_visual_name = QLabel("-")
        self.lbl_visual_name.setAlignment(Qt.AlignCenter)
        self.btn_prev = QToolButton(); self.btn_prev.setText("◀"); self.btn_prev.setObjectName("NavArrow"); self.btn_prev.setFixedSize(72, 72)
        self.btn_next = QToolButton(); self.btn_next.setText("▶"); self.btn_next.setObjectName("NavArrow"); self.btn_next.setFixedSize(72, 72)
        self.btn_prev.setToolTip("上一张形象 (向左)")
        self.btn_next.setToolTip("下一张形象 (向右)")
        self.btn_prev.clicked.connect(self.app.show_prev_visual)
        self.btn_next.clicked.connect(self.app.show_next_visual)

        l_lay = QVBoxLayout(left)
        l_lay.addWidget(self.animated, 1)
        nav = QHBoxLayout(); nav.setSpacing(16)
        nav.addStretch(1); nav.addWidget(self.btn_prev); nav.addSpacing(16); nav.addWidget(self.btn_next); nav.addStretch(1)
        l_lay.addLayout(nav)
        l_lay.addWidget(self.lbl_visual_name)

        # 右侧：表单
        self.input_name = QLineEdit()
        self.input_age = QLineEdit()
        self.combo_l2 = QComboBox()
        self.combo_l3 = QComboBox()
        self.txt_currently = QTextEdit()
        self.txt_innate = QTextEdit()
        self.txt_learned = QTextEdit()
        self.txt_lifestyle = QTextEdit()
        self.txt_daily = QTextEdit()
        # 合并按钮：创建角色并进入第2步
        self.btn_create_and_next = QPushButton("创建角色并进入第2步")
        self.btn_create_and_next.clicked.connect(self.app.create_character_and_go_step2)
        # 跳过当前步骤
        self.btn_skip = QPushButton("跳过当前步骤")
        self.btn_skip.clicked.connect(self.app.skip_step1)

        grid = QGridLayout(right)
        r = 0
        grid.addWidget(QLabel("角色名称"), r, 0); grid.addWidget(self.input_name, r, 1); r += 1
        grid.addWidget(QLabel("角色年龄"), r, 0); grid.addWidget(self.input_age, r, 1); r += 1
        grid.addWidget(QLabel("生活区域-二级"), r, 0); grid.addWidget(self.combo_l2, r, 1); r += 1
        grid.addWidget(QLabel("生活区域-三级"), r, 0); grid.addWidget(self.combo_l3, r, 1); r += 1
        grid.addWidget(QLabel("当前状态"), r, 0); grid.addWidget(self.txt_currently, r, 1); r += 1
        grid.addWidget(QLabel("天赋特性"), r, 0); grid.addWidget(self.txt_innate, r, 1); r += 1
        grid.addWidget(QLabel("所学知识"), r, 0); grid.addWidget(self.txt_learned, r, 1); r += 1
        grid.addWidget(QLabel("生活方式"), r, 0); grid.addWidget(self.txt_lifestyle, r, 1); r += 1
        grid.addWidget(QLabel("每日计划"), r, 0); grid.addWidget(self.txt_daily, r, 1); r += 1
        grid.addWidget(self.btn_create_and_next, r, 0, 1, 2); r += 1
        grid.addWidget(self.btn_skip, r, 0, 1, 2)

        root = QVBoxLayout(self)
        title = QLabel("第1步：角色核心设定"); title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)
        root.addWidget(splitter, 1)

    def apply_visual(self, name: str, frames: List[QPixmap]):
        self.lbl_visual_name.setText(f"形象：{name}")
        self.animated.set_frames(frames)


class Step2Widget(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        splitter = QSplitter(Qt.Horizontal)
        left, right = QWidget(), QWidget()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 6)

        # 左：角色列表
        self.scroll_area = QScrollArea(); self.scroll_area.setWidgetResizable(True)
        self.list_container = QWidget(); self.list_layout = QVBoxLayout(self.list_container); self.list_layout.addStretch(1)
        self.items = {}
        self.scroll_area.setWidget(self.list_container)
        btn_refresh = QPushButton("刷新角色列表"); btn_refresh.clicked.connect(self.app.load_personas)
        ops = QHBoxLayout()
        btn_all = QToolButton(); btn_all.setText("全选可见"); btn_all.clicked.connect(self.app.persona_select_all)
        btn_none = QToolButton(); btn_none.setText("全不选可见"); btn_none.clicked.connect(self.app.persona_select_none)
        btn_inv = QToolButton(); btn_inv.setText("反选可见"); btn_inv.clicked.connect(self.app.persona_select_invert)
        self.input_search = QLineEdit(); self.input_search.setPlaceholderText("搜索角色名称…")
        self.input_search.textChanged.connect(self.apply_filters)
        self.combo_sort = QComboBox(); self.combo_sort.addItems(["默认", "名称 A→Z", "名称 Z→A"]) ; self.combo_sort.currentIndexChanged.connect(self.apply_filters)
        self.cb_only_selected = QCheckBox("仅显示已选") ; self.cb_only_selected.stateChanged.connect(self.apply_filters)
        ops.addWidget(btn_all); ops.addWidget(btn_none); ops.addWidget(btn_inv); ops.addStretch(1)
        ops.addWidget(QLabel("排序:")); ops.addWidget(self.combo_sort)
        ops.addWidget(self.cb_only_selected)
        l_lay = QVBoxLayout(left)
        header_row = QHBoxLayout(); header_row.addWidget(QLabel("选择参与模拟的角色"));
        self.lbl_summary = QLabel("已选 0 / 总 0") ; header_row.addStretch(1); header_row.addWidget(self.lbl_summary)
        l_lay.addLayout(header_row)
        l_lay.addWidget(self.input_search)
        l_lay.addLayout(ops)
        l_lay.addWidget(self.scroll_area, 1)
        l_lay.addWidget(btn_refresh)

        # 右：预览 + 编辑
        self.preview = AnimatedLabel(); self.lbl_preview_name = QLabel("- 选中的角色 -")
        self.edit_age = QLineEdit(); self.edit_currently = QTextEdit(); self.edit_innate = QTextEdit(); self.edit_learned = QTextEdit(); self.edit_lifestyle = QTextEdit(); self.edit_daily = QTextEdit()
        self.btn_save = QPushButton("保存修改"); self.btn_save.clicked.connect(self.app.save_persona_edits); self.btn_save.setEnabled(False)

        r_lay = QVBoxLayout(right)
        r_lay.addWidget(QLabel("角色形象预览"))
        r_lay.addWidget(self.preview)
        r_lay.addWidget(self.lbl_preview_name)
        form = QFormLayout()
        form.addRow("角色年龄", self.edit_age)
        form.addRow("当前状态", self.edit_currently)
        form.addRow("天赋特性", self.edit_innate)
        form.addRow("所学知识", self.edit_learned)
        form.addRow("生活方式", self.edit_lifestyle)
        form.addRow("每日计划", self.edit_daily)
        r_lay.addLayout(form)
        r_lay.addWidget(self.btn_save)

        root = QVBoxLayout(self)
        root.addWidget(QLabel("第2步：选择参与者与配置"))
        root.addWidget(splitter, 1)
        self.btn_start = QPushButton("启动模拟（已选 0）"); self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self.app.start_simulation_and_go_to_step3)
        root.addWidget(self.btn_start)

    def add_persona_item(self, name: str, checked: bool):
        def on_modify(n):
            self.app.load_persona_for_editing(n)

        def on_toggle(n, state):
            self.app.toggle_persona(n, state)

        w = PersonaItem(name, checked, on_modify, on_toggle, self.app.delete_persona)
        w.enterEvent = lambda e, n=name: self.app.preview_persona_visual(n)
        w.leaveEvent = lambda e: self.app.clear_preview_if_not_sticky()
        def _row_click(ev, n=name, widget=w):
            # 点击整行任意区域均可切换（更友好），但不拦截“修改”按钮默认行为
            try:
                pos = ev.position().toPoint() if hasattr(ev, 'position') else ev.pos()
                target = widget.childAt(pos)
                from PySide6.QtWidgets import QToolButton as _QTB
                if isinstance(target, _QTB):
                    return QWidget.mousePressEvent(widget, ev)
            except Exception:
                pass
            widget.cb.setChecked(not widget.cb.isChecked())
            self.app.preview_persona_visual(n, sticky=True)
            QWidget.mousePressEvent(widget, ev)
        w.mousePressEvent = _row_click
        self.list_layout.insertWidget(self.list_layout.count() - 1, w)
        self.items[name] = w

    def update_start_button_state(self):
        selected = sum(1 for v in self.app.persona_states.values() if v)
        total = len(self.items)
        self.lbl_summary.setText(f"已选 {selected} / 总 {total}")
        self.btn_start.setText(f"启动模拟（已选 {selected}）")
        self.btn_start.setEnabled(selected > 0)

    def apply_filters(self):
        text = (self.input_search.text() or "").strip().lower()
        only_selected = self.cb_only_selected.isChecked()
        # 先过滤可见性
        for name, w in self.items.items():
            visible = True
            if text and text not in name.lower():
                visible = False
            if only_selected and not self.app.persona_states.get(name, False):
                visible = False
            w.setVisible(visible)
        # 再排序可见项
        mode = self.combo_sort.currentText()
        names = [n for n, w in self.items.items() if w.isVisible()]
        if mode == "名称 A→Z":
            names.sort(key=lambda x: x.lower())
        elif mode == "名称 Z→A":
            names.sort(key=lambda x: x.lower(), reverse=True)
        # 重新插入可见项的顺序（隐藏项保持在末尾前）
        # 先移除所有可见项
        for n in names:
            w = self.items[n]
            self.list_layout.removeWidget(w)
        insert_index = self.list_layout.count() - 1
        for n in names:
            w = self.items[n]
            self.list_layout.insertWidget(insert_index, w)
        # 更新汇总与启动状态
        self.update_start_button_state()


class Step3Widget(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        root = QVBoxLayout(self)
        root.addWidget(QLabel("第3步：运行与监控"))

        self.lbl_overall = QLabel("等待任务...")
        self.lbl_recent = QLabel("")
        # 防止超长文本拉伸界面：标签启用自动换行并限制高度
        try:
            self.lbl_overall.setWordWrap(True)
            self.lbl_recent.setWordWrap(True)
            self.lbl_recent.setMaximumHeight(64)
        except Exception:
            pass
        root.addWidget(self.lbl_overall)
        root.addWidget(self.lbl_recent)

        # 实时日志视图
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        # 日志窗口启用按控件宽度换行，并在必要时任意位置换行
        try:
            self.log_view.setLineWrapMode(QTextEdit.WidgetWidth)
            self.log_view.setWordWrapMode(QTextOption.WrapAnywhere)
        except Exception:
            pass
        root.addWidget(self.log_view, 1)

        # 由于已采用线程+subprocess执行流程，进度条按任务块显示可选保留
        self.progress_container = QVBoxLayout(); self.progress_container.addStretch(1)
        frame_widget = QWidget(); frame_widget.setLayout(self.progress_container)
        frame_widget.setStyleSheet(f"background:{Palette.BG_CARD}; border:1px solid {Palette.BORDER};")
        root.addWidget(frame_widget, 0)

        ctrl = QHBoxLayout()
        self.input_resume_steps = QLineEdit("100")
        btn_resume = QPushButton("继续当前模拟"); btn_resume.clicked.connect(self.app.resume_simulation)
        ctrl.addWidget(QLabel("继续步数:")); ctrl.addWidget(self.input_resume_steps); ctrl.addWidget(btn_resume); ctrl.addStretch(1)
        root.addLayout(ctrl)

        hist = QHBoxLayout()
        self.combo_history = QComboBox()
        btn_load = QPushButton("加载"); btn_load.clicked.connect(self.app.load_selected_history)
        btn_refresh = QPushButton("刷新"); btn_refresh.clicked.connect(self.app.refresh_history)
        hist.addWidget(QLabel("历史模拟结果:")); hist.addWidget(self.combo_history, 1); hist.addWidget(btn_load); hist.addWidget(btn_refresh)
        root.addLayout(hist)

        actions = QHBoxLayout()
        self.btn_finish = QPushButton("完成并查看模拟"); self.btn_finish.clicked.connect(self.app.finish_and_open_results)
        self.btn_img = QPushButton("生成绘画图片"); self.btn_img.clicked.connect(self.app.trigger_generate_images)
        self.btn_music = QPushButton("生成背景音乐（vpn）"); self.btn_music.clicked.connect(self.app.trigger_generate_music)
        self.btn_web = QPushButton("生成网页模拟（vpn）"); self.btn_web.clicked.connect(self.app.trigger_generate_web)
        actions.addWidget(self.btn_finish); actions.addWidget(self.btn_img); actions.addWidget(self.btn_music); actions.addWidget(self.btn_web)
        root.addLayout(actions)

    def add_progress_row(self, label: str) -> Tuple[QLabel, QProgressBar, QWidget]:
        container = QWidget(); lay = QVBoxLayout(container)
        title = QLabel(label); bar = QProgressBar(); bar.setRange(0, 0)
        lay.addWidget(title); lay.addWidget(bar)
        self.progress_container.insertWidget(self.progress_container.count() - 1, container)
        return title, bar, container


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI外星小镇")
        self.resize(1400, 900)

        self.log_bus = LogBus(); self.log_bus.message.connect(self.on_log)

        self.persona_states: Dict[str, bool] = {}
        self.living_area_data: Dict[str, Dict] = {}
        self.visual_templates: List[str] = []
        self.visual_frames: List[List[QPixmap]] = []
        self.visual_index = -1
        self.selected_visual_path = ""
        self.last_created_name: Optional[str] = None
        self.last_sim_name: Optional[str] = None
        self.sticky_persona: Optional[str] = None
        self.progress_rows: Dict[str, Tuple[QLabel, QProgressBar, QWidget]] = {}
        self.step_total = 50
        self._tasks: Dict[str, ProcessTask] = {}
        # 回放服务端口（Python运行模式下避免重复启动）
        self._replay_port: Optional[int] = None

        # 先构建界面（避免加载时访问未初始化控件）
        self.stack = QStackedWidget()
        self.step1 = Step1Widget(self); self.step2 = Step2Widget(self); self.step3 = Step3Widget(self)
        self.stack.addWidget(self.step1); self.stack.addWidget(self.step2); self.stack.addWidget(self.step3)
        self._build_shell_ui()

        # 顶部新布局不再使用工具栏
        self.apply_theme()

        # 再加载数据（需要 step1/step2 已存在）
        self._ensure_default_personas_in_start_py()
        self._load_living_area_options()
        self._load_visual_templates()
        self.show_step(0)
        self.load_personas()
        self.refresh_history()

    # Theme
    def apply_theme(self):
        base = f"""
        QWidget {{ background: {Palette.BG}; color: {Palette.TEXT}; }}
        /* 黑金：倒角卡片 */
        QFrame#Card {{ background:{Palette.BG_CARD}; border:1px solid {Palette.BORDER}; border-radius:12px; }}
        /* 输入控件 */
        QLineEdit, QTextEdit, QComboBox {{ background: {Palette.BG_CARD}; border:1px solid {Palette.BORDER}; padding:10px; border-radius:10px; }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{ border-color: {Palette.ACCENT}; }}
        /* 按钮：金色渐变 + 倒角 */
        QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {Palette.ACCENT}, stop:1 {Palette.ACCENT_2}); border:1px solid {Palette.ACCENT_2}; padding:10px; color: #1A1A1A; border-radius:10px; font-weight:700; }}
        QPushButton:hover {{ background: {Palette.ACCENT_2}; }}
        QToolButton {{ background: {Palette.BG_SOFT}; border:1px solid {Palette.BORDER}; padding:6px 10px; color:{Palette.TEXT}; border-radius:10px; }}
        QToolButton:hover {{ background: {Palette.ACCENT}; color:#1A1A1A; }}
        /* Step1：大号圆形箭头 */
        QToolButton#NavArrow {{
            background: {Palette.BG_SOFT}; color:{Palette.TEXT}; border:2px solid {Palette.ACCENT_2};
            border-radius:36px; font-weight:900; font-size:22px;
        }}
        QToolButton#NavArrow:hover {{ background:{Palette.ACCENT}; color:#1A1A1A; }}
        QToolButton#NavArrow:pressed {{ background:{Palette.ACCENT_2}; }}
        /* Step2：角色行 可选中高亮 */
        #PersonaRow {{ background: transparent; border:1px solid transparent; border-radius:10px; }}
        #PersonaRow:hover {{ background: rgba(255, 209, 102, 0.08); border:1px solid {Palette.BORDER}; }}
        #PersonaRow[selected="true"] {{ background: rgba(255, 209, 102, 0.16); border:1px solid {Palette.ACCENT_2}; }}
        /* 选中后名字行变黄 */
        #PersonaRow QLabel#PersonaName {{ padding: 4px 10px; border-radius: 8px; }}
        #PersonaRow QLabel#PersonaName[selected="true"] {{
            color: {Palette.ACCENT}; font-weight: 800;
            border: 1px solid {Palette.ACCENT_2};
            background: rgba(255, 209, 102, 0.12);
        }}
        QToolButton#Danger {{ background: rgba(234, 84, 85, 0.12); color: {Palette.TEXT}; border:1px solid {Palette.ERR}; border-radius:10px; padding:6px 10px; }}
        QToolButton#Danger:hover {{ background: {Palette.ERR}; color:#1A1A1A; }}
        QLabel {{ color: {Palette.TEXT}; }}
        /* 滚动与进度 */
        QScrollArea {{ border:1px solid {Palette.BORDER}; border-radius:10px; }}
        QProgressBar {{ border: 1px solid {Palette.BORDER}; border-radius:10px; text-align: center; height:18px; background:{Palette.BG_CARD}; }}
        QProgressBar::chunk {{ border-radius:10px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {Palette.CYAN}, stop:1 {Palette.LIME}); }}
        /* 头部容器 */
        #Header {{ background:{Palette.BG_CARD}; border:1px solid {Palette.BORDER}; border-radius:12px; }}
        /* 顶部分段按钮 */
        QPushButton#StepTab {{
            background: {Palette.BG_SOFT};
            border:1px solid {Palette.BORDER};
            padding:10px 16px; border-radius:10px; color:{Palette.TEXT};
        }}
        QPushButton#StepTab:checked {{
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {Palette.ACCENT}, stop:1 {Palette.ACCENT_2});
            color:#1A1A1A; border:1px solid {Palette.ACCENT_2};
        }}
        """
        self.setStyleSheet(base)
        font = load_pixel_font()
        # 全局设置字体，避免局部不生效
        try:
            app = QApplication.instance()
            if app is not None:
                app.setFont(font)
        except Exception:
            pass
        self.setFont(font)

    def _build_shell_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 顶部头部 + 分段按钮
        self.header = QWidget(); self.header.setObjectName("Header")
        h = QHBoxLayout(self.header)
        h.setContentsMargins(16, 12, 16, 12)
        title = QLabel("AI小镇启动器")
        h.addWidget(title)
        h.addStretch(1)

        # 分段按钮组
        tabs = QWidget(); tabs_layout = QHBoxLayout(tabs)
        tabs_layout.setContentsMargins(0,0,0,0); tabs_layout.setSpacing(8)
        self.btn_tab1 = QPushButton("第1步 角色设定"); self.btn_tab1.setObjectName("StepTab"); self.btn_tab1.setCheckable(True)
        self.btn_tab2 = QPushButton("第2步 选择与配置"); self.btn_tab2.setObjectName("StepTab"); self.btn_tab2.setCheckable(True)
        self.btn_tab3 = QPushButton("第3步 运行与监控"); self.btn_tab3.setObjectName("StepTab"); self.btn_tab3.setCheckable(True)
        self.btn_tab1.clicked.connect(lambda: self.show_step(0))
        self.btn_tab2.clicked.connect(lambda: self.show_step(1))
        self.btn_tab3.clicked.connect(lambda: self.show_step(2))
        self.step_tabs_group = QButtonGroup(self)
        self.step_tabs_group.setExclusive(True)
        self.step_tabs_group.addButton(self.btn_tab1, 0)
        self.step_tabs_group.addButton(self.btn_tab2, 1)
        self.step_tabs_group.addButton(self.btn_tab3, 2)
        self.btn_tab1.setChecked(True)
        tabs_layout.addWidget(self.btn_tab1)
        tabs_layout.addWidget(self.btn_tab2)
        tabs_layout.addWidget(self.btn_tab3)
        h.addWidget(tabs)

        # 设置按钮
        self.btn_settings_hdr = QToolButton(); self.btn_settings_hdr.setText("设置")
        self.btn_settings_hdr.clicked.connect(self.open_settings)
        h.addWidget(self.btn_settings_hdr)

        layout.addWidget(self.header)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        # 投影效果
        effect = QGraphicsDropShadowEffect(self.header)
        effect.setBlurRadius(18); effect.setColor(QColor(0,0,0,160)); effect.setOffset(0,6)
        self.header.setGraphicsEffect(effect)

    # 旧的工具栏导航已移除，使用顶部分段按钮
    def _build_toolbar(self):
        pass

    # Log
    def log(self, text: str, tag: str = "info"):
        # 清理 BOM，避免 GBK/控制台编码错误
        out = str(text or "").replace("\ufeff", "")
        try:
            try:
                print(out)
            except Exception:
                try:
                    sys.stdout.write(out + "\n")
                    try:
                        sys.stdout.flush()
                    except Exception:
                        pass
                except Exception:
                    try:
                        if getattr(sys, "stdout", None) is not None and getattr(sys.stdout, "buffer", None) is not None:
                            enc = getattr(sys.stdout, "encoding", None) or "utf-8"
                            sys.stdout.buffer.write((out + "\n").encode(enc, errors="ignore"))
                            try:
                                sys.stdout.buffer.flush()
                            except Exception:
                                pass
                    except Exception:
                        pass
        finally:
            self.log_bus.message.emit(out, tag)

    def on_log(self, text: str, tag: str):
        # 界面尚未就绪时直接返回，避免初始化早期日志触发异常
        if not hasattr(self, 'stack') or self.stack is None or not hasattr(self, 'step3'):
            return
        if self.stack.currentWidget() is self.step3:
            color_map = {"error": Palette.ERR, "warn": Palette.WARN, "sim_start": Palette.OK, "sim_end": Palette.ACCENT_2, "info": Palette.TEXT}
            self.step3.lbl_recent.setText(text)
            self.step3.lbl_recent.setStyleSheet(f"color:{color_map.get(tag, Palette.TEXT)}")
            try:
                self.step3.log_view.append(text)
            except Exception:
                pass
            # 仅在完成时更新总提示，其余情况不改变，避免误报
            if tag == "sim_end":
                self.step3.lbl_overall.setText("任务完成。"); self.step3.lbl_overall.setStyleSheet(f"color:{Palette.ACCENT_2}")

    # Steps
    def show_step(self, idx: int):
        self.stack.setCurrentIndex(idx)
        titles = ["第1步：角色核心设定", "第2步：选择参与者与配置", "第3步：运行与监控"]
        if hasattr(self, 'header_title') and 0 <= idx < len(titles):
            self.header_title.setText(titles[idx])
        # 更新分段按钮选中态
        if hasattr(self, 'step_tabs_group'):
            btn = self.step_tabs_group.button(idx)
            if btn:
                btn.setChecked(True)

    def next_step(self):
        i = self.stack.currentIndex()
        if i == 0:
            self.show_step(1)
        elif i == 1:
            if not self.update_start_py_personas():
                return
            self.show_step(2)
        else:
            self.finish_and_open_results()

    def prev_step(self):
        i = self.stack.currentIndex()
        if i > 0:
            self.show_step(i - 1)

    def open_settings(self):
        dlg = SettingsDialog(self, step_value=self.step_total, font_size=self.font().pointSize())
        if dlg.exec() == QDialog.Accepted:
            self.step_total = dlg.spin_steps.value()
            # 全量应用字号到全局与现有控件
            try:
                point = dlg.spin_font.value()
                base_font = self.font()
                base_font.setPointSize(point)
                app = QApplication.instance()
                if app is not None:
                    app.setFont(base_font)
                self.setFont(base_font)
                for w in self.findChildren(QWidget):
                    w.setFont(base_font)
            except Exception:
                pass

    # Step2 批量选择操作
    def persona_select_all(self):
        try:
            for name, w in getattr(self.step2, 'items', {}).items():
                w.cb.setChecked(True)
        except Exception:
            pass

    def persona_select_none(self):
        try:
            for name, w in getattr(self.step2, 'items', {}).items():
                w.cb.setChecked(False)
        except Exception:
            pass

    def persona_select_invert(self):
        try:
            for name, w in getattr(self.step2, 'items', {}).items():
                w.cb.setChecked(not w.cb.isChecked())
        except Exception:
            pass

    def delete_persona(self, name: str):
        try:
            folder = os.path.join(BASE_AGENT_PATH, name)
            agent_json = os.path.join(folder, "agent.json")
            if not (os.path.isdir(folder) and os.path.isfile(agent_json)):
                QMessageBox.warning(self, "提示", f"角色 '{name}' 的文件不存在。")
                return
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除角色 '{name}' 吗？该操作不可撤销。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            shutil.rmtree(folder, ignore_errors=True)
            # 同步状态
            if name in self.persona_states:
                self.persona_states.pop(name, None)
            # 从界面移除
            w = getattr(self.step2, 'items', {}).pop(name, None)
            if w:
                w.setParent(None)
            # 移除 start.py 中该 persona 名称
            try:
                with open(START_PY_PATH, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                new_lines = []
                in_list = False
                for line in lines:
                    s = line.strip()
                    if s.startswith("personas = ["):
                        in_list = True
                        new_lines.append(line)
                        continue
                    if in_list:
                        # 过滤掉包含该名字的行
                        if (f'"{name}"' in s) or (f"'{name}'" in s):
                            continue
                        new_lines.append(line)
                        if s.endswith("]"):
                            in_list = False
                        continue
                    new_lines.append(line)
                with open(START_PY_PATH, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
            except Exception as e:
                self.log(f"从 start.py 移除 {name} 失败: {e}", "error")
            self.step2.update_start_button_state()
            self.log(f"角色 '{name}' 已删除。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除角色失败: {e}")

    # Visual templates
    def _load_visual_templates(self):
        self.visual_templates.clear(); self.visual_frames.clear()
        if not os.path.isdir(VISUAL_TEMPLATE_DIR):
            self.log(f"错误: 角色形象文件夹未找到: {VISUAL_TEMPLATE_DIR}", "error"); self.apply_current_visual(); return
        try:
            folders = sorted([f for f in os.listdir(VISUAL_TEMPLATE_DIR) if os.path.isdir(os.path.join(VISUAL_TEMPLATE_DIR, f))], key=lambda x: int(x) if x.isdigit() else 999999)
        except Exception as e:
            self.log(f"读取角色形象文件夹失败: {e}", "error"); return
        for name in folders:
            path = os.path.join(VISUAL_TEMPLATE_DIR, name)
            tex = os.path.join(path, "texture.png")
            if os.path.exists(tex):
                frames = slice_sprite_frames(tex, SPRITE_COLS, SPRITE_ROWS, IDLE_ANIM_FRAME_INDICES)
                if frames:
                    self.visual_templates.append(path); self.visual_frames.append(frames)
            else:
                portrait = os.path.join(path, "portrait.png")
                if os.path.exists(portrait):
                    try:
                        img = Image.open(portrait)
                        self.visual_templates.append(path); self.visual_frames.append([pil_to_qpixmap(img)])
                    except Exception:
                        pass
        if self.visual_templates:
            self.visual_index = 0; self.selected_visual_path = self.visual_templates[0]
        self.apply_current_visual()

    def apply_current_visual(self):
        if self.visual_index < 0 or self.visual_index >= len(self.visual_templates):
            self.step1.apply_visual("无可用形象", [])
            return
        folder = os.path.basename(self.visual_templates[self.visual_index])
        frames = self.visual_frames[self.visual_index]
        self.selected_visual_path = self.visual_templates[self.visual_index]
        self.step1.apply_visual(folder, frames)

    def show_prev_visual(self):
        if not self.visual_templates: return
        self.visual_index = (self.visual_index - 1) % len(self.visual_templates)
        self.apply_current_visual()

    def show_next_visual(self):
        if not self.visual_templates: return
        self.visual_index = (self.visual_index + 1) % len(self.visual_templates)
        self.apply_current_visual()

    # Data loading
    def _load_living_area_options(self):
        tpl = os.path.join(VISUAL_TEMPLATE_DIR, DEFAULT_TEMPLATE_AGENT, "agent.json")
        try:
            with open(tpl, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.living_area_data = data.get("spatial", {}).get("tree", {}).get("the Ville", {})
            self.log("成功加载生活区域选项。")
        except Exception as e:
            self.log(f"加载生活区域选项失败: {e}", "error"); self.living_area_data = {}
        l2 = list(self.living_area_data.keys())
        self.step1.combo_l2.clear(); self.step1.combo_l2.addItems(l2)
        self.step1.combo_l2.currentTextChanged.connect(self._on_l2_changed)
        if l2:
            self.step1.combo_l2.setCurrentIndex(0); self._on_l2_changed(l2[0])

    def _on_l2_changed(self, txt: str):
        level3_data = self.living_area_data.get(txt, {}) if txt else {}
        self.step1.combo_l3.clear(); self.step1.combo_l3.addItems(list(level3_data.keys()))

    # Personas list
    def load_personas(self):
        lay = self.step2.list_layout
        for i in reversed(range(lay.count() - 1)):
            w = lay.itemAt(i).widget()
            if w: w.setParent(None)
        # 清空映射
        if hasattr(self.step2, 'items'):
            self.step2.items.clear()
        personas: List[str] = []
        # 优先：冻结环境使用资源目录直接扫描可用角色
        if getattr(sys, "frozen", False) or not os.path.isfile(START_PY_PATH):
            try:
                if os.path.isdir(BASE_AGENT_PATH):
                    personas = [n for n in os.listdir(BASE_AGENT_PATH) if os.path.isdir(os.path.join(BASE_AGENT_PATH, n))]
                    personas.sort()
            except Exception as e:
                self.log(f"扫描角色目录失败: {e}", "error")
        else:
            try:
                with open(START_PY_PATH, 'r', encoding='utf-8') as f:
                    content = f.read()
                m = re.search(r"personas\s*=\s*\[([\s\S]*?)\]", content)
                personas = re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)) if m else []
            except Exception as e:
                self.log(f"读取 start.py 失败: {e}", "error")
        # 渲染 UI
        for p in personas:
            folder = os.path.join(BASE_AGENT_PATH, p)
            agent_json = os.path.join(folder, "agent.json")
            if not (os.path.isdir(folder) and os.path.isfile(agent_json)):
                continue
            checked = self.persona_states.get(p, False)
            self.step2.add_persona_item(p, checked)
        self.log(f"成功加载并验证 {len(self.step2.items)} 个角色。")
        # 刷新筛选、计数与按钮状态
        try:
            self.step2.apply_filters()
        except Exception:
            pass

    def toggle_persona(self, name: str, state: bool):
        self.persona_states[name] = state
        # 同步更新第2步启动按钮与计数
        try:
            if hasattr(self, 'step2'):
                self.step2.update_start_button_state()
                # 同步名字行选中样式（通过属性刷新）
                w = getattr(self.step2, 'items', {}).get(name)
                if w:
                    w._apply_selected_style()
        except Exception:
            pass

    # Preview & edit
    def _load_agent_frames(self, persona_name: str) -> List[QPixmap]:
        asset_dir = os.path.join(BASE_AGENT_PATH, persona_name)
        tex = os.path.join(asset_dir, "texture.png"); portrait = os.path.join(asset_dir, "portrait.png")
        frames: List[QPixmap] = []
        if os.path.exists(tex):
            frames = slice_sprite_frames(tex, SPRITE_COLS, SPRITE_ROWS, IDLE_ANIM_FRAME_INDICES)
        if not frames and os.path.exists(portrait):
            try:
                img = Image.open(portrait); frames = [pil_to_qpixmap(img)]
            except Exception: pass
        return frames

    def preview_persona_visual(self, persona_name: str, sticky: bool = False):
        if sticky: self.sticky_persona = persona_name
        frames = self._load_agent_frames(persona_name)
        self.step2.preview.set_frames(frames); self.step2.lbl_preview_name.setText(persona_name)

    def clear_preview_if_not_sticky(self):
        if not self.sticky_persona:
            self.step2.preview.set_frames([]); self.step2.lbl_preview_name.setText("- 选中的角色 -")

    def load_persona_for_editing(self, name: str):
        try:
            agent = os.path.join(BASE_AGENT_PATH, name, "agent.json")
            with open(agent, 'r', encoding='utf-8') as f: data = json.load(f)
            self.step2.edit_age.setText(str(data.get('scratch', {}).get('age', '')))
            self.step2.edit_currently.setPlainText(data.get('currently', ''))
            self.step2.edit_innate.setPlainText(data.get('scratch', {}).get('innate', ''))
            self.step2.edit_learned.setPlainText(data.get('scratch', {}).get('learned', ''))
            self.step2.edit_lifestyle.setPlainText(data.get('scratch', {}).get('lifestyle', ''))
            self.step2.edit_daily.setPlainText(data.get('scratch', {}).get('daily_plan', ''))
            self.editing_persona_name = name; self.step2.btn_save.setEnabled(True)
            self.log(f"角色 '{name}' 的设定已加载到编辑表单。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载角色 '{name}' 进行编辑时出错: {e}")
            self.log(f"加载编辑时出错: {e}", "error")

    def save_persona_edits(self):
        name = getattr(self, 'editing_persona_name', None)
        if not name:
            QMessageBox.information(self, "提示", "请先选择要编辑的角色。"); return
        path = os.path.join(BASE_AGENT_PATH, name, "agent.json")
        try:
            with open(path, 'r', encoding='utf-8') as f: data = json.load(f)
            data.setdefault('scratch', {})
            age_text = self.step2.edit_age.text().strip()
            if age_text: data['scratch']['age'] = int(age_text)
            data['currently'] = self.step2.edit_currently.toPlainText().strip()
            data['scratch']['innate'] = self.step2.edit_innate.toPlainText().strip()
            data['scratch']['learned'] = self.step2.edit_learned.toPlainText().strip()
            data['scratch']['lifestyle'] = self.step2.edit_lifestyle.toPlainText().strip()
            data['scratch']['daily_plan'] = self.step2.edit_daily.toPlainText().strip()
            with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "成功", f"角色 '{name}' 的设定已保存。")
            self.step2.btn_save.setEnabled(False); self.log(f"角色 '{name}' 的设定已保存到 {path}")
        except ValueError:
            QMessageBox.critical(self, "数值错误", "年龄必须是有效整数。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    # Create character
    def create_character(self):
        name = self.step1.input_name.text().strip(); age_str = self.step1.input_age.text().strip()
        currently = self.step1.txt_currently.toPlainText().strip(); innate = self.step1.txt_innate.toPlainText().strip()
        learned = self.step1.txt_learned.toPlainText().strip(); lifestyle = self.step1.txt_lifestyle.toPlainText().strip()
        daily = self.step1.txt_daily.toPlainText().strip(); l2 = self.step1.combo_l2.currentText().strip(); l3 = self.step1.combo_l3.currentText().strip()
        base_template_dir = os.path.join(VISUAL_TEMPLATE_DIR, DEFAULT_TEMPLATE_AGENT); base_agent_json = os.path.join(base_template_dir, "agent.json")
        if not name: QMessageBox.critical(self, "错误", "请输入角色名称。"); return
        try: age = int(age_str)
        except Exception: QMessageBox.critical(self, "错误", "年龄必须是整数。"); return
        safe_name = re.sub(r"[\\/*?\"<>|]", "_", name)
        if not os.path.exists(base_agent_json): QMessageBox.critical(self, "错误", f"找不到模板配置: {base_agent_json}"); return
        agent_dir = os.path.join(BASE_AGENT_PATH, safe_name); os.makedirs(agent_dir, exist_ok=True)
        new_agent_json = os.path.join(agent_dir, "agent.json")
        try:
            with open(base_agent_json, 'r', encoding='utf-8') as f: agent_data = json.load(f)
            agent_data['name'] = safe_name; agent_data.setdefault('scratch', {})
            agent_data['currently'] = currently; agent_data['scratch']['age'] = age
            agent_data['scratch']['innate'] = innate; agent_data['scratch']['lifestyle'] = lifestyle
            agent_data['scratch']['daily_plan'] = daily; agent_data['scratch']['learned'] = learned
            if l2 and l3:
                agent_data.setdefault('spatial', {}).setdefault('address', {})['living_area'] = ["the Ville", l2, l3]
            agent_data['portrait'] = f"assets/village/agents/{safe_name}/portrait.png"
            with open(new_agent_json, 'w', encoding='utf-8') as f: json.dump(agent_data, f, ensure_ascii=False, indent=2)
            sel_dir = self.selected_visual_path
            def copy_if_exists(src, dst):
                if os.path.exists(src): shutil.copy2(src, dst)
            # 优先复制玩家选择的形象资源
            if sel_dir and os.path.isdir(sel_dir):
                copy_if_exists(os.path.join(sel_dir, "portrait.png"), os.path.join(agent_dir, "portrait.png"))
                copy_if_exists(os.path.join(sel_dir, "texture.png"), os.path.join(agent_dir, "texture.png"))
                copy_if_exists(os.path.join(sel_dir, "texture.svg"), os.path.join(agent_dir, "texture.svg"))
            # 若缺失则回退复制默认模板资源
            for rf in ["portrait.png", "texture.png", "texture.svg"]:
                dst_path = os.path.join(agent_dir, rf)
                if not os.path.exists(dst_path):
                    copy_if_exists(os.path.join(base_template_dir, rf), dst_path)
            self._add_persona_to_start_py_if_needed(safe_name)
            # 同步写入本文件的默认角色列表，保证下次启动也能显示
            self._add_persona_to_default_personas_if_needed(safe_name)
            self.last_created_name = safe_name; self.last_sim_name = safe_name
            QMessageBox.information(self, "成功", f"角色 '{safe_name}' 创建完成并已加入启动列表。")
            self.load_personas(); self._load_visual_templates()
        except Exception as e:
            shutil.rmtree(agent_dir, ignore_errors=True); QMessageBox.critical(self, "错误", f"创建角色失败: {e}")

    def create_character_and_go_step2(self):
        # 调用创建逻辑并在成功后跳转到第2步
        name_text = self.step1.input_name.text().strip()
        safe_name = re.sub(r"[\\/*?\"<>|]", "_", name_text) if name_text else ""
        before_exists = os.path.isdir(os.path.join(BASE_AGENT_PATH, safe_name)) if safe_name else False
        self.create_character()
        if safe_name and os.path.isdir(os.path.join(BASE_AGENT_PATH, safe_name)) and not before_exists:
            self.show_step(1)

    def skip_step1(self):
        # 直接进入第2步，不做创建
        self.show_step(1)

    def _add_persona_to_start_py_if_needed(self, name: str):
        # 冻结环境不修改只读文件，跳过
        if getattr(sys, "frozen", False) or not os.path.isfile(START_PY_PATH):
            return
        try:
            with open(START_PY_PATH, 'r', encoding='utf-8') as f: lines = f.readlines()
            new_lines = []; in_list = False; found = False; start_idx = -1
            for i, line in enumerate(lines):
                s = line.strip()
                if s.startswith("personas = ["):
                    in_list = True; start_idx = i; new_lines.append(line)
                    if f'"{name}"' in s or f"'{name}'" in s: found = True
                    continue
                if in_list:
                    if f'"{name}"' in s or f"'{name}'" in s: found = True
                    new_lines.append(line)
                    if s.endswith("]"):
                        in_list = False
                        if not found:
                            indent = "    "
                            if start_idx + 1 < len(lines):
                                m = re.match(r"^(\s+)", lines[start_idx + 1])
                                if m: indent = m.group(1)
                            if not new_lines[-2].strip().endswith(','):
                                new_lines[-2] = new_lines[-2].rstrip() + ',\n'
                            new_lines.insert(len(new_lines) - 1, f"{indent}\"{name}\",\n")
                    continue
                new_lines.append(line)
            with open(START_PY_PATH, 'w', encoding='utf-8') as f: f.writelines(new_lines)
        except Exception as e:
            self.log(f"更新 start.py 失败: {e}", "error")

    def _add_persona_to_default_personas_if_needed(self, name: str):
        try:
            path = os.path.abspath(__file__)
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            head = "DEFAULT_PERSONAS_LIST = ["
            personas_in_file: List[str] = []
            in_block = False
            original_head = None
            for line in lines:
                s = line.strip()
                if s.startswith(head):
                    original_head = line.split('[')[0] + '['
                    in_block = True
                    personas_in_file += re.findall(r"['\"]([^'\"]+)['\"]", s)
                    if s.endswith(']'):
                        in_block = False
                    continue
                if in_block:
                    personas_in_file += re.findall(r"['\"]([^'\"]+)['\"]", s)
                    if s.endswith(']'):
                        in_block = False
            if name in personas_in_file:
                return
            updated = personas_in_file + [name]
            new: List[str] = []
            in_block = False
            wrote = False
            indent = "    "
            for i, line in enumerate(lines):
                s = line.strip()
                if s.startswith(head) and not wrote:
                    if i + 1 < len(lines):
                        m = re.match(r"^(\s+)", lines[i + 1])
                        if m:
                            indent = m.group(1)
                    new.append((original_head or head) + "\n")
                    for j, n in enumerate(updated):
                        end = ',' if j < len(updated) - 1 else ''
                        new.append(f"{indent}\"{n}\"{end}\n")
                    new.append(indent.rstrip() + "]\n")
                    wrote = True
                    in_block = True
                    continue
                if in_block:
                    if s.endswith(']'):
                        in_block = False
                    continue
                new.append(line)
            if wrote and ''.join(new) != ''.join(lines):
                with open(path, 'w', encoding='utf-8') as f:
                    f.writelines(new)
                self.log(f"已将角色 '{name}' 添加到 DEFAULT_PERSONAS_LIST。")
        except Exception as e:
            self.log(f"更新 DEFAULT_PERSONAS_LIST 失败: {e}", "error")

    def update_start_py_personas(self) -> bool:
        selected = [n for n, v in self.persona_states.items() if v]
        if not selected:
            QMessageBox.warning(self, "警告", "没有选择任何角色参与模拟。"); return False
        # 冻结环境：把选择写入 results/selected_personas.json，供 start.exe 读取
        if getattr(sys, "frozen", False) or not os.path.isfile(START_PY_PATH):
            try:
                results_dir = os.path.join(SCRIPT_DIR, "results")
                os.makedirs(results_dir, exist_ok=True)
                sel_file = os.path.join(results_dir, "selected_personas.json")
                with open(sel_file, 'w', encoding='utf-8') as f:
                    json.dump(selected, f, ensure_ascii=False, indent=2)
                self.log(f"已保存选择的角色到 {sel_file}")
                return True
            except Exception as e:
                self.log(f"保存选择角色失败: {e}", "error")
                QMessageBox.critical(self, "错误", f"保存选择角色失败: {e}")
                return False
        # 开发环境：回写 start.py
        try:
            with open(START_PY_PATH, 'r', encoding='utf-8') as f: lines = f.readlines()
            new_lines = []; in_list = False; wrote = False; indent = "    "
            for i, line in enumerate(lines):
                s = line.strip()
                if s.startswith("personas = ["):
                    in_list = True
                    if i + 1 < len(lines):
                        m = re.search(r'^(\s+)["\']', lines[i + 1])
                        if m: indent = m.group(1)
                    new_lines.append(line.split('[')[0] + '[\n')
                    for j, name in enumerate(selected):
                        end = ',' if j < len(selected) - 1 else ''
                        new_lines.append(f"{indent}\"{name}\"{end}\n")
                    new_lines.append(indent.rstrip() + "]\n"); wrote = True; continue
                if in_list:
                    if s.endswith("]"): in_list = False
                    continue
                new_lines.append(line)
            if not wrote:
                self.log("未找到 personas 列表。", "error"); QMessageBox.critical(self, "错误", "更新 personas 列表失败。"); return False
            with open(START_PY_PATH, 'w', encoding='utf-8') as f: f.writelines(new_lines)
            self.log(f"成功更新 personas，数量 {len(selected)}。"); return True
        except Exception as e:
            self.log(f"更新 start.py 时出错: {e}", "error"); QMessageBox.critical(self, "错误", f"更新启动脚本失败: {e}")
            return False

    # Simulation
    def start_simulation_and_go_step3(self):
        if not self.update_start_py_personas(): return
        if self.start_simulation(): self.show_step(2)

    def start_simulation_and_go_to_step3(self):
        self.start_simulation_and_go_step3()

    def start_simulation(self) -> bool:
        # 对齐参考：当没有 last_created_name 时使用时间戳
        sim = self.last_created_name or f"sim_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.last_sim_name = sim
        # 使用绝对路径，避免空格路径被误解析
        start_abs = os.path.abspath(START_PY_PATH)
        cmd = [sys.executable, "-u", start_abs, "--name", sim, "--start", "20240213-09:30", "--step", str(self.step_total), "--stride", "10"]
        self.log(f"准备运行模拟 '{sim}'，共 {self.step_total} 步...", "sim_start")
        # 切换到第3步并清空日志
        try:
            self.show_step(2)
            if hasattr(self.step3, 'log_view'):
                self.step3.log_view.clear()
        except Exception:
            pass
        # 使用线程 + subprocess 执行（参考实现逻辑）
        self._execute_command_in_thread(
            cmd,
            log_prefix=f"模拟运行 ({sim})",
            success_message=f"模拟 '{sim}' 进程已启动。",
            failure_message=f"模拟 '{sim}' 启动失败。",
            on_success=self._start_post_chain,
            on_failure=None,
        )
        return True

    def resume_simulation(self):
        if not self.last_sim_name:
            QMessageBox.information(self, "提示", "没有模拟可继续。"); return
        steps = self.step3.input_resume_steps.text().strip() or "100"
        try: int(steps)
        except Exception: QMessageBox.critical(self, "错误", "继续步数必须是正整数。"); return
        sim = self.last_sim_name
        start_abs = os.path.abspath(START_PY_PATH)
        cmd = [sys.executable, "-u", start_abs, "--name", sim, "--start", "20240213-09:30", "--step", steps, "--stride", "10", "--resume"]
        self.log(f"准备继续模拟 '{sim}'，继续 {steps} 步...", "sim_start")
        # 切换到第3步并清空日志
        try:
            self.show_step(2)
            if hasattr(self.step3, 'log_view'):
                self.step3.log_view.clear()
        except Exception:
            pass
        self._execute_command_in_thread(
            cmd,
            log_prefix=f"继续模拟 ({sim})",
            success_message=f"继续模拟 '{sim}' 的进程已启动。",
            failure_message=f"继续模拟 '{sim}' 失败。",
            on_success=self._start_post_chain,
            on_failure=None,
        )

    def finish_and_open_results(self):
        if not self.last_sim_name: QMessageBox.information(self, "提示", "尚无模拟记录。"); return
        self._compress_and_open(self.last_sim_name)

    def _compress_and_open(self, sim_name: str):
        # 无论是否存在 .py 文件，均调用执行器；冻结环境将自动映射为 compress.exe
        comp = os.path.join(SCRIPT_DIR, "compress.py")
        self._execute_command_in_thread(
            [sys.executable, "-u", comp, "--name", sim_name],
            log_prefix=f"压缩 ({sim_name})",
            success_message=f"模拟 '{sim_name}' 结果压缩命令已发送。",
            failure_message=f"压缩模拟 '{sim_name}' 结果失败。",
            on_success=lambda: self._on_compress_success(sim_name),
            on_failure=None,
        )

    def _on_compress_success(self, sim_name: str):
        replay = os.path.join(SCRIPT_DIR, "replay.py")
        # 若已有回放在运行，复用端口直接打开浏览器
        try:
            if self._replay_port:
                import socket
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    if s.connect_ex(("127.0.0.1", int(self._replay_port))) == 0:
                        self._open_browser(sim_name, int(self._replay_port))
                        return
        except Exception:
            pass
        # 为 Python 运行模式选择一个可用端口，避免已有端口占用
        port = 5000
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
        except Exception:
            port = 5000
        # 通过环境变量传递端口和 results 目录，replay.py 会读取 GA_REPLAY_PORT/PORT 与 GA_RESULTS_DIR
        try:
            os.environ["GA_REPLAY_PORT"] = str(port)
        except Exception:
            pass
        # 启动回放服务
        self._execute_command_in_thread(
            [sys.executable, "-u", replay],
            log_prefix=f"本地回放 ({sim_name})",
            success_message="本地播放 (replay) 命令已发送。",
            failure_message="启动本地播放失败。",
        )
        # 等待端口就绪后再打开浏览器，最多等待 ~30 秒
        ready = False
        try:
            import socket, time as _time
            deadline = _time.time() + 30
            while _time.time() < deadline:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    try:
                        if s.connect_ex(("127.0.0.1", port)) == 0:
                            ready = True
                            break
                    except Exception:
                        pass
                _time.sleep(0.5)
        except Exception:
            pass
        if ready:
            # 记录当前回放端口，避免重复启动
            try:
                self._replay_port = int(port)
            except Exception:
                self._replay_port = port
            self._open_browser(sim_name, port)
        else:
            self.log(f"回放服务未启动，端口 {port} 未开放，可能被防火墙或其他进程占用。", "error")

    def _open_browser(self, sim_name: str, port: int = 5000):
        url = f"http://127.0.0.1:{port}/?name={sim_name}"
        try: webbrowser.open_new_tab(url); self.log(f"已请求打开浏览器: {url}")
        except Exception as e: self.log(f"打开浏览器失败: {e}", "error")

    # Records & autogen
    def _start_post_chain(self):
        sim = self.last_sim_name
        if not sim: self._final_complete(); return
        self.log(f"模拟 '{sim}' 运行完成。开始自动后期处理...", "sim_end")
        queue = []
        # 严格按字段判断，防止不同类型记录被串用
        if self._check_record(os.path.join(SCRIPT_DIR, "results", "paint-records", f"{sim}.json"), required_key="绘画内容"): queue.append(self.trigger_generate_images)
        if self._check_record(os.path.join(SCRIPT_DIR, "results", "music-records", f"{sim}.json"), required_key="音乐内容"): queue.append(self.trigger_generate_music)
        if self._check_record(os.path.join(SCRIPT_DIR, "results", "quantum-computing-records", f"{sim}.json"), required_key="量子计算内容"): queue.append(self.trigger_generate_web)
        self._autogen_queue = queue; self._process_autogen()

    def _check_record(self, path: str, required_key: Optional[str] = None) -> bool:
        if not os.path.exists(path): return False
        try:
            with open(path, 'r', encoding='utf-8') as f: data = json.load(f)
            if not isinstance(data, list) or not data: return False
            if required_key:
                # 仅当至少有一条记录包含所需键时才视为有效
                for item in data:
                    if isinstance(item, dict) and str(item.get(required_key, "")).strip():
                        return True
                return False
            return True
        except Exception:
            return False

    def _process_autogen(self):
        if not getattr(self, '_autogen_queue', None): self._final_complete(); return
        func = self._autogen_queue.pop(0); func(on_done=self._process_autogen)

    def _final_complete(self):
        if self.last_sim_name:
            self.log(f"模拟 '{self.last_sim_name}' 及关联任务完成，准备压缩与打开结果...", "sim_end")
            self._compress_and_open(self.last_sim_name)

    def trigger_generate_images(self, on_done=None):
        if not self.last_sim_name: return on_done and on_done()
        script = os.path.join(SCRIPT_DIR, "liblib_starflow_txt2img_api.py")
        # 不再依赖 .py 是否存在，冻结环境会自动映射为同名 .exe
        self._execute_command_in_thread(
            [sys.executable, "-u", script, "--sim_name", self.last_sim_name],
            log_prefix=f"绘画图片生成 ({self.last_sim_name})",
            success_message=f"模拟 '{self.last_sim_name}' 的绘画图片生成任务已发送。",
            failure_message=f"为模拟 '{self.last_sim_name}' 生成绘画图片失败。",
            on_success=on_done,
        )

    def trigger_generate_music(self, on_done=None):
        if not self.last_sim_name: return on_done and on_done()
        script = os.path.join(SCRIPT_DIR, "suno-api.py")
        self._execute_command_in_thread(
            [sys.executable, "-u", script, "--sim_name", self.last_sim_name],
            log_prefix=f"背景音乐生成 ({self.last_sim_name})",
            success_message=f"模拟 '{self.last_sim_name}' 的背景音乐生成任务已发送。",
            failure_message=f"为模拟 '{self.last_sim_name}' 生成背景音乐失败。",
            on_success=on_done,
        )

    def trigger_generate_web(self, on_done=None):
        if not self.last_sim_name: return on_done and on_done()
        script = os.path.join(SCRIPT_DIR, "gemini_API.py")
        self._execute_command_in_thread(
            [sys.executable, "-u", script, "--sim_name", self.last_sim_name],
            log_prefix=f"网页模拟生成 ({self.last_sim_name})",
            success_message=f"模拟 '{self.last_sim_name}' 的网页模拟生成任务已发送。",
            failure_message=f"为模拟 '{self.last_sim_name}' 生成网页模拟失败。",
            on_success=on_done,
        )

    # 参考 copy.py：线程 + subprocess 的执行器
    def _execute_command_in_thread(self, command, log_prefix="执行", success_message=None, failure_message=None, on_success=None, on_failure=None):
        def _normalize_command_and_cwd(cmd):
            # 冻结模式下，将 "python -u xxx.py ..." 或含任意标志的命令转换为相邻或上级同名 exe 调用
            try:
                if getattr(sys, "frozen", False) and cmd and len(cmd) >= 2:
                    base_dir = os.path.dirname(sys.executable)
                    parent_dir = os.path.dirname(base_dir)
                    # 寻找第一个以 .py 结尾的参数
                    py_idx = -1
                    script_arg = None
                    for i, a in enumerate(cmd):
                        if isinstance(a, str) and a.lower().endswith(".py"):
                            py_idx = i
                            script_arg = a
                            break
                    if py_idx != -1:
                        script_name = os.path.basename(script_arg)
                        stem, _ = os.path.splitext(script_name)
                        exe_name_default = stem + ".exe"
                        mapping = {
                            "start.py": "start.exe",
                            "compress.py": "compress.exe",
                            "replay.py": "replay.exe",
                            "liblib_starflow_txt2img_api.py": "liblib_starflow_txt2img_api.exe",
                            "suno-api.py": "suno-api.exe",
                            "gemini_API.py": "gemini_API.exe",
                        }
                        mapped = mapping.get(script_name, exe_name_default)
                        exe_candidates = [
                            os.path.join(base_dir, mapped),
                            os.path.join(parent_dir, os.path.splitext(mapped)[0], mapped),
                            os.path.join(base_dir, exe_name_default),
                            os.path.join(parent_dir, stem, exe_name_default),
                        ]
                        for c in exe_candidates:
                            if os.path.exists(c):
                                # 新命令：替换为 exe，并移除 python 可执行与 .py 脚本参数
                                new_cmd = [c] + cmd[py_idx + 1:]
                                return new_cmd, os.path.dirname(c)
            except Exception:
                pass
            return cmd, SCRIPT_DIR

        normalized_command, working_dir = _normalize_command_and_cwd(command)
        try:
            self.log(f"{log_prefix}: {' '.join(normalized_command)}")
            self.log(f"工作目录: {working_dir}")
        except Exception:
            pass

        def _reader(pipe, is_err=False):
            try:
                for line in iter(pipe.readline, ''):
                    line = (line or '').replace('\ufeff', '').rstrip('\n')
                    if not line:
                        continue
                    if is_err:
                        self.log(line, 'error')
                    else:
                        self.log(line)
            except Exception as e:
                self.log(f"读取输出时出错: {e}", 'error')

        def _runner():
            env = os.environ.copy(); env['PYTHONIOENCODING'] = 'utf-8'
            # 将配置中的服务密钥、端点注入子进程，避免冻结环境下读取失败
            try:
                for k, v in (LAUNCHER_SERVICE_ENV or {}).items():
                    if k and v and not env.get(k):
                        env[k] = v
            except Exception:
                pass
            # 提示子进程正确的 results 根目录，供生成脚本查找记录（优先使用子进程工作目录）
            try:
                base_results_dir = os.path.join(working_dir or SCRIPT_DIR, 'results')
                env['GA_RESULTS_DIR'] = base_results_dir
            except Exception:
                pass
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win') else 0
            try:
                proc = subprocess.Popen(
                    normalized_command,
                    cwd=working_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    creationflags=creationflags,
                    env=env,
                )
                self.log(f"已启动进程 (PID: {proc.pid})")
                t_out = threading.Thread(target=_reader, args=(proc.stdout, False), daemon=True)
                t_err = threading.Thread(target=_reader, args=(proc.stderr, True), daemon=True)
                t_out.start(); t_err.start()
                exit_code = proc.wait()
                self.log(f"进程 (PID: {proc.pid}) 已结束，退出代码: {exit_code}")
                if exit_code == 0:
                    if success_message:
                        self.log(success_message)
                    if on_success:
                        on_success()
                else:
                    if failure_message:
                        self.log(failure_message, 'error')
                    if on_failure:
                        on_failure()
            except FileNotFoundError:
                self.log(f"错误：无法找到可执行文件 '{command[0]}'。", 'error')
                if on_failure:
                    on_failure()
            except Exception as e:
                self.log(f"错误：执行命令时发生异常: {e}", 'error')
                if on_failure:
                    on_failure()

        threading.Thread(target=_runner, daemon=True).start()

    # Process + progress
    def _run_process(self, task_id: str, label: str, program: str, args: List[str], on_success=None, on_failure=None) -> bool:
        if task_id in self.progress_rows:
            title, bar, _ = self.progress_rows[task_id]
        else:
            title, bar, container = self.step3.add_progress_row(label); self.progress_rows[task_id] = (title, bar, container)
        self.log(f"执行: {program} {' '.join(args)}")
        task = ProcessTask(self, enable_buffer=False); task.on_success = on_success; task.on_failure = on_failure
        def done(success: bool):
            bar.setRange(0, 1); bar.setValue(1)
            bar.setStyleSheet(f"QProgressBar::chunk{{background:{Palette.OK if success else Palette.ERR};}}")
            # 移除任务引用
            try:
                self._tasks.pop(task_id, None)
            except Exception:
                pass
        task.finished.connect(done)
        # 进程事件日志
        try:
            def _on_started():
                self.log(f"进程已启动: PID={int(task.proc.processId())}")
            def _on_error(err):
                self.log(f"进程启动/运行出错: {err}", "error")
            task.proc.started.connect(_on_started)
            task.proc.errorOccurred.connect(_on_error)
        except Exception:
            pass
        # 实时转发 stdout/stderr 到日志
        def _forward_stdout():
            try:
                data = task.proc.readAllStandardOutput()
                if data:
                    text = bytes(data).decode('utf-8', 'ignore')
                    if text:
                        # 直接追加，保留换行与缓冲
                        if hasattr(self.step3, 'log_view'):
                            self.step3.log_view.moveCursor(self.step3.log_view.textCursor().End)
                            self.step3.log_view.insertPlainText(text)
                        for line in text.splitlines():
                            if line.strip():
                                self.log(line)
            except Exception:
                pass
        def _forward_stderr():
            try:
                data = task.proc.readAllStandardError()
                if data:
                    text = bytes(data).decode('utf-8', 'ignore')
                    if text:
                        if hasattr(self.step3, 'log_view'):
                            self.step3.log_view.moveCursor(self.step3.log_view.textCursor().End)
                            self.step3.log_view.insertPlainText(text)
                        for line in text.splitlines():
                            if line.strip():
                                self.log(line, 'error')
            except Exception:
                pass
        task.proc.readyReadStandardOutput.connect(_forward_stdout)
        task.proc.readyReadStandardError.connect(_forward_stderr)
        # 工作目录与环境变量（对齐参考实现）
        try:
            task.proc.setWorkingDirectory(SCRIPT_DIR)
            env = QProcessEnvironment.systemEnvironment()
            env.insert("PYTHONIOENCODING", "utf-8")
            task.proc.setProcessEnvironment(env)
        except Exception:
            pass
        try:
            task.start(program, args)
            # 保持任务存活
            self._tasks[task_id] = task
            return True
        except Exception as e:
            self.log(f"进程启动失败: {e}", "error")
            # 额外诊断：打印当前工作目录与文件存在性
            try:
                self.log(f"工作目录: {SCRIPT_DIR}")
                self.log(f"Python: {sys.executable}")
                self.log(f"start.py 存在: {os.path.exists(os.path.abspath(START_PY_PATH))}")
            except Exception:
                pass
            return False

    # History
    def refresh_history(self):
        comp_dir = os.path.join(SCRIPT_DIR, "results", "compressed")
        self.step3.combo_history.clear()
        if not os.path.isdir(comp_dir): return
        sims = [d for d in os.listdir(comp_dir) if os.path.isdir(os.path.join(comp_dir, d))]
        sims.sort(reverse=True)
        self.step3.combo_history.addItems(sims)
        if self.last_sim_name and self.last_sim_name in sims: self.step3.combo_history.setCurrentText(self.last_sim_name)

    def load_selected_history(self):
        sel = self.step3.combo_history.currentText()
        if sel: self.last_sim_name = sel; self.log(f"已加载历史模拟: {sel}")

    # Ensure defaults
    def _ensure_default_personas_in_start_py(self):
        try:
            with open(START_PY_PATH, 'r', encoding='utf-8') as f: lines = f.readlines()
            personas_in_file: List[str] = []; in_block = False; head = "personas = ["; original_head = None
            for line in lines:
                s = line.strip()
                if s.startswith(head):
                    original_head = line.split('[')[0] + '['; in_block = True
                    personas_in_file += re.findall(r"['\"]([^'\"]+)['\"]", s)
                    if s.endswith(']'): in_block = False
                    continue
                if in_block:
                    personas_in_file += re.findall(r"['\"]([^'\"]+)['\"]", s)
                    if s.endswith(']'): in_block = False
            if not personas_in_file: return
            updated = list(dict.fromkeys(DEFAULT_PERSONAS_LIST + [p for p in personas_in_file if p not in DEFAULT_PERSONAS_LIST]))
            new = []; in_block = False; wrote = False; indent = "    "
            for i, line in enumerate(lines):
                s = line.strip()
                if s.startswith(head) and not wrote:
                    new.append((original_head or head) + "\n")
                    for j, n in enumerate(updated):
                        end = ',' if j < len(updated) - 1 else ''
                        new.append(f"{indent}\"{n}\"{end}\n")
                    new.append(indent.rstrip() + "]\n"); wrote = True; in_block = True; continue
                if in_block:
                    if s.endswith(']'): in_block = False
                    continue
                new.append(line)
            if wrote and ''.join(new) != ''.join(lines):
                with open(START_PY_PATH, 'w', encoding='utf-8') as f: f.writelines(new)
                self.log("已确保默认角色存在。")
        except Exception as e:
            self.log(f"确保默认角色失败: {e}", "error")


def main():
    # 先创建 QApplication，避免在 ensure_dirs 中使用 QMessageBox 时崩溃
    app = QApplication(sys.argv)
    ensure_dirs()
    QApplication.setStyle(QStyleFactory.create('Fusion'))
    w = MainWindow(); w.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

 
