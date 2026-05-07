import tempfile

from fastapi.testclient import TestClient

from app.config import settings
from app.db import init_db
from app.main import app


def main() -> None:
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
        created.raise_for_status()
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
        memory.raise_for_status()
        result = client.post(
            f"/projects/{project_id}/retrieve",
            json={"query": "灵气 经脉 共振", "limit": 3},
        )
        result.raise_for_status()
        assert result.json()["memories"], result.json()
        print("smoke ok")


if __name__ == "__main__":
    main()
