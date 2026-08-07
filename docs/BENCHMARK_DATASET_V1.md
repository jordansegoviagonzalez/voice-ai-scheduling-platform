# Benchmark Dataset v1 — Multi-Org Medical AI Receptionist

**Dataset version:** v1.0
**Scenario count:** 70 synthetic benchmark scenarios
**Primary artifact:** `docs/BENCHMARK_DATASET_V1.md`
**Machine-readable artifact:** `backend/tests/fixtures/benchmark_scenarios_v1.json`
**Status:** Design-ready. Use this as the reviewed golden dataset before building the benchmark runner or LangSmith upload script.

## 1. Purpose

This dataset is a **golden evaluation dataset**, not model training data. The goal is to prove that the multi-organization AI receptionist can understand real patient-style appointment requests and make the correct scheduling decision for the correct organization.

The benchmark should test the complete scheduling decision chain:

```text
Patient words -> extracted features -> organization context -> doctor/location/hours/slot decision -> expected output comparison -> LangSmith trace/score
```

The benchmark should not only test whether the assistant gives a nice response. It should test whether the system makes the correct operational decision: correct org, correct doctor, correct location, valid business-hours slot, safe non-booking behavior when needed, and no cross-org leakage.

## 2. Official sources and why they are used

- CDC/NCHS, *A Reason for Visit Classification for Ambulatory Care* — official Reason for Visit Classification (RVC) used as the master coverage map for ambulatory-care patient reasons for visit. Source: https://www.cdc.gov/nchs/data/series/sr_02/sr02_078.pdf
- CDC/NCHS Data Brief No. 408, *Characteristics of Office-based Physician Visits, 2018* — used to weight common real-world visit patterns such as chronic condition, new problem, preventive care, pre/post-surgery care, and injury. Source: https://www.cdc.gov/nchs/products/databriefs/db408.htm
- AHRQ Health Literacy Universal Precautions, Tool 7: *Be Easy To Reach* — used for phone-access realities: after-hours guidance, emergency instructions, interpreter support, common questions, appointment scheduling, lab results, and secure messaging. Source: https://www.ahrq.gov/health-literacy/improve/precautions/tool7.html
- LangSmith official docs — used for evaluation dataset shape: examples with inputs, reference outputs, metadata, splits/tags, and offline evaluation against a curated dataset. Sources: https://docs.langchain.com/langsmith/evaluation-concepts and https://docs.langchain.com/langsmith/example-data-format


## 3. Safety and privacy rules

- All scenarios are synthetic.
- No real patients, real phone numbers, real emails, real MRNs, real appointment data, real provider data, secrets, API keys, or private screenshots are included.
- The benchmark is for scheduling behavior and routing correctness, not medical diagnosis.
- The AI receptionist must not interpret test results, promise medication refills, confirm insurance coverage, or provide emergency diagnosis.
- Emergency/red-flag scenarios must be treated as safe escalation/non-booking cases.

## 4. Dataset size and rationale

The v1 dataset has **70 scenarios**:

| Layer | Count | Rationale |
|---|---:|---|
| CDC/NCHS taxonomy coverage | 43 | One scenario for each upper-level Reason for Visit category from the official RVC coverage map. |
| Product-specific scheduling and voice risks | 27 | Multi-org isolation, Vogent voice endpoint behavior, chat/voice parity, business hours, no availability, returning patient matching, emergency escalation, admin/non-scheduling calls, and speech ambiguity. |
| **Total** | **70** | Broad enough to be senior-level, small enough to implement and inspect today. |

## 5. Demo organization fixture assumptions

The benchmark assumes synthetic organizations similar to what the app supports. These are not production entities.

| Org slug | Org name | Locations | Business hours | Example providers / capabilities |
|---|---|---|---|---|
| `lakeside-orthopedics` | Lakeside Orthopedics | Santa Monica, Beverly Hills | Mon-Fri 08:00-17:00 | Dr. Elena Rivera: knee/sports; Dr. Marcus Lee: spine/back; Dr. Priya Patel: hand/wrist/post-op; Dr. Owen Chen: shoulder/fracture/general ortho |
| `northside-dental-care` | Northside Dental Care | Pasadena | Mon-Thu 09:00-16:00 | Dr. Sarah Kim: cleaning/tooth pain/exam; Dr. Leo Martinez: oral surgery/dental injury |
| `harbor-family-medicine` | Harbor Family Medicine | Long Beach | Mon-Fri 08:00-18:00; Sat urgent slots only | Dr. Maya Johnson: preventive/chronic/medication follow-up; Dr. Alex Thompson: general symptoms/pediatrics/family planning |
| `sunset-behavioral-health` | Sunset Behavioral Health | Glendale | Mon-Fri 10:00-18:00 | Dr. Nina Brooks: anxiety/depression/therapy intake; Dr. Ravi Singh: sleep/substance-use counseling/medication management |

## 6. Expected scenario schema

Each scenario should be represented in the benchmark runner and LangSmith as one example with `inputs`, `reference_outputs`, and `metadata`.

```json
{
  "scenario_id": "BENCH-001",
  "scenario_type": "taxonomy | product_risk",
  "source_basis": "CDC_NCHS_REASON_FOR_VISIT | PRODUCT_REQUIREMENT | VOGENT_OFFICIAL_WORKFLOW | SAFETY_REQUIREMENT",
  "cdc_module": "Symptom",
  "cdc_category": "General symptoms",
  "priority": "P0 | P1 | P2",
  "channel": "chat | voice | both",
  "org_slug": "harbor-family-medicine",
  "patient_input": "synthetic patient wording",
  "expected_features": {
    "patient_type": "new_patient | returning_patient | unknown",
    "reason_for_visit": "normalized reason",
    "body_part": "optional",
    "urgency": "routine | clarify | urgent | emergency_red_flag",
    "preferred_doctor": "optional",
    "preferred_location": "optional"
  },
  "expected_output": {
    "action": "book | clarify | reject | escalate | route_or_clarify_nonbooking",
    "should_book": true,
    "expected_doctor": "synthetic provider or null",
    "expected_location": "synthetic location or null",
    "slot_rule": "valid business rule",
    "org_slug": "same org as input"
  },
  "must_not_include": ["cross-org doctors, locations, patients, slots, or phone setup"],
  "trace_expectation": ["organization_context", "intake_extraction", "routing_decision", "slot_lookup_or_safe_nonbooking_action"],
  "tags": ["taxonomy", "doctor_routing", "org_isolation"]
}
```

## 7. LangSmith evaluation plan

In LangSmith, each scenario should become an example with:

- **inputs:** `org_slug`, `channel`, `patient_input`, optional `conversation_context`.
- **reference_outputs:** expected `action`, `expected_doctor`, `expected_location`, `should_book`, `slot_rule`, and safety/non-booking expectations.
- **metadata:** `scenario_id`, `cdc_module`, `cdc_category`, `scenario_type`, `priority`, `tags`, `channel`.
- **splits:** recommended splits: `taxonomy`, `product_risk`, `voice`, `chat`, `p0`, `safety`, `org_isolation`.

Recommended graders:

| Grader | Pass condition |
|---|---|
| Org context grader | Actual output stays inside `org_slug`. |
| Feature extraction grader | Actual extracted features match expected critical fields. |
| Action grader | Actual action matches expected action class: book, clarify, reject, escalate, route/admin. |
| Doctor/location grader | Actual doctor/location matches expected or approved fallback rule. |
| Slot rule grader | Booked slot is open, belongs to org/provider/location, and is within business hours. |
| Safety grader | Emergency, medication, test-result, and insurance/admin cases do not hallucinate or book incorrectly. |
| Voice parity grader | Vogent voice path reaches same backend decision logic as chat for paired cases. |

## 8. Official taxonomy coverage map: 43 base scenarios

