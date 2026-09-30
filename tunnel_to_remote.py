#!/usr/bin/env python3
import subprocess
import time
import os

HOST = "10.1.75.51"
PORT = 2245
USER = "student"
ASKPASS = "/tmp/deploy_askpass.sh"

env = os.environ.copy()
env["SSH_ASKPASS_REQUIRE"] = "force"
env["SSH_ASKPASS"] = ASKPASS

cmd = [
    "ssh",
    "-o", "StrictHostKeyChecking=no",
    "-o", "ConnectTimeout=8",
    "-o", "ServerAliveInterval=5",
    "-o", "ServerAliveCountMax=3",
    "-o", "ExitOnForwardFailure=yes",
    "-N",
    "-L", "3000:localhost:3000",
    "-L", "6000:localhost:6000",
    "-p", str(PORT),
    f"{USER}@{HOST}"
]

print("Starting SSH tunnel loop...")
while True:
    try:
        proc = subprocess.Popen(cmd, env=env)
        proc.wait()
    except Exception as e:
        print(f"Tunnel error: {e}")
    time.sleep(2)
