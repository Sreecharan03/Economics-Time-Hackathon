-- Meridian platform -- initial schema.
-- Models the same entity relationships the source evaluation describes as the
-- eventual property-graph schema (Equipment, Specification, Submittal, Vendor,
-- ProcurementPackage, ScheduleActivity, CommissioningTest, RFI) as relational
-- tables + foreign keys. A knowledge graph is deferred until multi-hop,
-- multi-project queries are the actual bottleneck -- see top-level README.

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Procurement / commissioning reference tables
-- ---------------------------------------------------------------------------

CREATE TABLE procurement_package (
    package_id      TEXT PRIMARY KEY,
    description     TEXT
);

CREATE TABLE commissioning_test (
    test_id         TEXT PRIMARY KEY,
    test_name       TEXT NOT NULL,
    level           INT NOT NULL          -- 1-6, per FAT/SAT/pre-func/FPT/IST/handover
);

-- ---------------------------------------------------------------------------
-- Equipment + spec requirements
-- ---------------------------------------------------------------------------

CREATE TABLE equipment (
    equipment_id            TEXT PRIMARY KEY,
    description              TEXT,
    oem                       TEXT,
    model                     TEXT,
    spec_section              TEXT,
    package_id                TEXT REFERENCES procurement_package(package_id),
    install_activity_id       TEXT,        -- FK added after schedule_activity exists (see below)
    commissioning_test_id     TEXT REFERENCES commissioning_test(test_id)
);

-- One row per checkable attribute on a spec clause. `acceptable_range_low/high`
-- is null for enum-type checks (e.g. refrigerant type); populated for numeric
-- tolerance-band checks (e.g. transformer impedance).
CREATE TABLE spec_requirement (
    id                       SERIAL PRIMARY KEY,
    spec_section              TEXT NOT NULL,
    clause                    TEXT NOT NULL,
    equipment_type_hint       TEXT,         -- e.g. "transformer", used to route extraction
    attribute                 TEXT NOT NULL,
    required_value            TEXT,         -- stored as text; numeric checks cast at read time
    tolerance_pct              NUMERIC,
    acceptable_range_low       NUMERIC,
    acceptable_range_high      NUMERIC,
    unit                       TEXT,
    conflicting_clause_ref     TEXT,         -- non-null only for spec-internal-conflict cases (e.g. ATS-01)
    UNIQUE (spec_section, clause, attribute)
);

-- ---------------------------------------------------------------------------
-- Submittals + extraction + compliance results
-- ---------------------------------------------------------------------------

CREATE TABLE submittal (
    id                SERIAL PRIMARY KEY,
    equipment_id       TEXT NOT NULL REFERENCES equipment(equipment_id),
    submittal_no        TEXT,
    vendor               TEXT,
    raw_text             TEXT NOT NULL,
    submitted_at          TIMESTAMPTZ DEFAULT now()
);

-- extraction-service writes here
CREATE TABLE submittal_attribute (
    id              SERIAL PRIMARY KEY,
    submittal_id     INT NOT NULL REFERENCES submittal(id),
    attribute         TEXT NOT NULL,
    value             TEXT NOT NULL,
    unit              TEXT,
    source_span        TEXT,
    confidence          NUMERIC
);

-- compliance-service writes here; never written by an LLM call
CREATE TABLE compliance_result (
    id              SERIAL PRIMARY KEY,
    submittal_id     INT NOT NULL REFERENCES submittal(id),
    attribute         TEXT NOT NULL,
    verdict           TEXT NOT NULL CHECK (verdict IN ('PASS', 'FAIL', 'CONFLICT')),
    spec_requirement_id  INT REFERENCES spec_requirement(id),
    rationale          TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Schedule (CPM network)
-- ---------------------------------------------------------------------------

CREATE TABLE schedule_activity (
    activity_id         TEXT PRIMARY KEY,
    activity_name         TEXT NOT NULL,
    activity_type          TEXT NOT NULL,   -- design | submittal | procurement | construction | install | commissioning | milestone
    duration_days           INT NOT NULL,
    equipment_id             TEXT REFERENCES equipment(equipment_id),
    package_id                TEXT REFERENCES procurement_package(package_id),
    commissioning_test_id     TEXT REFERENCES commissioning_test(test_id),
    -- baseline CPM results, recomputed by schedule-service; stored for the
    -- no-deviation reference case so /schedule/propagate has a diff baseline
    early_start          INT,
    early_finish           INT,
    late_start              INT,
    late_finish               INT,
    total_float_days           INT
);

ALTER TABLE equipment
    ADD CONSTRAINT fk_equipment_install_activity
    FOREIGN KEY (install_activity_id) REFERENCES schedule_activity(activity_id);

CREATE TABLE schedule_predecessor (
    activity_id       TEXT NOT NULL REFERENCES schedule_activity(activity_id),
    predecessor_id      TEXT NOT NULL REFERENCES schedule_activity(activity_id),
    relationship_type      TEXT NOT NULL DEFAULT 'FS',   -- finish-to-start only, by design
    lag_days                 INT NOT NULL DEFAULT 0,
    PRIMARY KEY (activity_id, predecessor_id)
);

-- ---------------------------------------------------------------------------
-- RFIs (retrieval corpus) + drafted output
-- ---------------------------------------------------------------------------

CREATE TABLE rfi (
    rfi_id            TEXT PRIMARY KEY,
    source_project      TEXT,
    rfi_date              DATE,
    subject                TEXT,
    question                 TEXT,
    spec_section               TEXT,
    equipment_type               TEXT,
    resolution                     TEXT,
    tags                              TEXT[]
);

-- all-MiniLM-L6-v2 produces 384-dim embeddings; local model, no external API
CREATE TABLE rfi_embedding (
    rfi_id      TEXT PRIMARY KEY REFERENCES rfi(rfi_id),
    embedding     vector(384) NOT NULL
);

CREATE INDEX rfi_embedding_ivfflat
    ON rfi_embedding USING ivfflat (embedding vector_cosine_ops) WITH (lists = 20);

CREATE TABLE drafted_rfi (
    id              SERIAL PRIMARY KEY,
    equipment_id      TEXT NOT NULL REFERENCES equipment(equipment_id),
    draft_text          TEXT NOT NULL,
    citations              JSONB NOT NULL,
    requires_human_approval BOOLEAN NOT NULL DEFAULT true,
    approved                  BOOLEAN NOT NULL DEFAULT false,
    created_at                  TIMESTAMPTZ DEFAULT now()
);
