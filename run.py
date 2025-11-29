#!/usr/bin/env python3
"""
Zep Knowledge Graph Chat - Startup Script
Clean, optimized initialization for the full-stack application
"""

import os
import sys
import subprocess
import signal
import time
import webbrowser
from pathlib import Path

# Colors for terminal output
class C:
    G = '\033[92m'  # Green
    B = '\033[94m'  # Blue
    Y = '\033[93m'  # Yellow
    R = '\033[91m'  # Red
    E = '\033[0m'   # End

def log(emoji, msg, color=C.E):
    print(f"{emoji} {color}{msg}{C.E}")

def get_venv_python():
    """Get the venv Python executable"""
    venv = Path(".venv").absolute()
    if not venv.exists():
        log("⚠", "No venv found, creating one...", C.Y)
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    
    python_path = venv / "bin" / "python" if os.name != 'nt' else venv / "Scripts" / "python.exe"
    return str(python_path)

def ensure_deps():
    """Install dependencies if needed"""
    log("📦", "Installing dependencies...", C.B)
    
    venv_python = get_venv_python()
    
    try:
        # Install uv in venv first
        subprocess.run(
            [venv_python, "-m", "pip", "install", "-q", "uv"],
            check=True,
            capture_output=True
        )
        
        # Use venv's uv to install requirements
        result = subprocess.run(
            [venv_python, "-m", "uv", "pip", "install", "-r", "requirements.txt"],
            check=True,
            capture_output=True,
            text=True
        )
        log("✓", "Dependencies ready", C.G)
    except subprocess.CalledProcessError as e:
        log("✗", "Dependency install failed:", C.R)
        if e.stderr:
            print(e.stderr)
        sys.exit(1)

def start_server():
    """Start the FastAPI backend server"""
    log("🚀", "Starting backend server...", C.B)
    
    venv_python = get_venv_python()
    
    # Load environment variables from backend/.env
    env = os.environ.copy()
    env_file = Path("backend/.env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env[key] = value
    
    process = subprocess.Popen(
        [venv_python, "-m", "uvicorn", "server:app", 
         "--host", "0.0.0.0", "--port", "8000"],
        cwd="backend",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Wait and check for startup
    log("⏳", "Waiting for server to start...", C.Y)
    time.sleep(3)
    
    if process.poll() is not None:
        log("✗", "Server failed to start. Output:", C.R)
        output, _ = process.communicate()
        if output:
            print(output)
        sys.exit(1)
    
    log("✓", "Server running at http://localhost:8000", C.G)
    log("📖", "API docs at http://localhost:8000/docs", C.B)
    
    return process

def open_browser():
    """Open frontend in browser"""
    frontend = Path("frontend/index.html").absolute()
    if frontend.exists():
        log("🌐", "Opening frontend...", C.B)
        webbrowser.open("http://localhost:8000")
    else:
        log("⚠", "Frontend not found, skipping browser open", C.Y)

def main():
    """Main entry point"""
    os.chdir(Path(__file__).parent)
    
    log("🎯", "Zep Knowledge Graph Chat", C.G)
    print()
    
    # Setup
    ensure_deps()
    server = start_server()
    open_browser()
    
    print()
    log("✅", "Application running! Press Ctrl+C to stop", C.G)
    print()
    
    # Graceful shutdown handler
    def shutdown(sig, frame):
        print()
        log("🛑", "Shutting down...", C.Y)
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()
        log("👋", "Goodbye!", C.G)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown)
    
    # Keep running and show server output
    try:
        for line in server.stdout:
            print(line, end='')
    except KeyboardInterrupt:
        shutdown(None, None)

if __name__ == "__main__":
    main()
