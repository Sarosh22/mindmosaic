"""CBT engine: structured templates + a local Gemma model via Ollama.

Design rule: the model only does two narrow jobs: (1) spot which known
distortions appear, quoting the user's own words, and (2) write one short,
gentle alternative thought. Everything else (names, explanations, Socratic
questions) comes from the fixed template library below, so the app never
free-styles as a therapist.
"""
import json
import os
import re

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("MINDMOSAIC_MODEL", "gemma3:4b")

# Fixed template library (CBT-style thought-challenging prompts).
DISTORTIONS: dict[str, dict] = {
    "catastrophizing": {
        "name": "Catastrophizing",
        "meaning": "Jumping to the worst possible outcome and treating it as likely.",
        "questions": [
            "What is the most realistic outcome, not the worst one?",
            "If the worst did happen, how could I cope with it?",
            "How likely is it, on a scale of 0-100%?",
        ],
    },
    "black_and_white": {
        "name": "Black-and-white thinking",
        "meaning": "Seeing things as all good or all bad, with no middle ground.",
        "questions": [
            "Is there a shade of grey between these two extremes?",
            "What would I say if a friend described this situation?",
            "Where on a 0-100 scale does this really sit?",
        ],
    },
    "mind_reading": {
        "name": "Mind reading",
        "meaning": "Assuming you know what others think, without evidence.",
        "questions": [
            "What evidence do I have for what they think?",
            "What other explanations could there be for their behavior?",
            "Could I check this out by asking them?",
        ],
    },
    "fortune_telling": {
        "name": "Fortune telling",
        "meaning": "Predicting that things will turn out badly as if it were certain.",
        "questions": [
            "Have my predictions like this always come true?",
            "What would I need to see to believe a better outcome is possible?",
            "What can I do now to influence the result?",
        ],
    },
    "overgeneralization": {
        "name": "Overgeneralization",
        "meaning": "Treating one event as a never-ending pattern (always, never, everyone).",
        "questions": [
            "Is it really always or never? Can I think of an exception?",
            "What is the evidence for and against this being a pattern?",
        ],
    },
    "emotional_reasoning": {
        "name": "Emotional reasoning",
        "meaning": "Believing something is true because it feels true.",
        "questions": [
            "Feelings are real, but are they facts here?",
            "What would the facts say if I set the feeling aside for a moment?",
        ],
    },
    "should_statements": {
        "name": "Should statements",
        "meaning": "Rigid rules about how you or others must behave, causing guilt or anger.",
        "questions": [
            "Who made this rule, and is it fair and flexible?",
            "Could I replace 'should' with 'I would prefer' or 'it would help if'?",
        ],
    },
    "labeling": {
        "name": "Labeling",
        "meaning": "Defining yourself or others by one mistake or trait ('I'm a failure').",
        "questions": [
            "Does one action define a whole person?",
            "What are some things about me that don't fit this label?",
        ],
    },
    "personalization": {
        "name": "Personalization",
        "meaning": "Blaming yourself for things that are not fully in your control.",
        "questions": [
            "What other factors contributed to this?",
            "How much of this is truly my responsibility?",
        ],
    },
    "discounting_positives": {
        "name": "Discounting the positive",
        "meaning": "Dismissing good things as flukes or 'not counting'.",
        "questions": [
            "What did I do that helped this go well?",
            "Would I dismiss this if it happened to someone else?",
        ],
    },
}

EMOTIONS = ["anxious", "sad", "angry", "guilty", "ashamed", "lonely", "stressed", "hopeful", "calm", "happy", "tired", "overwhelmed"]

SYSTEM_PROMPT = """You are a careful assistant inside a private journaling app. You are NOT a therapist and must not give medical advice or diagnoses.
Read the journal entry and return JSON only.

Tasks:
1. mood: integer 1-10 (1 = very low, 10 = very good) estimating the writer's mood.
2. emotions: up to 3 words chosen ONLY from this list: {emotions}
3. distortions: list the cognitive distortions clearly present (often NONE). For each give:
   - id: ONLY one of: {ids}
   - quote: a SHORT exact phrase copied from the entry that shows it
4. alternative: ONE or TWO gentle sentences offering a more balanced perspective, written in second person ("You might..."). Be warm and tentative, never say what they must do.

How to tell the distortions apart (use the exact wording as evidence):
- catastrophizing: predicts a disaster ("everything will fall apart", "it will be a catastrophe", "my life is ruined").
- fortune_telling: predicts a bad outcome without evidence ("I will fail", "it won't work out").
- overgeneralization: one event turned into a pattern, with words like always, never, everyone, nobody, every time.
- black_and_white: all-or-nothing wording ("if I don't get an A, I'm a total failure", "completely ruined", "perfect or worthless").
- labeling: calls a PERSON a negative name ("I'm a failure", "I'm stupid", "she is a selfish person"). Describing something that happened is NOT labeling.
- mind_reading: assumes what others think or feel without evidence ("she must be annoyed with me").
- should_statements: rigid rules using should, must, ought, have to.
- emotional_reasoning: treats a feeling as proof ("I feel stupid, so I am stupid").
- personalization: blames oneself for things not fully in their control.
- discounting_positives: dismisses good things ("that doesn't count", "it was just luck").

Important rules:
- Many entries only describe a stressful or upsetting EVENT, such as a bus arriving early, a forgotten item or a bad day. Being upset about something that really happened is NOT a thinking error. For these, return an empty distortions list.
- Be conservative. If you are not sure, leave the distortion out.
- The alternative thought may use ONLY facts stated in the entry. Do NOT assume or claim that the writer prepared, has succeeded before, is loved, or anything else they did not write. Do not promise that things will be fine.
- For an entry with no distortion, the alternative should simply acknowledge the feeling kindly and, if fitting, suggest one small, gentle step."""

