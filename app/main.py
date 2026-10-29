"""MindMosaic API. Binds to localhost only; nothing is sent to the internet."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import cbt, db
from .safety import CRISIS_MESSAGE, DISCLAIMER, detect_crisis

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="MindMosaic", docs_url=None, redoc_url=None)
db.init_db()


class EntryIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {**cbt.health(), "disclaimer": DISCLAIMER}


@app.post("/api/entries")
def create_entry(body: EntryIn):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Entry is empty")

    # 1) Safety first: crisis language skips the model entirely.
    if detect_crisis(text):
        entry = db.add_entry(text, None, [], None, crisis=True)
        return {"entry": entry, "status": "crisis", "message": CRISIS_MESSAGE}

    # 2) CBT analysis with the local model; entry is saved even if it fails.
    try:
        analysis = cbt.analyze(text)
    except cbt.OllamaUnavailable:
        entry = db.add_entry(text, None, [], None, crisis=False)
        return {
            "entry": entry,
            "status": "no_model",
            "message": "Saved, but the local AI isn't reachable. Start Ollama and pull the model to get reflections.",
        }
    entry = db.add_entry(text, analysis["mood"], analysis["emotions"], analysis, crisis=False)
    return {"entry": entry, "status": "ok", "disclaimer": DISCLAIMER}


@app.get("/api/entries")
def get_entries():
    return db.list_entries()


@app.delete("/api/entries/{entry_id}")
def remove_entry(entry_id: int):
    if not db.delete_entry(entry_id):
        raise HTTPException(404, "Not found")
    return {"ok": True}


@app.delete("/api/entries")
def remove_all():
    db.delete_all()
    return {"ok": True}


@app.get("/api/insights")
def get_insights():
    return db.insights()


@app.get("/api/export")
def export():
    return JSONResponse(
        db.list_entries(limit=100000),
        headers={"Content-Disposition": "attachment; filename=mindmosaic-export.json"},
    )


app.mount("/static", StaticFiles(directory=STATIC), name="static")