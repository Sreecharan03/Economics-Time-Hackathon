# Project Meridian – Data Hall 1
## Electrical & Mechanical Equipment Specification (Synthetic Project)

**Project:** Fictional 12 MW colocation data hall, single-story, Tier III-equivalent concurrently maintainable electrical distribution.
**Spec basis:** CSI MasterFormat 2020, Divisions 26 (Electrical), 27 (Communications — not used in this dataset), 23 (HVAC).
**Issued for:** 100% Construction Documents (synthetic, for AI platform demo/eval purposes only — not a real project).
**Note:** This document is synthetic but numeric thresholds are grounded in real ANSI/NEMA/IEEE/UL standard practice for the equipment classes described, so that spec-vs-submittal comparison logic is technically realistic.

---

### SECTION 26 12 00 — MEDIUM VOLTAGE TRANSFORMERS

**26 12 00.1 General**
This section applies to the pad-mounted / indoor dry-type step-down transformers serving the medium-voltage utility service entrance. The Contractor shall coordinate transformer procurement with the Owner's utility interconnection agreement. Long lead times for this equipment class are a known industry risk (60–120+ weeks per current market conditions per Owner's procurement bulletin); the Contractor shall place orders immediately upon Owner's Notice to Proceed for the electrical package.

**26 12 00.2 Ratings**
Transformers shall be rated 2500 kVA, 3-phase, 60 Hz, primary 22 kV delta, secondary 400Y/230V wye, cast-coil dry-type construction, NEMA 3R enclosure if outdoor or NEMA 1 if indoor vault-mounted.

**26 12 00.3 Performance Characteristics**
Insulation system shall be rated Class H (180°C) minimum. Sound levels shall not exceed NEMA TR-1 limits for the kVA class. Temperature rise shall not exceed 150°C rise over 40°C ambient per NEMA MG1-32 basis. Basic Insulation Level (BIL) shall be 125 kV minimum on the primary winding.

Impedance is a critical parameter for downstream protective device coordination — the Engineer of Record has coordinated all upstream and downstream breaker/relay trip settings, short-circuit studies, and arc-flash studies around a nominal transformer impedance of **5.75%**, consistent with ANSI C57.12.01 standard values for this kVA class. Per ANSI/IEEE C57.12.90, manufactured impedance tolerance shall not exceed **±7.5% of the specified nominal value** (i.e., an acceptable submitted range of 5.32%–6.18% for this project). Submittals proposing an impedance value outside this tolerance band shall be rejected, as they invalidate the Engineer's coordination study and may compromise selective breaker coordination under fault conditions.

**26 12 00.4 Submittals**
Shop drawings shall include nameplate data, impedance test certificate, sound test data, and outline dimensions. No Exceptions Taken (NET) status requires full conformance to Section 26 12 00.3.

---

### SECTION 26 13 00 — MEDIUM VOLTAGE SWITCHGEAR

**26 13 00.1 General**
Metal-clad, indoor, medium voltage switchgear serving the utility/generator paralleling switchboard. Coordinate with generator paralleling controls specified in Section 26 32 00.

**26 13 00.2 Ratings**
Switchgear shall be rated 15 kV class, 1200A continuous main bus rating, vacuum circuit breakers, IEEE C37.20.2 metal-clad construction.

**26 13 00.3 Short-Circuit Withstand**
The Owner's fault current study (Appendix E, not reproduced here) establishes an available fault current of 34.6 kA symmetrical at the switchgear main bus, including contribution from the standby generator plant operating in parallel. Per IEEE C37.06 standard ratings and to provide adequate margin per Owner's engineering standard, switchgear short-circuit (momentary/close-and-latch) withstand rating shall be **40 kA minimum, 3-second rated**. This is a life-safety and equipment-protection requirement; no exceptions will be granted without a revised fault current study stamped by the Engineer of Record.

**26 13 00.4 Submittals**
Shop drawings shall include one-line diagram, short-circuit withstand test certification (or engineering justification per UL 1558), and relay coordination curves.

---

### SECTION 26 18 00 — LOW VOLTAGE SWITCHGEAR

**26 18 00.1 Ratings**
480Y/277V, 3-phase, 4-wire, metal-enclosed switchgear, drawout circuit breakers. Short-circuit withstand rating shall be **65 kA RMS symmetrical minimum**, fully rated (non-series-rated) throughout.

---

### SECTION 26 33 00 — UNINTERRUPTIBLE POWER SUPPLY (UPS) SYSTEMS

**26 33 00.1 General**
Double-conversion, transformerless UPS system, N+1 modular architecture, sized to support critical IT load with concurrent maintainability. Basis of design: Eaton Power Xpert 9395 or approved equal (Vertiv, Schneider Electric).