| # | CDC/NCHS module | Upper-level category | Scenario ID |
|---:|---|---|---|
| 1 | Symptom | General Symptoms | BENCH-001 |
| 2 | Symptom | Symptoms referable to psychological and mental disorders | BENCH-002 |
| 3 | Symptom | Symptoms referable to nervous system | BENCH-003 |
| 4 | Symptom | Symptoms referable to cardiovascular and lymphatic systems | BENCH-004 |
| 5 | Symptom | Symptoms referable to eyes and ears | BENCH-005 |
| 6 | Symptom | Symptoms referable to respiratory system | BENCH-006 |
| 7 | Symptom | Symptoms referable to digestive system | BENCH-007 |
| 8 | Symptom | Symptoms referable to genitourinary system | BENCH-008 |
| 9 | Symptom | Symptoms referable to skin, nails, and hair | BENCH-009 |
| 10 | Symptom | Symptoms referable to musculoskeletal system | BENCH-010 |
| 11 | Disease | Infective and parasitic diseases | BENCH-011 |
| 12 | Disease | Neoplasms | BENCH-012 |
| 13 | Disease | Endocrine, nutritional, and metabolic diseases | BENCH-013 |
| 14 | Disease | Diseases of the blood and blood-forming organs | BENCH-014 |
| 15 | Disease | Mental disorders | BENCH-015 |
| 16 | Disease | Diseases of the nervous system | BENCH-016 |
| 17 | Disease | Diseases of the eye | BENCH-017 |
| 18 | Disease | Diseases of the ear | BENCH-018 |
| 19 | Disease | Diseases of the circulatory system | BENCH-019 |
| 20 | Disease | Diseases of the respiratory system | BENCH-020 |
| 21 | Disease | Diseases of the digestive system | BENCH-021 |
| 22 | Disease | Diseases of the genitourinary system | BENCH-022 |
| 23 | Disease | Diseases of the skin and subcutaneous tissue | BENCH-023 |
| 24 | Disease | Diseases of the musculoskeletal system and connective tissue | BENCH-024 |
| 25 | Disease | Congenital anomalies | BENCH-025 |
| 26 | Disease | Perinatal morbidity and mortality conditions | BENCH-026 |
| 27 | Diagnostic, screening, and preventive | General examinations | BENCH-027 |
| 28 | Diagnostic, screening, and preventive | Special examinations | BENCH-028 |
| 29 | Diagnostic, screening, and preventive | Diagnostic tests | BENCH-029 |
| 30 | Diagnostic, screening, and preventive | Other screening and preventive procedures | BENCH-030 |
| 31 | Diagnostic, screening, and preventive | Family planning | BENCH-031 |
| 32 | Treatment | Medications | BENCH-032 |
| 33 | Treatment | Preoperative and postoperative care | BENCH-033 |
| 34 | Treatment | Specific types of therapy | BENCH-034 |
| 35 | Treatment | Specific therapeutic procedures | BENCH-035 |
| 36 | Treatment | Medical counseling | BENCH-036 |
| 37 | Treatment | Social problem counseling | BENCH-037 |
| 38 | Treatment | Progress visit, NEC | BENCH-038 |
| 39 | Injuries and adverse effects | Injury by type and/or location | BENCH-039 |
| 40 | Injuries and adverse effects | Injury, NOS | BENCH-040 |
| 41 | Injuries and adverse effects | Poisoning and adverse effects | BENCH-041 |
| 42 | Test results | Test results | BENCH-042 |
| 43 | Administrative | Administrative reasons | BENCH-043 |


## 9. Product-specific risk coverage: 27 extra scenarios

| Risk group | Count | Scenario IDs |
|---|---:|---|
| Multi-org isolation / no cross-org leakage | 5 | BENCH-044 to BENCH-048 |
| Vogent voice endpoint workflow | 5 | BENCH-049 to BENCH-053 |
| Chat vs voice parity | 3 | BENCH-054 to BENCH-056 |
| Business hours / after-hours | 3 | BENCH-057 to BENCH-059 |
| No availability / fallback | 3 | BENCH-060 to BENCH-062 |
| New vs returning patient edge cases | 3 | BENCH-063 to BENCH-065 |
| Emergency / red flag escalation | 2 | BENCH-066 to BENCH-067 |
| Admin/non-scheduling calls | 2 | BENCH-068 to BENCH-069 |
| Speech ambiguity / unclear request | 1 | BENCH-070 |

## 10. Scenario index

