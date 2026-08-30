"""
deploy.py  —  Upload and start the contourmao project on the remote server.
Usage:  python3 deploy.py
"""
import os
import sys
import tarfile
import io
import paramiko

# ── Connection config ──────────────────────────────────────────────────────
HOST     = "10.1.75.51"
PORT     = 2245
USER     = "student"
PASSWORD = "charithreddy9676"
REMOTE_DIR = "/home/student/contourmao"

# ── Files / dirs to include ────────────────────────────────────────────────
LOCAL_ROOT = "/home/charithreddy/Desktop/contourmao"
INCLUDE_PATHS = [
    "app",
    "tests",
    "requirements.txt",
    "contours_1m (1).kml",
]
EXCLUDE_DIRS = {".venv", "__pycache__", ".pytest_cache", ".git"}

# ──────────────────────────────────────────────────────────────────────────

def build_tarball() -> bytes:
    """Pack the project into an in-memory .tar.gz, excluding .venv etc."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for item in INCLUDE_PATHS:
            src = os.path.join(LOCAL_ROOT, item)
            if not os.path.exists(src):
                print(f"  [skip] {item} not found locally")
                continue
            if os.path.isfile(src):
                tar.add(src, arcname=item)
                print(f"  [+] {item}")
            else:
                for root, dirs, files in os.walk(src):
                    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                    for fname in files:
                        full = os.path.join(root, fname)
                        rel  = os.path.relpath(full, LOCAL_ROOT)
                        tar.add(full, arcname=rel)
                        print(f"  [+] {rel}")
    buf.seek(0)
    return buf.read()


def run(ssh: paramiko.SSHClient, cmd: str, check=True) -> str:
    """Run a command over SSH and return stdout."""
    print(f"\n$ {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out.rstrip())
    if err: print("[stderr]", err.rstrip())
    rc = stdout.channel.recv_exit_status()
    if check and rc != 0:
        raise RuntimeError(f"Command failed (exit {rc}): {cmd}")
    return out


def main():
    print("=== Building tarball ===")
    tarball = build_tarball()
    print(f"\nTarball size: {len(tarball) / 1024:.1f} KB")

    print("\n=== Connecting to remote server ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD,
                timeout=15, banner_timeout=15)
    print(f"Connected to {USER}@{HOST}:{PORT}")

    sftp = ssh.open_sftp()

    print("\n=== Uploading project ===")
    remote_tar = "/tmp/contourmao.tar.gz"
    with sftp.open(remote_tar, "wb") as f:
        f.write(tarball)
    print(f"Uploaded to {remote_tar}")

    print("\n=== Extracting on server ===")
    run(ssh, f"mkdir -p {REMOTE_DIR}")
    run(ssh, f"tar -xzf {remote_tar} -C {REMOTE_DIR}")
    run(ssh, f"rm -f {remote_tar}")

    print("\n=== Setting up Python venv ===")
    run(ssh, f"python3 -m venv {REMOTE_DIR}/.venv")
    run(ssh, f"{REMOTE_DIR}/.venv/bin/pip install --upgrade pip -q")
    run(ssh, f"{REMOTE_DIR}/.venv/bin/pip install -r {REMOTE_DIR}/requirements.txt -q")

    print("\n=== Checking disk usage ===")
    run(ssh, f"du -sh {REMOTE_DIR}/.venv", check=False)

    print("\n=== Stopping any old instance ===")
    run(ssh, "pkill -f 'uvicorn app.main' || true", check=False)

    print("\n=== Starting server ===")
    start_cmd = (
        f"cd {REMOTE_DIR} && "
        f"nohup {REMOTE_DIR}/.venv/bin/uvicorn app.main:app "
        f"--host 0.0.0.0 --port 8000 --workers 1 "
        f"> {REMOTE_DIR}/uvicorn.log 2>&1 &"
    )
    run(ssh, start_cmd)

    import time; time.sleep(2)

    print("\n=== Smoke test: GET /health ===")
    out = run(ssh, "curl -s http://127.0.0.1:8000/health", check=False)
    if '"ok"' in out:
        print("\n✅ Server is UP and healthy!")
    else:
        print("\n⚠️  Health check response unexpected — check the log:")
        run(ssh, f"tail -30 {REMOTE_DIR}/uvicorn.log", check=False)

    sftp.close()
    ssh.close()

    print(f"\n=== Done! ===")
    print(f"API is running on the server at: http://{HOST}:8000")
    print(f"Swagger UI:                       http://{HOST}:8000/docs")
    print(f"Logs:                             {REMOTE_DIR}/uvicorn.log")


if __name__ == "__main__":
    main()
