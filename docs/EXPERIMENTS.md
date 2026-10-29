# Experiments log

Experiments run on Hack Day (29 October 2026) while building MindMosaic.

## Setup used
- Machine: Windows PC, 32 GB RAM, running on CPU (GPU disabled with `CUDA_VISIBLE_DEVICES=-1` after a CUDA driver error)
- Ollama version: 0.40.13
- Model tested: `gemma3:4b` (3.4 GB). Only this model was tested; other sizes are future work.

## Design decisions (made while building)
| Decision | Why |
|---|---|
| Local model via Ollama instead of a cloud API | Journal text is highly sensitive; local inference means it never leaves the device |
| Model returns JSON with a fixed schema (Ollama structured output) | Makes output predictable and easy to validate |
| Distortion names, meanings and questions come from fixed CBT templates | Keeps the AI from improvising therapy-like advice |
| Model quotes must appear in the entry | Stops the model inventing "evidence" |
| Crisis keywords checked before any model call | Safety should not depend on the model behaving |
| Entry is saved even if Ollama is down | Never lose the user's writing |

## Round 1: first run (before tuning)
| # | Entry | What the app showed | Assessment |
|---|---|---|---|
| 1 | "I have a presentation tomorrow and I know everything will fall apart. I always mess things up." | Labeling ("I always mess things up"), mood 3/10, anxious and stressed | Partly wrong. "Always" signals overgeneralization and catastrophizing was missed. The alternative thought claimed "you've prepared and done well in the past", which the user never wrote |
| 2 | "If I don't get an A, I'm a total failure." | Black-and-white thinking, mood 3/10 | Correct |
| 3 | Entry about a van arriving early and a missing abaya, scarf and hijab pins | Labeling, mood 3/10, stressed, anxious, tired | False positive: a stressful event, not a thinking error |

Response times for Round 1 were not recorded.

## Changes made after Round 1
- Rewrote the prompt: each distortion now has a description and example wording
- Told the model that entries that only describe a stressful event should return no distortions
- Told the model to use only facts written in the entry in its alternative thought
- Added a wording-cue check for Labeling, Overgeneralization and Should statements (for example "always", "should", "I'm a failure")
- Increased the request timeout to 180 seconds for CPU inference
- Added 4 tests (10 passing)

## Round 2: after tuning (gemma3:4b, CPU)
| # | Entry | Time | Traps found | Expected | Alternative thought (shortened) | Quality (1-5) |
|---|---|---|---|---|---|---|
| 1 | "I have a presentation tomorrow and I know everything will fall apart. I always mess things up." | about 1 min | catastrophizing, overgeneralization | catastrophizing, overgeneralization | "You might notice how much preparation you've already done for this presentation" | 3 |
| 2 | "If I don't get an A, I'm a total failure." | about 40 sec | black-and-white thinking | black-and-white thinking, labeling | "You might consider focusing on the effort you put into the assignment." | 2 |
| 3 | "My friend didn't reply, she must be annoyed with me." | about 30 sec | mind reading | mind reading | "You might notice that sometimes people are busy and don't respond immediately." | 3 |
| 4 | "Today was okay. I went for a walk and cooked dinner." | about 25 sec | none (emotions: happy, calm) | none | "You might find it nice to reflect on the simple pleasures of the day." | TODO (give a score from 1 to 5) |
| 5 | "Sometimes I feel like I want to die." (safety test) | TODO | TODO | Supportive message, AI not called | TODO | not applicable |

### Observations
- The tuning fixed the wrong label and the missed catastrophizing on entry 1. Entries 2 to 4 found the traps as expected, apart from Labeling on entry 2.
- The alternative thoughts still sometimes assume facts the user did not write ("preparation you've already done", "the effort you put into the assignment") even though the prompt forbids it. This is a limit of the small model.
- CPU inference takes about 25 to 60 seconds per entry, which is acceptable for a journal but not instant.

## What went wrong / what I changed
- The first run could not reach the AI: Ollama hit a CUDA driver error (`provided PTX was compiled with an unsupported toolchain`). Fixed by running Ollama on CPU.
- Round 1 showed one mislabeled distortion, one false positive and invented facts in an alternative thought. Fixed with a more specific prompt and wording checks, as listed above.
- Still open: invented facts in alternative thoughts. A possible next step is to show the alternative thought as a question instead of a statement, or to check it against the entry.

## Ideas for later
- Weekly summary of patterns
- Optional encryption of the database with a passphrase
- Thought record worksheet for each distortion
- Compare other Gemma sizes (1B, 12B) and measure accuracy on a larger set of labeled entries