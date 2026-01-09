#!/usr/bin/env python3
"""
Bootstrap and run the Zep Chat backend.

Usage:
    uv run run.py

This script:
1. Starts the FastAPI server with hot-reload
2. SQLAlchemy auto-creates tables on startup
3. Syncs existing Zep sessions to PostgreSQL
"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    root_dir = Path(__file__).parent.resolve()
    backend_dir = root_dir / "backend"
    
    # Quick sanity check
    if not (backend_dir / "server.py").exists():
        print("Error: backend/server.py not found")
        sys.exit(1)
    
    print("=" * 50)
    print("  Zep OpenRouter Chat")
    print("=" * 50)
    print(f"  Backend: {backend_dir}")
    print(f"  Python:  {sys.executable}")
    print("=" * 50)
    print()
    print("Starting server on http://localhost:8000")
    print("Press Ctrl+C to stop")
    print()
    
    try:
        subprocess.run(
            [
                sys.executable, "-m", "uvicorn",
                "server:app",
                "--host", "0.0.0.0",
                "--port", "8000",
                "--reload",
            ],
            cwd=backend_dir,
            check=True,
        )
    except KeyboardInterrupt:
        print("\nShutdown complete.")
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
