# PR Review: feat/vocabulary-feedback-loop

**Reviewer:** Critic (Jordan Schindel lens)
**Date:** 2026-03-25
**Branch:** feat/vocabulary-feedback-loop → main
**Commit:** 05714a0

---

## Verdict: FAIL — Do Not Merge

Three blocking issues. One is bad logic. One is prompt bloat into a 4B model. One is zero evidence. Together they make this unshippable.

---

## Findings

### 1. CRITICAL — The "used" signal is wrong. You're measuring the wrong thing.

**What I found:**

`runner.py` lines 372-382. A word is classified as "used" if it appears as the **target** of a Dreamer correction:

```python
corrected_targets = set()
for c in corrections:
    if " → " in c:
        corrected_targets.add(c.split(" → ")[1].strip())
```

So `kirtan` is "used" only if the Dreamer caught a mishear AND the Archivist applied the correction AND it ended up in `corrected_targets`.

A word is "unused" (noise) if it appeared in the vocab list but *no correction targeted it*.

**Why it's a problem:**

This conflates three completely different failure modes:

1. The word was in vocab, Whisper got it right the first time (no correction needed — this is a WIN, not noise)
2. The word was in vocab, Whisper mangled it, but the Dreamer missed it (correction needed but not caught — this is a MISS)
3. The word was in vocab, Whisper mangled it, Dreamer caught it, Archivist applied it (this is "used")
4. The word was in vocab, it wasn't in the audio at all (genuinely unused)

Cases 1 and 4 both land in `unused_words`. Case 1 is a success — Whisper priming worked exactly as intended. Case 4 is legitimate noise. The code treats them identically and labels both as "noise." 

After 5 sessions of a user who talks about the same ashram, `kirtan` gets primed, Whisper gets it right every time, it never needs a correction, and this system marks it as noise and tells the Worker to deprioritize it. You will systematically teach the Worker to stop priming the words that are working.

**What I'd demand before approving:**

The signal needs to come from Whisper's transcript directly. If the word appears correctly in the transcript, it was primed successfully -- not noise. The only genuine noise is words that appear in neither the transcript nor the corrections. Fix the classification logic before anything else.

---

### 2. CRITICAL — You're dumping the full memory file as context to the Worker. Then adding feedback on top.

**What I found:**

`harness/runner.py` lines 107-120:

```python
context = WHISPER_BRIEFING + "\n\n"
if memory_text:
    context += f"Previously learned vocabulary:\n{memory_text}\n\n"

    # Read feedback to guide the Worker
    feedback = get_vocabulary_feedback(memory_text)
    if feedback["useful"]:
        context += f"Words that have historically HELPED ...: {', '.join(feedback['useful'])}\n"
    if feedback["noise"]:
        context += f"Words that were generated but NEVER matched ...: {', '.join(feedback['noise'])}\n"
    context += "\n"

context += f"User description: {user_description}"
```

`memory_text` is the **entire `archivist_memory.md` file** -- Sessions, Vocabulary history, Vocabulary Feedback, all of it. This already existed pre-branch. This branch then appends MORE text on top of it: the aggregated useful/noise lists.

**Why it's a problem:**

The WHISPER_BRIEFING alone is 568 words. The Worker prompt cap is 15-40 vocabulary words. The Worker is a 4B model. The whisper_briefing.md itself says: "More than ~100 words — the decoder context window is limited, overstuffing dilutes the signal."

That warning is about the Whisper decoder's prompt. The same logic applies to the 4B Worker generating that prompt. A model that can barely handle 40-word vocabulary generation is now receiving:

- Full WHISPER_BRIEFING (568 words)
- Full memory file (grows with every session -- could be 500+ words after a month of use)
- Aggregated useful word list
- Aggregated noise word list
- User description

On session 20 of the same user, the Worker context could easily be 1500+ tokens before the user says a single word. This is the exact failure mode the whisper_briefing.md describes for the Whisper decoder, now applied to the Worker itself. The model degrades. The useful/noise signal gets buried in the noise of everything else.

The `agent.py` version of `worker_generate_vocabulary` (line 280) does the same dump: `context_parts = [WHISPER_BRIEFING]` then appends memory. This branch didn't introduce that bug, but it made it worse.

**What I'd demand before approving:**

1. Strip `memory_text` passed to the Worker down to only the vocabulary history section, not the whole file. The Worker doesn't need to know about Sessions.
2. If feedback is added, it should replace the raw history, not append to it. The Worker needs 3 lines of guidance, not 3 layers of context.
3. Show a token count comparison: Worker context before this branch vs after, across 1 session, 5 sessions, 20 sessions.

