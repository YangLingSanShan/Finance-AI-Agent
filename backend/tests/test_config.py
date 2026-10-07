from pathlib import Path

from app.config import Settings


def test_env_path_is_project_root_regardless_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    expected = Path(__file__).resolve().parents[2] / ".env"
    assert Settings.model_config['env_file'] == expected


def test_settings_read_env_file_and_environment_takes_precedence(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    env_file.write_text('LLM_MODEL=test-file-model\n', encoding='utf-8')
    monkeypatch.delenv('LLM_MODEL', raising=False)
    assert Settings(_env_file=env_file).LLM_MODEL == 'test-file-model'
    monkeypatch.setenv('LLM_MODEL', 'test-environment-model')
    assert Settings(_env_file=env_file).LLM_MODEL == 'test-environment-model'
