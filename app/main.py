import logging
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .db import DatabaseNotConfigured
from .limiter import limiter
from .routes import admin, public

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("hackathon")

STATIC = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="JM Vertex Hackathon 2027",
    description="Official Registration Platform & Admin Portal",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)
app.state.limiter = limiter


# ---------- Friendly field-level errors (never raw stack traces) ----------
def _friendly(err: dict) -> str:
    kind, ctx = err.get("type", ""), err.get("ctx", {}) or {}
    if kind in {"missing", "string_too_short"}:
        return "This field is required."
    if kind == "string_too_long":
        return f"Maximum {ctx.get('max_length')} characters allowed."
    if "email" in kind or "email" in err.get("msg", "").lower():
        return "Enter a valid email address."
    return err.get("msg", "Invalid value.").removeprefix("Value error, ")


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors: dict[str, str] = {}
    for e in exc.errors():
        path = ".".join(str(p) for p in e["loc"] if p not in ("body", "query"))
        errors.setdefault(path or "form", _friendly(e))
    return JSONResponse(status_code=422, content={"errors": errors})


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"message": "Too many requests. Please wait a minute and try again."}
    )


@app.exception_handler(DatabaseNotConfigured)
async def db_missing_handler(request: Request, exc: DatabaseNotConfigured):
    log.error("Database connection issue: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"message": "The database service is initializing. Please try again shortly."}
    )


@app.exception_handler(StarletteHTTPException)
async def http_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404 and not request.url.path.startswith("/api/"):
        return FileResponse(STATIC / "404.html", status_code=404)
    # If detail is dict, return dict as errors or message
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content={"errors": exc.detail})
    return JSONResponse(status_code=exc.status_code, content={"message": str(exc.detail)})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"message": "Something went wrong on our side. Please try again."}
    )


# ---------- Security Headers Middleware ----------
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-XSS-Protection", "1; mode=block")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


# ---------- Routes Registration ----------
app.include_router(public.router)
app.include_router(admin.router)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ---------- HTML Page Endpoints ----------
@app.get("/", include_in_schema=False)
def landing():
    return FileResponse(STATIC / "index.html")


@app.get("/register", include_in_schema=False)
def register_page():
    return FileResponse(STATIC / "register.html")


@app.get("/terms", include_in_schema=False)
def terms_page():
    return FileResponse(STATIC / "terms.html")


@app.get("/confirmation/{team_code}", include_in_schema=False)
def confirmation_page(team_code: str):
    return FileResponse(STATIC / "confirmation.html")


@app.get("/admin/login", include_in_schema=False)
def admin_login_page():
    return FileResponse(STATIC / "admin-login.html")


@app.get("/admin", include_in_schema=False)
def admin_dashboard_page():
    return FileResponse(STATIC / "admin.html")


# ---------- Complete SEO: Sitemap & Robots ----------
@app.get("/robots.txt", include_in_schema=False)
def robots_txt():
    content = """User-agent: *
Allow: /
Allow: /register
Allow: /terms
Allow: /download/idea-template
Disallow: /admin
Disallow: /admin/
Disallow: /api/admin/

Sitemap: /sitemap.xml
"""
    return Response(content=content, media_type="text/plain")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml(request: Request):
    base_url = str(request.base_url).rstrip("/")
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{base_url}/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>{base_url}/register</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>{base_url}/terms</loc>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>{base_url}/download/idea-template</loc>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
</urlset>"""
    return Response(content=xml_content, media_type="application/xml")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=not settings.is_production)
