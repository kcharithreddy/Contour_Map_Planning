"""
frontend_server.py — Dedicated Frontend Server for Port 3000.
Serves static Web GIS dashboard and proxies API calls to backend on port 6000.
"""
import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import urllib.request
import urllib.error

app = FastAPI(title="AI Pond Planner Frontend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:6000")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static")

# Mount /static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/health")
async def health():
    return {"status": "ok", "service": "frontend", "port": 3000}

# Proxy all other routes to backend port 6000
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_to_backend(request: Request, path: str):
    target = f"{BACKEND_URL}/{path}"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    body = await request.body()
    req = urllib.request.Request(
        target,
        data=body if body else None,
        headers={k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")},
        method=request.method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            content = resp.read()
            return Response(content=content, status_code=resp.status, media_type=resp.headers.get("Content-Type"))
    except urllib.error.HTTPError as e:
        content = e.read()
        return Response(content=content, status_code=e.code, media_type=e.headers.get("Content-Type"))
    except Exception as e:
        return Response(content=str(e), status_code=502)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
