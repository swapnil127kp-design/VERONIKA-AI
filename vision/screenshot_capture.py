"""
VERONIKA AI - Screenshot Capture
Captures screen content for visual analysis.
"""
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

from app.config import SCREENSHOTS_DIR

logger = logging.getLogger(__name__)


class ScreenshotCapture:
    """Captures screenshots using the mss library."""

    def capture_screen(self, monitor: int = 0) -> Optional[str]:
        """Capture the entire screen or a specific monitor.
        Returns the path to the saved screenshot.
        """
        try:
            import mss
            import mss.tools

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = SCREENSHOTS_DIR / filename

            with mss.mss() as sct:
                # Monitor 0 = all monitors combined, 1+ = individual monitors
                monitor_data = sct.monitors[monitor]
                screenshot = sct.grab(monitor_data)

                # Save using mss.tools
                mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(filepath))

            logger.info("Screenshot saved: %s", filepath)
            return str(filepath)

        except ImportError:
            logger.error("mss not installed. Install with: pip install mss")
            return None
        except Exception as e:
            logger.error("Screenshot capture failed: %s", e)
            return None

    def capture_to_bytes(self, monitor: int = 0) -> Optional[Tuple[bytes, str]]:
        """Capture screen and return as PNG bytes for AI analysis.
        Returns (png_bytes, mime_type) or None.
        """
        try:
            import mss
            import io
            from PIL import Image

            with mss.mss() as sct:
                monitor_data = sct.monitors[monitor]
                screenshot = sct.grab(monitor_data)

                # Convert to PIL Image then to PNG bytes
                img = Image.frombytes(
                    "RGB",
                    (screenshot.width, screenshot.height),
                    screenshot.rgb,
                )
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                png_bytes = buffer.getvalue()

            return (png_bytes, "image/png")

        except ImportError as e:
            logger.error("Required package not installed: %s", e)
            return None
        except Exception as e:
            logger.error("Screenshot capture to bytes failed: %s", e)
            return None

    def get_monitor_count(self) -> int:
        """Return the number of available monitors."""
        try:
            import mss
            with mss.mss() as sct:
                return len(sct.monitors) - 1  # Exclude the "all monitors" entry
        except Exception:
            return 1
