"""GcsBlobStore.signed_url on credentials that cannot sign (a developer's own `gcloud auth application-default login`).

Cloud Run signs through IAM (its credentials carry a service-account email). A developer machine has user credentials: a
token and no private key, so google-cloud-storage raises AttributeError and /api/files answered 500, which left the SLD
and 3D hall empty with "Live updates stopped (API 500)". It must say "cannot sign" (SigningUnavailable) instead, so
/api/files serves the bytes inline, exactly as it does for the in-process store.
"""
from datetime import timedelta

import pytest
from google.cloud import storage
from google.oauth2.credentials import Credentials

import google.auth
from kirchhoff.runs.blobs import GcsBlobStore, SigningUnavailable


class UserCreds(Credentials):
    """A signed-in user's credentials: an access token, no private key. refresh() is a no-op (no network in tests)."""

    def refresh(self, request):  # noqa: ARG002
        pass


def _store(creds) -> GcsBlobStore:
    store = GcsBlobStore("test-bucket")
    store._bucket = storage.Client(project="p", credentials=creds).bucket("test-bucket")
    return store


def test_user_credentials_cannot_sign_so_the_store_says_so(monkeypatch):
    creds = UserCreds(token="user-token")
    monkeypatch.setattr(google.auth, "default", lambda *a, **k: (creds, "p"))
    with pytest.raises(SigningUnavailable):
        _store(creds).signed_url("workspaces/u1/revisions/r1/model.json")


class ServiceAccountCreds(UserCreds):
    """Cloud Run: the runtime service account, which signs through IAM signBlob."""

    service_account_email = "runtime@p.iam.gserviceaccount.com"


def test_service_account_credentials_still_sign_through_iam(monkeypatch):
    creds = ServiceAccountCreds(token="sa-token")
    monkeypatch.setattr(google.auth, "default", lambda *a, **k: (creds, "p"))
    seen = {}

    class FakeBlob:
        def generate_signed_url(self, **kw):
            seen.update(kw)
            return "https://signed.example/x"

    class FakeBucket:
        def blob(self, path):
            return FakeBlob()

    store = GcsBlobStore("test-bucket")
    store._bucket = FakeBucket()
    assert store.signed_url("workspaces/u1/x", 600) == "https://signed.example/x"
    assert seen["service_account_email"] == "runtime@p.iam.gserviceaccount.com"
    assert seen["access_token"] == "sa-token"
    assert seen["expiration"] == timedelta(seconds=600)
