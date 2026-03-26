# MemoryVault Agents

Three agents, one model, isolated context per call.

## Archivist (driver)
- Talks to the user
- Reads MEMORY.md on startup for vocabulary and preferences
- Generates vocabulary from conversation
- Controls the pipeline: prime → capture → transcribe → label → score → save
- Context: full conversation history + MEMORY.md

## Worker (labeler)
- Generates Whisper vocabulary lists
- Generates titles, descriptions, tags from transcripts
- Reads skills/whisper_briefing.md before vocabulary tasks
- Context: only the skill briefing + transcript + last score feedback
- Never sees the conversation

## Scorer (enforcer)
- Rates label quality 1-10
- States human consequences for scores below 7
- Context: only the transcript + generated label
- Never sees the conversation or memory
- One consequence statement per score. Not a lecture.