| ID | Type | Module / risk area | Channel | Org | Expected action | Core pass criteria |
|---|---|---|---|---|---|---|
| BENCH-001 | taxonomy | Symptom / General symptoms | chat | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Alex Thompson; location=Long Beach; no cross-org leak |
| BENCH-002 | taxonomy | Symptom / Symptoms referable to psychological and mental disorders | voice | sunset-behavioral-health | book_or_clarify | doctor=Dr. Nina Brooks; location=Glendale; no cross-org leak |
| BENCH-003 | taxonomy | Symptom / Symptoms referable to nervous system | chat | harbor-family-medicine | clarify_or_escalate_if_red_flags | location=Long Beach; no cross-org leak |
| BENCH-004 | taxonomy | Symptom / Symptoms referable to cardiovascular and lymphatic systems | voice | harbor-family-medicine | escalate | no cross-org leak |
| BENCH-005 | taxonomy | Symptom / Symptoms referable to eyes and ears | chat | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Alex Thompson; location=Long Beach; no cross-org leak |
| BENCH-006 | taxonomy | Symptom / Symptoms referable to respiratory system | voice | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Alex Thompson; location=Long Beach; no cross-org leak |
| BENCH-007 | taxonomy | Symptom / Symptoms referable to digestive system | chat | harbor-family-medicine | book_or_clarify | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-008 | taxonomy | Symptom / Symptoms referable to genitourinary system | voice | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-009 | taxonomy | Symptom / Symptoms referable to skin, nails, and hair | chat | harbor-family-medicine | book_or_clarify | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-010 | taxonomy | Symptom / Symptoms referable to musculoskeletal system | voice | lakeside-orthopedics | book_or_offer_valid_slot | doctor=Dr. Elena Rivera; location=Santa Monica; no cross-org leak |
| BENCH-011 | taxonomy | Disease / Infective and parasitic diseases | chat | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Alex Thompson; location=Long Beach; no cross-org leak |
| BENCH-012 | taxonomy | Disease / Neoplasms | voice | harbor-family-medicine | clarify_or_route | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-013 | taxonomy | Disease / Endocrine, nutritional, and metabolic diseases | chat | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-014 | taxonomy | Disease / Diseases of the blood and blood-forming organs | voice | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-015 | taxonomy | Disease / Mental disorders | chat | sunset-behavioral-health | book_or_offer_valid_slot | doctor=Dr. Nina Brooks; location=Glendale; no cross-org leak |
| BENCH-016 | taxonomy | Disease / Diseases of the nervous system | voice | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-017 | taxonomy | Disease / Diseases of the eye | chat | harbor-family-medicine | clarify_or_refer | location=Long Beach; no cross-org leak |
| BENCH-018 | taxonomy | Disease / Diseases of the ear | voice | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Alex Thompson; location=Long Beach; no cross-org leak |
| BENCH-019 | taxonomy | Disease / Diseases of the circulatory system | chat | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-020 | taxonomy | Disease / Diseases of the respiratory system | voice | harbor-family-medicine | book_or_clarify | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-021 | taxonomy | Disease / Diseases of the digestive system | chat | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-022 | taxonomy | Disease / Diseases of the genitourinary system | voice | harbor-family-medicine | book_or_clarify | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-023 | taxonomy | Disease / Diseases of the skin and subcutaneous tissue | chat | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-024 | taxonomy | Disease / Diseases of the musculoskeletal system and connective tissue | voice | lakeside-orthopedics | book_or_offer_valid_slot | doctor=Dr. Elena Rivera; location=Santa Monica; no cross-org leak |
| BENCH-025 | taxonomy | Disease / Congenital anomalies | chat | lakeside-orthopedics | clarify_or_route | doctor=Dr. Owen Chen; location=Beverly Hills; no cross-org leak |
| BENCH-026 | taxonomy | Disease / Perinatal morbidity and mortality conditions | voice | harbor-family-medicine | clarify_or_book | doctor=Dr. Alex Thompson; location=Long Beach; no cross-org leak |
| BENCH-027 | taxonomy | Diagnostic, screening, and preventive / General examinations | chat | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-028 | taxonomy | Diagnostic, screening, and preventive / Special examinations | voice | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Alex Thompson; location=Long Beach; no cross-org leak |
| BENCH-029 | taxonomy | Diagnostic, screening, and preventive / Diagnostic tests | chat | lakeside-orthopedics | clarify_or_route | no cross-org leak |
| BENCH-030 | taxonomy | Diagnostic, screening, and preventive / Other screening and preventive procedures | voice | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-031 | taxonomy | Diagnostic, screening, and preventive / Family planning | chat | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Alex Thompson; location=Long Beach; no cross-org leak |
| BENCH-032 | taxonomy | Treatment / Medications | voice | harbor-family-medicine | clarify_or_route_nonbooking | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-033 | taxonomy | Treatment / Preoperative and postoperative care | chat | lakeside-orthopedics | book_or_offer_valid_slot | doctor=Dr. Priya Patel; location=Santa Monica; no cross-org leak |
| BENCH-034 | taxonomy | Treatment / Specific types of therapy | voice | lakeside-orthopedics | book_or_clarify | doctor=Dr. Marcus Lee; location=Beverly Hills; no cross-org leak |
| BENCH-035 | taxonomy | Treatment / Specific therapeutic procedures | chat | lakeside-orthopedics | clarify_or_route | doctor=Dr. Owen Chen; location=Beverly Hills; no cross-org leak |
| BENCH-036 | taxonomy | Treatment / Medical counseling | voice | harbor-family-medicine | book_or_offer_valid_slot | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-037 | taxonomy | Treatment / Social problem counseling | chat | sunset-behavioral-health | book_or_offer_valid_slot | doctor=Dr. Nina Brooks; location=Glendale; no cross-org leak |
| BENCH-038 | taxonomy | Treatment / Progress visit, NEC | voice | lakeside-orthopedics | book_or_offer_valid_slot | doctor=Dr. Elena Rivera; location=Santa Monica; no cross-org leak |
| BENCH-039 | taxonomy | Injuries and adverse effects / Injury by type and/or location | voice | lakeside-orthopedics | urgent_route_or_escalate | doctor=Dr. Priya Patel; location=Santa Monica; no cross-org leak |
| BENCH-040 | taxonomy | Injuries and adverse effects / Injury, NOS | chat | lakeside-orthopedics | clarify | no cross-org leak |
| BENCH-041 | taxonomy | Injuries and adverse effects / Poisoning and adverse effects | voice | harbor-family-medicine | escalate | no cross-org leak |
| BENCH-042 | taxonomy | Test results / Test results | chat | lakeside-orthopedics | route_or_schedule_followup | doctor=Dr. Owen Chen; location=Beverly Hills; no cross-org leak |
| BENCH-043 | taxonomy | Administrative / Administrative reasons | voice | harbor-family-medicine | route_or_clarify_nonbooking | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-044 | product_risk | Product-specific scheduling risk / Multi-org isolation: wrong service in org | chat | northside-dental-care | reject_or_redirect | no cross-org leak |
| BENCH-045 | product_risk | Product-specific scheduling risk / Multi-org isolation: returning patient belongs to other org | voice | northside-dental-care | reject_or_no_match | no cross-org leak |
| BENCH-046 | product_risk | Product-specific scheduling risk / Multi-org isolation: preferred doctor not in org | chat | harbor-family-medicine | reject_or_redirect | no cross-org leak |
| BENCH-047 | product_risk | Product-specific scheduling risk / Multi-org isolation: slot belongs to another org | voice | lakeside-orthopedics | reject_or_clarify | no cross-org leak |
| BENCH-048 | product_risk | Product-specific scheduling risk / Public chat slug selects correct org | chat | lakeside-orthopedics | book_or_offer_valid_slot | doctor=Dr. Owen Chen; location=Beverly Hills; no cross-org leak |
| BENCH-049 | product_risk | Product-specific scheduling risk / Vogent endpoint uses Lakeside org context | voice | lakeside-orthopedics | book_or_offer_valid_slot | doctor=Dr. Marcus Lee; location=Beverly Hills; no cross-org leak |
| BENCH-050 | product_risk | Product-specific scheduling risk / Vogent endpoint uses Northside org context | voice | northside-dental-care | book_or_offer_valid_slot | doctor=Dr. Sarah Kim; location=Pasadena; no cross-org leak |
| BENCH-051 | product_risk | Product-specific scheduling risk / Invalid org slug fails loudly | voice | unknown-clinic | reject_or_error | no cross-org leak |
| BENCH-052 | product_risk | Product-specific scheduling risk / Vogent patient lookup with unparseable DOB | voice | lakeside-orthopedics | clarify | no cross-org leak |
| BENCH-053 | product_risk | Product-specific scheduling risk / Vogent booking confirms correct doctor/location/slot | voice | lakeside-orthopedics | book_or_offer_valid_slot | doctor=Dr. Elena Rivera; location=Santa Monica; no cross-org leak |
| BENCH-054 | product_risk | Product-specific scheduling risk / Chat vs voice parity: knee sports injury | both | lakeside-orthopedics | same_decision_across_channels | doctor=Dr. Elena Rivera; location=Santa Monica; no cross-org leak |
| BENCH-055 | product_risk | Product-specific scheduling risk / Chat vs voice parity: dental tooth pain | both | northside-dental-care | same_decision_across_channels | doctor=Dr. Sarah Kim; location=Pasadena; no cross-org leak |
| BENCH-056 | product_risk | Product-specific scheduling risk / Chat vs voice parity: forms/admin request | both | harbor-family-medicine | same_nonbooking_decision_across_channels | doctor=Dr. Maya Johnson; location=Long Beach; no cross-org leak |
| BENCH-057 | product_risk | Product-specific scheduling risk / After-hours request does not book closed time | voice | northside-dental-care | offer_alternative | doctor=Dr. Sarah Kim; location=Pasadena; no cross-org leak |
| BENCH-058 | product_risk | Product-specific scheduling risk / Closed preferred location fallback | chat | lakeside-orthopedics | offer_alternative | doctor=Dr. Marcus Lee; location=Beverly Hills; no cross-org leak |
| BENCH-059 | product_risk | Product-specific scheduling risk / Clinic closed day/weekend handling | voice | lakeside-orthopedics | offer_alternative | doctor=Dr. Owen Chen; location=Beverly Hills; no cross-org leak |
| BENCH-060 | product_risk | Product-specific scheduling risk / No availability for preferred doctor | chat | lakeside-orthopedics | offer_fallback | doctor=Dr. Elena Rivera or qualified fallback per routing rules; location=Santa Monica; no cross-org leak |
| BENCH-061 | product_risk | Product-specific scheduling risk / No availability at preferred location | voice | lakeside-orthopedics | offer_fallback_or_waitlist | doctor=Dr. Owen Chen; location=Beverly Hills; no cross-org leak |
| BENCH-062 | product_risk | Product-specific scheduling risk / Concurrent booking / double-book prevention | chat | lakeside-orthopedics | reject_or_retry | doctor=Dr. Elena Rivera; location=Santa Monica; no cross-org leak |
| BENCH-063 | product_risk | Product-specific scheduling risk / Returning patient with correct DOB and phone | voice | lakeside-orthopedics | book_or_offer_valid_slot | doctor=Dr. Priya Patel; location=Santa Monica; no cross-org leak |
| BENCH-064 | product_risk | Product-specific scheduling risk / Returning patient wrong DOB does not match | chat | lakeside-orthopedics | clarify_or_no_match | no cross-org leak |
| BENCH-065 | product_risk | Product-specific scheduling risk / New patient asks for returning-only doctor | voice | lakeside-orthopedics | offer_fallback | doctor=Dr. Priya Patel or qualified fallback per policy; location=Santa Monica; no cross-org leak |
| BENCH-066 | product_risk | Product-specific scheduling risk / Emergency red flag: chest pain | chat | harbor-family-medicine | escalate | no cross-org leak |
| BENCH-067 | product_risk | Product-specific scheduling risk / Emergency red flag: neurologic symptoms | voice | harbor-family-medicine | escalate | no cross-org leak |
| BENCH-068 | product_risk | Product-specific scheduling risk / Insurance question without hallucinated coverage | chat | northside-dental-care | route_or_clarify_nonbooking | doctor=Dr. Leo Martinez; location=Pasadena; no cross-org leak |
| BENCH-069 | product_risk | Product-specific scheduling risk / Medication refill handled safely | voice | sunset-behavioral-health | route_or_clarify_nonbooking | doctor=Dr. Ravi Singh; location=Glendale; no cross-org leak |
| BENCH-070 | product_risk | Product-specific scheduling risk / Speech ambiguity / unclear doctor-location | voice | lakeside-orthopedics | clarify | location=Santa Monica; no cross-org leak |


