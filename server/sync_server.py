"""
VERONIKA AI - Cross-Platform Phone Sync Server

FastAPI REST + WebSocket server so the Android client can:
  - authenticate                POST /api/auth
  - bidirectional memory sync   GET/POST /api/memory
  - remote chat + PC actions    POST /api/chat,  WS /ws/chat
  - live realtime transport     WS /ws/live      (Gemini-Live-style control)
  - health / status             GET  /api/status

Runs on 0.0.0.0:8765 by default. Serves the Android app over the LAN.
NOTE: the reference Android client disables cleartext traffic, so for a phone
on the LAN you must either use HTTPS/WSS (put a reverse proxy with a real cert
in front) or relax the app's network_security_config for debug builds.
"""
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from app.config import config

logger = logging.getLogger(__name__)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765


# ======================================================================
# Dependency resolution (kept lazy so importing this module never fails)
# ======================================================================

class _Services:
    """Holder for the app subsystems the server needs."""

    def __init__(self):
        self.memory = None
        self.provider_manager = None
        self.action_registry = None
        self.persona_manager = None
        self.bridge = None
        self.mcp_manager = None

    def resolve(self):
        if self.memory is None:
            from memory.memory_manager import MemoryManager
            self.memory = MemoryManager()
        if self.provider_manager is None:
            from ai.provider_manager import ProviderManager
            self.provider_manager = ProviderManager()
        if self.mcp_manager is None:
            try:
                from mcp.mcp_client import build_mcp_manager
                self.mcp_manager = build_mcp_manager(start=True)
            except Exception as e:  # noqa: BLE001
                logger.warning("MCP subsystem unavailable: %s", e)
                self.mcp_manager = None
        if self.action_registry is None:
            from automation.action_registry import ActionRegistry
            self.action_registry = ActionRegistry(
                memory_manager=self.memory,
                provider_manager=self.provider_manager,
                mcp_manager=self.mcp_manager,
            )
        if self.persona_manager is None:
            from ai.persona_manager import PersonaManager
            self.persona_manager = PersonaManager.get_instance()
        return self


# ======================================================================
# FastAPI application factory
# ======================================================================

