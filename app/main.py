from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .db import ROOT_DIR, init_db
from .routes import router


app = FastAPI(title="PMP Practice System")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(router)


@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
def chrome_devtools_probe() -> JSONResponse:
    return JSONResponse({})


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


app.mount("/assets", StaticFiles(directory=ROOT_DIR / "static" / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def frontend_app(path: str = "") -> FileResponse:
    return FileResponse(ROOT_DIR / "static" / "index.html")
