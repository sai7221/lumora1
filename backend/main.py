from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routers import auth, notes

app = FastAPI(title="Lumora API")

# This same service serves the frontend too, so CORS is mostly moot in
# production (same origin). Kept open in case you test the API from
# elsewhere (e.g. Swagger UI on a different host) during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(notes.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------
# Frontend — plain HTML/CSS/JS, no build step, served directly.
# Mounted AFTER the API routes above so /api/* always wins.
# ---------------------------------------------------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")
