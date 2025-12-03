#!/usr/bin/env python3
import subprocess
import sys
import os
import shutil

def find_uv():
    # Check PATH
    if shutil.which("uv"):
        return "uv"
    
    # Check .venv
    venv_uv = os.path.join(os.getcwd(), ".venv", "bin", "uv")
    if os.path.exists(venv_uv):
        return venv_uv
    
    return None

def ensure_uv():
    uv = find_uv()
    if uv:
        return uv
    
    print("uv not found. Bootstrapping in .venv...")
    venv_path = os.path.join(os.getcwd(), ".venv")
    if not os.path.exists(venv_path):
        subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)
    
    pip_path = os.path.join(venv_path, "bin", "pip")
    subprocess.run([pip_path, "install", "uv"], check=True)
    
    return os.path.join(venv_path, "bin", "uv")

def main():
    print("Starting OpenAgent...")

    uv = ensure_uv()
    print(f"Using uv: {uv}")

    # Ensure dependencies are up to date
    print("Syncing dependencies...")
    try:
        # uv sync creates/updates the environment
        subprocess.run([uv, "sync"], check=True)
    except subprocess.CalledProcessError:
        print("Error: Failed to sync dependencies.")
        sys.exit(1)

    # Start the server
    print("Starting backend server at http://localhost:8000...")
    try:
        # Run uvicorn using uv run
        subprocess.run(
            [uv, "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd="backend",
            check=True
        )
    except KeyboardInterrupt:
        print("\nStopping...")
    except subprocess.CalledProcessError as e:
        print(f"Server crashed with error code {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
