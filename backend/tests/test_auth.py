import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy.orm import Session

from app.core import security
from app.models.user import User

SIGNUP = {"username": "homelabber", "email": "Me@Example.com", "password": "correct horse battery"}


@pytest.fixture
def sent_emails(monkeypatch: MonkeyPatch) -> list[tuple[str, str]]:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.api.routes.auth.send_verification_email",
        lambda to, username, token: sent.append((to, token)),
    )
    return sent


def _verify(client: TestClient, sent: list[tuple[str, str]]) -> None:
    assert client.post("/api/auth/verify-email", json={"token": sent[-1][1]}).status_code == 200


def test_signup_creates_unverified_user_and_sends_email(
    client: TestClient, sent_emails: list[tuple[str, str]]
) -> None:
    response = client.post("/api/auth/signup", json=SIGNUP)
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "homelabber"
    assert body["is_verified"] is False
    assert "password" not in body and "password_hash" not in body
    assert [to for to, _ in sent_emails] == ["Me@example.com"]


def test_signup_rejects_duplicates_case_insensitively(
    client: TestClient, sent_emails: list[tuple[str, str]]
) -> None:
    client.post("/api/auth/signup", json=SIGNUP)
    same_name = {**SIGNUP, "username": "HOMELABBER", "email": "other@example.com"}
    same_email = {**SIGNUP, "username": "other", "email": "me@example.com"}
    assert client.post("/api/auth/signup", json=same_name).status_code == 409
    assert client.post("/api/auth/signup", json=same_email).status_code == 409


@pytest.mark.parametrize(
    "patch",
    [
        {"username": "ab"},
        {"username": "has space"},
        {"email": "not-an-email"},
        {"password": "short"},
    ],
)
def test_signup_validates_input(client: TestClient, patch: dict[str, str]) -> None:
    assert client.post("/api/auth/signup", json={**SIGNUP, **patch}).status_code == 422


def test_password_is_hashed(
    client: TestClient, db_session: Session, sent_emails: list[tuple[str, str]]
) -> None:
    client.post("/api/auth/signup", json=SIGNUP)
    user = db_session.query(User).one()
    assert user.password_hash != SIGNUP["password"]
    assert security.verify_password(SIGNUP["password"], user.password_hash)


def test_login_requires_verified_email(
    client: TestClient, sent_emails: list[tuple[str, str]]
) -> None:
    client.post("/api/auth/signup", json=SIGNUP)
    creds = {"identifier": "homelabber", "password": SIGNUP["password"]}
    assert client.post("/api/auth/login", json=creds).status_code == 403

    _verify(client, sent_emails)
    response = client.post("/api/auth/login", json=creds)
    assert response.status_code == 200
    token = response.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["is_verified"] is True


def test_login_by_email_and_wrong_password(
    client: TestClient, sent_emails: list[tuple[str, str]]
) -> None:
    client.post("/api/auth/signup", json=SIGNUP)
    _verify(client, sent_emails)
    ok = client.post(
        "/api/auth/login", json={"identifier": "me@example.com", "password": SIGNUP["password"]}
    )
    assert ok.status_code == 200
    bad = client.post("/api/auth/login", json={"identifier": "homelabber", "password": "nope"})
    assert bad.status_code == 401
    unknown = client.post("/api/auth/login", json={"identifier": "ghost", "password": "nope"})
    assert unknown.status_code == 401


def test_verify_rejects_bad_and_wrong_type_tokens(
    client: TestClient, sent_emails: list[tuple[str, str]]
) -> None:
    user = client.post("/api/auth/signup", json=SIGNUP).json()
    assert client.post("/api/auth/verify-email", json={"token": "garbage"}).status_code == 400
    # An access token must not be usable as a verification token.
    import uuid

    access = security.create_token(uuid.UUID(user["id"]), "access")
    assert client.post("/api/auth/verify-email", json={"token": access}).status_code == 400


def test_verification_token_cannot_authenticate(
    client: TestClient, sent_emails: list[tuple[str, str]]
) -> None:
    client.post("/api/auth/signup", json=SIGNUP)
    verify_token = sent_emails[-1][1]
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {verify_token}"})
    assert response.status_code == 401


def test_me_requires_auth(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_resend_verification_is_uniform(
    client: TestClient, sent_emails: list[tuple[str, str]]
) -> None:
    client.post("/api/auth/signup", json=SIGNUP)
    sent_emails.clear()
    known = client.post("/api/auth/resend-verification", json={"email": "me@example.com"})
    unknown = client.post("/api/auth/resend-verification", json={"email": "no@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(sent_emails) == 1

    _verify(client, sent_emails)
    sent_emails.clear()
    client.post("/api/auth/resend-verification", json={"email": "me@example.com"})
    assert sent_emails == []
