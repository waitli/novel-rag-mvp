import tempfile

from fastapi.testclient import TestClient

from app.config import settings
from app.db import init_db
from app.main import app


def test_project_memory_retrieve_flow():
    with tempfile.NamedTemporaryFile() as tmp:
        settings.database_path = tmp.name
        init_db()
        client = TestClient(app)

        created = client.post(
            "/projects",
            json={
                "title": "科学修仙路",
                "genre": "科学修仙",
                "premise": "用科学方法理解灵气",
            },
        )
        assert created.status_code == 200
        project_id = created.json()["id"]

        memory = client.post(
            f"/projects/{project_id}/memories",
            json={
                "source_type": "character",
                "title": "主角状态",
                "body": "林澈正在研究灵气浓度和经脉共振之间的关系。",
                "metadata": {"chapter": 1},
            },
        )
        assert memory.status_code == 200

        result = client.post(
            f"/projects/{project_id}/retrieve",
            json={"query": "灵气 经脉 共振", "limit": 3},
        )
        assert result.status_code == 200
        memories = result.json()["memories"]
        assert memories
        assert "经脉共振" in memories[0]["body"]
