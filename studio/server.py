import argparse
import webbrowser
import threading
import uvicorn
from .app import create_app


def main():
    parser = argparse.ArgumentParser(description="Start Jozi Buddy's local study studio.")
    parser.add_argument("--port", type=int, choices=(8765, 8766), default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    app = create_app()
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, ws_max_size=16384)


if __name__ == "__main__":
    main()
