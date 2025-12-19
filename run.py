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
    if not os.path.exists(uv_exe):
        import shutil
        system_uv = shutil.which("uv")
        if system_uv:
            uv_exe = system_uv

    uvicorn_exe = os.path.join(venv_bin, "uvicorn")
    
    # Prepare environment
    # This fixes the "VIRTUAL_ENV mismatch" warning by explicitly setting it
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = venv_dir
    env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
    env.pop("PYTHONHOME", None)


    # Check for venv
    if not os.path.exists(venv_dir):
        print(f"❌ Error: Virtual environment not found at {venv_dir}")
        print("Please run 'python3 -m venv .venv' and install dependencies first.")
        sys.exit(1)
        
    print(f"Project root: {root_dir}")
    
    # Sync dependencies if uv is available
    if os.path.exists(uv_exe):
        print("Syncing dependencies with uv...")
        try:
            # We don't want to capture output unless error, to let user see progress
            subprocess.run([uv_exe, "sync"], cwd=root_dir, env=env, check=True)
            print("✅ Dependencies synced.")
        except subprocess.CalledProcessError:
            print("⚠️ Warning: Failed to sync dependencies with uv.")
            print("Attempting to run server anyway...")
    else:
        print("ℹ️ uv not found, skipping dependency sync.")

    # Run server
    print("\nStarting backend server (uvicorn)...")
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
        print("\nStopping server...")
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print(f"❌ Error: uvicorn not found at {uvicorn_exe}")
        print("Ensure 'uvicorn' is installed in your virtual environment.")
        sys.exit(1)

if __name__ == "__main__":
    main()
