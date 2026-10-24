from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


def override_settings() -> Settings:
    return Settings(openai_api_key=None)


def test_review_api_in_demo_mode() -> None:
    app.dependency_overrides[get_settings] = override_settings
    client = TestClient(app)

    response = client.post(
        "/review",
        files={"file": ("design.md", "# 設計書\n処理仕様".encode(), "text/markdown")},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["document_name"] == "design.md"
    assert payload["demo_mode"] is True
    assert payload["issue_count"] == 3
    assert payload["high_count"] == 1


def test_review_api_rejects_unsupported_file() -> None:
    app.dependency_overrides[get_settings] = override_settings
    client = TestClient(app)

    response = client.post(
        "/review",
        files={"file": ("design.csv", b"id,name", "text/csv")},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 400
    assert "対応していない" in response.json()["detail"]
