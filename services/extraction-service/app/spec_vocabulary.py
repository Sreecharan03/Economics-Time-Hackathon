"""
Loads the attribute-name/unit vocabulary per spec_section from
dataset/submittals/equipment_master.json -- NOT the required values or
verdicts (this service must never see or emit a PASS/FAIL judgment, per
README.md's "what it does NOT do"). Purpose is narrow: give the LLM a closed
vocabulary of field names to extract into, so it isn't guessing attribute
names from scratch on every call (the source evaluation's own guidance:
"vocabulary is consistent" is what makes extraction tractable).
"""
import json
import os
from pathlib import Path

DEFAULT_PATH = Path(__file__).parent.parent.parent.parent / "dataset" / "submittals" / "equipment_master.json"
EQUIPMENT_MASTER_PATH = Path(os.environ.get("EQUIPMENT_MASTER_PATH", DEFAULT_PATH))

_vocabulary_cache: dict[str, list[dict]] | None = None


def load_vocabulary() -> dict[str, list[dict]]:
    """Returns {spec_section: [{"attribute": ..., "unit": ...}, ...]}"""
    global _vocabulary_cache
    if _vocabulary_cache is not None:
        return _vocabulary_cache

    data = json.loads(EQUIPMENT_MASTER_PATH.read_text())
    vocab: dict[str, list[dict]] = {}
    for item in data["equipment"]:
        section = item["spec_section"]
        seen = {(a["attribute"], a["unit"]) for a in vocab.get(section, [])}
        for attr in item["attributes"]:
            key = (attr["attribute"], attr["unit"])
            if key not in seen:
                vocab.setdefault(section, []).append({"attribute": attr["attribute"], "unit": attr["unit"]})
                seen.add(key)
    _vocabulary_cache = vocab
    return vocab


def vocabulary_for_section(spec_section: str | None) -> list[dict]:
    if spec_section is None:
        return []
    return load_vocabulary().get(spec_section, [])
