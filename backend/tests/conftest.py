import pytest
from app.storage.conversations import ConversationStore


@pytest.fixture(autouse=True)
def isolate_conversation_history(tmp_path, monkeypatch):
    import app.agents.orchestrator as module
    store = ConversationStore(tmp_path / 'history.sqlite3')
    monkeypatch.setattr(module, 'get_conversation_store', lambda: store)
    monkeypatch.setattr(module, '_orchestrator', None)