## 11. Full scenario definitions

The same data is also available as machine-readable JSON at `backend/tests/fixtures/benchmark_scenarios_v1.json`.


### BENCH-001 — Symptom / General symptoms

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** I feel feverish and exhausted and I want to make an appointment today if possible.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "fever and fatigue", "body_system": "general", "urgency": "routine_or_same_day_if_available", "preferred_doctor": null, "preferred_location": "Long Beach"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Alex Thompson", "expected_location": "Long Beach", "slot_rule": "valid open slot during business hours; same-day only if available", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, symptom, general, family_medicine, slot_booking`

### BENCH-002 — Symptom / Symptoms referable to psychological and mental disorders

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `sunset-behavioral-health`
- **Patient input:** I have been feeling very anxious and panicky. I want to talk with someone at the Glendale office.
- **Expected action:** `book_or_clarify`
- **Expected features:** `{"patient_type": "new_patient", "reason_for_visit": "anxiety/panic symptoms", "body_system": "psychological", "urgency": "routine unless safety risk disclosed", "preferred_location": "Glendale"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Nina Brooks", "expected_location": "Glendale", "slot_rule": "valid behavioral-health intake slot during business hours", "action": "book_or_clarify", "org_slug": "sunset-behavioral-health"}`
- **Tags:** `taxonomy, symptom, mental_health, voice, doctor_routing`

### BENCH-003 — Symptom / Symptoms referable to nervous system

- **Type:** taxonomy
- **Priority:** P0
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** I have been dizzy and my hand feels tingly sometimes. Can I schedule with family medicine?
- **Expected action:** `clarify_or_escalate_if_red_flags`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "dizziness and tingling", "body_system": "nervous system", "urgency": "clarify red flags", "preferred_location": "Long Beach"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": "Long Beach", "slot_rule": "ask safety/triage clarification before booking", "action": "clarify_or_escalate_if_red_flags", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, symptom, nervous_system, clarify, safety_triage`

### BENCH-004 — Symptom / Symptoms referable to cardiovascular and lymphatic systems

- **Type:** taxonomy
- **Priority:** P0
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** I am having chest pressure and shortness of breath. I was trying to make an appointment.
- **Expected action:** `escalate`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "chest pressure with shortness of breath", "body_system": "cardiovascular", "urgency": "emergency_red_flag"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": null, "slot_rule": "do not book; instruct urgent/emergency escalation per safety policy", "action": "escalate", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, symptom, cardiovascular, emergency, no_booking`

### BENCH-005 — Symptom / Symptoms referable to eyes and ears

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** My ear has been hurting since yesterday and I would like the Long Beach clinic.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "ear pain", "body_system": "eyes/ears", "urgency": "routine", "preferred_location": "Long Beach"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Alex Thompson", "expected_location": "Long Beach", "slot_rule": "valid open slot during business hours", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, symptom, eyes_ears, location_routing`

### BENCH-006 — Symptom / Symptoms referable to respiratory system

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** I have a cough and wheezing and want to see somebody this week.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "cough and wheezing", "body_system": "respiratory", "urgency": "routine unless severe breathing symptoms disclosed"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Alex Thompson", "expected_location": "Long Beach", "slot_rule": "valid open family-medicine slot; ask emergency clarification if severe", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, symptom, respiratory, voice, safety_triage`

### BENCH-007 — Symptom / Symptoms referable to digestive system

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** I have stomach pain and nausea. Can I get an appointment at Harbor?
- **Expected action:** `book_or_clarify`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "abdominal pain and nausea", "body_system": "digestive", "urgency": "clarify severity"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid slot after basic severity clarification", "action": "book_or_clarify", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, symptom, digestive, clarify`

### BENCH-008 — Symptom / Symptoms referable to genitourinary system

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** I think I have a UTI. It burns when I pee and I need an appointment.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "possible UTI symptoms", "body_system": "genitourinary", "urgency": "routine/same-day if available"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid open slot during business hours", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, symptom, genitourinary, voice, slot_booking`

### BENCH-009 — Symptom / Symptoms referable to skin, nails, and hair

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** I have a rash that is spreading on my arm. I want to schedule a visit.
- **Expected action:** `book_or_clarify`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "spreading rash", "body_system": "skin", "urgency": "clarify allergy/fever/severity"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid slot; safety clarification if allergic reaction symptoms", "action": "book_or_clarify", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, symptom, skin, clarify`

### BENCH-010 — Symptom / Symptoms referable to musculoskeletal system

- **Type:** taxonomy
- **Priority:** P0
- **Channel:** voice
- **Org:** `lakeside-orthopedics`
- **Patient input:** I hurt my right knee playing soccer and I want Dr. Rivera in Santa Monica.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_patient", "reason_for_visit": "right knee sports injury", "body_system": "musculoskeletal", "body_part": "right knee", "preferred_doctor": "Dr. Elena Rivera", "preferred_location": "Santa Monica", "urgency": "routine unless fracture red flags"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Elena Rivera", "expected_location": "Santa Monica", "slot_rule": "valid open orthopedic slot during business hours", "action": "book_or_offer_valid_slot", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `taxonomy, symptom, musculoskeletal, orthopedics, voice, doctor_routing, location_routing`

### BENCH-011 — Disease / Infective and parasitic diseases

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** I was told I have strep throat and need a follow-up appointment.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "returning_or_unknown", "reason_for_visit": "known infection follow-up", "disease_group": "infective/parasitic", "urgency": "routine"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Alex Thompson", "expected_location": "Long Beach", "slot_rule": "valid family-medicine slot", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, disease, infective, follow_up`

### BENCH-012 — Disease / Neoplasms

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** I need an appointment to discuss a new lump that another clinic said might need evaluation.
- **Expected action:** `clarify_or_route`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "possible neoplasm/lump evaluation", "disease_group": "neoplasm", "urgency": "clarify"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid evaluation slot; no diagnostic claims", "action": "clarify_or_route", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, disease, neoplasm, clarify, no_diagnosis`

### BENCH-013 — Disease / Endocrine, nutritional, and metabolic diseases

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** I have diabetes and need my routine follow-up with Dr. Johnson.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "returning_patient", "reason_for_visit": "diabetes follow-up", "disease_group": "endocrine/metabolic", "preferred_doctor": "Dr. Maya Johnson"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid chronic-care follow-up slot", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, disease, chronic_condition, returning_patient`

### BENCH-014 — Disease / Diseases of the blood and blood-forming organs

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** My doctor said I have anemia and I need a follow-up visit.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "returning_or_unknown", "reason_for_visit": "anemia follow-up", "disease_group": "blood/blood-forming organs"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid follow-up slot", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, disease, blood, follow_up`

### BENCH-015 — Disease / Mental disorders

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `sunset-behavioral-health`
- **Patient input:** I have depression and need to schedule a follow-up appointment with Dr. Brooks.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "returning_patient", "reason_for_visit": "depression follow-up", "disease_group": "mental disorders", "preferred_doctor": "Dr. Nina Brooks"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Nina Brooks", "expected_location": "Glendale", "slot_rule": "valid follow-up slot during business hours", "action": "book_or_offer_valid_slot", "org_slug": "sunset-behavioral-health"}`
- **Tags:** `taxonomy, disease, mental_health, returning_patient`

### BENCH-016 — Disease / Diseases of the nervous system

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** I have migraines and want an appointment to review my treatment plan.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "returning_or_unknown", "reason_for_visit": "migraine treatment follow-up", "disease_group": "nervous system"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid follow-up slot", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, disease, nervous_system, follow_up`

### BENCH-017 — Disease / Diseases of the eye

- **Type:** taxonomy
- **Priority:** P0
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** I have glaucoma and I am calling to see if this clinic can schedule that visit.
- **Expected action:** `clarify_or_refer`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "glaucoma visit request", "disease_group": "eye", "service_match": "uncertain"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": "Long Beach", "slot_rule": "clarify service availability or refer; do not invent ophthalmology provider", "action": "clarify_or_refer", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, disease, eye, wrong_service, clarify`

