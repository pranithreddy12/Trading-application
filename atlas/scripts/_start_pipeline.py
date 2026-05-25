"""
Start full_autonomous_cycle.py in the background using subprocess.Popen.
"""
import subprocess
import sys
import os

os.chdir(r"C:\Pranith\Freelancing_Projects\05-11-2026-Amit-ATLAS\atlas")

log_file = open("phase26_soak_pipeline.log", "w", buffering=1)
proc = subprocess.Popen(
    [sys.executable, "scripts/full_autonomous_cycle.py", "--duration-minutes", "60"],
    stdout=log_file,
    stderr=subprocess.STDOUT,
    close_fds=True,
)
with open("soak_pid.txt", "w") as f:
    f.write(str(proc.pid))
print(f"Pipeline started with PID {proc.pid}")
