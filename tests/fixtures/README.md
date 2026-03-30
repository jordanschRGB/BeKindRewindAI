# Test Fixtures

This directory contains JSON fixture files for test data.

## Structure

```
fixtures/
├── __init__.py
├── README.md
└── scorer/
    ├── __init__.py
    ├── valid_response.json          # High-quality passing response
    ├── vague_slop_response.json     # Borderline/low-quality response
    ├── hallucinated_response.json   # Contains fabricated content
    └── mangled_names_response.json  # Accuracy issues with names
```

## Fixture Descriptions

### valid_response.json
A model response with high scores across all criteria. Represents a transcript
that passes all quality thresholds with minimal issues.

### vague_slop_response.json
A borderline response with mediocre scores. Represents a transcript that is
incomplete and lacks specific context but doesn't contain major hallucinations.

### hallucinated_response.json
A response with serious hallucination issues. The model invented dialogue and
events not present in the source audio, resulting in a low hallucination score.

### mangled_names_response.json
A response with accuracy issues, specifically around proper nouns and names.
Common with Whisper transcription errors on unfamiliar terms.

## Usage

```python
import json
from pathlib import Path

def load_fixture(name):
    fixture_path = Path(__file__).parent / "fixtures" / "scorer" / f"{name}.json"
    with open(fixture_path) as f:
        return json.load(f)

# In tests
valid_response = load_fixture("valid_response")
```
