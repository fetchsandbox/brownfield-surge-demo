"""Auth failure-path tests for verify_clerk_jwt.

The FetchSandbox `sessions_expired` workflow can prove Clerk's
state-machine, but not our local PyJWT enforcement. This file is the
local-only proof for the expired-token contract.
"""
import os
import time
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt as pyjwt
from fastapi.testclient import TestClient

ISSUER = "https://test.clerk.accounts.dev"


@pytest.fixture(scope="session", autouse=True)
def _env():
    os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_x")
    os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_x")
    os.environ.setdefault("ORDERS_SERVICE_URL", "http://localhost:9000")
    os.environ.setdefault("ORDERS_SERVICE_TOKEN", "t")
    os.environ.setdefault("CLERK_JWT_ISSUER", ISSUER)
    os.environ.setdefault("CLERK_WEBHOOK_SECRET", "whsec_clerk")


@pytest.fixture(scope="session")
def rsa_keypair():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def client(rsa_keypair, monkeypatch):
    from server import main

    signing_key = MagicMock()
    signing_key.key = rsa_keypair.public_key()
    monkeypatch.setattr(
        main.jwks_client,
        "get_signing_key_from_jwt",
        lambda token: signing_key,
    )
    return TestClient(main.app)


def _sign(private_key, *, exp_offset_seconds: int) -> str:
    now = int(time.time())
    payload = {
        "sub": "user_test_123",
        "iss": ISSUER,
        "iat": now - 60,
        "exp": now + exp_offset_seconds,
    }
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pyjwt.encode(payload, pem, algorithm="RS256")


def test_expired_jwt_returns_401(client, rsa_keypair):
    token = _sign(rsa_keypair, exp_offset_seconds=-3600)
    response = client.post(
        "/create-payment-intent",
        json={"amount_cents": 4999, "currency": "usd"},
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "test-expired-1",
        },
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_missing_authorization_header_returns_403(client):
    response = client.post(
        "/create-payment-intent",
        json={"amount_cents": 4999, "currency": "usd"},
        headers={"Idempotency-Key": "test-no-auth-1"},
    )
    assert response.status_code == 403


def test_wrong_issuer_returns_401(client, rsa_keypair):
    now = int(time.time())
    pem = rsa_keypair.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    token = pyjwt.encode(
        {
            "sub": "user_test_123",
            "iss": "https://attacker.example.com",
            "iat": now - 60,
            "exp": now + 3600,
        },
        pem,
        algorithm="RS256",
    )
    response = client.post(
        "/create-payment-intent",
        json={"amount_cents": 4999, "currency": "usd"},
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "test-bad-iss-1",
        },
    )
    assert response.status_code == 401
