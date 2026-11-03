"""
VERONIKA AI - System Tray
System tray integration for background operation.
"""
import logging
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QRadialGradient
from PySide6.QtCore import Signal, QObject, QRectF

logger = logging.getLogger(__name__)


def create_tray_icon_pixmap() -> QPixmap:
    """Generate a simple cyan orb icon programmatically (no external files needed)."""
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Outer glow
    grad = QRadialGradient(size / 2, size / 2, size / 2)
    grad.setColorAt(0, QColor(0, 230, 255, 200))
    grad.setColorAt(0.5, QColor(40, 80, 200, 120))
    grad.setColorAt(1, QColor(0, 0, 0, 0))
    painter.setPen(QColor(0, 0, 0, 0))
    painter.setBrush(QBrush(grad))
    painter.drawEllipse(QRectF(4, 4, size - 8, size - 8))

    # Inner bright core
    core_grad = QRadialGradient(size / 2, size / 2, size * 0.2)
    core_grad.setColorAt(0, QColor(255, 255, 255, 220))
    core_grad.setColorAt(1, QColor(0, 230, 255, 0))
    painter.setBrush(QBrush(core_grad))
    painter.drawEllipse(QRectF(size * 0.35, size * 0.35, size * 0.3, size * 0.3))

    painter.end()
    return pixmap


class SystemTrayManager(QObject):
    """Manages the system tray icon and its context menu."""

    show_window = Signal()
    hide_window = Signal()
    quit_app = Signal()
    open_settings = Signal()
    new_conversation = Signal()
    toggle_voice = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray: QSystemTrayIcon | None = None

    def setup(self, parent_widget=None):
        """Initialize the system tray icon."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray not available on this system")
            return

        pixmap = create_tray_icon_pixmap()
        icon = QIcon(pixmap)

        self._tray = QSystemTrayIcon(icon, parent_widget)
        self._tray.setToolTip("VERONIKA AI — Desktop Assistant")

        # Context menu
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: rgb(24, 24, 32);
                color: rgb(230, 235, 245);
                border: 1px solid rgb(50, 55, 70);
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: rgba(0, 200, 240, 30);
            }
            QMenu::separator {
                height: 1px;
                background: rgb(50, 55, 70);
                margin: 4px 8px;
            }
        """)

        show_action = menu.addAction("Show VERONIKA")
        show_action.triggered.connect(self.show_window.emit)

        menu.addSeparator()

        new_action = menu.addAction("New Conversation")
        new_action.triggered.connect(self.new_conversation.emit)

        voice_action = menu.addAction("Voice Input")
        voice_action.triggered.connect(self.toggle_voice.emit)

        menu.addSeparator()

        settings_action = menu.addAction("Settings")
        settings_action.triggered.connect(self.open_settings.emit)

        menu.addSeparator()

        quit_action = menu.addAction("Quit VERONIKA")
        quit_action.triggered.connect(self.quit_app.emit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.show()
        logger.info("System tray icon initialized")

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window.emit()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window.emit()

    def show_notification(self, title: str, message: str, duration_ms: int = 5000):
        """Show a system notification."""
        if self._tray:
            self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, duration_ms)

    def hide(self):
        if self._tray:
            self._tray.hide()
