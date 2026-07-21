from __future__ import annotations

import threading
from datetime import UTC, datetime

from flask import Flask
from sqlalchemy import func, select

from app.errors import ApiError
from app.extensions import get_session_factory
from app.models import Appointment, Call, Doctor, IntegrationRequestLog, Patient, Slot
from app.services.booking import BookingService
from app.services.confirmation import BookingConfirmationService
from app.services.idempotency import IdempotencyService


def test_scenario_i_two_concurrent_attempts_create_one_appointment(app: Flask) -> None:
    factory = get_session_factory()
    setup = factory()
    vasquez_id = setup.scalar(select(Doctor.id).where(Doctor.last_name == "Vasquez"))
    slot_id = setup.scalar(
        select(Slot.id).where(Slot.doctor_id == vasquez_id, Slot.status == "OPEN").order_by(Slot.starts_at)
    )
    patient_ids = list(setup.scalars(select(Patient.id).order_by(Patient.id).limit(2)))
    assert slot_id is not None
    assert len(patient_ids) == 2
    confirmation_tokens: dict[int, tuple[int, str]] = {}
    for patient_id in patient_ids:
        call = Call(
            patient_id=patient_id,
            status="IN_PROGRESS",
            caller_phone=f"+1805555{patient_id:04d}",
            started_at=datetime.now(UTC),
            transcript=[],
        )
        setup.add(call)
        setup.flush()
        confirmation = BookingConfirmationService(setup).confirm(
            call_id=call.id,
            patient_id=patient_id,
            slot_id=slot_id,
            body_part="Shoulder",
            issue_type="Fracture",
            source="CONCURRENCY_TEST",
        )
        confirmation_tokens[patient_id] = (call.id, confirmation.confirmation_token)
    setup.close()

    barrier = threading.Barrier(2)
    results: list[str] = []
    lock = threading.Lock()

    def attempt(patient_id: int) -> None:
        session = factory()
        try:
            barrier.wait(timeout=5)
            call_id, confirmation_token = confirmation_tokens[patient_id]
            BookingService(session).book(
                patient_id=patient_id,
                slot_id=slot_id,
                body_part="Shoulder",
                issue_type="Fracture",
                call_id=call_id,
                booking_source="CONCURRENCY_TEST",
                confirmation_token=confirmation_token,
            )
            outcome = "success"
        except ApiError as error:
            outcome = error.code
        finally:
            session.close()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=attempt, args=(patient_id,)) for patient_id in patient_ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    verify = factory()
    appointment_count = verify.scalar(select(func.count(Appointment.id)).where(Appointment.slot_id == slot_id))
    verify.close()

    assert results.count("success") == 1
    assert len([result for result in results if result in {"SLOT_ALREADY_BOOKED", "PHYSICIAN_NOT_ELIGIBLE"}]) == 1
    assert appointment_count == 1


def test_concurrent_idempotency_key_creates_one_request_log(app: Flask) -> None:
    factory = get_session_factory()
    barrier = threading.Barrier(2)
    results: list[str] = []
    lock = threading.Lock()
    payload = {"call_id": 1, "operation": "duplicate-check"}

    def attempt() -> None:
        session = factory()
        try:
            barrier.wait(timeout=5)
            service = IdempotencyService(session)
            started = service.begin_request(
                provider="vogent",
                operation="confirm-slot",
                payload=payload,
                external_id="concurrent-idempotency-key",
            )
            if started.is_duplicate:
                outcome = "duplicate"
            else:
                service.complete_request(started.log, response={"confirmed": True}, status_code=201)
                session.commit()
                outcome = "created"
        except ApiError as error:
            session.rollback()
            outcome = error.code
        finally:
            session.close()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    verify = factory()
    log_count = verify.scalar(
        select(func.count(IntegrationRequestLog.id)).where(
            IntegrationRequestLog.provider == "vogent",
            IntegrationRequestLog.operation == "confirm-slot",
            IntegrationRequestLog.external_id == "concurrent-idempotency-key",
        )
    )
    verify.close()

    assert results.count("created") == 1
    assert len([result for result in results if result in {"duplicate", "IDEMPOTENT_REQUEST_IN_PROGRESS"}]) == 1
    assert log_count == 1


def test_same_confirmation_token_concurrent_replay_books_once(app: Flask) -> None:
    factory = get_session_factory()
    setup = factory()
    vasquez_id = setup.scalar(select(Doctor.id).where(Doctor.last_name == "Vasquez"))
    slot_id = setup.scalar(
        select(Slot.id).where(Slot.doctor_id == vasquez_id, Slot.status == "OPEN").order_by(Slot.starts_at)
    )
    patient_id = setup.scalar(select(Patient.id).order_by(Patient.id))
    assert slot_id is not None
    assert patient_id is not None
    call = Call(
        patient_id=patient_id,
        status="IN_PROGRESS",
        caller_phone="+18055550998",
        started_at=datetime.now(UTC),
        transcript=[],
    )
    setup.add(call)
    setup.flush()
    confirmation = BookingConfirmationService(setup).confirm(
        call_id=call.id,
        patient_id=patient_id,
        slot_id=slot_id,
        body_part="Shoulder",
        issue_type="Fracture",
        source="CONFIRMATION_REPLAY_TEST",
    )
    call_id = call.id
    confirmation_token = confirmation.confirmation_token
    setup.close()

    barrier = threading.Barrier(2)
    results: list[str] = []
    lock = threading.Lock()

    def attempt() -> None:
        session = factory()
        try:
            barrier.wait(timeout=5)
            BookingService(session).book(
                patient_id=patient_id,
                slot_id=slot_id,
                body_part="Shoulder",
                issue_type="Fracture",
                call_id=call_id,
                booking_source="CONFIRMATION_REPLAY_TEST",
                confirmation_token=confirmation_token,
            )
            outcome = "success"
        except ApiError as error:
            outcome = error.code
        finally:
            session.close()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    verify = factory()
    appointment_count = verify.scalar(select(func.count(Appointment.id)).where(Appointment.slot_id == slot_id))
    verify.close()

    assert results.count("success") == 1
    assert (
        len(
            [
                result
                for result in results
                if result in {"BOOKING_CONFIRMATION_USED", "SLOT_ALREADY_BOOKED", "PHYSICIAN_NOT_ELIGIBLE"}
            ]
        )
        == 1
    )
    assert appointment_count == 1
