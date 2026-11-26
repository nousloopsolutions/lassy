from lassy.secret_store import fingerprint


def test_secret_fingerprint_is_short_and_stable() -> None:
    assert fingerprint("a" * 32) == "3ba3f5f43b92"


def test_runner_secret_set_reads_stdin(monkeypatch, tmp_path) -> None:
    from typer.testing import CliRunner

    import lassy.secret_store as ss
    from lassy.cli import app

    got = {}
    monkeypatch.setattr(
        ss.RunnerSecretStore, "set", lambda self, s: got.setdefault("s", s) and "fp"
    )
    ok = CliRunner().invoke(
        app, ["runner-secret-set", "--data-dir", str(tmp_path), "--stdin"], input="x" * 40 + "\r\n"
    )
    assert ok.exit_code == 0 and got["s"] == "x" * 40 and "x" * 40 not in ok.output
    short = CliRunner().invoke(
        app, ["runner-secret-set", "--data-dir", str(tmp_path), "--stdin"], input="short\n"
    )
    assert short.exit_code != 0
