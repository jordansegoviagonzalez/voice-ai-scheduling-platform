from __future__ import annotations

from flask.testing import FlaskClient

from app.extensions import get_session_factory
from app.models import Location


def _login_admin(client: FlaskClient) -> None:
    response = client.post(
        "/api/auth/admin/login",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert response.status_code == 200, response.get_json()


def _create_organization(client: FlaskClient, name: str, slug: str | None = None) -> dict[str, object]:
    payload = {"name": name}
    if slug is not None:
        payload["slug"] = slug
    response = client.post("/api/v1/organizations", json=payload)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["organization"]


def _create_location(organization_id: int, code: str, name: str) -> int:
    session = get_session_factory()()
    try:
        location = Location(organization_id=organization_id, code=code, name=name)
        session.add(location)
        session.commit()
        return location.id
    finally:
        session.close()


def test_organization_can_be_created_with_generated_slug_and_listed(client: FlaskClient) -> None:
    _login_admin(client)

    created = _create_organization(client, "Summit Orthopedics")

    assert created["slug"] == "summit-orthopedics"
    assert created["status"] == "ACTIVE"
    assert created["timezone"] == "America/Los_Angeles"

    listed = client.get("/api/v1/organizations")

    assert listed.status_code == 200, listed.get_json()
    organizations = listed.get_json()["organizations"]
    assert any(organization["id"] == created["id"] for organization in organizations)


def test_organization_can_be_retrieved_updated_and_resolved_by_slug(client: FlaskClient) -> None:
    _login_admin(client)
    created = _create_organization(client, "North Valley Clinic", slug="North Valley!")

    retrieved = client.get(f"/api/v1/organizations/{created['id']}")
    assert retrieved.status_code == 200, retrieved.get_json()
    assert retrieved.get_json()["organization"]["slug"] == "north-valley"

    updated = client.patch(
        f"/api/v1/organizations/{created['id']}",
        json={
            "name": "North Valley Orthopedics",
            "slug": "North Valley Ortho",
            "timezone": "America/New_York",
        },
    )
    assert updated.status_code == 200, updated.get_json()
    organization = updated.get_json()["organization"]
    assert organization["name"] == "North Valley Orthopedics"
    assert organization["slug"] == "north-valley-ortho"
    assert organization["timezone"] == "America/New_York"

    resolved = client.get("/api/v1/organizations/slug/north-valley-ortho")
    assert resolved.status_code == 200, resolved.get_json()
    assert resolved.get_json()["organization"]["slug"] == "north-valley-ortho"

    inactive = client.patch(f"/api/v1/organizations/{created['id']}", json={"status": "INACTIVE"})
    assert inactive.status_code == 200, inactive.get_json()

    rejected = client.get("/api/v1/organizations/slug/north-valley-ortho")
    assert rejected.status_code == 409, rejected.get_json()
    assert rejected.get_json()["error"]["code"] == "ORGANIZATION_INACTIVE"


def test_duplicate_organization_slug_is_rejected(client: FlaskClient) -> None:
    _login_admin(client)
    _create_organization(client, "Duplicate Clinic", slug="Duplicate Clinic")

    response = client.post("/api/v1/organizations", json={"name": "Other Clinic", "slug": "duplicate-clinic"})

    assert response.status_code == 409, response.get_json()
    assert response.get_json()["error"]["code"] == "ORGANIZATION_SLUG_CONFLICT"


def test_missing_organization_slug_returns_clear_error(client: FlaskClient) -> None:
    response = client.get("/api/v1/organizations/slug/not-a-real-organization")

    assert response.status_code == 404, response.get_json()
    assert response.get_json()["error"]["code"] == "ORGANIZATION_NOT_FOUND"


def test_doctor_crud_is_scoped_to_selected_organization(client: FlaskClient) -> None:
    _login_admin(client)
    organization_a = _create_organization(client, "Alpha Orthopedics")
    organization_b = _create_organization(client, "Beta Orthopedics")
    organization_a_id = int(organization_a["id"])
    organization_b_id = int(organization_b["id"])
    location_a_id = _create_location(organization_a_id, "ALPHA", "Alpha Clinic")
    location_b_id = _create_location(organization_b_id, "BETA", "Beta Clinic")

    doctor_a = client.post(
        f"/api/v1/organizations/{organization_a_id}/doctors",
        json={
            "first_name": "Iris",
            "last_name": "Stone",
            "accepts_new_patients": True,
            "location_ids": [location_a_id],
            "capabilities": [{"body_part": "Knee", "issue_type": "General"}],
        },
    )
    assert doctor_a.status_code == 201, doctor_a.get_json()
    doctor_a_payload = doctor_a.get_json()["doctor"]
    assert doctor_a_payload["organization_id"] == organization_a_id
    assert [location["id"] for location in doctor_a_payload["locations"]] == [location_a_id]

    doctor_b = client.post(
        f"/api/v1/organizations/{organization_b_id}/doctors",
        json={
            "first_name": "Nolan",
            "last_name": "Reed",
            "accepts_new_patients": True,
            "location_ids": [location_b_id],
            "capabilities": [{"body_part": "Shoulder", "issue_type": "Sports Medicine"}],
        },
    )
    assert doctor_b.status_code == 201, doctor_b.get_json()
    doctor_b_payload = doctor_b.get_json()["doctor"]

    alpha_doctors = client.get(f"/api/v1/organizations/{organization_a_id}/doctors")
    assert alpha_doctors.status_code == 200, alpha_doctors.get_json()
    alpha_ids = {doctor["id"] for doctor in alpha_doctors.get_json()["doctors"]}
    assert doctor_a_payload["id"] in alpha_ids
    assert doctor_b_payload["id"] not in alpha_ids

    beta_doctors = client.get(f"/api/v1/organizations/{organization_b_id}/doctors")
    assert beta_doctors.status_code == 200, beta_doctors.get_json()
    beta_ids = {doctor["id"] for doctor in beta_doctors.get_json()["doctors"]}
    assert doctor_b_payload["id"] in beta_ids
    assert doctor_a_payload["id"] not in beta_ids

    retrieved = client.get(f"/api/v1/organizations/{organization_a_id}/doctors/{doctor_a_payload['id']}")
    assert retrieved.status_code == 200, retrieved.get_json()
    assert retrieved.get_json()["doctor"]["id"] == doctor_a_payload["id"]

    wrong_get = client.get(f"/api/v1/organizations/{organization_b_id}/doctors/{doctor_a_payload['id']}")
    assert wrong_get.status_code == 404, wrong_get.get_json()
    assert wrong_get.get_json()["error"]["code"] == "DOCTOR_NOT_FOUND"

    updated = client.patch(
        f"/api/v1/organizations/{organization_a_id}/doctors/{doctor_a_payload['id']}",
        json={"last_name": "Gray", "accepts_new_patients": False, "active": False},
    )
    assert updated.status_code == 200, updated.get_json()
    updated_doctor = updated.get_json()["doctor"]
    assert updated_doctor["last_name"] == "Gray"
    assert updated_doctor["accepts_new_patients"] is False
    assert updated_doctor["active"] is False

    wrong_patch = client.patch(
        f"/api/v1/organizations/{organization_b_id}/doctors/{doctor_a_payload['id']}",
        json={"active": True},
    )
    assert wrong_patch.status_code == 404, wrong_patch.get_json()
    assert wrong_patch.get_json()["error"]["code"] == "DOCTOR_NOT_FOUND"


def test_doctor_location_must_belong_to_selected_organization(client: FlaskClient) -> None:
    _login_admin(client)
    organization_a = _create_organization(client, "Gamma Orthopedics")
    organization_b = _create_organization(client, "Delta Orthopedics")
    wrong_location_id = _create_location(int(organization_b["id"]), "DELTA", "Delta Clinic")

    response = client.post(
        f"/api/v1/organizations/{organization_a['id']}/doctors",
        json={
            "first_name": "Mara",
            "last_name": "Hayes",
            "accepts_new_patients": True,
            "location_ids": [wrong_location_id],
        },
    )

    assert response.status_code == 404, response.get_json()
    assert response.get_json()["error"]["code"] == "LOCATION_NOT_FOUND"