---

### 3. CRITICAL — No evidence this produces better vocabulary. None.

**What I found:**

230 lines of unit tests that verify the functions work correctly. Zero tests that verify the feedback loop produces better Whisper output.

The PR has no:
- A/B comparison: vocabulary generated with feedback vs without
- Transcription accuracy comparison on any real tape
- Evidence that "deprioritize noise words" changes what the Worker generates at all
- Evidence that the Worker (a 4B model) even follows the "deprioritize" instruction reliably

**Why it's a problem:**

The Dreamer was justified with 3/3 vs 2/3 vs essay-style side-by-side tests. Those showed the approach worked before it shipped. This PR has no equivalent. We don't know if the Worker actually produces different vocabulary when told "these words were noise." We don't know if different vocabulary produces better transcription. We don't know if the signal direction is even right (see Finding 1).

What we have is: "the functions correctly store and retrieve feedback data." That's not product value. That's a database with no query that matters.

**What I'd demand before approving:**

Run 10 sessions. Split them: 5 with feedback enabled, 5 without. Compare vocabulary lists. Do the feedback-informed lists look more targeted? Then transcribe the same audio both ways. Does accuracy improve? If you can't show that, this is speculation shipped as a feature.

---

### 4. WARNING — The feedback section in memory grows unbounded and is never pruned.

**What I found:**

`agent.py` `append_vocabulary_feedback` prepends each new entry after the section header. No limit. No rotation. Every session adds a line. After 100 sessions, the Vocabulary Feedback section is 100 lines long.

`get_vocabulary_feedback` reads all of them every call and counts votes. This is fine at 20 sessions. At 200 sessions, you're parsing a multi-kilobyte section to produce a word list that then gets stuffed into an already-bloated prompt.

**Why it's a problem:**

Pi hardware. Constrained. The memory file is a flat markdown file with no size management. This branch adds a section with no ceiling. Combined with Finding 2 (full memory file as context), this compounds: longer memory file = bigger Worker context = worse model output.

**What I'd demand before approving:**

Cap the feedback section at the last N sessions (30 max). Only recent behavior is signal. Entries from 6 months ago are noise about noise.

---

### 5. WARNING — The "used" vs "unused" log entry discards unused words. Asymmetric logging.

**What I found:**

`runner.py` line 384:

```python
log("vocabulary_feedback", {"used": used_words, "unused_count": len(unused_words)})
```

Logs the actual used words but only the COUNT of unused words.

**Why it's a problem:**

Minor, but inconsistent. If you ever want to audit what was classified as noise, you can't — you only have a count. The `append_vocabulary_feedback` call above it correctly stores both lists in memory. The log entry is just misleading.

**What I'd demand before approving:**

Log `unused_words` not `unused_count`, or explain why you intentionally dropped it. Probably a one-line fix.

---

### 6. PASS — The parsing logic in `get_vocabulary_feedback` is solid.

Section boundary detection works. The majority-wins voting (useful_count > noise_count) is correct. The Counter approach is clean. The test coverage for parsing edge cases is thorough. If the signal being fed into this were valid (it isn't, see Finding 1), the extraction logic would hold up.

One sentence. Moving on.

---

## Summary

| # | Severity | Issue |
|---|----------|-------|
| 1 | CRITICAL | "Used" signal is wrong -- success looks like noise, punishes working vocab |
| 2 | CRITICAL | Prompt bloat into 4B Worker, grows unbounded with sessions |
| 3 | CRITICAL | Zero evidence the loop produces better output |
| 4 | WARNING  | Memory section grows unbounded, no pruning |
| 5 | WARNING  | Asymmetric log entry discards unused word list |
| 6 | PASS     | Parsing/extraction logic is correct |

**Do not merge.** Finding 1 alone makes this actively harmful -- it will teach the system to stop priming vocabulary that's working. Fix the signal, address the prompt bloat, and come back with A/B evidence.

---

## Receipt

**Files reviewed:**
- `agent.py` (full diff + context around `append_vocabulary_feedback`, `get_vocabulary_feedback`, `worker_generate_vocabulary`)
- `harness/runner.py` (full diff + `step_generate_vocabulary`, `run_pipeline`, pipeline flow)
- `tests/test_vocabulary_feedback.py` (full file, 230 lines)
- `skills/whisper_briefing.md` (full file, 568 words -- referenced for context window constraints)

**Scope:** Functional correctness, signal validity, prompt economics, evidence baseline. No style review.
