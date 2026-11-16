import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers import admin, assistant, auth, learn, me, playground, practice, projects
from app.services.sandbox.postgres import SandboxBusy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("app")

app = FastAPI(title="SQLab — SQL Learning & Practice Platform API", version="1.0.0",
              docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)

for r in (auth.router, me.router, learn.router, practice.router, projects.router, playground.router, assistant.router, admin.router):
    app.include_router(r)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    log.info("rid=%s %s %s -> %s %dms", rid, request.method, request.url.path, response.status_code,
             (time.perf_counter() - start) * 1000)
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "ข้อมูลไม่ถูกต้อง", "errors": errors})


@app.exception_handler(SandboxBusy)
async def sandbox_busy(request: Request, exc: SandboxBusy):
    return JSONResponse(status_code=429, headers={"Retry-After": "2"},
                        content={"detail": "คุณมี query ที่กำลังทำงานพร้อมกันมากเกินไป กรุณารอสักครู่แล้วลองใหม่"})


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "เกิดข้อผิดพลาดภายในระบบ กรุณาลองใหม่อีกครั้ง"})


@app.get("/api/health")
def health():
    return {"status": "ok"}