**26 33 00.2 Ratings**
Each UPS module shall be rated 750 kW/750 kVA at unity power factor, 480V input/output, N+1 redundant configuration (minimum 2 modules per system, sized such that the system delivers full rated critical load with any single module out of service).

**26 33 00.3 Battery / Autonomy**
Battery system (VRLA, AGM, or lithium-ion, Contractor's option, coordinated with UPS OEM) shall provide a minimum of **10 minutes of autonomy at 100% rated UPS load**, sized to bridge to generator start and stable closed-transition transfer per Section 26 32 00. Runtime shall be independently verified by battery discharge test during Level 4 commissioning (Functional Performance Testing).

**26 33 00.4 Overcurrent Protection / Input Breakers**
Given the available fault current at the UPS input bus (coordinated with the 40 kA switchgear rating in Section 26 13 00.3 and downstream low-voltage distribution), UPS input breakers shall be rated **100 kAIC (kilo-amperes interrupting capacity) minimum**. This exceeds the UPS OEM's standard 65 kAIC offering; Contractor shall specify the OEM's optional 100 kAIC input breaker package. Submittals proposing standard 65 kAIC breakers without an accompanying series-rating or current-limiting justification stamped by a licensed engineer shall be rejected.

**26 33 00.5 Efficiency**
Minimum 96% efficiency in double-conversion mode at 480V, per Section 26 33 00 basis-of-design OEM published data.

---

### SECTION 26 32 00 — ENGINE GENERATORS

**26 32 00.1 General**
Diesel standby generator plant, N+1 configuration, paralleling switchgear per Section 26 13 00. Basis of design: Caterpillar 3512B or approved equal (Kohler, Cummins).

**26 32 00.2 Ratings**
Each generator shall be rated not less than **1250 kW standby** output at project site conditions (elevation, ambient temperature per Appendix A), 400V, 3-phase, 50/60 Hz per utility service. Generator set shall accept 100% rated load in one step per NFPA 110 Level 1 System requirements and shall meet ISO 8528-5 transient response (frequency dip and recovery) criteria.

**26 32 00.3 Submittals**
Shop drawings shall include genset performance data sheet, motor starting kVA capability, fuel consumption curves, and NFPA 110 compliance statement.

---

### SECTION 26 36 00 — TRANSFER SWITCHES

**26 36 00.1 General**
Automatic transfer switches (ATS) serving critical distribution downstream of the UPS/generator plant.

**26 36 00.2 Transfer Time**
Transfer switches shall complete open-transition transfer in not more than **4 cycles** (per Section 26 36 00.2, coordinated with UPS ride-through capability specified in Section 26 33 00).

*[Cross-reference note retained from prior project template — flagged during internal QA but not yet resolved at time of issue: Section 26 05 00 (Common Work Results for Electrical), paragraph 3.4.C, states emergency system transfer devices shall transfer "within 10 cycles in accordance with NFPA 99 essential electrical systems requirements." This paragraph appears to reference an older base-building (healthcare-derived) template and has not been confirmed as applicable to this data center project by the Engineer of Record. Contractor to issue RFI for clarification prior to ATS procurement.]*

---

### SECTION 23 65 00 — COOLING TOWERS / AIR-COOLED CHILLERS

**23 65 00.1 General**
Air-cooled, free-cooling chiller plant serving the CRAH/CRAC distribution loop. Basis of design: Vertiv Liebert HPC-S or approved equal.

**23 65 00.2 Refrigerant**
In accordance with Owner's sustainability policy and applicable state HFC phase-down regulations (mirroring the AIM Act GWP step-down schedule), chiller units shall use a **low-global-warming-potential (low-GWP) refrigerant, R-454B**, with a GWP not exceeding 466. Legacy refrigerants including **R-410A (GWP 2088) are not permitted** for new equipment on this project regardless of OEM standard offering, per Owner's Sustainability Requirements Addendum SR-04 (bound separately, referenced here for the Contractor's convenience — see Div 01 Section 01 81 13 Sustainable Design Requirements for full addendum text).

**23 65 00.3 Capacity**
Each chiller module shall provide not less than 350 kW total cooling capacity at ARI standard rating conditions.

---

### SECTION 23 74 00 — IN-ROW / PRECISION COOLING UNITS

**23 74 00.1 Ratings**
In-row cooling units serving the white space shall be rated 40 kW sensible cooling minimum per unit, R-454B or R-32 refrigerant (low-GWP per Section 23 65 00.2 policy, applicable project-wide to all new mechanical cooling equipment), N+1 redundant per pod.

---

*End of synthetic spec excerpt. Full project spec set (30–50 pages per real-world norm) is represented here only for the sections relevant to the seeded equipment/deviation set used in this AI platform demo dataset.*
