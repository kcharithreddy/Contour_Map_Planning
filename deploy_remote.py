import subprocess
import time
import socket
import os
import sys

HOST = os.environ.get("REMOTE_HOST", "10.1.75.51")
PORT = int(os.environ.get("REMOTE_PORT", 2245))
USER = os.environ.get("REMOTE_USER", "student")
PASSWORD = os.environ.get("REMOTE_PASSWORD", "charithreddy9676")
REMOTE_DIR = "/home/student/contourmao"
LOCAL_TAR = "/tmp/contourmao_code.tar.gz"

askpass_path = "/tmp/deploy_askpass.sh"
with open(askpass_path, "w") as f:
    f.write(f"#!/bin/bash\necho '{PASSWORD}'\n")
os.chmod(askpass_path, 0o755)

env = os.environ.copy()
env["SSH_ASKPASS_REQUIRE"] = "force"
env["SSH_ASKPASS"] = askpass_path

def ssh_cmd(cmd, timeout=15):
    full_cmd = [
        "setsid", "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=8",
        "-o", "ServerAliveInterval=3",
        "-o", "ServerAliveCountMax=2",
        "-p", str(PORT),
        f"{USER}@{HOST}",
        cmd
    ]
    return subprocess.run(full_cmd, env=env, capture_output=True, text=True, timeout=timeout)

def run_step_with_retry(name, action_fn, max_tries=15):
    for i in range(1, max_tries + 1):
        print(f"[{name}] Attempt {i}/{max_tries}...")
        try:
            success, output = action_fn()
            if success:
                print(f"[{name}] SUCCESS!")
                return output
            else:
                print(f"  Failed: {output}. Retrying in 2s...")
        except Exception as e:
            print(f"  Exception: {e}. Retrying in 2s...")
        time.sleep(2)
    raise RuntimeError(f"Step '{name}' failed after {max_tries} attempts.")

# Step 1: Connectivity & mkdir
def step_mkdir():
    res = ssh_cmd(f"mkdir -p {REMOTE_DIR}")
    return res.returncode == 0, res.stderr or res.stdout

run_step_with_retry("Create Remote Directory", step_mkdir)

# Step 2: Upload tarball
with open(LOCAL_TAR, "rb") as f:
    tar_data = f.read()

def step_upload():
    pipe_cmd = [
        "setsid", "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=8",
        "-p", str(PORT),
        f"{USER}@{HOST}",
        f"tar -xzf - -C {REMOTE_DIR}"
    ]
    p = subprocess.Popen(pipe_cmd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate(input=tar_data, timeout=30)
    return p.returncode == 0, stderr.decode()

run_step_with_retry("Upload Code Tarball", step_upload)

# Step 3: Stop old processes and start daemon
def step_start():
    cmd = (
        f"cd {REMOTE_DIR} && "
        "fuser -k 3000/tcp 2>/dev/null || true; "
        "fuser -k 6000/tcp 2>/dev/null || true; "
        "chmod +x start_remote_daemon.sh; "
        "setsid nohup ./start_remote_daemon.sh > daemon_remote.log 2>&1 & "
        "sleep 4; "
        "ps aux | grep -E 'start_remote_daemon|uvicorn' | grep -v grep"
    )
    res = ssh_cmd(cmd, timeout=25)
    return res.returncode == 0, res.stdout

out = run_step_with_retry("Start Daemon on Remote", step_start)
print("Running processes:")
print(out)

# Step 4: Verify health
def step_verify():
    cmd = (
        "curl -s -m 3 http://localhost:6000/health && echo '' && "
        "curl -s -m 3 http://localhost:3000/health && echo '' && "
        "curl -s -m 3 http://localhost:3000/api/dataset-bounds"
    )
    res = ssh_cmd(cmd, timeout=15)
    if res.returncode == 0 and '"status":"ok"' in res.stdout:
        return True, res.stdout
    return False, res.stderr or res.stdout

health_out = run_step_with_retry("Verify Health on Ports 3000 and 6000", step_verify)
print("\n=== VERIFICATION RESULTS ===")
print(health_out)
print("\n🎉 REMOTE DEPLOYMENT SUCCESSFUL!")
