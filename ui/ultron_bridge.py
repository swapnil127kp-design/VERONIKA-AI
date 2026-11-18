"""
VERONIKA AI - Ultron Bridge
Bridges VERONIKA's internal state to the 3D holographic orb UI over WebSocket.

Architecture:
  - Local HTTP server (default http://127.0.0.1:3000) serves ui/assets/orb.html
  - WebSocket server (default ws://127.0.0.1:8766/orb) pushes JSON state updates:
        {"type": "state", "value": "IDLE|LISTENING|THINKING|SPEAKING"}
        {"type": "mode",  "value": "FRIDAY|GIRLFRIEND|ULTRON"}
        {"type": "audio", "value": 0.0..1.0}      # mic FFT amplitude
  - Optional AudioFFT captures microphone amplitude and streams it to the orb.

The WebSocket server is implemented with the standard library only (RFC 6455
subset), so no extra dependency is required.
"""
import base64
import hashlib
import json
import logging
import os
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, List, Optional, Set

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
ORB_HTML = os.path.join(_HERE, "assets", "ultron", "index.html")

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Actual WS port, injected into orb.html at serve time (sync server owns 8765).
_ACTIVE_WS_PORT = 8766

# VERONIKA entity/persona -> orb mode names
# "companion" maps to the orb's GIRLFRIEND palette (same pink visuals) until
# the orb asset itself is relabeled; "girlfriend" stays as a deprecated alias.
_PERSONA_TO_ORB = {
    "veronika": "VERONIKA",
    "friday": "FRIDAY",
    "companion": "GIRLFRIEND",
    "girlfriend": "GIRLFRIEND",
    "ultron": "ULTRON",
    "partner": "PARTNER",
    "exam_mentor": "EXAM_MENTOR",
}

# VERONIKA UI states -> orb states
_STATE_MAP = {
    "idle": "IDLE",
    "listening": "LISTENING",
    "processing": "THINKING",
    "executing": "THINKING",
    "speaking": "SPEAKING",
    "error": "IDLE",
    "disconnected": "IDLE",
}


# ======================================================================
# Minimal RFC 6455 WebSocket server (standard library only)
# ======================================================================

class _WebSocketClient:
    """Wraps a connected socket as a WebSocket endpoint."""

    def __init__(self, sock: socket.socket, addr):
        self.sock = sock
        self.addr = addr
        self.lock = threading.Lock()
        self.closed = False

    def send_text(self, text: str) -> bool:
        """Send an unmasked text frame (server -> client)."""
        payload = text.encode("utf-8")
        header = bytearray([0x81])  # FIN + text opcode
        n = len(payload)
        if n < 126:
            header.append(n)
        elif n < (1 << 16):
            header.append(126)
            header += struct.pack("!H", n)
        else:
            header.append(127)
            header += struct.pack("!Q", n)
        try:
            with self.lock:
                if self.closed:
                    return False
                self.sock.sendall(header + payload)
            return True
        except OSError:
            self.close()
            return False

    def send_close(self):
        try:
            with self.lock:
                if not self.closed:
                    self.sock.sendall(b"\x88\x00")
        except OSError:
            pass
        self.close()

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass

    # -- frame reading (for pings / close from client) --------------

    def read_frame(self) -> Optional[tuple]:
        """Read one frame. Returns (opcode, payload) or None on error/close."""
        try:
            head = self._recv_exact(2)
            if head is None:
                return None
            opcode = head[0] & 0x0F
            masked = (head[1] & 0x80) != 0
            length = head[1] & 0x7F
            if length == 126:
                ext = self._recv_exact(2)
                if ext is None:
                    return None
                length = struct.unpack("!H", ext)[0]
            elif length == 127:
                ext = self._recv_exact(8)
                if ext is None:
                    return None
                length = struct.unpack("!Q", ext)[0]
            mask_key = self._recv_exact(4) if masked else None
            payload = self._recv_exact(length) if length else b""
            if payload is None:
                return None
            if mask_key:
                payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
            return opcode, payload
        except OSError:
            return None

    def _recv_exact(self, n: int) -> Optional[bytes]:
        buf = b""
        while len(buf) < n:
            try:
                chunk = self.sock.recv(n - len(buf))
            except OSError:
                return None
            if not chunk:
                return None
            buf += chunk
        return buf


