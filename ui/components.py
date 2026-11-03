"""
VERONIKA AI - UI Components
Reusable animated UI widgets for the futuristic interface.
"""
import math
import random
import logging
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QLineEdit, QTextEdit, QProgressBar, QFrame, QGraphicsOpacityEffect,
)
from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, Property,
    Signal, QRect, QSize, QPoint, QRectF,
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient, QLinearGradient,
    QFont, QPainterPath, QConicalGradient,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Color Palette
# ═══════════════════════════════════════════════════════════════
class Colors:
    BG_DARK = QColor(18, 18, 24)
    BG_CARD = QColor(26, 26, 36)
    BG_CARD_HOVER = QColor(32, 32, 44)
    BG_INPUT = QColor(22, 22, 32)
    CYAN = QColor(0, 230, 255)
    CYAN_DIM = QColor(0, 180, 200)
    CYAN_GLOW = QColor(0, 230, 255, 60)
    BLUE = QColor(60, 120, 255)
    BLUE_GLOW = QColor(60, 120, 255, 40)
    PURPLE = QColor(140, 80, 255)
    GREEN = QColor(0, 220, 130)
    RED = QColor(255, 70, 80)
    ORANGE = QColor(255, 160, 40)
    YELLOW = QColor(255, 220, 50)
    TEXT_PRIMARY = QColor(230, 235, 245)
    TEXT_SECONDARY = QColor(140, 150, 170)
    TEXT_DIM = QColor(80, 90, 110)
    BORDER = QColor(50, 55, 70)
    BORDER_ACTIVE = QColor(0, 200, 230, 120)


