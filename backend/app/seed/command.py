from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import click
from flask import Flask
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.extensions import get_session_factory
from app.models import (
    Appointment,
    Call,
    Doctor,
    DoctorCapability,
    Location,
    Patient,
    PatientDoctorHistory,
    RoutingDecision,
    Slot,
    TranscriptTurn,
)
from app.models.entities import DoctorLocation
from app.seed.data import DOCTORS, LOCATIONS
from app.services.patient_account_security import hash_patient_password, verify_patient_password

JORDAN_DEMO_EMAIL = "jordan.patient@example.com"
JORDAN_DEMO_PASSWORD = "demo123"
GENERAL_ORTHOPEDICS_LAST_NAME = "Nguyen"
CLINIC_TIMEZONE = ZoneInfo("America/Los_Angeles")
GENERAL_ROTATION_BY_WEEKDAY = {
    0: "MAIN",
    1: "EAST",
    2: "NORTH",
    3: "WEST",
    4: "SOUTH",
}


def register_seed_command(app: Flask) -> None:
    @app.cli.command("seed")
    def seed_command() -> None:
        session = get_session_factory()()
        try:
            seed_database(session)
            session.commit()
            click.echo("Seed data is ready.")
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def _doctor_last_name_aliases(last_name: str) -> list[str]:
    if last_name == "O'Brien":
        return ["O'Brien", "O’Brien"]
    return [last_name]