class OrbWebSocketServer:
    """Threaded WebSocket server for the orb bridge."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8766, path: str = "/orb"):
        self.host = host
        self.port = port
        self.path = path
        self._server_sock: Optional[socket.socket] = None
        self._clients: Set[_WebSocketClient] = set()
        self._clients_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._accept_thread_active = False
        self.on_message: Optional[Callable[[str], None]] = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    def start(self):
        if self.is_running:
            return
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.host, self.port))
            srv.listen(8)
            srv.settimeout(1.0)
            self._server_sock = srv
        except OSError as e:
            logger.warning("Orb WebSocket server could not bind %s:%s: %s",
                           self.host, self.port, e)
            self._server_sock = None
            return

        global _ACTIVE_WS_PORT
        _ACTIVE_WS_PORT = self.port
        self._accept_thread_active = True
        self._thread = threading.Thread(target=self._accept_loop,
                                        name="OrbWS", daemon=True)
        self._thread.start()
        logger.info("Orb WebSocket server on ws://%s:%s%s",
                    self.host, self.port, self.path)

    def stop(self):
        self._accept_thread_active = False
        with self._clients_lock:
            clients = list(self._clients)
            self._clients.clear()
        for c in clients:
            c.send_close()
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None
        logger.info("Orb WebSocket server stopped")

    # -- internals -------------------------------------------------

    def _accept_loop(self):
        while self._accept_thread_active and self._server_sock:
            try:
                conn, addr = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle_client, args=(conn, addr),
                             daemon=True).start()

    def _handle_client(self, conn: socket.socket, addr):
        try:
            conn.settimeout(10)
            request = self._read_http_request(conn)
            if request is None:
                conn.close()
                return

            first_line = request.split(b"\r\n", 1)[0].decode("latin-1", "replace")
            parts = first_line.split()
            if len(parts) < 2 or not parts[1].startswith(self.path):
                self._respond(conn, "404 Not Found")
                conn.close()
                return

            key = None
            for line in request.split(b"\r\n")[1:]:
                if line.lower().startswith(b"sec-websocket-key:"):
                    key = line.split(b":", 1)[1].strip().decode("latin-1")
                    break
            if not key:
                self._respond(conn, "400 Bad Request")
                conn.close()
                return

            accept = base64.b64encode(
                hashlib.sha1((key + _WS_GUID).encode("latin-1")).digest()
            ).decode("latin-1")
            handshake = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            )
            conn.sendall(handshake.encode("latin-1"))
            conn.settimeout(None)

            client = _WebSocketClient(conn, addr)
            with self._clients_lock:
                self._clients.add(client)
            logger.debug("Orb client connected: %s (total=%d)",
                         addr, self.client_count)

            # Send current snapshot so a late-joining orb syncs immediately
            self._send_snapshot(client)

            # Keep the connection alive; handle pings / close / app messages
            while self._accept_thread_active and not client.closed:
                frame = client.read_frame()
                if frame is None:
                    break
                opcode, payload = frame
                if opcode == 0x8:      # close
                    client.send_close()
                    break
                elif opcode == 0x9:    # ping -> pong
                    try:
                        with client.lock:
                            client.sock.sendall(b"\x8a" + bytes([len(payload)]) + payload)
                    except OSError:
                        break
                elif opcode == 0x1 and self.on_message:  # text app message
                    try:
                        self.on_message(payload.decode("utf-8", "replace"))
                    except Exception as e:
                        logger.warning("Orb message handler error: %s", e)
        except Exception as e:
            logger.debug("Orb client handler ended: %s", e)
        finally:
            with self._clients_lock:
                self._clients.discard(
                    next((c for c in self._clients if c.sock is conn), None)
                )
            try:
                conn.close()
            except OSError:
                pass

    @staticmethod
    def _read_http_request(conn: socket.socket) -> Optional[bytes]:
        data = b""
        while b"\r\n\r\n" not in data:
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                return None
            except OSError:
                return None
            if not chunk:
                return None
            data += chunk
            if len(data) > 65536:
                return None
        return data

    @staticmethod
    def _respond(conn: socket.socket, status: str):
        body = status.encode()
        try:
            conn.sendall(
                f"HTTP/1.1 {status}\r\nContent-Length: {len(body)}\r\n\r\n".encode()
                + body
            )
        except OSError:
            pass

    def _send_snapshot(self, client: _WebSocketClient):
        """Send the last-known state/mode to a freshly connected client."""
        snapshot = getattr(self, "_last_snapshot", None)
        if snapshot:
            for payload in snapshot:
                client.send_text(payload)

    # -- broadcast -------------------------------------------------

    def broadcast(self, payload: dict) -> int:
        """Send a JSON payload to every connected orb. Returns client count."""
        text = json.dumps(payload)
        # remember last state/mode for late joiners
        if payload.get("type") in ("state", "mode"):
            snap = list(getattr(self, "_last_snapshot", []) or [])
            snap = [p for p in snap if json.loads(p).get("type") != payload.get("type")]
            snap.append(text)
            self._last_snapshot = snap[-4:]

        with self._clients_lock:
            clients = list(self._clients)
        alive = []
        for c in clients:
            if c.send_text(text):
                alive.append(c)
            else:
                c.close()
        with self._clients_lock:
            self._clients.intersection_update(alive)
        return len(alive)


# ======================================================================
# Local HTTP server for the orb page
# ======================================================================

class _OrbPageHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Map request path to filesystem path
        if self.path in ("/", "/index.html"):
            file_path = ORB_HTML
            content_type = "text/html; charset=utf-8"
        elif self.path.startswith("/_next/"):
            # Serve Next.js static assets
            ultron_dir = os.path.dirname(ORB_HTML)
            file_path = os.path.join(ultron_dir, self.path.lstrip("/"))
            # Infer content type from extension
            if file_path.endswith(".js"):
                content_type = "application/javascript"
            elif file_path.endswith(".css"):
                content_type = "text/css"
            elif file_path.endswith(".json"):
                content_type = "application/json"
            elif file_path.endswith(".wasm"):
                content_type = "application/wasm"
            else:
                content_type = "application/octet-stream"
        else:
            self.send_error(404, "Not Found")
            return

        self._serve_file(file_path, content_type)

    def _serve_file(self, path: str, content_type: str):
        if not os.path.exists(path):
            self.send_error(404, "Not found")
            return

        # For HTML files, support port injection
        if content_type.startswith("text/html"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = f.read()
                data = data.replace("__ORB_WS_PORT__", str(_ACTIVE_WS_PORT))
                data = data.encode("utf-8")
            except OSError:
                self.send_error(500, "Read error")
                return
        else:
            # Binary/text assets served as-is
            try:
                with open(path, "rb") as f:
                    data = f.read()
            except OSError:
                self.send_error(500, "Read error")
                return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        # Cache static assets longer; HTML not cached for updates
        if "_next/" in self.path and not self.path.endswith(".html"):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        logger.debug("OrbHTTP: " + fmt, *args)


class OrbHTTPServer:
    """Serves the orb HTML page on a local port."""

    def __init__(self, host: str = "127.0.0.1", port: int = 3000):
        self.host = host
        self.port = port
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def start(self):
        if self.is_running:
            return
        try:
            self._httpd = ThreadingHTTPServer((self.host, self.port), _OrbPageHandler)
        except OSError as e:
            logger.warning("Orb HTTP server could not bind %s:%s: %s",
                           self.host, self.port, e)
            self._httpd = None
            return
        self._thread = threading.Thread(target=self._httpd.serve_forever,
                                        name="OrbHTTP", daemon=True)
        self._thread.start()
        logger.info("Orb UI available at %s", self.url)

    def stop(self):
        if self._httpd:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None


# ======================================================================
# Optional microphone FFT -> orb audio reactivity
# ======================================================================

class AudioFFT:
    """Captures microphone amplitude and forwards it to the orb bridge.

    Uses PyAudio + NumPy when available; otherwise silently disabled.
    """

    def __init__(self, on_level: Callable[[float], None],
                 rate: int = 16000, chunk: int = 1024):
        self._on_level = on_level
        self._rate = rate
        self._chunk = chunk
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._pyaudio = None
        self._stream = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.is_running:
            return
        try:
            import numpy  # noqa: F401
            import pyaudio  # noqa: F401
        except ImportError:
            logger.debug("AudioFFT disabled (pyaudio/numpy not installed)")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="OrbFFT", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None

    def _run(self):
        import numpy as np
        import pyaudio

        pa = pyaudio.PyAudio()
        self._pyaudio = pa
        try:
            stream = pa.open(format=pyaudio.paInt16, channels=1, rate=self._rate,
                             input=True, frames_per_buffer=self._chunk)
            self._stream = stream
            while not self._stop.is_set():
                try:
                    raw = stream.read(self._chunk, exception_on_overflow=False)
                except OSError:
                    break
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                if samples.size == 0:
                    continue
                spectrum = np.abs(np.fft.rfft(samples))
                # Weight low/mid bins (speech band) more heavily.
                weights = np.linspace(1.0, 0.3, spectrum.size)
                level = float(np.average(spectrum * weights)) / 32768.0
                level = max(0.0, min(1.0, level * 4.0))
                try:
                    self._on_level(level)
                except Exception:
                    pass
        finally:
            try:
                if self._stream:
                    self._stream.stop_stream()
                    self._stream.close()
            except Exception:
                pass
            try:
                if self._pyaudio:
                    self._pyaudio.terminate()
            except Exception:
                pass


# ======================================================================
# Public facade
# ======================================================================

class UltronBridge:
    """High-level bridge between VERONIKA and the 3D orb UI."""

    def __init__(
        self,
        http_host: str = "127.0.0.1",
        http_port: int = 3000,
        ws_host: str = "127.0.0.1",
        ws_port: int = 8766,
        enable_audio: bool = True,
    ):
        self._http = OrbHTTPServer(http_host, http_port)
        self._ws = OrbWebSocketServer(ws_host, ws_port, path="/orb")
        self._audio = AudioFFT(on_level=self._on_audio_level) if enable_audio else None
        self._state = "IDLE"
        self._mode = "FRIDAY"
        self._min_interval = 0.05   # throttle audio frames
        self._last_audio_ts = 0.0
        self.on_greeting: Optional[Callable[[str], None]] = None

    # -- lifecycle -------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._ws.is_running or self._http.is_running

    @property
    def orb_url(self) -> str:
        return self._http.url

    def start(self):
        self._ws.start()
        self._http.start()
        if self._audio:
            self._audio.start()
        logger.info("Ultron bridge started (orb at %s)", self.orb_url)

    def stop(self):
        if self._audio:
            self._audio.stop()
        self._ws.stop()
        self._http.stop()
        logger.info("Ultron bridge stopped")

    def open_orb(self):
        """Open the orb UI in the system default browser."""
        import webbrowser
        webbrowser.open(self.orb_url)

    # -- state / mode push ----------------------------------------

    def set_state(self, state: str):
        """Map a VERONIKA UI state and push it to the orb."""
        mapped = _STATE_MAP.get(str(state).lower(), "IDLE")
        if mapped == self._state:
            return
        self._state = mapped
        self._ws.broadcast({"type": "state", "value": mapped})

    def set_mode(self, mode_or_persona: str):
        """Set the orb color mode (FRIDAY / GIRLFRIEND / ULTRON)."""
        key = str(mode_or_persona).lower()
        mapped = _PERSONA_TO_ORB.get(key, str(mode_or_persona).upper())
        if mapped not in _PERSONA_TO_ORB.values():
            mapped = "FRIDAY"
        if mapped == self._mode:
            return
        self._mode = mapped
        self._ws.broadcast({"type": "mode", "value": mapped})

    def set_persona(self, persona_manager):
        """Convenience: pull mode + color straight from a PersonaManager."""
        try:
            self.set_mode(persona_manager.mode_id)
        except Exception as e:
            logger.debug("Bridge set_mode failed: %s", e)

    def set_color(self, primary: str, secondary: str = None, label: str = None):
        """Push an exact entity/overlay palette (hex strings, e.g. '#00d2ff')."""
        if not primary:
            return
        self._ws.broadcast({
            "type": "color",
            "primary": primary,
            "secondary": secondary or primary,
            "label": label or self._mode,
        })

    def set_entity(self, entity_manager):
        """Convenience: pull entity mode label AND its exact palette + overlay."""
        try:
            self.set_mode(entity_manager.entity_id)
            if entity_manager.overlay_id:
                self.set_mode(entity_manager.overlay_id)
            self.set_color(
                entity_manager.orb_color,
                entity_manager.accent_color,
                entity_manager.display_name.upper(),
            )
        except Exception as e:
            logger.debug("Bridge set_entity failed: %s", e)

    def send_greeting(self, text: str):
        """Notify the orb of a wake greeting (used by the ULTRON wake routine)."""
        self._ws.broadcast({"type": "greeting", "value": text})
        if self.on_greeting:
            try:
                self.on_greeting(text)
            except Exception:
                pass

    @property
    def client_count(self) -> int:
        return self._ws.client_count

    # -- audio ----------------------------------------------------

    def _on_audio_level(self, level: float):
        import time
        now = time.monotonic()
        if now - self._last_audio_ts < self._min_interval:
            return
        self._last_audio_ts = now
        self._ws.broadcast({"type": "audio", "value": round(level, 3)})

    def enable_audio(self, enabled: bool):
        if enabled and self._audio is None:
            self._audio = AudioFFT(on_level=self._on_audio_level)
            self._audio.start()
        elif not enabled and self._audio is not None:
            self._audio.stop()
            self._audio = None
