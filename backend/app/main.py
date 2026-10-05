import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db import connect, init_db, scalar
from .routers import analytics, assets, assistant_reports, auth

log = logging.getLogger("inspection")
_state = {"seeding": False, "ready": False}


def _ensure_data():
    from .seed import seed
    _state["seeding"] = True
    try:
        seed()
    except Exception:  # pragma: no cover
        log.exception("seeding failed")
    finally:
        _state.update(seeding=False, ready=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    conn = connect()
    empty = scalar(conn, "SELECT COUNT(*) FROM equipment") == 0
    conn.close()
    if empty and config.AUTO_SEED:
        threading.Thread(target=_ensure_data, daemon=True).start()
    else:
        _state["ready"] = True
    yield


app = FastAPI(title="سامانه هوشمند بازرسی، پیش‌بینی خوردگی و مدیریت یکپارچگی دارایی", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def timing(request: Request, call_next):
    t = time.time()
    resp = await call_next(request)
    resp.headers["X-Process-Time"] = f"{time.time() - t:.3f}"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):  # pragma: no cover
    log.exception("unhandled error")
    return JSONResponse({"detail": "خطای داخلی سرور"}, status_code=500)


@app.get("/health")
def health():
    return {"status": "ok" if _state["ready"] else "seeding", **_state}


for r in (auth.router, assets.router, analytics.router, assistant_reports.router):
    app.include_router(r)

if config.FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=config.FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(config.FRONTEND_DIR / "index.html")
