from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _register_user(
    client,
    *,
    full_name: str = "Admin User",
    email: str = "admin@example.com",
    password: str = "StrongPass123!",
) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": full_name,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login_user(client, *, email: str, password: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _register_device(client, *, user_token: str, device_identifier: str) -> dict:
    response = client.post(
        "/api/v1/devices/register",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "device_identifier": device_identifier,
            "name": f"Device {device_identifier}",
            "device_type": "patient_monitor",
            "manufacturer": "Acme Medical",
            "model": "PM-1000",
            "firmware_version": "1.0.0",
            "location": "ICU-1",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _issue_device_token(client, *, api_key: str) -> dict:
    response = client.post(
        "/api/v1/devices/token",
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_health_endpoint(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"


def test_auth_register_login_and_current_user(client) -> None:
    registration = _register_user(client)
    assert registration["user"]["role"] == "admin"

    login = _login_user(client, email="admin@example.com", password="StrongPass123!")
    token = login["access_token"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    me_body = me.json()
    assert me_body["email"] == "admin@example.com"
    assert me_body["role"] == "admin"


def test_rbac_admin_can_create_user_and_analyst_is_forbidden_for_admin_routes(client) -> None:
    admin_registration = _register_user(client)
    admin_token = admin_registration["access_token"]

    create_user_response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "full_name": "Analyst User",
            "email": "analyst@example.com",
            "password": "StrongPass123!",
            "role": "analyst",
            "is_active": True,
        },
    )
    assert create_user_response.status_code == 201, create_user_response.text

    analyst_login = _login_user(
        client,
        email="analyst@example.com",
        password="StrongPass123!",
    )
    analyst_token = analyst_login["access_token"]

    list_users_as_analyst = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert list_users_as_analyst.status_code == 403
    assert "permission" in list_users_as_analyst.json()["detail"].lower()


def test_device_registration_token_exchange_and_current_device(client) -> None:
    admin_registration = _register_user(client)
    admin_token = admin_registration["access_token"]

    device = _register_device(
        client,
        user_token=admin_token,
        device_identifier="DEV-0001",
    )
    token_payload = _issue_device_token(client, api_key=device["api_key"])
    device_token = token_payload["access_token"]

    me = client.get(
        "/api/v1/devices/me",
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert me.status_code == 200
    me_body = me.json()
    assert me_body["device_identifier"] == "DEV-0001"
    assert me_body["status"] == "active"


def test_telemetry_ingest_pagination_filtering_and_alerts(client) -> None:
    admin_registration = _register_user(client)
    admin_token = admin_registration["access_token"]
    device = _register_device(
        client,
        user_token=admin_token,
        device_identifier="DEV-0002",
    )
    device_token = _issue_device_token(client, api_key=device["api_key"])["access_token"]

    now = datetime.now(timezone.utc)
    payloads = [
        {
            "recorded_at": (now - timedelta(minutes=2)).isoformat(),
            "metric_name": "heart_rate",
            "metric_type": "vital_sign",
            "value_numeric": 78.5,
            "unit": "bpm",
            "payload": {"source": "test"},
        },
        {
            "recorded_at": (now - timedelta(minutes=1)).isoformat(),
            "metric_name": "battery_status",
            "metric_type": "status",
            "value_text": "critical",
            "payload": {"source": "test"},
        },
        {
            "recorded_at": now.isoformat(),
            "metric_name": "spo2",
            "metric_type": "vital_sign",
            "value_numeric": 96.2,
            "unit": "%",
            "payload": {"source": "test"},
        },
    ]

    for payload in payloads:
        response = client.post(
            "/api/v1/telemetry",
            headers={"Authorization": f"Bearer {device_token}"},
            json=payload,
        )
        assert response.status_code == 201, response.text

    page_1 = client.get(
        "/api/v1/telemetry?page=1&page_size=2",
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert page_1.status_code == 200
    body_1 = page_1.json()
    assert body_1["total_items"] == 3
    assert body_1["total_pages"] == 2
    assert len(body_1["items"]) == 2

    page_2 = client.get(
        "/api/v1/telemetry?page=2&page_size=2",
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert page_2.status_code == 200
    body_2 = page_2.json()
    assert len(body_2["items"]) == 1

    start_time = (now - timedelta(minutes=1, seconds=30)).isoformat()
    end_time = (now - timedelta(seconds=30)).isoformat()
    filtered = client.get(
        "/api/v1/telemetry",
        headers={"Authorization": f"Bearer {device_token}"},
        params={"start_time": start_time, "end_time": end_time},
    )
    assert filtered.status_code == 200
    filtered_body = filtered.json()
    assert filtered_body["total_items"] == 1
    assert filtered_body["items"][0]["metric_name"] == "battery_status"

    alerts = client.get(
        "/api/v1/alerts",
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert alerts.status_code == 200
    alerts_body = alerts.json()
    assert alerts_body["total_items"] >= 1
    assert any(item["severity"] == "critical" for item in alerts_body["items"])


def test_request_validation_rejects_non_json_content_type(client) -> None:
    response = client.post(
        "/api/v1/auth/register",
        content="not-json",
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 415
    assert "application/json" in response.json()["detail"]


def test_batch_telemetry_ingestion_path(client) -> None:
    admin_registration = _register_user(client)
    admin_token = admin_registration["access_token"]
    device = _register_device(
        client,
        user_token=admin_token,
        device_identifier="DEV-BATCH-001",
    )
    device_token = _issue_device_token(client, api_key=device["api_key"])["access_token"]
    now = datetime.now(timezone.utc)

    batch_payload = {
        "items": [
            {
                "recorded_at": now.isoformat(),
                "metric_name": "heart_rate",
                "metric_type": "vital_sign",
                "value_numeric": 81.0,
                "unit": "bpm",
                "payload": {"source": "batch-test"},
            },
            {
                "recorded_at": (now + timedelta(seconds=1)).isoformat(),
                "metric_name": "network_status",
                "metric_type": "status",
                "value_text": "tampered",
                "payload": {
                    "source": "batch-test",
                    "intrusion_detected": True,
                    "intrusion_type": "device_tampering",
                    "intrusion_score": 0.96,
                },
            },
            {
                "recorded_at": (now + timedelta(seconds=2)).isoformat(),
                "metric_name": "battery_status",
                "metric_type": "status",
                "value_text": "critical",
                "payload": {"source": "batch-test"},
            },
        ]
    }

    ingest_response = client.post(
        "/api/v1/telemetry/batch",
        headers={"Authorization": f"Bearer {device_token}"},
        json=batch_payload,
    )
    assert ingest_response.status_code == 201, ingest_response.text
    body = ingest_response.json()
    assert body["ingested_items"] == 3
    assert body["intrusion_items"] >= 1
    assert body["alerts_created"] >= 1
