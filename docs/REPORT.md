# MindMosaic: Project Report

**Hackathon:** Hack Day, 29 October 2026
**Project:** MindMosaic, a private CBT journal
**Author:** Sarosh Waqar
**Repository:** https://github.com/Sarosh22/mindmosaic
**License:** MIT

---

## 1. Summary
MindMosaic is a local-first journaling app that helps people notice unhelpful thinking patterns (cognitive distortions) in what they write. It runs an open-weight Gemma model on the user's own computer through Ollama, so journal entries are never sent to the internet. When it spots a thinking trap, it shows the user's own words, a fixed set of CBT-style questions, and one gentle alternative view. It also tracks mood and patterns over time.

## 2. The real problem
- Journaling is a common way to cope with stress and anxiety, but a blank page doesn't show *how* you are thinking.
- CBT teaches that thinking traps such as catastrophizing or all-or-nothing thinking increase distress, and that noticing them helps.
- Professional support is not available to everyone.
- Mental-health writing is among the most private data a person has, so uploading it to a cloud AI is a real concern.

## 3. Solution and features
- Journal entries stored locally in SQLite
- Detection of 10 common cognitive distortions, each shown with the user's own quoted words
- Fixed Socratic CBT questions per distortion and one short alternative thought
- Mood (1-10) and emotion tracking, a mood-over-time chart, and counts of the most frequent traps
- Crisis safety layer that runs before the AI
- Export to JSON, delete one entry or all data
- Entries are saved even if the AI is offline

## 4. How AI is used
AI is the core of the product: finding thinking traps in free-form writing needs language understanding that simple keyword rules can't provide.

| Task | Done by |
|---|---|
| Estimate mood and emotions | Gemma 3 (4B), local via Ollama |
| Choose which distortions appear and quote evidence | Gemma 3, limited to a fixed list of IDs |
| Write one short, tentative alternative thought | Gemma 3 |
| Distortion names, explanations and Socratic questions | Fixed CBT templates (not AI) |
| Crisis detection | Rule-based check before any AI call |

**Guardrails around the model**
1. Structured JSON output with a fixed schema (Ollama structured outputs)
2. Unknown distortion IDs are dropped
3. Quoted evidence must appear in the entry, otherwise it is discarded
4. For Labeling, Overgeneralization and Should statements, the quote must contain typical wording (for example "always", "should", "I'm a failure")
5. The prompt forbids the model from assuming facts the user did not write
6. Low temperature (0.2) for consistent output
7. A medical disclaimer is always visible and the model is never asked to diagnose

## 5. Architecture
```
Browser UI  ->  FastAPI (127.0.0.1)  ->  safety check  ->  Ollama (Gemma 3)
                     |                                          |
                  SQLite (local file)          validated JSON + CBT templates
```
Files: `app/safety.py` (disclaimer, crisis check), `app/cbt.py` (templates, prompt, model client, validation), `app/db.py` (storage, insights), `app/main.py` (routes), `app/static/index.html` (UI), `tests/` (pytest).

## 6. Open-source tools
Gemma 3, Ollama, FastAPI, Uvicorn, SQLite, httpx, pytest, plain HTML/CSS/JS.

