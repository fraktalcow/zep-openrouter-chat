#!/usr/bin/env python3
import os
import subprocess
import sys

def main():
    # Get absolute paths
    root_dir = os.path.abspath(os.path.dirname(__file__))
    venv_dir = os.path.join(root_dir, ".venv")
    venv_bin = os.path.join(venv_dir, "bin")
    
    # Executables
    uv_exe = os.path.join(venv_bin, "uv")
    uvicorn_exe = os.path.join(venv_bin, "uvicorn")
    
    # Prepare environment
    # This fixes the "VIRTUAL_ENV mismatch" warning by explicitly setting it
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = venv_dir
    env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
    env.pop("PYTHONHOME", None)

    print(f"Project root: {root_dir}")
    
    # Check for uv
    if not os.path.exists(uv_exe):
        print("uv not found in .venv, bootstrapping...")
        if not os.path.exists(venv_dir):
            subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)
        
        pip_exe = os.path.join(venv_bin, "pip")
        subprocess.run([pip_exe, "install", "uv"], check=True)

    # Sync dependencies
    print("Syncing dependencies...")
    try:
        subprocess.run([uv_exe, "sync"], cwd=root_dir, env=env, check=True)
    except subprocess.CalledProcessError:
        print("Failed to sync dependencies.")
        sys.exit(1)

    # Run server
    print("Starting backend server...")
    backend_dir = os.path.join(root_dir, "backend")
    
    try:
        # Run uvicorn directly from the venv
        subprocess.run(
            [uvicorn_exe, "server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
            cwd=backend_dir,
            env=env,
            check=True
        )
    except KeyboardInterrupt:
        pass
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print(f"Error: uvicorn not found at {uvicorn_exe}")
        sys.exit(1)

if __name__ == "__main__":
    main()