# ═══════════════════════════════════════════════════════════════
# Animated AI Orb
# ═══════════════════════════════════════════════════════════════
class AIOrb(QWidget):
    """Animated central AI orb that responds to assistant state."""

    STATE_COLORS = {
        "idle": (QColor(0, 180, 220), QColor(40, 60, 140)),
        "listening": (QColor(0, 255, 180), QColor(0, 200, 255)),
        "processing": (QColor(100, 80, 255), QColor(0, 200, 255)),
        "speaking": (QColor(0, 230, 255), QColor(60, 120, 255)),
        "executing": (QColor(255, 180, 40), QColor(255, 100, 60)),
        "error": (QColor(255, 70, 80), QColor(200, 40, 60)),
        "disconnected": (QColor(80, 90, 110), QColor(50, 55, 70)),
    }

    def __init__(self, size: int = 160, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self._state = "idle"
        self._angle = 0.0
        self._pulse = 0.0
        self._wave_phase = 0.0
        self._particles = []
        self._accent: QColor | None = None
        self._accent2: QColor | None = None
        self._state_colors = dict(self.STATE_COLORS)

        # Animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(16)  # ~60fps

        # Generate particles
        for _ in range(12):
            self._particles.append({
                "angle": random.uniform(0, 360),
                "dist": random.uniform(0.6, 0.9),
                "speed": random.uniform(0.3, 1.2),
                "size": random.uniform(1.5, 3.5),
                "alpha": random.uniform(0.3, 0.8),
            })

    def set_state(self, state: str):
        """Set the orb state: idle, listening, processing, speaking, executing, error, disconnected."""
        if state in self.STATE_COLORS:
            self._state = state

    def set_accent_color(self, color: QColor, secondary: QColor = None):
        """Recolor the orb for the active persona (FRIDAY/Girlfriend/ULTRON)."""
        self._accent = QColor(color)
        self._accent2 = QColor(secondary) if secondary is not None else QColor(color).darker(160)
        self._state_colors = dict(self.STATE_COLORS)
        self._state_colors["idle"] = (self._accent, self._accent2)
        self._state_colors["listening"] = (self._accent.lighter(120), self._accent2)
        self._state_colors["speaking"] = (self._accent.lighter(115), self._accent2)
        self._state_colors["processing"] = (self._accent.darker(130), self._accent2)
        self.update()

    def _animate(self):
        self._angle += 0.8
        self._pulse += 0.04
        self._wave_phase += 0.06
        for p in self._particles:
            p["angle"] += p["speed"]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self._size / 2, self._size / 2
        base_r = self._size * 0.3
        pulse_offset = math.sin(self._pulse) * 4

        c1, c2 = self._state_colors.get(self._state, self._state_colors["idle"])

        # Outer glow
        glow_r = base_r + 20 + pulse_offset
        glow_grad = QRadialGradient(cx, cy, glow_r)
        glow_color = QColor(c1)
        glow_color.setAlpha(35)
        glow_grad.setColorAt(0, glow_color)
        glow_color2 = QColor(c1)
        glow_color2.setAlpha(0)
        glow_grad.setColorAt(1, glow_color2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow_grad))
        painter.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))

        # Main orb
        orb_r = base_r + pulse_offset * 0.5
        orb_grad = QRadialGradient(cx - orb_r * 0.3, cy - orb_r * 0.3, orb_r * 1.5)
        orb_grad.setColorAt(0, c1)
        orb_grad.setColorAt(0.6, c2)
        dark = QColor(c2)
        dark.setAlpha(200)
        orb_grad.setColorAt(1, dark)
        painter.setBrush(QBrush(orb_grad))
        painter.drawEllipse(QRectF(cx - orb_r, cy - orb_r, orb_r * 2, orb_r * 2))

        # Inner bright core
        core_r = orb_r * 0.35
        core_grad = QRadialGradient(cx, cy, core_r)
        core_color = QColor(255, 255, 255, 120)
        core_grad.setColorAt(0, core_color)
        core_grad.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2, core_r * 2))

        # Rotating ring
        ring_r = orb_r + 10
        ring_pen = QPen(QColor(c1.red(), c1.green(), c1.blue(), 80), 1.5)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._angle)
        painter.drawEllipse(QRectF(-ring_r, -ring_r, ring_r * 2, ring_r * 2))

        # Ring markers
        for i in range(4):
            angle_rad = math.radians(i * 90)
            mx = ring_r * math.cos(angle_rad)
            my = ring_r * math.sin(angle_rad)
            marker_color = QColor(c1.red(), c1.green(), c1.blue(), 200)
            painter.setBrush(QBrush(marker_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(mx - 2.5, my - 2.5, 5, 5))
        painter.restore()

        # Orbiting particles
        for p in self._particles:
            angle_rad = math.radians(p["angle"])
            dist = (base_r + 15) * p["dist"]
            px = cx + dist * math.cos(angle_rad)
            py = cy + dist * math.sin(angle_rad)
            alpha = int(p["alpha"] * 255 * (0.5 + 0.5 * math.sin(self._pulse + p["angle"])))
            pcolor = QColor(c1.red(), c1.green(), c1.blue(), max(0, min(255, alpha)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(pcolor))
            painter.drawEllipse(QRectF(px - p["size"], py - p["size"], p["size"] * 2, p["size"] * 2))

        # Audio waveform (active in listening/speaking states)
        if self._state in ("listening", "speaking"):
            self._draw_waveform(painter, cx, cy, orb_r, c1)

        painter.end()

    def _draw_waveform(self, painter, cx, cy, orb_r, color):
        """Draw audio waveform around the orb."""
        num_bars = 24
        bar_width = 2
        max_bar_height = 18

        for i in range(num_bars):
            angle = (360 / num_bars) * i + self._angle * 0.5
            angle_rad = math.radians(angle)

            # Animated bar height
            height = abs(math.sin(self._wave_phase * 3 + i * 0.5)) * max_bar_height
            height = max(3, height)

            start_dist = orb_r + 14
            end_dist = start_dist + height

            x1 = cx + start_dist * math.cos(angle_rad)
            y1 = cy + start_dist * math.sin(angle_rad)
            x2 = cx + end_dist * math.cos(angle_rad)
            y2 = cy + end_dist * math.sin(angle_rad)

            alpha = int(180 * (height / max_bar_height))
            bar_color = QColor(color.red(), color.green(), color.blue(), alpha)
            pen = QPen(bar_color, bar_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))


# ═══════════════════════════════════════════════════════════════
# State Label
# ═══════════════════════════════════════════════════════════════
class StateLabel(QLabel):
    """Displays the current assistant state with color coding."""

    STATE_LABELS = {
        "idle": ("● Ready", Colors.CYAN),
        "listening": ("◉ Listening...", Colors.GREEN),
        "processing": ("◎ Processing...", Colors.PURPLE),
        "speaking": ("◉ Speaking...", Colors.BLUE),
        "executing": ("⚡ Executing...", Colors.ORANGE),
        "error": ("✕ Error", Colors.RED),
        "disconnected": ("○ Disconnected", Colors.TEXT_DIM),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state("idle")

    def set_state(self, state: str):
        text, color = self.STATE_LABELS.get(state, ("● Unknown", Colors.TEXT_DIM))
        self.setText(text)
        self.setStyleSheet(f"""
            QLabel {{
                color: {color.name()};
                font-size: 13px;
                font-weight: 600;
                letter-spacing: 1px;
                padding: 4px 12px;
                background: rgba({color.red()}, {color.green()}, {color.blue()}, 15);
                border-radius: 10px;
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# Glass Card
# ═══════════════════════════════════════════════════════════════
class GlassCard(QFrame):
    """Glassmorphism card container."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            GlassCard {
                background-color: rgba(26, 26, 36, 200);
                border: 1px solid rgba(50, 55, 70, 150);
                border-radius: 12px;
            }
        """)


# ═══════════════════════════════════════════════════════════════
# Cyber Button
# ═══════════════════════════════════════════════════════════════
class CyberButton(QPushButton):
    """Futuristic styled button with glow effect."""

    def __init__(self, text: str, color: QColor = None, parent=None):
        super().__init__(text, parent)
        c = color or Colors.CYAN
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({c.red()}, {c.green()}, {c.blue()}, 25);
                color: {c.name()};
                border: 1px solid rgba({c.red()}, {c.green()}, {c.blue()}, 80);
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background-color: rgba({c.red()}, {c.green()}, {c.blue()}, 50);
                border: 1px solid rgba({c.red()}, {c.green()}, {c.blue()}, 160);
            }}
            QPushButton:pressed {{
                background-color: rgba({c.red()}, {c.green()}, {c.blue()}, 70);
            }}
            QPushButton:disabled {{
                background-color: rgba(40, 40, 50, 80);
                color: rgba(80, 90, 110, 150);
                border: 1px solid rgba(50, 55, 70, 80);
            }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)


# ═══════════════════════════════════════════════════════════════
# Chat Bubble
# ═══════════════════════════════════════════════════════════════
class ChatBubble(QFrame):
    """Chat message bubble for conversation display."""

    def __init__(self, text: str, is_user: bool = True, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)

        # Role label
        role = QLabel("You" if is_user else "VERONIKA")
        role.setStyleSheet(f"""
            QLabel {{
                color: {Colors.CYAN.name() if not is_user else Colors.TEXT_SECONDARY.name()};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
        """)

        # Message text
        msg = QLabel(text)
        msg.setWordWrap(True)
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY.name()};
                font-size: 13px;
                line-height: 1.5;
                padding-top: 4px;
            }}
        """)

        layout.addWidget(role)
        layout.addWidget(msg)

        if is_user:
            bg = "rgba(30, 35, 50, 180)"
            border = "rgba(60, 70, 90, 100)"
        else:
            bg = "rgba(0, 180, 220, 12)"
            border = "rgba(0, 200, 240, 40)"

        self.setStyleSheet(f"""
            ChatBubble {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 12px;
                margin: 2px {'40px 2px 0px' if is_user else '0px 2px 40px'};
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# Connection Status Indicator
# ═══════════════════════════════════════════════════════════════
class ConnectionIndicator(QWidget):
    """Shows AI provider connection status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 24)
        self._status = "disconnected"
        self._provider = "None"

    def set_status(self, connected: bool, provider: str = ""):
        self._status = "connected" if connected else "disconnected"
        self._provider = provider
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = Colors.GREEN if self._status == "connected" else Colors.RED
        # Dot
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(4, 8, 8, 8)

        # Text
        painter.setPen(QPen(Colors.TEXT_SECONDARY))
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        text = self._provider if self._provider else self._status.capitalize()
        painter.drawText(18, 17, text)
        painter.end()
