import os
import json
import time
import subprocess
import sys

# Base folder (where app.py and this file live)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# This file is shared with app.py
COMMAND_FILE = os.path.join(BASE_DIR, "control_command.json")

# Map modes to your real Python scripts
SCRIPTS = {
    "hand": os.path.join(BASE_DIR, "AImouse.py"),           # or "handGesture.py"
    "eye": os.path.join(BASE_DIR, "eyecontrol.py"),
    "voice": os.path.join(BASE_DIR, "voicecommand.py"),
    "keyboard": os.path.join(BASE_DIR, "AIKeyboard", "inference_classifier.py"),
    # adjust if different
}

current_mode = "none"
current_proc: subprocess.Popen | None = None


def stop_current():
    """Stop the currently running control script, if any."""
    global current_proc, current_mode

    if current_proc is not None and current_proc.poll() is None:
        print(f"Stopping current mode: {current_mode}, PID={current_proc.pid}")
        try:
            current_proc.terminate()
            try:
                current_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                current_proc.kill()
        except Exception as e:
            print("Error stopping process:", e)

    current_proc = None
    current_mode = "none"


def start_mode(mode: str):
    """Start the script for the given mode, after stopping the old one."""
    global current_proc, current_mode

    # Stop any existing mode first
    stop_current()

    if mode == "none":
        print("No mode requested (none).")
        return

    script_path = SCRIPTS.get(mode)
    if not script_path or not os.path.exists(script_path):
        print(f"Script for mode '{mode}' not found at:", script_path)
        return

    print(f"Starting mode: {mode}, script: {script_path}")
    try:
        # Use same Python interpreter as app.py
        proc = subprocess.Popen([sys.executable, script_path])
        current_proc = proc
        current_mode = mode
        print(f"Started {mode} with PID={proc.pid}")
    except Exception as e:
        print(f"Failed to start mode {mode}: {e}")


def main_loop():
    global current_mode

    print("control_service.py running. Waiting for commands...")

    last_cmd_time = 0

    while True:
        try:
            if os.path.exists(COMMAND_FILE):
                with open(COMMAND_FILE, "r", encoding="utf-8") as f:
                    cmd = json.load(f)

                # Remove file so we only process once
                os.remove(COMMAND_FILE)

                mode = cmd.get("mode", "none")
                ts = cmd.get("time", 0)

                # Only handle newer commands
                if ts > last_cmd_time:
                    last_cmd_time = ts
                    print("New command:", cmd)
                    start_mode(mode)

        except Exception as e:
            print("Error in control_service loop:", e)

        time.sleep(0.3)


if __name__ == "__main__":
    main_loop()
