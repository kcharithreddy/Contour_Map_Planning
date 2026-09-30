"""
deploy.py — Upload and start the contourmao project across the four allocated lab systems.
Usage:  python3 deploy.py [sys1|sys2|sys3|sys4|all]
"""
import os
import sys
import tarfile
import io
import time
import paramiko

# ── Systems Allocation Config ──────────────────────────────────────────────
SYSTEMS = [
    {"name": "stu12_sys1", "host": "10.1.75.51", "port": 2245, "user": "student", "password": "charithreddy9676"},
    {"name": "stu12_sys2", "host": "10.1.75.51", "port": 2246, "user": "student", "password": "charithreddy9676"},
    {"name": "stu12_sys3", "host": "10.1.75.51", "port": 2247, "user": "student", "password": "charithreddy9676"},
    {"name": "stu12_sys4", "host": "10.1.75.51", "port": 2248, "user": "student", "password": "61162343"},
]

REMOTE_DIR = "/home/student/contourmao"
LOCAL_ROOT = "/home/charithreddy/Desktop/contourmao"
INCLUDE_PATHS = [
    "app",
    "tests",
    "requirements.txt",
    "contours_1m (1).kml",
    "start_daemon.sh",
]
EXCLUDE_DIRS = {".venv", "__pycache__", ".pytest_cache", ".git"}

def build_tarball() -> bytes:
    """Pack the project into an in-memory .tar.gz, excluding .venv etc."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for item in INCLUDE_PATHS:
            src = os.path.join(LOCAL_ROOT, item)
            if not os.path.exists(src):
                continue
            if os.path.isfile(src):
                tar.add(src, arcname=item)
            else:
                for root, dirs, files in os.walk(src):
                    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                    for fname in files:
                        full = os.path.join(root, fname)
                        rel  = os.path.relpath(full, LOCAL_ROOT)
                        tar.add(full, arcname=rel)
    buf.seek(0)
    return buf.read()

def run(ssh: paramiko.SSHClient, cmd: str, check=True) -> str:
    _, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out.rstrip())
    if err: print("[stderr]", err.rstrip())
    rc = stdout.channel.recv_exit_status()
    if check and rc != 0:
        raise RuntimeError(f"Command failed (exit {rc}): {cmd}")
    return out

def deploy_to_node(node: dict, tarball: bytes):
    name = node["name"]
    host = node["host"]
    port = node["port"]
    user = node["user"]
    password = node["password"]

    print(f"\n{'='*60}")
    print(f"Deploying to {name} ({user}@{host}:{port})...")
    print(f"{'='*60}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connected = False

    for attempt in range(1, 4):
        try:
            print(f"Connecting (attempt {attempt}/3)...")
            ssh.connect(host, port=port, username=user, password=password, timeout=10, banner_timeout=10)
            connected = True
            print(f"Connected successfully to {name}!")
            break
        except Exception as e:
            print(f"  Attempt {attempt} failed: {e}")
            time.sleep(2)

    if not connected:
        print(f"⚠️  Could not connect to {name}. Ensure you are on the lab network (10.1.x.x) or VPN.")
        return False

    sftp = ssh.open_sftp()
    remote_tar = "/tmp/contourmao.tar.gz"
    print("Uploading project tarball...")
    with sftp.open(remote_tar, "wb") as f:
        f.write(tarball)

    print("Extracting files on remote host...")
    run(ssh, f"mkdir -p {REMOTE_DIR}")
    run(ssh, f"tar -xzf {remote_tar} -C {REMOTE_DIR}")
    run(ssh, f"rm -f {remote_tar}")

    print("Installing Python dependencies...")
    run(ssh, f"pip3 install --break-system-packages -r {REMOTE_DIR}/requirements.txt -q || pip install --break-system-packages -r {REMOTE_DIR}/requirements.txt -q", check=False)
    run(ssh, f"rm -rf {REMOTE_DIR}/.venv", check=False)

    print("Stopping any old supervisor daemon or uvicorn processes...")
    run(ssh, "pkill -9 -f 'uvicorn app.main' || true", check=False)
    run(ssh, "pkill -9 -f 'start_daemon.sh' || true", check=False)

    print("Launching background supervisor daemon...")
    run(ssh, f"chmod +x {REMOTE_DIR}/start_daemon.sh")
    chan = ssh.get_transport().open_session()
    chan.exec_command(f"cd {REMOTE_DIR} && ( setsid ./start_daemon.sh </dev/null >/dev/null 2>&1 & )")
    chan.close()

    print("Waiting 6 seconds for worker initialization...")
    time.sleep(6)

    print("Executing smoke test: GET /health...")
    out = run(ssh, "curl -s http://127.0.0.1:3245/health", check=False)
    print("Health response:", out)

    if '"ok"' in out:
        print(f"✅ {name} is UP and healthy on port 3245 & 3000!")
    else:
        print(f"⚠️  Health check returned unexpected response on {name}")

    sftp.close()
    ssh.close()
    return True

def main():
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    tarball = build_tarball()
    print(f"Packed project tarball: {len(tarball)/1024:.1f} KB")

    nodes_to_deploy = []
    if target == "all":
        nodes_to_deploy = SYSTEMS
    else:
        nodes_to_deploy = [n for n in SYSTEMS if target in n["name"].lower()]

    if not nodes_to_deploy:
        print(f"No matching systems found for target '{target}'. Choose from: all, sys1, sys2, sys3, sys4.")
        return

    results = {}
    for node in nodes_to_deploy:
        try:
            ok = deploy_to_node(node, tarball)
            results[node["name"]] = "SUCCESS" if ok else "FAILED"
        except Exception as e:
            print(f"Error deploying to {node['name']}: {e}")
            results[node["name"]] = f"ERROR: {e}"

    print("\n" + "="*50)
    print("DEPLOYMENT SUMMARY:")
    for k, v in results.items():
        print(f"  • {k}: {v}")
    print("="*50)

if __name__ == "__main__":
    main()
