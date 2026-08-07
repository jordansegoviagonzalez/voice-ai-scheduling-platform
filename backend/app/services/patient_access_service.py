from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.normalization import normalize_date_of_birth, normalize_phone
from app.errors import ApiError
from app.models.entities import Patient
from app.services.patient_account_security import (
    hash_patient_password,
    normalize_email,
    patient_login_error,
    validate_new_account_password,
    verify_patient_password,
)


class PatientAccessService:
    def __init__(self, db_session: Session):
        self.session = db_session

    def verify_returning_patient(
        self,
        organization_id: int,
        *,
        email: str | None = None,
        password: object = None,
        full_name: str | None = None,
        dob: str | None = None,
        phone: str | None = None,
    ) -> Patient:
        if email or password:
            if not isinstance(email, str):
                raise patient_login_error()
            try:
                normalized_email = normalize_email(email)
            except ApiError as error:
                raise patient_login_error() from error
            patient = self.session.scalar(select(Patient).where(Patient.organization_id == organization_id, Patient.email == normalized_email))
            if patient and verify_patient_password(patient.password_hash, password):
                return patient
            raise patient_login_error()

        if phone:
            try:
                normalized_phone = normalize_phone(phone)
            except ApiError as error:
                raise patient_login_error() from error
            patient = self.session.scalar(select(Patient).where(Patient.organization_id == organization_id, Patient.phone == normalized_phone))
            if patient:
                return patient
            raise patient_login_error()

        raise ApiError("BAD_REQUEST", "Please provide email/password or full_name/dob/phone", 400)

    def create_or_get_new_patient(
        self,
        *,
        organization_id: int,
        full_name: str,
        date_of_birth: str,
        phone: str,
        email: str | None,
        insurance_provider: str | None,
        password: object = None,
        password_confirmation: object = None,
    ) -> tuple[Patient, bool]:
        first_name, last_name = _split_name(full_name)
        dob = normalize_date_of_birth(date_of_birth)
        if dob >= date.today():
            raise ApiError(
                "VALIDATION_ERROR",
                "Date of birth must be in the past.",
                422,
                {"date_of_birth": ["Invalid date"]},
            )
        normalized_phone = normalize_phone(phone)
        normalized_email = normalize_email(email or "")
        validated_password = validate_new_account_password(password, password_confirmation)
        password_hash = hash_patient_password(validated_password)
        existing = self.session.scalar(
            select(Patient).where(Patient.organization_id == organization_id, Patient.phone == normalized_phone, Patient.date_of_birth == dob)
        )
        email_owner = self.session.scalar(select(Patient).where(Patient.organization_id == organization_id, Patient.email == normalized_email))
        if email_owner is not None and (existing is None or email_owner.id != existing.id):
            raise ApiError(
                "ACCOUNT_EMAIL_CONFLICT",
                "That email is already associated with another patient account.",
                409,
                {"email": ["Email is already in use"]},
            )
        if existing:
            if existing.password_hash:
                if existing.email != normalized_email or not verify_patient_password(
                    existing.password_hash,
                    validated_password,
                ):
                    raise ApiError(
                        "PATIENT_ACCOUNT_EXISTS",
                        "A patient account already exists for those details. Sign in as a returning patient.",
                        409,
                    )
                if insurance_provider and not existing.insurance_provider:
                    existing.insurance_provider = insurance_provider
                self.session.commit()
                return existing, False
            existing.email = normalized_email
            existing.password_hash = password_hash
            if insurance_provider and not existing.insurance_provider:
                existing.insurance_provider = insurance_provider
            self.session.commit()
            return existing, False

        patient = Patient(
            organization_id=organization_id,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            phone=normalized_phone,
            email=normalized_email,
            password_hash=password_hash,
            insurance_provider=insurance_provider,
        )
        self.session.add(patient)
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            existing_after_conflict = self.session.scalar(
                select(Patient).where(Patient.organization_id == organization_id, Patient.phone == normalized_phone, Patient.date_of_birth == dob)
            )
            if existing_after_conflict:
                return existing_after_conflict, False
            raise ApiError(
                "PATIENT_ACCOUNT_CONFLICT",
                "A patient account with that email or identity already exists.",
                409,
            ) from error
        return patient, True

    def update_contact(self, patient: Patient, *, email: str, phone: str) -> Patient:
        normalized_email = normalize_email(email)
        normalized_phone = normalize_phone(phone)
        email_owner = self.session.scalar(
            select(Patient).where(Patient.organization_id == patient.organization_id, Patient.email == normalized_email, Patient.id != patient.id)
        )
        if email_owner is not None:
            raise ApiError(
                "CONTACT_CONFLICT",
                "That email is already associated with another patient record.",
                409,
                {"email": ["Email is already in use"]},
            )
        identity_owner = self.session.scalar(
            select(Patient).where(
                Patient.organization_id == patient.organization_id,
                Patient.phone == normalized_phone,
                Patient.date_of_birth == patient.date_of_birth,
                Patient.id != patient.id,
            )
        )
        if identity_owner is not None:
            raise ApiError(
                "CONTACT_CONFLICT",
                "That phone number conflicts with another patient record.",
                409,
                {"phone": ["Phone number conflicts with an existing patient"]},
            )
        patient.email = normalized_email
        patient.phone = normalized_phone
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise ApiError(
                "CONTACT_CONFLICT",
                "The profile update conflicts with another patient record.",
                409,
            ) from error
        return patient


def _split_name(full_name: str) -> tuple[str, str]:
    parts = [part for part in full_name.strip().split() if part]
    if len(parts) < 2:
        raise ApiError("VALIDATION_ERROR", "Enter both first and last name.", 422, {"full_name": ["Required"]})
    return parts[0], " ".join(parts[1:])