def seed_database(session: Session) -> None:
    location_by_code: dict[str, Location] = {}
    for location_seed in LOCATIONS:
        location = session.scalar(select(Location).where(Location.code == location_seed["code"]))
        if location is None:
            location = Location(**location_seed)
            session.add(location)
            session.flush()
        else:
            location.name = location_seed["name"]
        location_by_code[location_seed["code"]] = location

    doctor_by_last_name: dict[str, Doctor] = {}
    for doctor_seed in DOCTORS:
        doctor = session.scalar(
            select(Doctor).where(
                Doctor.first_name == doctor_seed["first_name"],
                Doctor.last_name.in_(_doctor_last_name_aliases(doctor_seed["last_name"])),
            )
        )
        if doctor is None:
            doctor = Doctor(
                first_name=doctor_seed["first_name"],
                last_name=doctor_seed["last_name"],
                accepts_new_patients=doctor_seed["accepts_new_patients"],
                active=True,
            )
            session.add(doctor)
            session.flush()
        doctor.last_name = doctor_seed["last_name"]
        doctor.accepts_new_patients = doctor_seed["accepts_new_patients"]
        doctor.active = True
        doctor_by_last_name[doctor_seed["last_name"]] = doctor

        current_links = set(
            session.scalars(select(DoctorLocation.location_id).where(DoctorLocation.doctor_id == doctor.id))
        )
        desired_links = {location_by_code[code].id for code in doctor_seed["locations"]}
        for location_id in desired_links - current_links:
            session.add(DoctorLocation(doctor_id=doctor.id, location_id=location_id))
        if current_links - desired_links:
            session.execute(
                delete(DoctorLocation).where(
                    DoctorLocation.doctor_id == doctor.id,
                    DoctorLocation.location_id.in_(current_links - desired_links),
                )
            )

        current_capabilities = set(
            session.execute(
                select(DoctorCapability.body_part, DoctorCapability.issue_type).where(
                    DoctorCapability.doctor_id == doctor.id
                )
            ).all()
        )
        desired_capabilities = set(doctor_seed["capabilities"])
        for body_part, issue_type in desired_capabilities - current_capabilities:
            session.add(DoctorCapability(doctor_id=doctor.id, body_part=body_part, issue_type=issue_type))
        for body_part, issue_type in current_capabilities - desired_capabilities:
            session.execute(
                delete(DoctorCapability).where(
                    DoctorCapability.doctor_id == doctor.id,
                    DoctorCapability.body_part == body_part,
                    DoctorCapability.issue_type == issue_type,
                )
            )
    session.flush()

    patients = [
        ("Sarah", "Johnson", date(1990, 4, 12), "+18055550101", "sarah@example.test"),
        ("Michael", "Brown", date(1978, 9, 2), "+18055550102", None),
        ("Emily", "Davis", date(1985, 1, 18), "+18055550103", "emily@example.test"),
        ("David", "Wilson", date(1968, 7, 30), "+18055550104", None),
        ("Maya", "Patel", date(1982, 11, 6), "+18055550105", "maya@example.test"),
        ("Jordan", "Segovia", date(1988, 9, 22), "+18052644217", JORDAN_DEMO_EMAIL),
    ]
    patient_by_phone: dict[str, Patient] = {}
    for first, last, dob, phone, email in patients:
        patient = session.scalar(select(Patient).where(Patient.phone == phone, Patient.date_of_birth == dob))
        if patient is None and email:
            patient = session.scalar(select(Patient).where(Patient.email == email, Patient.date_of_birth == dob))
        if patient is None and email == JORDAN_DEMO_EMAIL:
            patient = session.scalar(
                select(Patient).where(Patient.phone == "805-264-4217", Patient.date_of_birth == dob)
            )
        if patient is None:
            patient = Patient(
                first_name=first,
                last_name=last,
                date_of_birth=dob,
                phone=phone,
                email=email,
                password_hash=hash_patient_password(JORDAN_DEMO_PASSWORD) if email == JORDAN_DEMO_EMAIL else None,
                insurance_provider=None,
            )
            session.add(patient)
            session.flush()
        else:
            patient.first_name = first
            patient.last_name = last
            patient.phone = phone
            patient.email = email
        if email == JORDAN_DEMO_EMAIL and not verify_patient_password(patient.password_hash, JORDAN_DEMO_PASSWORD):
            patient.password_hash = hash_patient_password(JORDAN_DEMO_PASSWORD)
        patient_by_phone[phone] = patient

    maya = patient_by_phone["+18055550105"]
    patel = doctor_by_last_name["Patel"]
    history = session.scalar(
        select(PatientDoctorHistory).where(
            PatientDoctorHistory.patient_id == maya.id,
            PatientDoctorHistory.doctor_id == patel.id,
        )
    )
    history_date = datetime.now(UTC) - timedelta(days=120)
    if history is None:
        session.add(
            PatientDoctorHistory(
                patient_id=maya.id,
                doctor_id=patel.id,
                first_seen_at=history_date,
                most_recent_seen_at=history_date,
                source="legacy_ehr_seed",
            )
        )

    now = datetime.now(UTC)
    local_today = now.astimezone(CLINIC_TIMEZONE).date()
    fallback_no_slot_date = _first_future_weekday(local_today)
    specialist_desired_keys: set[tuple[int, int, datetime]] = set()
    specialist_doctor_ids: set[int] = set()
    for doctor_data in DOCTORS:
        if doctor_data["last_name"] == GENERAL_ORTHOPEDICS_LAST_NAME:
            continue
        doctor = doctor_by_last_name[doctor_data["last_name"]]
        specialist_doctor_ids.add(doctor.id)
        for day_offset in range(1, 15):
            local_day = local_today + timedelta(days=day_offset)
            if local_day.weekday() >= 5:
                continue
            for location_code in doctor_data["locations"]:
                location = location_by_code[location_code]
                for hour in (9, 11, 14, 16):
                    local_start = datetime.combine(local_day, time(hour=hour), tzinfo=CLINIC_TIMEZONE)
                    starts_at = local_start.astimezone(UTC)
                    ends_at = (local_start + timedelta(minutes=45)).astimezone(UTC)
                    specialist_desired_keys.add(_slot_identity_key(doctor.id, location.id, starts_at))
                    slot = session.scalar(
                        select(Slot).where(
                            Slot.doctor_id == doctor.id,
                            Slot.location_id == location.id,
                            Slot.starts_at == starts_at,
                        )
                    )
                    if slot is None:
                        slot = Slot(
                            doctor_id=doctor.id,
                            location_id=location.id,
                            starts_at=starts_at,
                            ends_at=ends_at,
                            status="OPEN",
                        )
                        session.add(slot)
                        session.flush()
                    else:
                        slot.ends_at = ends_at
                    if session.scalar(select(Appointment.id).where(Appointment.slot_id == slot.id)) is None:
                        slot.status = "OPEN"
                    # Fallback fixture: Dr. Chen is valid for knee sports medicine but
                    # has no opening on the first future weekday date-range test.
                    if doctor.last_name == "Chen" and local_day == fallback_no_slot_date:
                        slot.status = "BOOKED"
    _close_stale_unbooked_future_slots(
        session,
        doctor_ids=specialist_doctor_ids,
        desired_keys=specialist_desired_keys,
        starts_after=now,
    )
    _seed_general_orthopedics_rotation(
        session,
        doctor=doctor_by_last_name[GENERAL_ORTHOPEDICS_LAST_NAME],
        location_by_code=location_by_code,
    )
    session.flush()

    # Idempotently create one scheduled appointment and four representative calls.
    vasquez = doctor_by_last_name["Vasquez"]
    main = location_by_code["MAIN"]
    sarah = patient_by_phone["+18055550101"]
    scheduled_slot = session.scalar(
        select(Slot)
        .where(
            Slot.doctor_id == vasquez.id,
            Slot.location_id == main.id,
            Slot.status == "OPEN",
        )
        .order_by(Slot.starts_at)
    )
    demo_call = session.scalar(select(Call).where(Call.external_call_id == "demo-scheduled-001"))
    if demo_call is None:
        demo_call = Call(
            external_call_id="demo-scheduled-001",
            patient_id=sarah.id,
            status="SCHEDULED",
            caller_phone=sarah.phone,
            patient_status="NEW",
            requested_body_part="Knee",
            requested_issue_type="Fracture",
            preferred_doctor_id=doctor_by_last_name["Chen"].id,
            preferred_location_id=main.id,
            started_at=datetime.now(UTC) - timedelta(hours=2),
            ended_at=datetime.now(UTC) - timedelta(hours=1, minutes=55),
            transcript=[],
        )
        session.add(demo_call)
        session.flush()
        turns = [
            ("AI", "Thank you for calling. Are you a new or returning patient?"),
            ("HUMAN", "I am new and I think I fractured my knee. I wanted Dr. Chen."),
            ("AI", "Dr. Chen does not treat knee fractures. Dr. Vasquez has a matching opening at Main Campus."),
            ("HUMAN", "Yes, please book that appointment."),
            ("AI", "Your appointment is confirmed with Dr. Elena Vasquez at Main Campus."),
        ]
        for sequence, (speaker, text_value) in enumerate(turns, start=1):
            occurred_at = demo_call.started_at + timedelta(seconds=sequence * 25)
            demo_call.transcript_turns.append(
                TranscriptTurn(
                    sequence_number=sequence,
                    speaker=speaker,
                    text=text_value,
                    occurred_at=occurred_at,
                )
            )
            demo_call.transcript.append(
                {
                    "sequence_number": sequence,
                    "speaker": speaker,
                    "text": text_value,
                    "occurred_at": occurred_at.isoformat(),
                }
            )
        session.add_all(
            [
                RoutingDecision(
                    call_id=demo_call.id,
                    patient_id=sarah.id,
                    doctor_id=doctor_by_last_name["Chen"].id,
                    decision="REJECTED",
                    reason_code="ISSUE_TYPE_NOT_SUPPORTED",
                    human_readable_reason=(
                        "Dr. Maria Chen treats knee joint replacement and sports medicine cases, "
                        "but not knee fractures."
                    ),
                    request_context={"body_part": "Knee", "issue_type": "Fracture"},
                    created_at=demo_call.started_at + timedelta(minutes=1),
                ),
                RoutingDecision(
                    call_id=demo_call.id,
                    patient_id=sarah.id,
                    doctor_id=vasquez.id,
                    decision="ACCEPTED",
                    reason_code="FALLBACK_SELECTED",
                    human_readable_reason=(
                        "Dr. Elena Vasquez was selected as the next valid physician with an open slot."
                    ),
                    request_context={"body_part": "Knee", "issue_type": "Fracture"},
                    created_at=demo_call.started_at + timedelta(minutes=2),
                ),
            ]
        )
        if scheduled_slot is not None:
            appointment = Appointment(
                patient_id=sarah.id,
                doctor_id=vasquez.id,
                location_id=main.id,
                slot_id=scheduled_slot.id,
                body_part="Knee",
                issue_type="Fracture",
                status="SCHEDULED",
                booking_source="VOGENT",
                call_id=demo_call.id,
            )
            session.add(appointment)
            session.flush()
            scheduled_slot.status = "BOOKED"
            demo_call.appointment_id = appointment.id

    demo_calls = [
        (
            "demo-redirected-001",
            "REDIRECTED",
            "+18055550102",
            "Spine",
            "Fracture",
            "No matching new-patient physician with availability.",
        ),
        (
            "demo-abandoned-001",
            "ABANDONED",
            "+18055550103",
            "Shoulder",
            "Sports Medicine",
            "Caller ended before confirming a slot.",
        ),
        ("demo-failed-001", "FAILED", "+18055550104", None, None, "Call disconnected before patient identification."),
    ]
    for index, (external_id, status, phone, body, issue, reason) in enumerate(demo_calls, start=1):
        if session.scalar(select(Call).where(Call.external_call_id == external_id)) is None:
            patient = patient_by_phone.get(phone)
            session.add(
                Call(
                    external_call_id=external_id,
                    patient_id=patient.id if patient else None,
                    status=status,
                    caller_phone=phone,
                    patient_status="RETURNING" if patient else None,
                    requested_body_part=body,
                    requested_issue_type=issue,
                    started_at=datetime.now(UTC) - timedelta(days=index, hours=index),
                    ended_at=datetime.now(UTC) - timedelta(days=index, hours=index) + timedelta(minutes=3),
                    transcript=[],
                    failure_reason=reason if status in {"FAILED", "ABANDONED"} else None,
                    redirect_summary=reason if status == "REDIRECTED" else None,
                )
            )


