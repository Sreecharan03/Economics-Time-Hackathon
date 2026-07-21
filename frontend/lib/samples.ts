// Real submittal text from the project's own synthetic dataset
// (dataset/submittals/*.txt), embedded so the tool is usable without anyone
// needing to have their own document handy first. Four cases spanning the
// four possible outcomes: a deadline-critical deviation, a real-but-not-
// urgent one, a spec that contradicts itself, and a clean pass.

export interface Sample {
  equipmentId: string;
  specSection: string;
  label: string;
  outcome: string;
  text: string;
}

export const SAMPLES: Sample[] = [
  {
    equipmentId: "XFMR-01",
    specSection: "26 12 00",
    label: "Transformer — service entrance A",
    outcome: "Fails spec, delays the deadline",
    text: `SUBMITTAL TRANSMITTAL
Project: Meridian Data Hall 1
Submittal No.: 26 12 00-001
Spec Section: 26 12 00 – Medium Voltage Transformers
Equipment Tag: XFMR-01
Vendor: ABB Electrification
Contractor: [General Contractor]
Date: (synthetic)

---
ABB CAST RESIN DRY-TYPE TRANSFORMER
Type: KR Series, Cast Coil
Product Code: KR-2500-22-0.4

ELECTRICAL DATA
Rated Power: 2500 kVA
Phases: 3
Frequency: 50/60 Hz
Primary Voltage: 22,000 V, Delta
Secondary Voltage: 400Y/230 V
Vector Group: Dyn11
Insulation Class: F (155°C) — standard product line
Temperature Rise: 150°C over 40°C ambient (per NEMA MG1-32 equivalent)
BIL Primary: 125 kV
Tap Changer: ±2 x 2.5% (off-circuit)

PERFORMANCE
No-Load Losses: 4,500 W
Load Losses (75°C): 20,900 W
Impedance (Z%): 7.0% at rated tap, measured per factory routine test
Sound Level: 68 dB(A) at 1m

CONSTRUCTION
Enclosure: IP23, floor-mounted, indoor vault
Winding Material: Aluminum
Cooling Class: AN (natural air)

STANDARDS
Design and test per IEC 60076-11 / ANSI C57.12.01 (dual-rated product)

Factory Test Certificate: Routine test report attached (impedance measured 7.0% ±0.1%, within manufacturing tolerance of standard product offering)

Notes from Vendor: This is ABB's standard 2500 kVA cast-coil impedance value for this frame size and is the value consistently produced across the KR product line. A lower-impedance custom wind is available on special order with an additional 6-week fabrication lead time and approximately 4% cost premium.`,
  },
  {
    equipmentId: "SWGR-MV-01",
    specSection: "26 13 00",
    label: "Switchgear — utility paralleling bus",
    outcome: "Fails spec, but doesn't move the deadline",
    text: `SUBMITTAL TRANSMITTAL
Project: Meridian Data Hall 1
Submittal No.: 26 13 00-001
Spec Section: 26 13 00 – Medium Voltage Switchgear
Equipment Tag: SWGR-MV-01
Vendor: Vertiv
Contractor: [General Contractor]
Date: (synthetic)

---
VERTIV POWERBOARD MEDIUM VOLTAGE SWITCHGEAR
Type: Metal-Clad, Indoor, Fixed-Mount Vacuum Circuit Breaker
Product Line: PowerBoard MV, IEC 62271-200 / IEEE C37.20.2

ELECTRICAL DATA
Rated Voltage: 15 kV class
Rated Continuous Current (Main Bus): 1200 A
Rated Frequency: 60 Hz
Number of Breaker Cells: 6 (2 incoming, 2 tie, 2 feeder)
Breaker Type: Vacuum, stored-energy spring operated

SHORT-CIRCUIT RATINGS
Rated Short-Time Withstand Current: 25 kA, 3 sec
Rated Peak Withstand (Close & Latch): 65 kA peak
(Note: this is Vertiv's standard PowerBoard MV offering for the 15kV/1200A frame at this list configuration; the 40 kA / 3-sec withstand class requires the next frame size up and is available as a non-standard configuration — see Vertiv Options Bulletin VOB-114 for upgrade pricing and 6-week lead time adder.)

Basic Insulation Level (BIL): 95 kV
Enclosure: NEMA 1, indoor, freestanding

CONTROLS
Protective Relaying: Microprocessor-based, ANSI 50/51/27/59/81 functions standard
Communications: Modbus TCP, DNP3 optional

STANDARDS
IEEE C37.20.2 (Metal-Clad Switchgear)
IEEE C37.06 (Preferred Ratings)
UL 1558 (Metal-Enclosed Low-Voltage Switchgear — reference only, MV unit tested to IEEE)

Factory witness test scheduled per project milestone schedule; short-circuit withstand demonstrated by design test report (Vertiv Test Report TR-4471, on file, applicable to this frame/rating combination).`,
  },
  {
    equipmentId: "ATS-01",
    specSection: "26 36 00",
    label: "Transfer switch — critical distribution",
    outcome: "Spec contradicts itself",
    text: `SUBMITTAL TRANSMITTAL
Project: Meridian Data Hall 1
Submittal No.: 26 36 00-001
Spec Section: 26 36 00 – Transfer Switches
Equipment Tag: ATS-01
Vendor: ASCO Power Technologies
Contractor: [General Contractor]
Date: (synthetic)

---
ASCO 7000 SERIES AUTOMATIC TRANSFER SWITCH
Type: Open transition, microprocessor-controlled

ELECTRICAL DATA
Rated Voltage: 480V, 3-phase, 4-wire
Rated Current: 800A

PERFORMANCE
Transfer Time: 4 cycles maximum, open-transition — meets Section 26 36 00.2 requirement.

CONTROLS
Microprocessor controller, programmable transfer/retransfer logic, exercise scheduling.

Vendor Note: Standard ASCO 7000 Series transfer time is 4 cycles for this frame. Contractor to confirm applicability of Section 26 05 00 paragraph 3.4.C's 10-cycle reference, which appears to originate from a different base-building system type.`,
  },
  {
    equipmentId: "XFMR-02",
    specSection: "26 12 00",
    label: "Transformer — service entrance B",
    outcome: "Clean pass",
    text: `SUBMITTAL TRANSMITTAL
Project: Meridian Data Hall 1
Submittal No.: 26 12 00-002
Spec Section: 26 12 00 – Medium Voltage Transformers
Equipment Tag: XFMR-02
Vendor: ABB Electrification
Contractor: [General Contractor]
Date: (synthetic)

---
ABB CAST RESIN DRY-TYPE TRANSFORMER
Type: KR Series, Cast Coil, Custom Low-Impedance Wind
Product Code: KR-2500-22-0.4-LZ

ELECTRICAL DATA
Rated Power: 2500 kVA
Phases: 3
Frequency: 50/60 Hz
Primary Voltage: 22,000 V, Delta
Secondary Voltage: 400Y/230 V
Vector Group: Dyn11
Insulation Class: F (155°C)
BIL Primary: 125 kV
Tap Changer: ±2 x 2.5% (off-circuit)

PERFORMANCE
No-Load Losses: 4,700 W
Load Losses (75°C): 21,400 W
Impedance (Z%): 5.9% at rated tap, measured per factory routine test — custom low-impedance wind per Owner's coordination study requirement (see prior RFI on XFMR-01)
Sound Level: 68 dB(A) at 1m

CONSTRUCTION
Enclosure: IP23, floor-mounted, indoor vault
Winding Material: Aluminum
Cooling Class: AN (natural air)

Factory Test Certificate: Routine test report attached (impedance measured 5.9% ±0.1%, within the 5.32-6.18% acceptable tolerance band per Section 26 12 00.3).`,
  },
];
