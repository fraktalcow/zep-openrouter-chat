#!/usr/bin/env python3
import subprocess
import sys
import os

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "backend")

    print(f"Starting backend server with {sys.executable}...")
    try:
        # Run uvicorn as a module to ensure we rely on the current python environment
        # rather than searching PATH for a 'uvicorn' binary.
        subprocess.run(
            [sys.executable, "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
            cwd=backend_dir,
            check=True
        )
    except KeyboardInterrupt:
        pass
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
