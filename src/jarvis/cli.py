"""Command Line Interface for Jarvis Assistant."""

import argparse
import asyncio
import sys
from jarvis import __version__
from jarvis.config import settings
from jarvis.core.orchestrator import TaskOrchestrator
from jarvis.core.profiler import HardwareProfiler
from jarvis.core.session import SessionManager
from jarvis.logging import setup_logging
from jarvis.providers.factory import ProviderFactory
from jarvis.server.app import create_app


def start_server(host: str, port: int) -> None:
    """Launch the ASGI web and API server."""
    import uvicorn
    setup_logging(log_level=settings.log_level, log_dir=settings.logs_dir)
    print(f"=== Starting Jarvis Assistant v{__version__} ===")
    print(f"Interface: http://{host}:{port}")
    print(f"Inference Mode: {settings.inference_mode.value.upper()}")
    print(f"Autonomy Mode:  {settings.autonomy_mode.value.upper()}")
    uvicorn.run("jarvis.server.app:app", host=host, port=port, reload=False)


def show_status() -> None:
    """Print system status and hardware diagnostics."""
    prof = HardwareProfiler.profile()
    print(f"=== Jarvis Assistant v{__version__} Status ===")
    print(f"Operating System:     {prof.os_name} ({prof.architecture})")
    print(f"CPU Cores:            {prof.cpu_cores}")
    print(f"Apple Silicon:        {prof.has_apple_silicon}")
    print(f"Recommended Profile:  {prof.recommended_profile}")
    print(f"Inference Mode:       {settings.inference_mode.value}")
    print(f"Autonomy Mode:        {settings.autonomy_mode.value}")
    print(f"Local Endpoint:       {settings.local_endpoint}")
    print(f"Database Path:        {settings.db_path}")
    print(f"Logs Directory:       {settings.logs_dir}")


async def interactive_terminal_chat() -> None:
    """Interactive command-line chat session."""
    print(f"=== Jarvis Terminal Chat v{__version__} ===")
    print("Type your message and press Enter. Type 'exit' or 'quit' to end.\n")

    sm = SessionManager()
    session = sm.create_session(title="Terminal Session")
    provider = ProviderFactory.get_provider(app_settings=settings)
    orchestrator = TaskOrchestrator(session_manager=sm, provider=provider)

    while True:
        try:
            user_input = input("You > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Ending terminal chat.")
                break

            print(f"{settings.assistant_name} > ", end="", flush=True)
            async for event in orchestrator.execute(
                session_id=session.session_id,
                user_prompt=user_input,
                force_fast_path=True,
            ):
                if event.event_type == "token":
                    print(event.data.get("delta", ""), end="", flush=True)
                elif event.event_type == "error":
                    print(f"\n[Error: {event.data.get('error')}]")
            print("\n")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Jarvis Personal Assistant CLI")
    parser.add_argument("--version", action="version", version=f"Jarvis {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Start server
    start_parser = subparsers.add_parser("start", help="Start the desktop API and web interface")
    start_parser.add_argument("--host", default=settings.host, help="Bind host (default: 127.0.0.1)")
    start_parser.add_argument("--port", type=int, default=settings.port, help="Bind port (default: 8000)")

    # Status
    subparsers.add_parser("status", help="Show hardware and configuration status")

    # Interactive Chat
    subparsers.add_parser("chat", help="Start interactive terminal chat")

    args = parser.parse_args()

    if args.command == "start":
        start_server(host=args.host, port=args.port)
    elif args.command == "status":
        show_status()
    elif args.command == "chat":
        asyncio.run(interactive_terminal_chat())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