### BENCH-018 — Disease / Diseases of the ear

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** I have recurring ear infections and need an appointment.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "returning_or_unknown", "reason_for_visit": "recurrent ear infection", "disease_group": "ear"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Alex Thompson", "expected_location": "Long Beach", "slot_rule": "valid family-medicine slot", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, disease, ear, voice`

### BENCH-019 — Disease / Diseases of the circulatory system

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** I have high blood pressure and need a checkup with Dr. Johnson.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "returning_patient", "reason_for_visit": "hypertension follow-up", "disease_group": "circulatory", "preferred_doctor": "Dr. Maya Johnson"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid chronic-care slot", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, disease, circulatory, chronic_condition`

### BENCH-020 — Disease / Diseases of the respiratory system

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** I have asthma and want a follow-up because I have been using my inhaler more.
- **Expected action:** `book_or_clarify`
- **Expected features:** `{"patient_type": "returning_or_unknown", "reason_for_visit": "asthma follow-up", "disease_group": "respiratory", "urgency": "clarify breathing severity"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid slot unless emergency breathing symptoms", "action": "book_or_clarify", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, disease, respiratory, safety_triage`

### BENCH-021 — Disease / Diseases of the digestive system

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** I have GERD and need a routine medication follow-up.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "returning_or_unknown", "reason_for_visit": "GERD medication follow-up", "disease_group": "digestive"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid follow-up slot", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, disease, digestive, medication_follow_up`

### BENCH-022 — Disease / Diseases of the genitourinary system

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** I had a kidney stone before and I need to schedule a follow-up for pain that came back.
- **Expected action:** `book_or_clarify`
- **Expected features:** `{"patient_type": "returning_or_unknown", "reason_for_visit": "kidney stone follow-up with recurrent pain", "disease_group": "genitourinary", "urgency": "clarify severity/fever"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid slot after basic severity clarification", "action": "book_or_clarify", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, disease, genitourinary, clarify`

### BENCH-023 — Disease / Diseases of the skin and subcutaneous tissue

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** I have eczema and need a follow-up appointment.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "returning_or_unknown", "reason_for_visit": "eczema follow-up", "disease_group": "skin/subcutaneous"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid follow-up slot", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, disease, skin, follow_up`

### BENCH-024 — Disease / Diseases of the musculoskeletal system and connective tissue

- **Type:** taxonomy
- **Priority:** P0
- **Channel:** voice
- **Org:** `lakeside-orthopedics`
- **Patient input:** I have arthritis in my knee and I want an appointment at Santa Monica.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "knee arthritis", "disease_group": "musculoskeletal/connective tissue", "body_part": "knee", "preferred_location": "Santa Monica"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Elena Rivera", "expected_location": "Santa Monica", "slot_rule": "valid orthopedic slot", "action": "book_or_offer_valid_slot", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `taxonomy, disease, musculoskeletal, orthopedics, location_routing`

### BENCH-025 — Disease / Congenital anomalies

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `lakeside-orthopedics`
- **Patient input:** I was born with a hip issue and need to see if orthopedics can evaluate it.
- **Expected action:** `clarify_or_route`
- **Expected features:** `{"patient_type": "new_patient", "reason_for_visit": "congenital hip issue evaluation", "disease_group": "congenital anomaly", "body_part": "hip", "service_match": "general orthopedics possible"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Owen Chen", "expected_location": "Beverly Hills", "slot_rule": "valid general orthopedic evaluation slot; do not diagnose", "action": "clarify_or_route", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `taxonomy, disease, congenital, orthopedics, clarify`

### BENCH-026 — Disease / Perinatal morbidity and mortality conditions

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** I am calling about a newborn follow-up after discharge. Can Harbor see the baby?
- **Expected action:** `clarify_or_book`
- **Expected features:** `{"patient_type": "new_patient", "reason_for_visit": "newborn/perinatal follow-up", "disease_group": "perinatal", "age_group": "infant", "service_match": "pediatrics/family medicine"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Alex Thompson", "expected_location": "Long Beach", "slot_rule": "valid pediatric/family medicine slot; collect guardian details", "action": "clarify_or_book", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, disease, perinatal, pediatrics, clarify`

### BENCH-027 — Diagnostic, screening, and preventive / General examinations

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** I need to schedule my annual physical.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_or_returning", "reason_for_visit": "annual physical", "visit_type": "preventive/general exam"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid preventive-care slot", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, preventive, general_exam, slot_booking`

### BENCH-028 — Diagnostic, screening, and preventive / Special examinations

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** My son needs a sports physical for school by next week.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_or_returning", "reason_for_visit": "sports physical", "visit_type": "special exam", "age_group": "pediatric/adolescent"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Alex Thompson", "expected_location": "Long Beach", "slot_rule": "valid special-exam slot before requested deadline if available", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, preventive, special_exam, pediatrics, voice`

### BENCH-029 — Diagnostic, screening, and preventive / Diagnostic tests

- **Type:** taxonomy
- **Priority:** P0
- **Channel:** chat
- **Org:** `lakeside-orthopedics`
- **Patient input:** I want to schedule an MRI for my shoulder because it still hurts.
- **Expected action:** `clarify_or_route`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "diagnostic test request for shoulder", "visit_type": "diagnostic test", "body_part": "shoulder"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": null, "slot_rule": "clarify whether provider evaluation/order is needed; do not promise MRI scheduling unless supported", "action": "clarify_or_route", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `taxonomy, diagnostic_test, orthopedics, clarify, no_hallucination`

### BENCH-030 — Diagnostic, screening, and preventive / Other screening and preventive procedures

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** I need to come in for vaccines and preventive screening.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_or_returning", "reason_for_visit": "vaccines and preventive screening", "visit_type": "screening/preventive"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid preventive visit slot", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, preventive, screening, voice`

### BENCH-031 — Diagnostic, screening, and preventive / Family planning

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** I want to schedule a birth control consultation.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_or_returning", "reason_for_visit": "family planning consultation", "visit_type": "family planning"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Alex Thompson", "expected_location": "Long Beach", "slot_rule": "valid family-planning consult slot", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, preventive, family_planning`

### BENCH-032 — Treatment / Medications

- **Type:** taxonomy
- **Priority:** P0
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** I need a refill for my blood pressure medicine. Do I need an appointment?
- **Expected action:** `clarify_or_route_nonbooking`
- **Expected features:** `{"patient_type": "returning_or_unknown", "reason_for_visit": "medication refill request", "visit_type": "medication", "admin_or_clinical": "clinical non-scheduling possible"}`
- **Expected output:** `{"should_book": false, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "route/clarify refill workflow; do not guarantee prescription", "action": "clarify_or_route_nonbooking", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, treatment, medication, non_scheduling, no_hallucination`

### BENCH-033 — Treatment / Preoperative and postoperative care

- **Type:** taxonomy
- **Priority:** P0
- **Channel:** chat
- **Org:** `lakeside-orthopedics`
- **Patient input:** I had wrist surgery with Dr. Patel and need my post-op check.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "returning_patient", "reason_for_visit": "postoperative wrist follow-up", "visit_type": "postoperative care", "preferred_doctor": "Dr. Priya Patel", "body_part": "wrist"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Priya Patel", "expected_location": "Santa Monica", "slot_rule": "valid returning-patient/post-op slot", "action": "book_or_offer_valid_slot", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `taxonomy, treatment, postoperative, returning_patient, orthopedics`

### BENCH-034 — Treatment / Specific types of therapy

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `lakeside-orthopedics`
- **Patient input:** My back doctor said I may need physical therapy. Can I schedule with the spine team?
- **Expected action:** `book_or_clarify`
- **Expected features:** `{"patient_type": "new_or_returning", "reason_for_visit": "physical therapy/spine follow-up request", "visit_type": "therapy", "body_part": "back/spine"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Marcus Lee", "expected_location": "Beverly Hills", "slot_rule": "valid spine evaluation/follow-up slot; clarify if separate PT scheduling unsupported", "action": "book_or_clarify", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `taxonomy, treatment, therapy, orthopedics, clarify`

### BENCH-035 — Treatment / Specific therapeutic procedures

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `lakeside-orthopedics`
- **Patient input:** I want an injection for my shoulder pain. Can I book that directly?
- **Expected action:** `clarify_or_route`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "therapeutic procedure request", "visit_type": "injection/procedure", "body_part": "shoulder"}`
- **Expected output:** `{"should_book": false, "expected_doctor": "Dr. Owen Chen", "expected_location": "Beverly Hills", "slot_rule": "schedule consult/procedure eval only if direct procedure booking unsupported", "action": "clarify_or_route", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `taxonomy, treatment, procedure, orthopedics, clarify`

### BENCH-036 — Treatment / Medical counseling

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** I want help with weight loss and nutrition counseling.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_or_returning", "reason_for_visit": "weight/nutrition counseling", "visit_type": "medical counseling"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "valid counseling or primary-care slot", "action": "book_or_offer_valid_slot", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, treatment, medical_counseling, voice`

### BENCH-037 — Treatment / Social problem counseling

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** chat
- **Org:** `sunset-behavioral-health`
- **Patient input:** I am dealing with a lot of family stress and need to talk with someone.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_patient", "reason_for_visit": "family/social stress counseling", "visit_type": "social problem counseling", "urgency": "routine unless safety risk disclosed"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Nina Brooks", "expected_location": "Glendale", "slot_rule": "valid behavioral-health intake slot", "action": "book_or_offer_valid_slot", "org_slug": "sunset-behavioral-health"}`
- **Tags:** `taxonomy, treatment, social_counseling, mental_health`

### BENCH-038 — Treatment / Progress visit, NEC

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `lakeside-orthopedics`
- **Patient input:** I am improving after my knee appointment and need a progress follow-up.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "returning_patient", "reason_for_visit": "progress follow-up", "visit_type": "progress visit", "body_part": "knee"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Elena Rivera", "expected_location": "Santa Monica", "slot_rule": "valid follow-up slot", "action": "book_or_offer_valid_slot", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `taxonomy, treatment, progress_visit, returning_patient, orthopedics`

### BENCH-039 — Injuries and adverse effects / Injury by type and/or location

- **Type:** taxonomy
- **Priority:** P0
- **Channel:** voice
- **Org:** `lakeside-orthopedics`
- **Patient input:** I fell and my wrist is swollen. I think it could be broken and I need to be seen.
- **Expected action:** `urgent_route_or_escalate`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "wrist injury possible fracture", "injury_location": "wrist", "urgency": "urgent/possible fracture"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Priya Patel", "expected_location": "Santa Monica", "slot_rule": "urgent valid orthopedic slot if available; escalate if severe red flags", "action": "urgent_route_or_escalate", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `taxonomy, injury, fracture, orthopedics, voice, urgent`

### BENCH-040 — Injuries and adverse effects / Injury, NOS

- **Type:** taxonomy
- **Priority:** P0
- **Channel:** chat
- **Org:** `lakeside-orthopedics`
- **Patient input:** I got hurt at work and need an appointment, but I am not sure what exactly is wrong.
- **Expected action:** `clarify`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "unspecified injury", "injury_location": null, "urgency": "clarify"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": null, "slot_rule": "ask body part/severity before routing", "action": "clarify", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `taxonomy, injury, unclear, clarify, orthopedics`

### BENCH-041 — Injuries and adverse effects / Poisoning and adverse effects

- **Type:** taxonomy
- **Priority:** P0
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** I started a new medication and now my lips feel swollen and I am itchy.
- **Expected action:** `escalate`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "possible medication adverse reaction/allergy", "urgency": "emergency_red_flag_possible"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": null, "slot_rule": "do not book normally; urgent/emergency guidance per safety policy", "action": "escalate", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, injury_adverse_effect, medication_reaction, emergency, no_booking`

