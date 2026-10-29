import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["MINDMOSAIC_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app import cbt  # noqa: E402
from app.main import app  # noqa: E402
from app.safety import detect_crisis  # noqa: E402

client = TestClient(app)


def test_crisis_detection():
    assert detect_crisis("Sometimes I want to die")
    assert detect_crisis("I keep thinking about suicide")
    assert detect_crisis("I don't want to be here anymore")
    assert not detect_crisis("I'm dying to see that movie")
    assert not detect_crisis("Work was stressful but fine")


def test_validate_drops_unknown_ids_and_invented_quotes():
    text = "I failed the exam, so I'll never get a job."
    raw = {
        "mood": 15,
        "emotions": ["anxious", "bogus"],
        "distortions": [
            {"id": "fortune_telling", "quote": "I'll never get a job"},
            {"id": "made_up", "quote": "I failed"},
            {"id": "labeling", "quote": "I am a loser"},  # not in text
        ],
        "alternative": "You might remember one exam is not your whole future.",
    }
    out = cbt.validate(raw, text)
    assert out["mood"] == 10
    assert out["emotions"] == ["anxious"]
    assert [d["id"] for d in out["distortions"]] == ["fortune_telling"]
    assert out["distortions"][0]["questions"]  # comes from template


def test_cue_check_rejects_false_labeling():
    # Real false positive seen in testing: a stressful event labelled as "labeling".
    text = "my van came too early and i was not ready even i didnt wear abaya and scraf"
    raw = {"mood": 3, "emotions": ["stressed"],
           "distortions": [{"id": "labeling", "quote": "didnt wear abaya and scraf"}],
           "alternative": "It's understandable to feel stressed."}
    assert cbt.validate(raw, text)["distortions"] == []


def test_cue_check_keeps_real_labeling_and_overgeneralization():
    text = "I messed up again. I'm a failure and I always mess things up."
    raw = {"mood": 2, "emotions": ["sad"],
           "distortions": [{"id": "labeling", "quote": "I'm a failure"},
                           {"id": "overgeneralization", "quote": "I always mess things up"}],
           "alternative": "You might look at one mistake at a time."}
    ids = [d["id"] for d in cbt.validate(raw, text)["distortions"]]
    assert ids == ["labeling", "overgeneralization"]


def test_cue_check_rejects_mislabel_always_as_labeling():
    text = "I have a presentation tomorrow. I always mess things up."
    raw = {"mood": 3, "emotions": ["anxious"],
           "distortions": [{"id": "labeling", "quote": "I always mess things up"}],
           "alternative": "You might focus on one step."}
    assert cbt.validate(raw, text)["distortions"] == []


def test_prompt_formats_without_error():
    msgs = cbt.build_messages("test entry")
    assert "empty distortions list" in msgs[0]["content"]
    assert "catastrophizing" in msgs[0]["content"]


def test_crisis_entry_skips_model(monkeypatch):
    def boom(_):
        raise AssertionError("model must not be called for crisis text")

    monkeypatch.setattr(cbt, "analyze", boom)
    r = client.post("/api/entries", json={"text": "I want to end my life"})
    assert r.status_code == 200
    assert r.json()["status"] == "crisis"
    assert "findahelpline" in r.json()["message"]


def test_full_flow_with_mock_model(monkeypatch):
    monkeypatch.setattr(
        cbt, "analyze",
        lambda t: cbt.validate(
            {"mood": 3, "emotions": ["anxious"],
             "distortions": [{"id": "catastrophizing", "quote": "everything will fall apart"}],
             "alternative": "You might consider other outcomes."}, t),
    )
    r = client.post("/api/entries", json={"text": "Presentation tomorrow, everything will fall apart."})
    assert r.json()["status"] == "ok"
    ins = client.get("/api/insights").json()
    assert ins["distortion_counts"][0]["name"] == "Catastrophizing"
    assert len(client.get("/api/entries").json()) >= 1


def test_model_down_still_saves(monkeypatch):
    def down(_):
        raise cbt.OllamaUnavailable("down")

    monkeypatch.setattr(cbt, "analyze", down)
    r = client.post("/api/entries", json={"text": "Plain note while offline."})
    assert r.json()["status"] == "no_model"
    assert r.json()["entry"]["id"]


def test_index_served():
    assert "MindMosaic" in client.get("/").text