## 7. Privacy and safety design
- The server listens on `127.0.0.1` only. No cloud calls, no analytics, no external fonts or CDNs.
- Data is stored in a local file `data/mindmosaic.db`, excluded from git.
- Entries with self-harm or suicide wording skip the AI and show a supportive message with a pointer to real help (https://findahelpline.com).
- The app states clearly that it is a self-reflection tool, not therapy or medical advice.

## 8. How it was built (timeline, 29 October 2026)
| Time | What happened |
|---|---|
| Morning | Project scaffolded: backend, database, CBT engine, UI |
| About 09:19 | MIT license, README and experiments log added |
| About 10:13 | First run: entry saved but the AI was unreachable |
| About 10:17 | Found a CUDA error (GPU driver too old for Ollama) |
| About 10:41 | Worked around it by running Ollama on CPU |
| About 10:30 to 11:00 | Ran the first test entries on gemma3:4b |
| About 11:30 | Analyzed results, tuned the prompt, added wording-cue checks and tests |
| Afternoon | Pushed the project to GitHub and re-tested after tuning |

## 9. Experiments and results
**Setup:** Windows PC, 32 GB RAM, Ollama 0.40.13, `gemma3:4b` running on CPU. Only this model was tested.

### Round 1 (before tuning)
| # | Entry | Result | Assessment |
|---|---|---|---|
| 1 | "I have a presentation tomorrow and I know everything will fall apart. I always mess things up." | Labeling ("I always mess things up"), mood 3/10, anxious and stressed | Partly wrong: "always" signals Overgeneralization, and catastrophizing was missed. The alternative thought claimed "you've prepared and done well in the past", which the user never wrote |
| 2 | "If I don't get an A, I'm a total failure." | Black-and-white thinking, mood 3/10 | Correct |
| 3 | Entry about a van arriving early and a missing abaya, scarf and hijab pins | Labeling, mood 3/10, stressed, anxious, tired | False positive: a stressful event, not a thinking error |

Round 1 distortion accuracy: 1 of 3 fully correct. Response times were not recorded.

### Changes made after Round 1
- Rewrote the prompt with a description and example wording for each distortion
- Told the model that event-only entries should return no distortions
- Told the model to use only facts from the entry in its alternative thought
- Added wording-cue validation for Labeling, Overgeneralization and Should statements
- Increased the request timeout to 180 seconds for CPU inference
- Added 4 tests (10 passing)

### Round 2 (after tuning, gemma3:4b on CPU)
| # | Entry | Time | Traps found | Assessment |
|---|---|---|---|---|
| 1 | Presentation entry | about 1 min | catastrophizing, overgeneralization | Correct. Alternative thought still assumes "preparation you've already done" |
| 2 | "If I don't get an A, I'm a total failure." | about 40 sec | black-and-white thinking | Correct. Labeling was not flagged. Alternative thought assumes "effort you put into the assignment" |
| 3 | "My friend didn't reply, she must be annoyed with me." | about 30 sec | mind reading | Correct. Alternative thought is reasonable |
| 4 | "Today was okay. I went for a walk and cooked dinner." | about 25 sec | none (happy, calm) | Correct |
| 5 | Crisis-wording entry (safety test) | TODO | TODO | Expected: supportive message, AI not called |

Round 2 distortion accuracy: 4 of 4 traps matched what was expected, apart from Labeling on entry 2. TODO: update after you test entry 5.

## 10. Problems and how they were solved
| Problem | Fix |
|---|---|
| AI unreachable, entry saved without reflection | Ollama hit a CUDA driver error, so Ollama was run on CPU |
| Model mislabeled "always" as Labeling | Prompt now defines each distortion, and code checks for cue wording |
| Model flagged an event-only entry | Prompt says event-only entries get no distortions, and the cue check rejects unsupported labels |
| Model assumed facts in the alternative thought | Prompt now forbids it. Partly improved but still seen in Round 2 |

## 11. Limitations
- Not a medical device or therapist. It cannot diagnose or treat anything.
- Small local models make mistakes, so output is a prompt for reflection, not a conclusion.
- Alternative thoughts sometimes assume facts the user did not write.
- Wording-cue checks reduce false positives but can also remove a correct label that uses different words.
- Crisis detection is keyword-based and can miss indirect wording.
- The database is not encrypted. Anyone with access to the user's computer account can read it.
- Tested only with `gemma3:4b`, on CPU, with English entries, on a small set of examples.

## 12. Future work
- Passphrase encryption of the local database
- Weekly summary of patterns
- Guided thought record worksheet
- Compare other Gemma sizes and measure accuracy on a larger set of labeled entries
- Reduce invented facts in alternative thoughts
- Multi-language support

## 13. How to run
See the README. In short: install Ollama, `ollama pull gemma3:4b`, `pip install -r requirements.txt`, then `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` and open http://127.0.0.1:8000.

## 14. Screenshots
TODO: add images from `docs/screenshots/`, for example `![Thinking trap result](screenshots/result.png)`.