import subprocess
import sys
import os
import time

venv_python = os.path.join(".venv", "Scripts", "python.exe")

print("Starting GovStay Server and Batch Verifier at the same time...")

# Start batch verifier in the background
verifier_process = subprocess.Popen([venv_python, "batch_verifier.py"])

# Start server in the foreground
server_process = subprocess.Popen([venv_python, "server.py"])

try:
    # Wait for the server to finish (it runs indefinitely)
    server_process.wait()
except KeyboardInterrupt:
    print("\nShutting down GovStay agents...")
    server_process.terminate()
    verifier_process.terminate()
    server_process.wait()
    verifier_process.wait()
    print("Shutdown complete.")