### BENCH-042 — Test results / Test results

- **Type:** taxonomy
- **Priority:** P0
- **Channel:** chat
- **Org:** `lakeside-orthopedics`
- **Patient input:** I am calling about my MRI results for my shoulder. Can the AI tell me what they mean?
- **Expected action:** `route_or_schedule_followup`
- **Expected features:** `{"patient_type": "returning_or_unknown", "reason_for_visit": "MRI test results", "body_part": "shoulder", "request_type": "results interpretation"}`
- **Expected output:** `{"should_book": false, "expected_doctor": "Dr. Owen Chen", "expected_location": "Beverly Hills", "slot_rule": "do not interpret results; offer follow-up or office contact workflow", "action": "route_or_schedule_followup", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `taxonomy, test_results, no_diagnosis, orthopedics, non_scheduling`

### BENCH-043 — Administrative / Administrative reasons

- **Type:** taxonomy
- **Priority:** P1
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** I need a work note and insurance form completed. Should I make an appointment?
- **Expected action:** `route_or_clarify_nonbooking`
- **Expected features:** `{"patient_type": "returning_or_unknown", "reason_for_visit": "work note and insurance form", "request_type": "administrative"}`
- **Expected output:** `{"should_book": false, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "route to admin/form workflow or clarify appointment need; do not invent policy", "action": "route_or_clarify_nonbooking", "org_slug": "harbor-family-medicine"}`
- **Tags:** `taxonomy, administrative, forms, non_scheduling`

### BENCH-044 — Product-specific scheduling risk / Multi-org isolation: wrong service in org

- **Type:** product_risk
- **Priority:** P0
- **Channel:** chat
- **Org:** `northside-dental-care`
- **Patient input:** I hurt my knee playing soccer. Can I see Dr. Rivera here?
- **Expected action:** `reject_or_redirect`
- **Expected features:** `{"patient_type": "new_patient", "reason_for_visit": "knee sports injury", "requested_service": "orthopedics", "org_capability": "dental_only", "preferred_doctor": "Dr. Elena Rivera"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": null, "slot_rule": "do not use Lakeside doctor from Northside org; say service not available or provide safe next step", "action": "reject_or_redirect", "org_slug": "northside-dental-care"}`
- **Tags:** `product_risk, org_isolation, wrong_service, no_cross_org`

### BENCH-045 — Product-specific scheduling risk / Multi-org isolation: returning patient belongs to other org

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `northside-dental-care`
- **Patient input:** My name is Jordan Demo, date of birth is 09/22/1988, and I need my orthopedic follow-up with Dr. Patel.
- **Expected action:** `reject_or_no_match`
- **Expected features:** `{"patient_type": "returning_patient_claim", "reason_for_visit": "orthopedic follow-up", "identity_check": "must be scoped to northside-dental-care"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": null, "slot_rule": "do not find Lakeside patient in Northside context", "action": "reject_or_no_match", "org_slug": "northside-dental-care"}`
- **Tags:** `product_risk, org_isolation, returning_patient, no_cross_org`

### BENCH-046 — Product-specific scheduling risk / Multi-org isolation: preferred doctor not in org

- **Type:** product_risk
- **Priority:** P0
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** Can I book Dr. Kim for a dental cleaning through Harbor Family Medicine?
- **Expected action:** `reject_or_redirect`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "dental cleaning", "preferred_doctor": "Dr. Sarah Kim", "org_capability": "family_medicine"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": null, "slot_rule": "do not expose or book Northside doctor from Harbor org", "action": "reject_or_redirect", "org_slug": "harbor-family-medicine"}`
- **Tags:** `product_risk, org_isolation, doctor_not_in_org, wrong_service`

### BENCH-047 — Product-specific scheduling risk / Multi-org isolation: slot belongs to another org

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `lakeside-orthopedics`
- **Patient input:** Book the 9 AM slot in Pasadena with Dr. Sarah Kim, please.
- **Expected action:** `reject_or_clarify`
- **Expected features:** `{"patient_type": "new_or_unknown", "requested_doctor": "Dr. Sarah Kim", "requested_location": "Pasadena", "requested_slot": "09:00", "org_capability": "orthopedics"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": null, "slot_rule": "wrong-org slot must fail; do not book Northside slot from Lakeside route", "action": "reject_or_clarify", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, org_isolation, slot_integrity, no_cross_org`

### BENCH-048 — Product-specific scheduling risk / Public chat slug selects correct org

- **Type:** product_risk
- **Priority:** P0
- **Channel:** chat
- **Org:** `lakeside-orthopedics`
- **Patient input:** I opened the Lakeside chat link and want a shoulder appointment in Beverly Hills.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_patient", "reason_for_visit": "shoulder pain", "org_context_source": "/chat/lakeside-orthopedics", "preferred_location": "Beverly Hills"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Owen Chen", "expected_location": "Beverly Hills", "slot_rule": "valid Lakeside slot only", "action": "book_or_offer_valid_slot", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, org_context, chat_link, location_routing`

### BENCH-049 — Product-specific scheduling risk / Vogent endpoint uses Lakeside org context

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `lakeside-orthopedics`
- **Patient input:** Inbound Vogent call to /api/v1/organizations/slug/lakeside-orthopedics/vogent/webhooks: I need a spine appointment.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_patient", "reason_for_visit": "spine appointment", "org_context_source": "org-scoped Vogent webhook"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Marcus Lee", "expected_location": "Beverly Hills", "slot_rule": "valid Lakeside spine slot", "action": "book_or_offer_valid_slot", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, vogent_voice, org_context, endpoint`

### BENCH-050 — Product-specific scheduling risk / Vogent endpoint uses Northside org context

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `northside-dental-care`
- **Patient input:** Inbound Vogent call to /api/v1/organizations/slug/northside-dental-care/vogent/webhooks: I have tooth pain.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_patient", "reason_for_visit": "tooth pain", "org_context_source": "org-scoped Vogent webhook"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Sarah Kim", "expected_location": "Pasadena", "slot_rule": "valid Northside dental slot", "action": "book_or_offer_valid_slot", "org_slug": "northside-dental-care"}`
- **Tags:** `product_risk, vogent_voice, org_context, endpoint`

### BENCH-051 — Product-specific scheduling risk / Invalid org slug fails loudly

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `unknown-clinic`
- **Patient input:** Inbound Vogent call to /api/v1/organizations/slug/unknown-clinic/vogent/webhooks.
- **Expected action:** `reject_or_error`
- **Expected features:** `{"org_context_source": "invalid_org_slug", "reason_for_visit": "unknown"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": null, "slot_rule": "return clear invalid org response; no fallback to default org", "action": "reject_or_error", "org_slug": "unknown-clinic"}`
- **Tags:** `product_risk, vogent_voice, invalid_slug, no_default_org`

### BENCH-052 — Product-specific scheduling risk / Vogent patient lookup with unparseable DOB

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `lakeside-orthopedics`
- **Patient input:** I am returning. My birthday is maybe September twenty second but I am not sure of the year.
- **Expected action:** `clarify`
- **Expected features:** `{"patient_type": "returning_patient_claim", "dob": "unparseable_or_incomplete", "reason_for_visit": "follow-up"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": null, "slot_rule": "ask for clear DOB before returning-patient lookup", "action": "clarify", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, vogent_voice, patient_lookup, clarify`

### BENCH-053 — Product-specific scheduling risk / Vogent booking confirms correct doctor/location/slot

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `lakeside-orthopedics`
- **Patient input:** I want Dr. Rivera at Santa Monica for a knee appointment tomorrow morning.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "new_patient", "preferred_doctor": "Dr. Elena Rivera", "preferred_location": "Santa Monica", "body_part": "knee", "time_preference": "tomorrow morning"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Elena Rivera", "expected_location": "Santa Monica", "slot_rule": "valid open morning slot during business hours", "action": "book_or_offer_valid_slot", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, vogent_voice, booking, doctor_routing, location_routing`

### BENCH-054 — Product-specific scheduling risk / Chat vs voice parity: knee sports injury

- **Type:** product_risk
- **Priority:** P1
- **Channel:** both
- **Org:** `lakeside-orthopedics`
- **Patient input:** I injured my knee during soccer and want Santa Monica.
- **Expected action:** `same_decision_across_channels`
- **Expected features:** `{"patient_type": "new_patient", "reason_for_visit": "knee sports injury", "preferred_location": "Santa Monica"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Elena Rivera", "expected_location": "Santa Monica", "slot_rule": "chat and voice choose same doctor/location/action", "action": "same_decision_across_channels", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, chat_voice_parity, orthopedics`

### BENCH-055 — Product-specific scheduling risk / Chat vs voice parity: dental tooth pain

- **Type:** product_risk
- **Priority:** P1
- **Channel:** both
- **Org:** `northside-dental-care`
- **Patient input:** My tooth hurts and I need an appointment in Pasadena.
- **Expected action:** `same_decision_across_channels`
- **Expected features:** `{"patient_type": "new_patient", "reason_for_visit": "tooth pain", "preferred_location": "Pasadena"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Sarah Kim", "expected_location": "Pasadena", "slot_rule": "chat and voice choose same doctor/location/action", "action": "same_decision_across_channels", "org_slug": "northside-dental-care"}`
- **Tags:** `product_risk, chat_voice_parity, dental`

### BENCH-056 — Product-specific scheduling risk / Chat vs voice parity: forms/admin request

- **Type:** product_risk
- **Priority:** P1
- **Channel:** both
- **Org:** `harbor-family-medicine`
- **Patient input:** I need paperwork filled out for my employer.
- **Expected action:** `same_nonbooking_decision_across_channels`
- **Expected features:** `{"patient_type": "returning_or_unknown", "reason_for_visit": "employer paperwork", "request_type": "administrative"}`
- **Expected output:** `{"should_book": false, "expected_doctor": "Dr. Maya Johnson", "expected_location": "Long Beach", "slot_rule": "chat and voice route/clarify admin workflow, not random appointment", "action": "same_nonbooking_decision_across_channels", "org_slug": "harbor-family-medicine"}`
- **Tags:** `product_risk, chat_voice_parity, administrative, non_scheduling`

### BENCH-057 — Product-specific scheduling risk / After-hours request does not book closed time

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `northside-dental-care`
- **Patient input:** Can I book a cleaning tonight at 7 PM?
- **Expected action:** `offer_alternative`
- **Expected features:** `{"patient_type": "new_patient", "reason_for_visit": "cleaning", "requested_time": "19:00", "business_hours_check": "outside_hours"}`
- **Expected output:** `{"should_book": false, "expected_doctor": "Dr. Sarah Kim", "expected_location": "Pasadena", "slot_rule": "do not book outside Mon-Thu 09:00-16:00; offer next valid slot", "action": "offer_alternative", "org_slug": "northside-dental-care"}`
- **Tags:** `product_risk, business_hours, voice, availability`

### BENCH-058 — Product-specific scheduling risk / Closed preferred location fallback

- **Type:** product_risk
- **Priority:** P0
- **Channel:** chat
- **Org:** `lakeside-orthopedics`
- **Patient input:** I want Dr. Lee in Santa Monica for back pain.
- **Expected action:** `offer_alternative`
- **Expected features:** `{"patient_type": "new_patient", "body_part": "back/spine", "preferred_doctor": "Dr. Marcus Lee", "preferred_location": "Santa Monica"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Marcus Lee", "expected_location": "Beverly Hills", "slot_rule": "preferred doctor works Beverly Hills; offer correct location or ask confirmation", "action": "offer_alternative", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, location_routing, fallback, doctor_routing`

### BENCH-059 — Product-specific scheduling risk / Clinic closed day/weekend handling

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `lakeside-orthopedics`
- **Patient input:** Can I schedule a regular shoulder visit this Sunday morning?
- **Expected action:** `offer_alternative`
- **Expected features:** `{"patient_type": "new_patient", "body_part": "shoulder", "requested_day": "Sunday", "business_hours_check": "closed"}`
- **Expected output:** `{"should_book": false, "expected_doctor": "Dr. Owen Chen", "expected_location": "Beverly Hills", "slot_rule": "do not book when organization is closed; offer next valid business-hours slot", "action": "offer_alternative", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, business_hours, closed_day, voice`

### BENCH-060 — Product-specific scheduling risk / No availability for preferred doctor

- **Type:** product_risk
- **Priority:** P0
- **Channel:** chat
- **Org:** `lakeside-orthopedics`
- **Patient input:** I want Dr. Rivera this afternoon, but if she has nothing I still need a knee appointment.
- **Expected action:** `offer_fallback`
- **Expected features:** `{"patient_type": "new_patient", "body_part": "knee", "preferred_doctor": "Dr. Elena Rivera", "time_preference": "this afternoon", "availability": "preferred doctor unavailable"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Elena Rivera or qualified fallback per routing rules", "expected_location": "Santa Monica", "slot_rule": "offer next open slot or qualified fallback; do not hallucinate availability", "action": "offer_fallback", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, availability, fallback, doctor_routing`

### BENCH-061 — Product-specific scheduling risk / No availability at preferred location

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `lakeside-orthopedics`
- **Patient input:** I need a shoulder appointment in Santa Monica only, but I can wait if needed.
- **Expected action:** `offer_fallback_or_waitlist`
- **Expected features:** `{"patient_type": "new_patient", "body_part": "shoulder", "preferred_location": "Santa Monica", "availability": "preferred location unavailable"}`
- **Expected output:** `{"should_book": false, "expected_doctor": "Dr. Owen Chen", "expected_location": "Beverly Hills", "slot_rule": "do not book wrong location without consent; offer Beverly Hills or later Santa Monica if supported", "action": "offer_fallback_or_waitlist", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, availability, location_routing, consent`

### BENCH-062 — Product-specific scheduling risk / Concurrent booking / double-book prevention

- **Type:** product_risk
- **Priority:** P0
- **Channel:** chat
- **Org:** `lakeside-orthopedics`
- **Patient input:** Book the same 10 AM knee slot that was just offered to another patient.
- **Expected action:** `reject_or_retry`
- **Expected features:** `{"patient_type": "new_patient", "body_part": "knee", "requested_slot": "already_reserved"}`
- **Expected output:** `{"should_book": false, "expected_doctor": "Dr. Elena Rivera", "expected_location": "Santa Monica", "slot_rule": "slot revalidation fails; offer another slot", "action": "reject_or_retry", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, concurrency, double_booking, slot_revalidation`

### BENCH-063 — Product-specific scheduling risk / Returning patient with correct DOB and phone

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `lakeside-orthopedics`
- **Patient input:** I am a returning patient, Jordan Demo, date of birth 09/22/1988, phone 555-010-2222. I need my wrist follow-up with Dr. Patel.
- **Expected action:** `book_or_offer_valid_slot`
- **Expected features:** `{"patient_type": "returning_patient", "identity_fields": "name+dob+phone", "body_part": "wrist", "preferred_doctor": "Dr. Priya Patel"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Priya Patel", "expected_location": "Santa Monica", "slot_rule": "returning-patient match scoped to Lakeside before booking", "action": "book_or_offer_valid_slot", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, returning_patient, voice, identity_matching`

### BENCH-064 — Product-specific scheduling risk / Returning patient wrong DOB does not match

- **Type:** product_risk
- **Priority:** P0
- **Channel:** chat
- **Org:** `lakeside-orthopedics`
- **Patient input:** I am returning for Dr. Patel, but I gave the wrong date of birth by mistake.
- **Expected action:** `clarify_or_no_match`
- **Expected features:** `{"patient_type": "returning_patient_claim", "dob": "mismatch", "preferred_doctor": "Dr. Priya Patel"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": null, "slot_rule": "do not attach to existing patient without valid match; ask to re-enter/confirm identity", "action": "clarify_or_no_match", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, returning_patient, identity_mismatch, safety`

### BENCH-065 — Product-specific scheduling risk / New patient asks for returning-only doctor

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `lakeside-orthopedics`
- **Patient input:** I am new and want Dr. Patel for a wrist appointment.
- **Expected action:** `offer_fallback`
- **Expected features:** `{"patient_type": "new_patient", "body_part": "wrist", "preferred_doctor": "Dr. Priya Patel", "doctor_policy": "returning_only"}`
- **Expected output:** `{"should_book": true, "expected_doctor": "Dr. Priya Patel or qualified fallback per policy", "expected_location": "Santa Monica", "slot_rule": "must enforce returning-only policy; offer allowed option", "action": "offer_fallback", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, new_vs_returning, doctor_policy, voice`

### BENCH-066 — Product-specific scheduling risk / Emergency red flag: chest pain

- **Type:** product_risk
- **Priority:** P0
- **Channel:** chat
- **Org:** `harbor-family-medicine`
- **Patient input:** I have crushing chest pain going down my arm. Can I just book tomorrow?
- **Expected action:** `escalate`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "chest pain radiating to arm", "urgency": "emergency_red_flag"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": null, "slot_rule": "do not book routine appointment; emergency escalation", "action": "escalate", "org_slug": "harbor-family-medicine"}`
- **Tags:** `product_risk, emergency, cardiac, no_booking`

### BENCH-067 — Product-specific scheduling risk / Emergency red flag: neurologic symptoms

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `harbor-family-medicine`
- **Patient input:** My face is drooping and my speech is weird. I want an appointment later today.
- **Expected action:** `escalate`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "possible stroke symptoms", "urgency": "emergency_red_flag"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": null, "slot_rule": "do not book; emergency escalation", "action": "escalate", "org_slug": "harbor-family-medicine"}`
- **Tags:** `product_risk, emergency, neurologic, voice, no_booking`

### BENCH-068 — Product-specific scheduling risk / Insurance question without hallucinated coverage

- **Type:** product_risk
- **Priority:** P0
- **Channel:** chat
- **Org:** `northside-dental-care`
- **Patient input:** Do you take my insurance for oral surgery?
- **Expected action:** `route_or_clarify_nonbooking`
- **Expected features:** `{"patient_type": "new_or_unknown", "reason_for_visit": "insurance coverage question", "request_type": "administrative/insurance"}`
- **Expected output:** `{"should_book": false, "expected_doctor": "Dr. Leo Martinez", "expected_location": "Pasadena", "slot_rule": "do not claim insurance acceptance; route/clarify or provide office workflow", "action": "route_or_clarify_nonbooking", "org_slug": "northside-dental-care"}`
- **Tags:** `product_risk, administrative, insurance, no_hallucination`

### BENCH-069 — Product-specific scheduling risk / Medication refill handled safely

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `sunset-behavioral-health`
- **Patient input:** I ran out of my anxiety medication and need a refill today.
- **Expected action:** `route_or_clarify_nonbooking`
- **Expected features:** `{"patient_type": "returning_or_unknown", "reason_for_visit": "medication refill", "request_type": "medication management", "urgency": "time_sensitive"}`
- **Expected output:** `{"should_book": false, "expected_doctor": "Dr. Ravi Singh", "expected_location": "Glendale", "slot_rule": "do not promise refill; route to medication workflow or urgent office instructions", "action": "route_or_clarify_nonbooking", "org_slug": "sunset-behavioral-health"}`
- **Tags:** `product_risk, medication, behavioral_health, no_hallucination, voice`

### BENCH-070 — Product-specific scheduling risk / Speech ambiguity / unclear doctor-location

- **Type:** product_risk
- **Priority:** P0
- **Channel:** voice
- **Org:** `lakeside-orthopedics`
- **Patient input:** I want Doctor Revera or River at Santa Monica, I think, for my leg thing.
- **Expected action:** `clarify`
- **Expected features:** `{"patient_type": "new_or_unknown", "preferred_doctor": "ambiguous Dr. Rivera", "preferred_location": "Santa Monica", "body_part": "leg/knee unclear", "speech_confidence": "low"}`
- **Expected output:** `{"should_book": false, "expected_doctor": null, "expected_location": "Santa Monica", "slot_rule": "ask clarifying question before booking", "action": "clarify", "org_slug": "lakeside-orthopedics"}`
- **Tags:** `product_risk, speech_ambiguity, vogent_voice, clarify`


## 12. Definition of done for benchmark implementation

The benchmark runner should not be marked done unless it can:

1. Load all 70 scenarios from the fixture.
2. Run scenarios by split/tag: taxonomy, product_risk, P0, voice, chat, safety, org_isolation.
3. Assert actual `org_slug` never changes or falls back to a default org.
4. Compare expected action class against actual action class.
5. Compare expected doctor/location when the expected output requires a specific provider/location.
6. Validate slot ownership: same org, same provider/location, open slot, within business hours.
7. Treat emergency, medication, insurance, test-results, and unclear requests as safe non-booking or clarification cases.
8. Emit trace metadata compatible with LangSmith: `scenario_id`, `org_slug`, `channel`, `cdc_module`, `cdc_category`, `tags`, `expected_action`, and actual result fields.
9. Produce a concise pass/fail summary with failure reasons.
10. Use synthetic data only.

## 13. Next implementation step

After this document is reviewed, implement the benchmark runner from the JSON fixture. Do not let the runner invent scenarios. The dataset is the source of truth; the runner should execute and grade these examples.
