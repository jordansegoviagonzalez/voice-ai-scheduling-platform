from __future__ import annotations

import json

from flask.testing import FlaskClient

from app.extensions import get_session_factory
from app.models import Location


def _login_admin(client: FlaskClient) -> None:
    response = client.post(
        "/api/auth/admin/login",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert response.status_code == 200, response.get_json()


def _create_organization(
    client: FlaskClient,
    name: str,
    slug: str | None = None,
    **overrides: object,
) -> dict[str, object]:
    payload = {"name": name}
    if slug is not None:
        payload["slug"] = slug
    payload.update(overrides)
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


def test_organization_can_be_created_without_slug_and_listed(client: FlaskClient) -> None:
    _login_admin(client)

    created = _create_organization(client, "Lakeside Cardiology")

    assert created["slug"] == "lakeside-cardiology"
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
    payload = response.get_json()
    assert payload["error"]["code"] == "ORGANIZATION_NOT_FOUND"
    serialized = json.dumps(payload)
    assert "default-orthopedics" not in serialized
    assert "client_links" not in serialized
    assert "voice" not in serialized


def test_organization_response_includes_safe_client_links_and_voice_setup(client: FlaskClient) -> None:
    _login_admin(client)

    organization = _create_organization(
        client,
        "Lakeside Cardiology",
        slug="lakeside-cardiology",
        voice_enabled=True,
        voice_phone_number="+15550101010",
    )

    assert organization["client_links"] == {
        "chat_path": "/chat/lakeside-cardiology",
        "vogent_webhook_path": "/api/v1/organizations/slug/lakeside-cardiology/vogent/webhooks",
        "vogent_function_base_path": "/api/v1/organizations/slug/lakeside-cardiology/vogent/functions",
    }
    assert organization["voice"] == {
        "enabled": True,
        "phone_number": "+15550101010",
        "status": "Configured",
    }
    _assert_no_secret_material(organization)

    public_response = client.get("/api/v1/organizations/slug/lakeside-cardiology")
    assert public_response.status_code == 200, public_response.get_json()
    public_organization = public_response.get_json()["organization"]
    assert public_organization["client_links"] == organization["client_links"]
    assert public_organization["voice"] == organization["voice"]
    _assert_no_secret_material(public_organization)


def test_client_links_and_voice_setup_are_isolated_between_organizations(client: FlaskClient) -> None:
    _login_admin(client)
    org_a = _create_organization(
        client,
        "Voice Org A",
        slug="voice-org-a",
        voice_enabled=True,
        voice_phone_number="+15550101011",
    )
    org_b = _create_organization(
        client,
        "Voice Org B",
        slug="voice-org-b",
        voice_enabled=False,
        voice_phone_number="+15550101012",
    )

    assert org_a["client_links"]["chat_path"] == "/chat/voice-org-a"
    assert org_a["client_links"]["vogent_webhook_path"] == "/api/v1/organizations/slug/voice-org-a/vogent/webhooks"
    assert org_a["client_links"]["vogent_function_base_path"] == (
        "/api/v1/organizations/slug/voice-org-a/vogent/functions"
    )
    assert org_b["client_links"]["chat_path"] == "/chat/voice-org-b"
    assert org_b["client_links"]["vogent_webhook_path"] == "/api/v1/organizations/slug/voice-org-b/vogent/webhooks"
    assert org_b["client_links"]["vogent_function_base_path"] == (
        "/api/v1/organizations/slug/voice-org-b/vogent/functions"
    )

    serialized_a = json.dumps({"client_links": org_a["client_links"], "voice": org_a["voice"]}, sort_keys=True)
    serialized_b = json.dumps({"client_links": org_b["client_links"], "voice": org_b["voice"]}, sort_keys=True)
    assert "voice-org-b" not in serialized_a
    assert "voice-org-a" not in serialized_b
    assert "+15550101012" not in serialized_a
    assert "+15550101011" not in serialized_b


def test_organization_voice_config_can_be_updated_programmatically(client: FlaskClient) -> None:
    _login_admin(client)
    org_a = _create_organization(client, "Programmatic Voice A", slug="programmatic-voice-a")
    org_b = _create_organization(client, "Programmatic Voice B", slug="programmatic-voice-b")

    updated = client.patch(
        f"/api/v1/organizations/{org_a['id']}",
        json={"voice_enabled": True, "voice_phone_number": "+15550101013"},
    )
    assert updated.status_code == 200, updated.get_json()
    updated_org_a = updated.get_json()["organization"]
    assert updated_org_a["voice"] == {
        "enabled": True,
        "phone_number": "+15550101013",
        "status": "Configured",
    }

    fetched = client.get(f"/api/v1/organizations/{org_a['id']}")
    assert fetched.status_code == 200, fetched.get_json()
    assert fetched.get_json()["organization"]["voice"] == updated_org_a["voice"]

    cleared = client.patch(f"/api/v1/organizations/{org_a['id']}", json={"voice_phone_number": None})
    assert cleared.status_code == 200, cleared.get_json()
    assert cleared.get_json()["organization"]["voice"] == {
        "enabled": True,
        "phone_number": None,
        "status": "Voice number not configured yet",
    }

    org_b_response = client.get(f"/api/v1/organizations/{org_b['id']}")
    assert org_b_response.status_code == 200, org_b_response.get_json()
    org_b_payload = org_b_response.get_json()["organization"]
    assert org_b_payload["voice"]["phone_number"] is None
    assert "+15550101013" not in json.dumps(org_b_payload)


def _assert_no_secret_material(payload: dict[str, object]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    assert "VOGENT_FUNCTION_SECRET" not in serialized
    assert "VOGENT_WEBHOOK_SECRET" not in serialized
    assert "OPENAI_API_KEY" not in serialized
    assert "api_key" not in serialized.lower()
    assert "secret" not in serialized.lower()


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


def test_doctor_capabilities_support_broader_service_lines(client: FlaskClient) -> None:
    _login_admin(client)
    organization = _create_organization(client, "Benchmark Specialty Group")
    organization_id = int(organization["id"])

    examples = [
        ("Cara", "Pulse", "Heart/Circulation", "Routine Consult"),
        ("Dina", "Mouth", "Mouth/Teeth/Tongue", "Pain"),
        ("Sam", "Skin", "Skin/Hair/Nails", "Rash/Itching"),
        ("Evan", "Throat", "Ear/Nose/Throat", "Pain"),
    ]
    created_doctor_ids: list[int] = []
    for first_name, last_name, area, issue_type in examples:
        response = client.post(
            f"/api/v1/organizations/{organization_id}/doctors",
            json={
                "first_name": first_name,
                "last_name": last_name,
                "accepts_new_patients": True,
                "capabilities": [{"body_part": area, "issue_type": issue_type}],
            },
        )
        assert response.status_code == 201, response.get_json()
        doctor = response.get_json()["doctor"]
        created_doctor_ids.append(doctor["id"])
        assert doctor["organization_id"] == organization_id
        assert doctor["capabilities"] == [{"body_part": area, "issue_type": issue_type}]

    listed = client.get(f"/api/v1/organizations/{organization_id}/doctors")
    assert listed.status_code == 200, listed.get_json()
    listed_by_id = {doctor["id"]: doctor for doctor in listed.get_json()["doctors"]}
    assert set(created_doctor_ids).issubset(listed_by_id)
    assert listed_by_id[created_doctor_ids[0]]["primary_specialty"] == "Cardiology / Heart & Circulation"


def test_location_crud_is_scoped_to_selected_organization(client: FlaskClient) -> None:
    _login_admin(client)
    organization_a = _create_organization(client, "Omega Orthopedics")
    organization_b = _create_organization(client, "Zeta Orthopedics")
    organization_a_id = int(organization_a["id"])
    organization_b_id = int(organization_b["id"])

    # Create location A
    location_a = client.post(
        f"/api/v1/organizations/{organization_a_id}/locations",
        json={
            "code": "OMEGA-1",
            "name": "Omega Clinic Main",
            "address_line1": "123 Omega St",
            "city": "Seattle"
        }
    )
    assert location_a.status_code == 201, location_a.get_json()
    location_a_payload = location_a.get_json()["location"]
    assert location_a_payload["organization_id"] == organization_a_id
    assert location_a_payload["city"] == "Seattle"

    # Create location B
    location_b = client.post(
        f"/api/v1/organizations/{organization_b_id}/locations",
        json={
            "code": "ZETA-1",
            "name": "Zeta Clinic Main"
        }
    )
    assert location_b.status_code == 201, location_b.get_json()
    location_b_payload = location_b.get_json()["location"]

    # List locations A
    alpha_locations = client.get(f"/api/v1/organizations/{organization_a_id}/locations")
    assert alpha_locations.status_code == 200, alpha_locations.get_json()
    alpha_ids = {location["id"] for location in alpha_locations.get_json()["locations"]}
    assert location_a_payload["id"] in alpha_ids
    assert location_b_payload["id"] not in alpha_ids

    # List locations B
    beta_locations = client.get(f"/api/v1/organizations/{organization_b_id}/locations")
    assert beta_locations.status_code == 200, beta_locations.get_json()
    beta_ids = {location["id"] for location in beta_locations.get_json()["locations"]}
    assert location_b_payload["id"] in beta_ids
    assert location_a_payload["id"] not in beta_ids

    # Get location A
    retrieved = client.get(f"/api/v1/organizations/{organization_a_id}/locations/{location_a_payload['id']}")
    assert retrieved.status_code == 200, retrieved.get_json()
    assert retrieved.get_json()["location"]["id"] == location_a_payload["id"]

    # Cross-org get should fail
    wrong_get = client.get(f"/api/v1/organizations/{organization_b_id}/locations/{location_a_payload['id']}")
    assert wrong_get.status_code == 404, wrong_get.get_json()

    # Update location A
    updated = client.patch(
        f"/api/v1/organizations/{organization_a_id}/locations/{location_a_payload['id']}",
        json={"name": "Omega Clinic North", "state": "WA"}
    )
    assert updated.status_code == 200, updated.get_json()
    updated_location = updated.get_json()["location"]
    assert updated_location["name"] == "Omega Clinic North"
    assert updated_location["state"] == "WA"

    # Cross-org patch should fail
    wrong_patch = client.patch(
        f"/api/v1/organizations/{organization_b_id}/locations/{location_a_payload['id']}",
        json={"name": "Omega Clinic Hacked"}
    )
    assert wrong_patch.status_code == 404, wrong_patch.get_json()


def test_organization_business_hours(client: FlaskClient) -> None:
    _login_admin(client)

    # Create org with business hours
    created = client.post(
        "/api/v1/organizations",
        json={
            "name": "Hours Clinic",
            "business_hours": {"Monday": "9:00 AM - 5:00 PM"}
        }
    )
    assert created.status_code == 201, created.get_json()
    org = created.get_json()["organization"]
    assert org["business_hours"] == {"Monday": "9:00 AM - 5:00 PM"}

    # Update org business hours
    updated = client.patch(
        f"/api/v1/organizations/{org['id']}",
        json={
            "business_hours": {"Monday": "8:00 AM - 4:00 PM", "Tuesday": "9:00 AM - 5:00 PM"}
        }
    )
    assert updated.status_code == 200, updated.get_json()
    org_updated = updated.get_json()["organization"]
    assert org_updated["business_hours"] == {"Monday": "8:00 AM - 4:00 PM", "Tuesday": "9:00 AM - 5:00 PM"}


def test_organization_voice_setup_and_client_links(client: FlaskClient) -> None:
    _login_admin(client)

    # Create Lakeside
    lakeside = client.post(
        "/api/v1/organizations",
        json={
            "name": "Voice Lakeside",
            "slug": "voice-lakeside",
            "voice_enabled": False
        }
    )
    assert lakeside.status_code == 201
    lakeside_org = lakeside.get_json()["organization"]

    # Create Northside
    northside = client.post(
        "/api/v1/organizations",
        json={
            "name": "Voice Northside",
            "slug": "voice-northside",
            "voice_enabled": True,
            "voice_phone_number": "+15551234567"
        }
    )
    assert northside.status_code == 201
    northside_org = northside.get_json()["organization"]

    # Verify Lakeside setup
    assert lakeside_org["client_links"]["chat_path"] == "/chat/voice-lakeside"
    assert lakeside_org["client_links"]["vogent_webhook_path"] == (
        "/api/v1/organizations/slug/voice-lakeside/vogent/webhooks"
    )
    assert lakeside_org["voice"]["enabled"] is False
    assert lakeside_org["voice"]["phone_number"] is None
    assert "northside" not in str(lakeside_org)

    # Verify Northside setup
    assert northside_org["client_links"]["chat_path"] == "/chat/voice-northside"
    assert northside_org["client_links"]["vogent_webhook_path"] == (
        "/api/v1/organizations/slug/voice-northside/vogent/webhooks"
    )
    assert northside_org["voice"]["enabled"] is True
    assert northside_org["voice"]["phone_number"] == "+15551234567"
    assert "lakeside" not in str(northside_org)

    # Verify Public endpoints don't cross-contaminate or fallback
    lakeside_pub = client.get("/api/v1/organizations/slug/voice-lakeside").get_json()["organization"]
    assert lakeside_pub["client_links"]["chat_path"] == "/chat/voice-lakeside"

    northside_pub = client.get("/api/v1/organizations/slug/voice-northside").get_json()["organization"]
    assert northside_pub["client_links"]["chat_path"] == "/chat/voice-northside"

    invalid_pub = client.get("/api/v1/organizations/slug/invalid-org-slug")
    assert invalid_pub.status_code == 404
    assert invalid_pub.get_json()["error"]["code"] == "ORGANIZATION_NOT_FOUND"

    # Update to clear phone number
    updated = client.patch(
        f"/api/v1/organizations/{northside_org['id']}",
        json={"voice_phone_number": None}
    )
    assert updated.status_code == 200
    org_updated = updated.get_json()["organization"]
    assert org_updated["voice"]["phone_number"] is None
    assert org_updated["voice"]["status"] == "Voice number not configured yet"