def create_app(services: _Services):
    """Build the FastAPI app bound to the given service instances."""
    from fastapi import FastAPI, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field

    from server.auth import SyncAuth

    auth = SyncAuth()
    services.resolve()
    app = FastAPI(title="VERONIKA Sync Server", version="1.0.0")
    app.state.services = services
    app.state.auth = auth
    app.state.live_sessions: Dict[str, Any] = {}

    # ── models ───────────────────────────────────────────────

    class AuthRequest(BaseModel):
        token: str
        device_name: str = "android"

    class MemoryImport(BaseModel):
        conversations: List[dict] = Field(default_factory=list)
        memories: List[dict] = Field(default_factory=list)
        reminders: List[dict] = Field(default_factory=list)
        preferences: Dict[str, str] = Field(default_factory=dict)
        mode: str = "merge"  # "merge" | "replace"

    class ChatRequest(BaseModel):
        message: str
        conversation_id: Optional[int] = None
        persona: Optional[str] = None
        execute_actions: bool = True
        stream: bool = False

    class ActionRequest(BaseModel):
        action: str
        args: Dict[str, Any] = Field(default_factory=dict)

    class ReaRequest(BaseModel):
        action: Optional[str] = None
        args: Dict[str, Any] = Field(default_factory=dict)
        goal: Optional[str] = None
        context: List[dict] = Field(default_factory=list)

    # ── auth dependency ──────────────────────────────────────

    def require_auth(authorization: str = Header(default="")):
        token = ""
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        ok, kind = auth.authenticate(token)
        if not ok:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return kind

    # ── /api/auth ────────────────────────────────────────────

    @app.post("/api/auth")
    def api_auth(req: AuthRequest):
        if auth.verify_master_token(req.token):
            access, expires = auth.issue_access_token(req.device_name)
            return {
                "ok": True,
                "access_token": access,
                "expires_at": expires,
                "server": "VERONIKA",
                "persona": services.persona_manager.mode_id,
                "server_time": time.time(),
            }
        # Also accept an already-issued access token (re-auth / refresh).
        if auth.verify_access_token(req.token):
            access, expires = auth.issue_access_token(req.device_name)
            return {"ok": True, "access_token": access, "expires_at": expires,
                    "server": "VERONIKA", "persona": services.persona_manager.mode_id,
                    "server_time": time.time()}
        raise HTTPException(status_code=401, detail="Invalid sync token")

    # ── /api/status ──────────────────────────────────────────

    @app.get("/api/status")
    def api_status(_=Depends(require_auth)):
        pm = services.provider_manager
        return {
            "ok": True,
            "server": "VERONIKA",
            "persona": services.persona_manager.mode_id,
            "providers": {k: v.value for k, v in pm.get_all_providers().items()},
            "current_provider": pm.current_provider_name,
            "routing": pm.get_last_routing(),
            "orb_clients": services.bridge.client_count if services.bridge else 0,
            "server_time": time.time(),
        }

    # ── /api/memory (bidirectional sync) ─────────────────────

    @app.get("/api/memory")
    def api_memory_export(_=Depends(require_auth)):
        """Phone pulls the full PC-side memory snapshot."""
        return {"ok": True, "data": services.memory.export_data()}

    @app.post("/api/memory")
    def api_memory_import(payload: MemoryImport, _=Depends(require_auth)):
        """Phone pushes its local memory; server merges into the PC DB."""
        mem = services.memory
        stats = {"conversations": 0, "memories": 0, "reminders": 0, "preferences": 0}

        if payload.mode == "replace" and payload.conversations:
            # Only conversations are replaced; memories/reminders still merge.
            pass  # keep merge semantics for safety; deletion stays user-driven

        for m in payload.memories:
            category = str(m.get("category", "general"))
            key = str(m.get("key", "")).strip()
            value = str(m.get("value", ""))
            if not key:
                continue
            try:
                mem.save_memory(category, key, value)
                stats["memories"] += 1
            except Exception as e:
                logger.warning("Memory merge skipped (%s/%s): %s", category, key, e)

        for r in payload.reminders:
            title = str(r.get("title", "")).strip()
            due_at = str(r.get("due_at", "")).strip()
            if not title or not due_at:
                continue
            try:
                mem.create_reminder(title, due_at, str(r.get("description", "")))
                stats["reminders"] += 1
            except Exception as e:
                logger.warning("Reminder merge skipped (%s): %s", title, e)

        for key, value in (payload.preferences or {}).items():
            try:
                mem.preferences.set(str(key), str(value))
                stats["preferences"] += 1
            except Exception as e:
                logger.warning("Preference merge skipped (%s): %s", key, e)

        for conv in payload.conversations:
            title = str(conv.get("title", "Synced Conversation"))
            messages = conv.get("messages") or []
            try:
                conv_id = mem.conversations.create_conversation(title)
                for msg in messages:
                    role = msg.get("role", "user")
                    content = str(msg.get("content", ""))
                    if role in ("user", "assistant", "system") and content:
                        mem.conversations.add_message(conv_id, role, content)
                stats["conversations"] += 1
            except Exception as e:
                logger.warning("Conversation merge skipped (%s): %s", title, e)

        return {"ok": True, "merged": stats}

    # ── /api/chat (remote chat + PC actions) ─────────────────

    @app.post("/api/chat")
    def api_chat(payload: ChatRequest, _=Depends(require_auth)):
        """Chat with VERONIKA from the phone; optionally execute PC actions."""
        mem = services.memory
        pm = services.provider_manager

        if payload.persona:
            services.persona_manager.set_mode(payload.persona)

        if payload.conversation_id:
            mem._current_conversation_id = payload.conversation_id
        if not mem.current_conversation_id:
            mem.start_new_conversation("Phone Session")

        mem.add_user_message(payload.message)
        context = mem.get_context_messages(limit=20)
        response = pm.send_message(payload.message, context_messages=context)

        if response.is_error:
            return {"ok": False, "error": response.error,
                    "conversation_id": mem.current_conversation_id}

        reply = response.content
        mem.add_assistant_message(reply)

        action = pm.parse_action(reply)
        action_result = None
        if action and payload.execute_actions:
            result = services.action_registry.execute(
                action.get("action", ""), action.get("args", {})
            )
            action_result = result.to_dict()

        return {
            "ok": True,
            "reply": reply,
            "conversation_id": mem.current_conversation_id,
            "routing": pm.get_last_routing(),
            "action": action,
            "action_result": action_result,
        }

    # ── /api/actions (direct remote automation) ──────────────

    @app.post("/api/actions")
    def api_actions(payload: ActionRequest, _=Depends(require_auth)):
        result = services.action_registry.execute(payload.action, payload.args)
        return {"ok": result.success, "result": result.to_dict()}

    # ── /api/rea (remote Reasoning, Execution & Action) ──────

    @app.post("/api/rea")
    def api_rea(payload: ReaRequest, _=Depends(require_auth)):
        """Remote REA hook: run a one-shot action or an autonomous goal."""
        from mcp.rea_bridge import ReaBridge
        rea = ReaBridge(
            provider_manager=services.provider_manager,
            action_registry=services.action_registry,
            mcp_manager=services.mcp_manager,
        )
        result = rea.handle_remote_request(payload.model_dump())
        return {"ok": bool(result.get("success")), "result": result}

    # ── /api/persona ─────────────────────────────────────────

    @app.get("/api/persona")
    def api_persona_get(_=Depends(require_auth)):
        pm = services.persona_manager
        return {"ok": True, "mode": pm.mode_id, "modes": pm.get_available_modes()}

    @app.post("/api/persona")
    def api_persona_set(body: dict, _=Depends(require_auth)):
        mode = str(body.get("mode", "")).lower()
        ok = services.persona_manager.set_mode(mode)
        if not ok:
            raise HTTPException(status_code=400, detail=f"Unknown mode: {mode}")
        if services.bridge:
            services.bridge.set_mode(mode)
        return {"ok": True, "mode": services.persona_manager.mode_id}

    # ── /ws/chat (streaming chat) ────────────────────────────

    @app.websocket("/ws/chat")
    async def ws_chat(websocket: WebSocket):
        await websocket.accept()
        token = websocket.query_params.get("token", "")
        if not auth.authenticate(token):
            await websocket.send_json({"type": "error", "content": "unauthorized"})
            await websocket.close()
            return

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    msg = {"message": raw}

                text = str(msg.get("message", "")).strip()
                if not text:
                    continue
                if msg.get("persona"):
                    services.persona_manager.set_mode(str(msg["persona"]))
                    if services.bridge:
                        services.bridge.set_mode(services.persona_manager.mode_id)

                mem = services.memory
                if not mem.current_conversation_id:
                    mem.start_new_conversation("Phone Session")
                mem.add_user_message(text)
                context = mem.get_context_messages(limit=20)

                await websocket.send_json({"type": "state", "content": "THINKING"})
                pm = services.provider_manager
                full = []
                for chunk in pm.send_message_stream(text, context_messages=context):
                    full.append(chunk)
                    await websocket.send_json({"type": "chunk", "content": chunk})

                reply = "".join(full)
                mem.add_assistant_message(reply)
                await websocket.send_json({
                    "type": "done",
                    "content": reply,
                    "conversation_id": mem.current_conversation_id,
                    "routing": pm.get_last_routing(),
                })

                action = pm.parse_action(reply)
                if action and msg.get("execute_actions", True):
                    result = services.action_registry.execute(
                        action.get("action", ""), action.get("args", {})
                    )
                    await websocket.send_json({
                        "type": "action_result",
                        "action": action,
                        "result": result.to_dict(),
                    })
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.warning("ws/chat ended: %s", e)
            try:
                await websocket.send_json({"type": "error", "content": str(e)})
            except Exception:
                pass

    # ── /ws/live (Gemini-Live-style realtime transport) ──────

    @app.websocket("/ws/live")
    async def ws_live(websocket: WebSocket):
        """Realtime control channel mirroring the Gemini Live shape.

        Client -> server:
            {"type":"config", "persona": "...", "language": "..."}
            {"type":"text",   "content": "..."}
            {"type":"audio",  "pcm": "<base64>", "rate": 16000, "chunk_ms": 20}
        Server -> client:
            {"type":"state",  "content": "LISTENING|THINKING|SPEAKING"}
            {"type":"transcript", "content": "..."}
            {"type":"text",   "content": "..."}
            {"type":"error",  "content": "..."}
        """
        await websocket.accept()
        token = websocket.query_params.get("token", "")
        if not auth.authenticate(token):
            await websocket.send_json({"type": "error", "content": "unauthorized"})
            await websocket.close()
            return

        session_id = f"live-{int(time.time()*1000)}"
        services.live_sessions[session_id] = {"started": time.time(), "audio_chunks": 0}
        try:
            await websocket.send_json({"type": "state", "content": "LISTENING"})
            while True:
                raw = await websocket.receive()
                if raw.get("type") == "websocket.disconnect":
                    break
                data = raw.get("text")
                if data is None:
                    # Binary frame: raw PCM chunk; count it for telemetry.
                    services.live_sessions[session_id]["audio_chunks"] += 1
                    continue
                try:
                    msg = json.loads(data)
                except json.JSONDecodeError:
                    continue

                mtype = msg.get("type")
                if mtype == "config":
                    if msg.get("persona"):
                        services.persona_manager.set_mode(str(msg["persona"]))
                        if services.bridge:
                            services.bridge.set_mode(services.persona_manager.mode_id)
                    await websocket.send_json({
                        "type": "config_ack",
                        "persona": services.persona_manager.mode_id,
                    })
                elif mtype == "audio":
                    services.live_sessions[session_id]["audio_chunks"] += 1
                    # Full STT pipeline lives in the Android client; the PC
                    # side only tracks levels and state for the orb.
                    await websocket.send_json({"type": "state", "content": "LISTENING"})
                elif mtype == "text":
                    text = str(msg.get("content", "")).strip()
                    if not text:
                        continue
                    mem = services.memory
                    if not mem.current_conversation_id:
                        mem.start_new_conversation("Live Session")
                    mem.add_user_message(text)
                    context = mem.get_context_messages(limit=20)

                    await websocket.send_json({"type": "state", "content": "THINKING"})
                    await websocket.send_json({"type": "transcript", "content": text})
                    resp = services.provider_manager.send_message(
                        text, context_messages=context
                    )
                    reply = resp.error if resp.is_error else resp.content
                    mem.add_assistant_message(reply)
                    await websocket.send_json({"type": "state", "content": "SPEAKING"})
                    await websocket.send_json({"type": "text", "content": reply})
                    await websocket.send_json({"type": "state", "content": "LISTENING"})
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.warning("ws/live ended: %s", e)
        finally:
            services.live_sessions.pop(session_id, None)

    return app


