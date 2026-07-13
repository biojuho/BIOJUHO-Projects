from __future__ import annotations

from pathlib import Path

from scripts import setup_content_hub


class _FakeDatabases:
    def __init__(self):
        self.created_payload = None

    def retrieve(self, database_id: str):
        return {"parent": {"type": "page_id", "page_id": f"parent-{database_id}"}}

    def create(self, **payload):
        self.created_payload = payload
        return {"id": "hub-db", "url": "https://notion.test/hub"}


class _FakePages:
    def __init__(self):
        self.created_payload = None

    def create(self, **payload):
        self.created_payload = payload
        return {"url": "https://notion.test/sample"}


class _FakeNotion:
    def __init__(self):
        self.databases = _FakeDatabases()
        self.pages = _FakePages()


def test_content_hub_properties_include_workflow_fields():
    props = setup_content_hub._content_hub_properties()

    assert props["Name"] == {"title": {}}
    assert "Feedback State" in props
    assert "Draft ID" in props
    assert props["Platform"]["multi_select"]["options"][0]["name"] == "X"


def test_parent_page_from_existing_database():
    notion = _FakeNotion()

    assert setup_content_hub._parent_page_from_database(notion, "source-db") == "parent-source-db"


def test_append_env_settings(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text("EXISTING=true\n", encoding="utf-8")

    assert setup_content_hub._append_env_settings(env_path, "hub-db") is True

    text = env_path.read_text(encoding="utf-8")
    assert "ENABLE_CONTENT_HUB=true" in text
    assert "CONTENT_HUB_DATABASE_ID=hub-db" in text
    assert "TARGET_PLATFORMS=x,threads,naver_blog" in text


def test_create_content_hub_database_payload():
    notion = _FakeNotion()

    result = setup_content_hub._create_content_hub_database(notion, "parent-page")

    assert result["id"] == "hub-db"
    assert notion.databases.created_payload["parent"] == {"type": "page_id", "page_id": "parent-page"}
    assert notion.databases.created_payload["title"][0]["text"]["content"] == setup_content_hub.CONTENT_HUB_TITLE
    assert "Status" in notion.databases.created_payload["properties"]


def test_create_sample_page_payload():
    notion = _FakeNotion()

    result = setup_content_hub._create_sample_page(notion, "hub-db")

    assert result["url"] == "https://notion.test/sample"
    assert notion.pages.created_payload["parent"] == {"database_id": "hub-db"}
    assert notion.pages.created_payload["properties"]["Status"]["select"]["name"] == "Draft"
