"""Auth dependency + user-isolation tests."""

from __future__ import annotations

from backend.tests.conftest import auth, create_camera


def test_missing_token_rejected(client):
    assert client.get("/api/cameras").status_code == 401


def test_bad_scheme_rejected(client):
    assert (
        client.get("/api/cameras", headers={"Authorization": "Token abc"}).status_code
        == 401
    )


def test_valid_token_ok(client):
    assert client.get("/api/cameras", headers=auth("user-a")).status_code == 200


def test_camera_ownership(client):
    cam_a = create_camera(client, "A cam", user="user-a")
    # user-b must not see user-a's camera
    listing = client.get("/api/cameras", headers=auth("user-b")).json()
    assert all(c["id"] != cam_a for c in listing)
    # nor start/stop/delete it
    assert (
        client.post(f"/api/cameras/{cam_a}/start", headers=auth("user-b")).status_code
        == 404
    )
    assert (
        client.delete(f"/api/cameras/{cam_a}", headers=auth("user-b")).status_code
        == 404
    )
