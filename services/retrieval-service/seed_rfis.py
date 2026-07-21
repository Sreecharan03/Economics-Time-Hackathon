#!/usr/bin/env python3
"""
One-time indexing job (see README.md "Data dependency"): loads
dataset/rfis/rfis.json into the `rfi` + `rfi_embedding` tables. Not run per
request -- run this once after the DB is up, or whenever rfis.json changes.

    DATABASE_URL=postgresql://meridian:meridian_dev_only@localhost:5432/meridian \
        python3 seed_rfis.py
"""
import json
import os
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent))
from app.db import engine
from app.embeddings import embed_text, rfi_index_text

# RFIS_JSON_PATH lets this run either from the source tree (default: relative
# path to dataset/) or inside the Docker image (/data/rfis.json, matching the
# EQUIPMENT_MASTER_PATH convention in compliance-service/Dockerfile).
DEFAULT_PATH = Path(__file__).parent.parent.parent / "dataset" / "rfis" / "rfis.json"
RFIS_JSON_PATH = Path(os.environ.get("RFIS_JSON_PATH", DEFAULT_PATH))


def main():
    rfis = json.loads(RFIS_JSON_PATH.read_text())

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE rfi_embedding"))
        conn.execute(text("TRUNCATE TABLE rfi CASCADE"))

        for rfi in rfis:
            conn.execute(
                text(
                    """
                    INSERT INTO rfi (rfi_id, source_project, rfi_date, subject, question,
                                      spec_section, equipment_type, resolution, tags)
                    VALUES (:rfi_id, :source_project, :rfi_date, :subject, :question,
                            :spec_section, :equipment_type, :resolution, :tags)
                    """
                ),
                {
                    "rfi_id": rfi["rfi_id"],
                    "source_project": rfi["source_project"],
                    "rfi_date": rfi["date"],
                    "subject": rfi["subject"],
                    "question": rfi["question"],
                    "spec_section": rfi["spec_section"],
                    "equipment_type": rfi["equipment_type"],
                    "resolution": rfi["resolution"],
                    "tags": rfi["tags"],
                },
            )

        print(f"Embedding {len(rfis)} RFIs with all-MiniLM-L6-v2...")
        for rfi in rfis:
            vec = embed_text(rfi_index_text(rfi))
            conn.execute(
                text("INSERT INTO rfi_embedding (rfi_id, embedding) VALUES (:rfi_id, :embedding)"),
                {"rfi_id": rfi["rfi_id"], "embedding": str(vec)},
            )

    print(f"Seeded {len(rfis)} RFIs + embeddings.")


if __name__ == "__main__":
    main()
