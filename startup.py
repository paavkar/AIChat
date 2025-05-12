#!/usr/bin/env python
import subprocess
import signal
import sys

def start_processes():
    # Start the Discord bot
    discord_process = subprocess.Popen([sys.executable, "DiscordApp.py"])

    # Start the Twitch bot
    twitch_process = subprocess.Popen([sys.executable, "TwitchChat.py"])

    # Start the Django web UI with Uvicorn
    uvicorn_process = subprocess.Popen([
        "uvicorn", "aichat.asgi:application",
        "--host", "0.0.0.0",
        "--port", "8000"
    ],
    cwd="aichat")

    return [discord_process, twitch_process, uvicorn_process]

def shutdown_processes(processes):
    print("\nShutting down all processes...")
    for process in processes:
        process.terminate()
    # Optionally, wait a few seconds and then force kill any remaining processes.
    for process in processes:
        process.wait()

def main():
    processes = start_processes()

    # Handle termination signals so that we can shutdown all processes gracefully.
    def signal_handler(sig, frame):
        shutdown_processes(processes)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Wait indefinitely for any process to exit.
    try:
        for process in processes:
            process.wait()
    except KeyboardInterrupt:
        shutdown_processes(processes)

if __name__ == "__main__":
    main()