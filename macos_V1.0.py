import sys
import os
import json
import numpy as np
import random
import warnings
import gc

# 屏蔽所有警告
warnings.filterwarnings("ignore")

# 修复 imageio 版本检查问题
import importlib
import importlib.metadata
original_get_version = importlib.metadata.version
def mock_get_version(name):
    if name == "imageio":
        return "2.37.3"
    return original_get_version(name)
importlib.metadata.version = mock_get_version

import imageio
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QMenu,
                             QDialog, QVBoxLayout, QHBoxLayout,
                             QSpinBox, QPushButton)
from PyQt6.QtGui import QPixmap, QImage, QFont, QCursor
from PyQt6.QtCore import Qt, QTimer, QPoint

# ===================== 跨平台资源路径（100% 安全） =====================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    relative_path = relative_path.replace("\\", "/")
    return os.path.join(base_path, relative_path)

class PetWindow(QWidget):
    FIXED_SIZE = 180
    NORMAL_STATES = ["sleep", "walk", "play"]
    BREAK_STATE = "break"

    ENCOURAGE_TEXT = [
        "很棒，坚持住～",
        "辛苦啦，休息一下",
        "完成就是胜利 ✨",
        "你超厉害的！",
        "继续保持状态哦"
    ]

    def __init__(self):
        super().__init__()
        self.config = self.load_config()

        self.videos = {}
        self.current_video_name = None

        self.load_single_video("sleep", force=True)
        self.init_window()
        self.init_video_playback()
        self.init_pomodoro()
        self.init_bubble()

        self.dragging = False
        self.drag_start_pos = None
        self.play_video("sleep")

    # ===================== 气泡提示 =====================
    def init_bubble(self):
        self.bubble = QLabel(self)
        self.bubble.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.ToolTip)
        self.bubble.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.bubble.setStyleSheet("""
            QLabel{
                background-color: rgba(255,255,255,0.95);
                color: #3488eb;
                font-weight: bold;
                border-radius: 15px;
                padding: 6px 12px;
                border: 1px solid #ddd;
            }
        """)
        self.bubble.setFont(QFont("Arial", 10))  # 跨平台字体
        self.bubble.hide()

        self.bubble_close_timer = QTimer()
        self.bubble_close_timer.setSingleShot(True)
        self.bubble_close_timer.timeout.connect(self.bubble.hide)

    def pop_bubble_tip(self):
        try:
            tip_text = random.choice(self.ENCOURAGE_TEXT)
            self.bubble.setText(tip_text)
            self.bubble.adjustSize()
            x = self.x() + (self.width() - self.bubble.width()) // 2
            y = self.y() - self.bubble.height() - 15
            self.bubble.move(x, y)
            self.bubble.show()
            self.bubble_close_timer.start(8000)
        except:
            pass

    # ===================== 视频加载（绝对不崩溃） =====================
    def load_single_video(self, name, force=False):
        if not force:
            self.unload_all_videos()

        video_path = resource_path(f"{name}.mp4")
        if not os.path.exists(video_path):
            video_path = resource_path(f"{name}.mov")

        try:
            reader = imageio.get_reader(video_path, 'ffmpeg')
            frames = list(reader.iter_data())
            w, h = reader.get_meta_data()['size']
            fps = reader.get_meta_data().get('fps', 30)

            self.videos[name] = {
                "frames": frames,
                "w": w, "h": h,
                "fps": fps,
                "total": len(frames),
                "idx": 0
            }
            self.current_video_name = name
        except:
            self.videos[name] = {
                "frames": [], "w": 180, "h": 180,
                "fps": 30, "total": 0, "idx": 0
            }

    def unload_all_videos(self):
        try:
            for key in list(self.videos.keys()):
                if key != "sleep" and "frames" in self.videos[key]:
                    del self.videos[key]["frames"]
            gc.collect()
        except:
            pass

    # ===================== 窗口（Mac 透明完美版） =====================
    def init_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

        # ========== Mac 专用修复 ==========
        if sys.platform == "darwin":
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self.resize(self.FIXED_SIZE, self.FIXED_SIZE)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.width() - self.width() - 30, screen.height() - self.height() - 80)

        self.label = QLabel(self)
        self.label.setGeometry(0, 0, self.FIXED_SIZE, self.FIXED_SIZE)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.label.setStyleSheet("background: transparent;")

    # ===================== 视频播放 =====================
    def init_video_playback(self):
        self.video_timer = QTimer()
        self.video_timer.timeout.connect(self.next_frame)
        self.video_timer.stop()

    def play_video(self, name):
        try:
            if self.current_video_name == name and self.video_timer.isActive():
                return
            self.video_timer.stop()
            self.load_single_video(name)
            v = self.videos.get(name)
            if not v or v["total"] == 0:
                return
            v["idx"] = 0
            self.render_frame(v["frames"][0])
            self.video_timer.start(int(1000 / v["fps"]))
        except:
            pass

    def next_frame(self):
        try:
            v = self.videos.get(self.current_video_name)
            if not v or v["total"] == 0:
                self.video_timer.stop()
                return
            self.render_frame(v["frames"][v["idx"]])
            v["idx"] = (v["idx"] + 1) % v["total"]
        except:
            self.video_timer.stop()

    def render_frame(self, frame):
        try:
            h, w, ch = frame.shape
            if ch == 3:
                mask = (frame[:, :, 0] < 20) & (frame[:, :, 1] < 20) & (frame[:, :, 2] < 20)
                alpha = np.where(mask, 0, 255).astype(np.uint8)
                frame = np.dstack((frame, alpha))

            bytes_per_line = 4 * w
            qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGBA8888)
            pix = QPixmap.fromImage(qimg).scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.label.setPixmap(pix)
        except:
            pass

    # ===================== 拖动 + 菜单（Mac 完美） =====================
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_start_pos = event.globalPosition().toPoint() - self.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.show_click_menu()
        event.accept()

    def show_click_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(255,255,255,0.95);
                border-radius: 12px; padding:6px;
            }
            QMenu::item {
                padding:7px 14px; border-radius:8px; font-size:14px; color:#333;
            }
            QMenu::item:selected { background:#72B9E6; color:white; }
        """)
        menu.addAction("😴 睡觉").triggered.connect(lambda: self.play_video("sleep"))
        menu.addAction("🚶 走路").triggered.connect(lambda: self.play_video("walk"))
        menu.addAction("🎾 玩耍").triggered.connect(lambda: self.play_video("play"))
        menu.exec(QCursor.pos())  # 跨平台不偏移

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background:rgba(255,255,255,0.95);
                border-radius:12px; padding:6px;
            }
            QMenu::item {
                padding:7px 14px; border-radius:8px; font-size:14px; color:#333;
            }
            QMenu::item:selected { background:#72B9E6; color:white; }
        """)
        menu.addAction("▶ 开始专注").triggered.connect(self.start_pomodoro)
        menu.addAction("⏸ 暂停").triggered.connect(self.pause_pomodoro)
        menu.addAction("🔄 重置").triggered.connect(self.reset_pomodoro)
        menu.addAction("⚙️ 设置").triggered.connect(self.show_settings_dialog)
        menu.addSeparator()
        menu.addAction("😴 睡觉").triggered.connect(lambda: self.play_video("sleep"))
        menu.addAction("🚶 走路").triggered.connect(lambda: self.play_video("walk"))
        menu.addAction("🎾 玩耍").triggered.connect(lambda: self.play_video("play"))
        menu.addSeparator()
        menu.addAction("❌ 退出").triggered.connect(self.safe_quit)
        menu.exec(event.globalPos())

    # ===================== 安全退出（无残留） =====================
    def safe_quit(self):
        try:
            self.video_timer.stop()
            self.pomo_timer.stop()
            self.bubble_close_timer.stop()
            gc.collect()
        except:
            pass
        QApplication.quit()

    # ===================== 番茄钟 =====================
    def init_pomodoro(self):
        self.pomo_timer = QTimer()
        self.pomo_timer.timeout.connect(self.update_pomo)
        self.remaining = self.config['focus'] * 60
        self.running = False
        self.is_focus = True

        self.time_label = QLabel(self)
        self.time_label.setStyleSheet("color:white; background:rgba(0,0,0,0.5); padding:3px 6px; border-radius:3px; font-size:12px;")
        self.time_label.move(6, 6)
        self.update_time_text()

    def update_pomo(self):
        try:
            if self.remaining > 0:
                self.remaining -= 1
                self.update_time_text()
                return

            self.pomo_timer.stop()
            self.running = False
            self.pop_bubble_tip()

            if self.is_focus:
                self.play_video(self.BREAK_STATE)
                self.remaining = self.config['break'] * 60
                self.is_focus = False
            else:
                self.play_video("sleep")
                self.remaining = self.config['focus'] * 60
                self.is_focus = True

            self.update_time_text()
            self.start_pomodoro()
        except:
            pass

    def update_time_text(self):
        m, s = divmod(self.remaining, 60)
        self.time_label.setText(f"{m:02d}:{s:02d}")

    def start_pomodoro(self):
        if not self.running:
            self.pomo_timer.start(1000)
            self.running = True

    def pause_pomodoro(self):
        if self.running:
            self.pomo_timer.stop()
            self.running = False

    def reset_pomodoro(self):
        self.pomo_timer.stop()
        self.running = False
        self.is_focus = True
        self.remaining = self.config['focus'] * 60
        self.update_time_text()
        self.play_video("sleep")

    # ===================== 设置 =====================
    def show_settings_dialog(self):
        d = QDialog(self)
        d.setWindowTitle("番茄钟设置")
        d.setFixedSize(260, 140)
        layout = QVBoxLayout(d)

        f_layout = QHBoxLayout()
        f_layout.addWidget(QLabel("专注(分):"))
        f_spin = QSpinBox()
        f_spin.setRange(1, 300)
        f_spin.setValue(self.config['focus'])
        f_layout.addWidget(f_spin)
        layout.addLayout(f_layout)

        b_layout = QHBoxLayout()
        b_layout.addWidget(QLabel("休息(分):"))
        b_spin = QSpinBox()
        b_spin.setRange(1, 30)
        b_spin.setValue(self.config['break'])
        b_layout.addWidget(b_spin)
        layout.addLayout(b_layout)

        save = QPushButton("保存")
        save.clicked.connect(lambda: self.save_config_val(f_spin.value(), b_spin.value(), d))
        layout.addWidget(save)
        d.exec()

    def save_config_val(self, f, b, d):
        self.config['focus'] = f
        self.config['break'] = b
        self.save_config()
        self.reset_pomodoro()
        d.close()

    # ===================== 配置文件（Mac 权限 100% 可用） =====================
    def get_config_path(self):
        if sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support")
        else:
            base = os.path.expanduser("~")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "pet_config.json")

    def load_config(self):
        default = {"focus": 25, "break": 5}
        try:
            path = self.get_config_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                return {k: cfg.get(k, default[k]) for k in default}
        except:
            pass
        return default

    def save_config(self):
        try:
            path = self.get_config_path()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except:
            pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = PetWindow()
    pet.show()
    sys.exit(app.exec())