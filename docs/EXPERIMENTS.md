# Experiments log

Fill this in while you build and test on Hack Day. Judges like seeing what you tried, what failed and what you changed.
Rows marked TODO are for you to complete with your own real results.

## Setup used
- Machine / RAM: Windows PC, 32 GB RAM, running on CPU
- Ollama version: (`ollama --version`)
- Models tried: gemma3:4b

## Design decisions (made while building)
| Decision | Why |
|---|---|
| Local model via Ollama instead of a cloud API | Journal text is highly sensitive; local inference means it never leaves the device |
| Model returns JSON with a fixed schema (Ollama structured output) | Makes output predictable and easy to validate |
| Distortion names, meanings and questions come from fixed CBT templates | Keeps the AI from improvising therapy-like advice |
| Model quotes must appear in the entry | Stops the model inventing "evidence" |
| Crisis keywords checked before any model call | Safety should not depend on the model behaving |
| Entry is saved even if Ollama is down | Never lose the user's writing |

## Model comparison (TODO: run the same 5 test entries on each model)
| Model | Avg. response time | Found the right distortion? | Alternative thought quality (1-5) | Notes |
|---|---|---|---|---|
| gemma3:1b | TODO | TODO | TODO | TODO |
| gemma3:4b | 1 min | catastrophizing, overgeneralization | 3 | You might notice how much preparation you’ve already done for this presentation |
| gemma3:4b | 40 sec | Black-and-white thinking| 2 | You might consider focusing on the effort you put into the assignment. |
| gemma3:4b | 30 sec | Mind reading | 3 | You might notice that sometimes people are busy and don't respond immediately. |
| gemma3:4b | 25 sec | happy and Calm | 6 | You might find it nice to reflect on the simple pleasures of the day. |



## Test entries to try
1. "I have a presentation tomorrow and I know everything will fall apart. I always mess things up." (expect catastrophizing, overgeneralization)
2. "If I don't get an A, I'm a total failure." (expect black-and-white thinking, labeling)
3. "My friend didn't reply, she must be annoyed with me." (expect mind reading)
4. "Today was okay. I went for a walk and cooked dinner." (no distortions)
5. "Sometimes I feel like I want to die." (expect the supportive message and NO model call)

## What went wrong / what I changed
- TODO (e.g. small model flagged too many distortions, so I made the prompt more conservative)

## Ideas for later
- Weekly summary of patterns
- Optional encryption of the database with a passphrase
- Per-distortion "thought record" worksheet
