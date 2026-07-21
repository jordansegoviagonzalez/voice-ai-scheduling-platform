# Entity-Relationship Diagram

```mermaid
erDiagram
    PATIENTS ||--o{ PATIENT_DOCTOR_HISTORY : has
    DOCTORS ||--o{ PATIENT_DOCTOR_HISTORY : records
    PATIENTS ||--o{ APPOINTMENTS : books
    DOCTORS ||--o{ APPOINTMENTS : receives
    LOCATIONS ||--o{ APPOINTMENTS : hosts
    SLOTS ||--o| APPOINTMENTS : claimed_by
    DOCTORS ||--o{ SLOTS : owns
    LOCATIONS ||--o{ SLOTS : contains
    DOCTORS ||--o{ DOCTOR_LOCATIONS : practices_at
    LOCATIONS ||--o{ DOCTOR_LOCATIONS : includes
    DOCTORS ||--o{ DOCTOR_CAPABILITIES : supports
    PATIENTS ||--o{ CALLS : identified_in
    DOCTORS ||--o{ CALLS : preferred_in
    LOCATIONS ||--o{ CALLS : preferred_in
    APPOINTMENTS ||--o| CALLS : result_of
    CALLS ||--o{ TRANSCRIPT_TURNS : contains
    CALLS ||--o{ ROUTING_DECISIONS : audits
    DOCTORS ||--o{ ROUTING_DECISIONS : evaluated
    PATIENTS ||--o{ ROUTING_DECISIONS : contextualizes

    PATIENTS {
      bigint id PK
      string first_name
      string last_name
      date date_of_birth
      string phone
      string email NULL
      timestamptz created_at
      timestamptz updated_at
    }

    LOCATIONS {
      bigint id PK
      string code UK
      string name UK
    }

    DOCTORS {
      bigint id PK
      string first_name
      string last_name
      boolean accepts_new_patients
      boolean active
      timestamptz created_at
      timestamptz updated_at
    }

    DOCTOR_LOCATIONS {
      bigint doctor_id PK,FK
      bigint location_id PK,FK
    }

    DOCTOR_CAPABILITIES {
      bigint id PK
      bigint doctor_id FK
      string body_part
      string issue_type
      unique doctor_body_issue
    }

    PATIENT_DOCTOR_HISTORY {
      bigint id PK
      bigint patient_id FK
      bigint doctor_id FK
      timestamptz first_seen_at
      timestamptz most_recent_seen_at
      string source
      bigint appointment_id NULL
      unique patient_doctor
    }

    SLOTS {
      bigint id PK
      bigint doctor_id FK
      bigint location_id FK
      timestamptz starts_at
      timestamptz ends_at
      string status
      timestamptz created_at
      timestamptz updated_at
    }

    APPOINTMENTS {
      bigint id PK
      bigint patient_id FK
      bigint doctor_id FK
      bigint location_id FK
      bigint slot_id UK,FK
      string body_part
      string issue_type
      string status
      string booking_source
      bigint call_id NULL
      timestamptz created_at
      timestamptz updated_at
    }

    CALLS {
      bigint id PK
      string external_call_id NULL
      bigint patient_id NULL,FK
      string status
      string caller_phone
      string patient_status NULL
      string requested_body_part NULL
      string requested_issue_type NULL
      bigint preferred_doctor_id NULL,FK
      bigint preferred_location_id NULL,FK
      timestamptz started_at
      timestamptz ended_at NULL
      json transcript
      bigint appointment_id NULL,FK
      string failure_reason NULL
      string redirect_summary NULL
      timestamptz created_at
      timestamptz updated_at
    }

    TRANSCRIPT_TURNS {
      bigint id PK
      bigint call_id FK
      integer sequence_number
      string speaker
      text text
      timestamptz occurred_at
      unique call_sequence
    }

    ROUTING_DECISIONS {
      bigint id PK
      bigint call_id NULL,FK
      bigint patient_id NULL,FK
      bigint doctor_id NULL,FK
      string decision
      string reason_code
      text human_readable_reason
      jsonb request_context
      timestamptz created_at
    }
```

## Integrity rules

- Patient lookup uses normalized phone plus date of birth.
- Location codes and names are unique.
- Doctor capability tuples are unique.
- Patient-doctor history is unique per patient and doctor.
- A slot belongs to exactly one doctor and one location.
- The service verifies that the doctor practices at the slot location.
- `appointments.slot_id` is unique, so a slot cannot produce two appointments.
- Transcript sequence numbers are unique within a call.