# ======================================================================
# Threaded uvicorn runner
# ======================================================================

class SyncServer:
    """Runs the FastAPI sync server in a background thread."""

    def __init__(
        self,
        memory_manager=None,
        provider_manager=None,
        action_registry=None,
        persona_manager=None,
        bridge=None,
        host: str = None,
        port: int = None,
    ):
        self.host = host or config.get("sync", "host", DEFAULT_HOST)
        self.port = int(port or config.get("sync", "port", DEFAULT_PORT))
        self._services = _Services()
        self._services.memory = memory_manager
        self._services.provider_manager = provider_manager
        self._services.action_registry = action_registry
        self._services.persona_manager = persona_manager
        self._services.bridge = bridge
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self._port_in_use: Optional[int] = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def base_url(self) -> str:
        port = self._port_in_use or self.port
        return f"http://{self.host}:{port}"

    @property
    def ws_url(self) -> str:
        port = self._port_in_use or self.port
        host = "127.0.0.1" if self.host in ("0.0.0.0", "::") else self.host
        return f"ws://{host}:{port}/ws/chat"

    def start(self):
        if self.is_running:
            return
        try:
            import uvicorn
            from fastapi import FastAPI  # noqa: F401
        except ImportError as e:
            logger.warning(
                "Sync server disabled (install with: pip install fastapi uvicorn): %s", e
            )
            return

        app = create_app(self._services)
        config_kwargs = {
            "host": self.host,
            "port": self.port,
            "log_level": "warning",
            "access_log": False,
            # Do not let uvicorn reconfigure logging; it conflicts with the
            # app's logging setup and raises "Unable to configure formatter".
            "log_config": None,
        }
        try:
            self._server = uvicorn.Server(uvicorn.Config(app, **config_kwargs))
        except Exception as e:
            logger.error("Could not configure sync server: %s", e)
            return

        self._thread = threading.Thread(target=self._run, name="SyncServer", daemon=True)
        self._thread.start()

        # Wait briefly for bind success/failure.
        for _ in range(50):
            if self._server.started:
                self._port_in_use = self.port
                break
            if not self._thread.is_alive():
                return
            time.sleep(0.1)

        if self.is_running:
            logger.info("Sync server listening on %s", self.base_url)
            self._print_connection_info()
        else:
            logger.warning("Sync server failed to start (port %s busy?)", self.port)

    def _run(self):
        try:
            self._server.run()
        except Exception as e:
            logger.error("Sync server crashed: %s", e)

    def stop(self):
        if self._server is not None:
            try:
                self._server.should_exit = True
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        self._server = None
        logger.info("Sync server stopped")

    def _print_connection_info(self):
        try:
            from server.auth import SyncAuth
            token = SyncAuth().master_token
        except Exception:
            token = "(unavailable)"
        lan_ip = _detect_lan_ip()
        print("\n" + "=" * 62)
        print("  VERONIKA Phone Sync Server")
        print(f"  Local  : {self.base_url}")
        print(f"  LAN    : http://{lan_ip}:{self._port_in_use or self.port}")
        print(f"  WS     : {self.ws_url}")
        print(f"  Token  : {token}")
        print("  Enter this token in the Android app's API & Connection screen.")
        print("=" * 62 + "\n")


def _detect_lan_ip() -> str:
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
