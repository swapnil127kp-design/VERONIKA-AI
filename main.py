"""
VERONIKA AI Desktop — Entry Point
Launches the PySide6-based desktop assistant application.
"""
import sys
import os

# Ensure the project root is on sys.path so all packages resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.logging_config import setup_logging
from app.config import config


def run_cli():
    """Interactive CLI interface for VERONIKA AI."""
    from ai.provider_manager import ProviderManager
    from ai.persona_manager import PersonaManager
    from memory.memory_manager import MemoryManager
    from automation.action_registry import ActionRegistry

    pm = ProviderManager()
    persona = PersonaManager.get_instance()
    mem = MemoryManager()
    try:
        from mcp.mcp_client import build_mcp_manager
        mcp_manager = build_mcp_manager(start=True)
    except Exception as e:
        print(f"[MCP subsystem unavailable: {e}]")
        mcp_manager = None
    actions = ActionRegistry(memory_manager=mem, provider_manager=pm, mcp_manager=mcp_manager)

    # Optionally run the phone sync server alongside the CLI (--sync)
    sync_server = None
    if "--sync" in sys.argv:
        try:
            from server.sync_server import SyncServer
            sync_server = SyncServer(
                memory_manager=mem,
                provider_manager=pm,
                action_registry=actions,
                persona_manager=persona,
            )
            sync_server.start()
        except Exception as e:
            print(f"[Sync server unavailable: {e}]")

    print("\n" + "=" * 62)
    print("      VERONIKA AI — Desktop Assistant (Interactive CLI)")
    print(f"      Mode: {persona.persona.display_name.upper()} | "
          f"Provider: {pm.current_provider_name.upper()}")
    print("      Commands: exit | quit | help | modes | mode <name>")
    print("=" * 62 + "\n")

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    mem.start_new_conversation("CLI Session")
    while True:
        try:
            user_input = input("\nYou > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Goodbye!")
                break
            if user_input.lower() == "help":
                print("Available actions:")
                for a in actions.get_available_actions():
                    print(f" - {a}")
                print("\nPersona commands: modes | mode friday | mode girlfriend | mode ultron")
                continue
            if user_input.lower() == "modes":
                for m in persona.get_available_modes():
                    marker = "*" if m["mode_id"] == persona.mode_id else " "
                    print(f" {marker} {m['display_name']:<12} {m['description']}")
                continue
            if user_input.lower().startswith("mode "):
                requested = user_input[5:].strip().lower()
                if persona.set_mode(requested):
                    print(f"Mode switched to {persona.persona.display_name}. "
                          f"{persona.persona.wake_greeting}")
                else:
                    print(f"Unknown mode: {requested}. Use 'modes' to list options.")
                continue

            mem.add_user_message(user_input)
            context = mem.get_context_messages(limit=10)

            print("\nVERONIKA > ", end="", flush=True)
            full_resp = ""
            for chunk in pm.send_message_stream(user_input, context_messages=context):
                print(chunk, end="", flush=True)
                full_resp += chunk
            print()

            mem.add_assistant_message(full_resp)

            # Check action
            action_data = pm.parse_action(full_resp)
            if action_data:
                action_name = action_data.get("action", "")
                args = action_data.get("args", {})
                print(f"\n[Executing Action: {action_name}]")
                res = actions.execute(action_name, args)
                status_tag = "SUCCESS" if res.success else "FAILED"
                print(f"[{status_tag}: {res.message}]")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

    if sync_server:
        sync_server.stop()


def main():
    """Application entry point."""
    log_level = config.get("general", "log_level", "INFO")
    setup_logging(log_level)

    import logging
    logger = logging.getLogger(__name__)

    # If --cli flag is given, run CLI directly
    if "--cli" in sys.argv:
        logger.info("Starting VERONIKA AI in CLI mode...")
        run_cli()
        return

    # Try starting PySide6 GUI
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont
        from PySide6.QtCore import Qt

        logger.info("Starting VERONIKA AI Desktop GUI...")

        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        app = QApplication(sys.argv)
        app.setApplicationName("VERONIKA AI")
        app.setOrganizationName("VERONIKA AI Team")

        font = QFont("Segoe UI", 10)
        app.setFont(font)

        app.setStyleSheet("""
            QToolTip {
                background-color: rgb(26, 26, 36);
                color: rgb(230, 235, 245);
                border: 1px solid rgb(50, 55, 70);
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
            }
        """)

        from ui.main_window import MainWindow
        window = MainWindow()
        window.show()

        logger.info("VERONIKA AI Desktop is running")
        exit_code = app.exec()
        logger.info("VERONIKA AI Desktop exited with code %d", exit_code)
        sys.exit(exit_code)

    except ImportError as e:
        logger.warning("PySide6 not available (%s). Starting in interactive CLI mode.", e)
        print("Note: PySide6 is currently not loaded. Starting in Interactive CLI mode.")
        run_cli()


if __name__ == "__main__":
    main()