def _first_future_weekday(today: date) -> date:
    for day_offset in range(1, 15):
        day = today + timedelta(days=day_offset)
        if day.weekday() < 5:
            return day
    return today + timedelta(days=1)


def _seed_general_orthopedics_rotation(
    session: Session,
    *,
    doctor: Doctor,
    location_by_code: dict[str, Location],
) -> None:
    now = datetime.now(UTC)
    local_today = now.astimezone(CLINIC_TIMEZONE).date()
    desired_keys: set[tuple[int, int, datetime]] = set()
    for day_offset in range(1, 36):
        local_day = local_today + timedelta(days=day_offset)
        location_code = GENERAL_ROTATION_BY_WEEKDAY.get(local_day.weekday())
        if location_code is None:
            continue
        location = location_by_code[location_code]
        for hour in (9, 11, 14, 16):
            local_start = datetime.combine(local_day, time(hour=hour), tzinfo=CLINIC_TIMEZONE)
            starts_at = local_start.astimezone(UTC)
            ends_at = (local_start + timedelta(minutes=45)).astimezone(UTC)
            desired_keys.add(_slot_identity_key(doctor.id, location.id, starts_at))
            slot = session.scalar(
                select(Slot).where(
                    Slot.doctor_id == doctor.id,
                    Slot.location_id == location.id,
                    Slot.starts_at == starts_at,
                )
            )
            if slot is None:
                slot = Slot(
                    doctor_id=doctor.id,
                    location_id=location.id,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    status="OPEN",
                )
                session.add(slot)
                session.flush()
            else:
                slot.ends_at = ends_at
            if session.scalar(select(Appointment.id).where(Appointment.slot_id == slot.id)) is None:
                slot.status = "OPEN"

    _close_stale_unbooked_future_slots(
        session,
        doctor_ids={doctor.id},
        desired_keys=desired_keys,
        starts_after=now,
    )


def _close_stale_unbooked_future_slots(
    session: Session,
    *,
    doctor_ids: set[int],
    desired_keys: set[tuple[int, int, datetime]],
    starts_after: datetime,
) -> None:
    if not doctor_ids:
        return
    existing_future_slots = session.scalars(
        select(Slot).where(
            Slot.doctor_id.in_(doctor_ids),
            Slot.starts_at >= starts_after,
        )
    ).all()
    for slot in existing_future_slots:
        key = _slot_identity_key(slot.doctor_id, slot.location_id, slot.starts_at)
        if key in desired_keys:
            continue
        if session.scalar(select(Appointment.id).where(Appointment.slot_id == slot.id)) is None:
            slot.status = "CLOSED"


def _slot_identity_key(doctor_id: int, location_id: int, starts_at: datetime) -> tuple[int, int, datetime]:
    if starts_at.tzinfo is not None:
        starts_at = starts_at.astimezone(UTC).replace(tzinfo=None)
    return doctor_id, location_id, starts_at