# Extra safety net: for these distortions the quoted evidence must contain a
# typical wording cue, otherwise a small model's label is rejected.
CUE_PATTERNS: dict[str, "re.Pattern[str]"] = {
    "labeling": re.compile(
        r"\b(failure|loser|stupid|idiot|worthless|useless|pathetic|hopeless|incompetent|burden|disgusting|ugly|dumb"
        r"|bad (person|mother|father|friend|wife|husband|daughter|son))\b"
        r"|\b(i am|i'm|im|he is|he's|she is|she's|they are|you are) (a|an|such a|such an|so|totally|completely)\b",
        re.IGNORECASE,
    ),
    "overgeneralization": re.compile(
        r"\b(always|never|everyone|everybody|nobody|no one|nothing|everything|every time|all the time|constantly)\b",
        re.IGNORECASE,
    ),
    "should_statements": re.compile(
        r"\b(should|shouldn't|shouldnt|must|mustn't|have to|ought to|supposed to)\b", re.IGNORECASE
    ),
}

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "mood": {"type": "integer"},
        "emotions": {"type": "array", "items": {"type": "string"}},
        "distortions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "quote": {"type": "string"}},
                "required": ["id", "quote"],
            },
        },
        "alternative": {"type": "string"},
    },
    "required": ["mood", "emotions", "distortions", "alternative"],
}


class OllamaUnavailable(Exception):
    pass


def build_messages(text: str) -> list[dict]:
    system = SYSTEM_PROMPT.format(emotions=", ".join(EMOTIONS), ids=", ".join(DISTORTIONS))
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Journal entry:\n\"\"\"\n{text}\n\"\"\""},
    ]


def validate(raw: dict, text: str) -> dict:
    """Turn raw model output into a safe, template-backed analysis.

    - unknown distortion ids are dropped
    - quotes must really appear in the entry (stops invented evidence)
    - names/meanings/questions come from the template library, not the model
    """
    try:
        mood = max(1, min(10, int(raw.get("mood"))))
    except (TypeError, ValueError):
        mood = None
    emotions = [e.lower() for e in raw.get("emotions", []) if isinstance(e, str) and e.lower() in EMOTIONS][:3]

    seen, distortions = set(), []
    lowered = text.lower()
    for d in raw.get("distortions", []):
        if not isinstance(d, dict):
            continue
        did, quote = d.get("id"), str(d.get("quote", "")).strip()
        if did not in DISTORTIONS or did in seen:
            continue
        if not quote or quote.lower() not in lowered:
            continue
        cue = CUE_PATTERNS.get(did)
        if cue and not cue.search(quote):
            continue  # label not supported by the wording, treat as a false positive
        seen.add(did)
        t = DISTORTIONS[did]
        distortions.append({"id": did, "name": t["name"], "meaning": t["meaning"], "quote": quote, "questions": t["questions"]})

    alt = raw.get("alternative")
    alternative = alt.strip()[:500] if isinstance(alt, str) else ""
    return {"mood": mood, "emotions": emotions, "distortions": distortions, "alternative": alternative}


def analyze(text: str) -> dict:
    """Call the local Ollama server. Raises OllamaUnavailable on any failure."""
    payload = {
        "model": MODEL,
        "messages": build_messages(text),
        "stream": False,
        "format": RESPONSE_SCHEMA,
        "options": {"temperature": 0.2},
    }
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=180)
        r.raise_for_status()
        raw = json.loads(r.json()["message"]["content"])
    except (httpx.HTTPError, KeyError, json.JSONDecodeError) as e:
        raise OllamaUnavailable(str(e)) from e
    return validate(raw, text)


def health() -> dict:
    """Is Ollama running, and is the chosen model pulled?"""
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        r.raise_for_status()
        names = [m["name"] for m in r.json().get("models", [])]
    except httpx.HTTPError:
        return {"ollama": False, "model": MODEL, "model_ready": False}
    ready = any(n == MODEL or n.split(":")[0] == MODEL for n in names)
    return {"ollama": True, "model": MODEL, "model_ready": ready}