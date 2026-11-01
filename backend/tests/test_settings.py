from app.settings import get_setting, read_env_file


def test_env_file_is_read_and_a_real_environment_variable_wins(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('# comment\n\nOLLAMA_MODEL="llama3.1:8b"\nOLLAMA_HOST = http://example:11434\nnot a setting line\n')
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    file_values = read_env_file(env_file)

    assert file_values == {"OLLAMA_MODEL": "llama3.1:8b", "OLLAMA_HOST": "http://example:11434"}
    assert get_setting("OLLAMA_MODEL", "default", file_values) == "llama3.1:8b"
    assert get_setting("MISSING_SETTING", "default", file_values) == "default"

    monkeypatch.setenv("OLLAMA_MODEL", "from-the-shell")
    assert get_setting("OLLAMA_MODEL", "default", file_values) == "from-the-shell"
    assert read_env_file(tmp_path / "missing.env") == {}
