import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.db import ResearchHistory, SessionLocal


@pytest.fixture
def client():
    return TestClient(app)


def test_clear_search_history_workflow(client):
    # 1. Seed test history records
    with SessionLocal() as db:
        h1 = ResearchHistory(user_query="Test Query 1", answer="Answer 1", status="completed")
        h2 = ResearchHistory(user_query="Test Query 2", answer="Answer 2", status="completed")
        h3 = ResearchHistory(user_query="Test Query 3", answer="Answer 3", status="completed")
        db.add_all([h1, h2, h3])
        db.commit()
        id1, id2, id3 = h1.id, h2.id, h3.id

    # 2. List history
    resp = client.get("/history")
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()]
    assert id1 in ids
    assert id2 in ids
    assert id3 in ids

    # 3. Delete single history item
    resp_del1 = client.delete(f"/history/{id1}")
    assert resp_del1.status_code == 200
    assert resp_del1.json() == {"status": "ok", "deleted_id": id1}

    # 4. Deleting non-existent item returns 404
    resp_del_404 = client.delete(f"/history/{id1}")
    assert resp_del_404.status_code == 404

    # 5. Delete via alias /research/{rid}
    resp_del2 = client.delete(f"/research/{id2}")
    assert resp_del2.status_code == 200
    assert resp_del2.json() == {"status": "ok", "deleted_id": id2}

    # 6. Clear all remaining history
    resp_clear = client.delete("/history")
    assert resp_clear.status_code == 200
    data = resp_clear.json()
    assert data["status"] == "ok"
    assert data["deleted_count"] >= 1

    # 7. List history is now empty
    resp_empty = client.get("/history")
    assert resp_empty.status_code == 200
    assert len(resp_empty.json()) == 0
