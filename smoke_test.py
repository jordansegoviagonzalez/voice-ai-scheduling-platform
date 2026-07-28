import requests
import json
import time

BASE_URL = "https://scheduler.oliviacarter.com/api"
email = "olivia.carter.phase2.demo@example.com"
password = "Patient!2026"

session = requests.Session()

def print_step(msg):
    print(f"\n--- {msg} ---")

print_step("1. Patient sign-in")
resp = session.post(f"{BASE_URL}/chat/sessions", json={
    "patientMode": "returning",
    "email": email,
    "password": password
})
assert resp.status_code in (200, 201), f"Sign-in failed: {resp.text}"
session_id = resp.json()["sessionId"]
print("Session ID:", session_id)

messages = [
    "My right knee hurts from a sports injury",
    "It has been going on for 3 days and the pain is level 6",
    "It is a new patient visit",
    "I prefer the north clinic, earliest possible",
    "Yes, that is all."
]

print_step("2. Conversational intake")
chat_session = None
for msg in messages:
    print(f"Sending: {msg}")
    resp = session.post(f"{BASE_URL}/chat/sessions/{session_id}/messages", json={"message": msg})
    assert resp.status_code == 200, f"Failed: {resp.text}"
    chat_session = resp.json()
    print("Step:", chat_session["currentStep"])
    print("AI:", chat_session["assistantMessage"]["content"])
    if chat_session["currentStep"] == "slot_selection":
        break
    time.sleep(1)

print("Final step:", chat_session["currentStep"])

if chat_session["currentStep"] == "slot_selection":
    first_doc = chat_session["recommendations"][0]
    first_loc = first_doc["locations"][0]
    slot = first_loc["available_slots"][0]
    print(f"Booking {slot['display_date']} {slot['display_time']} with {first_doc['physician_name']}")
    
    resp = session.post(f"{BASE_URL}/chat/sessions/{session_id}/appointments/select", json={
        "slotId": slot["id"]
    })
    assert resp.status_code == 200, f"Slot selection failed: {resp.text}"

    resp = session.post(f"{BASE_URL}/chat/sessions/{session_id}/appointments/confirm")
    assert resp.status_code == 200, f"Booking failed: {resp.text}"
    print("Booking confirmed!")
    
    # Check Admin dashboard
    admin_session = requests.Session()
    resp = admin_session.post(f"{BASE_URL}/auth/admin/login", json={
        "email": "admin@example.com",
        "password": "admin123"
    })
    
    resp = admin_session.get(f"{BASE_URL}/v1/dashboard/chat-sessions/{session_id}")
    admin_chat = resp.json()["chat_session"]
    print("Admin Web Chat source:", admin_chat.get("source"))
    print("Duration collected:", admin_chat.get("collected_data", {}).get("symptom_duration"))
    print("SMOKE TEST PASSED!")
else:
    print("Failed to reach slot_selection.")
