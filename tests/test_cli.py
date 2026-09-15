from richping.cli import main, parser


def test_cli_defaults_to_shadow():
    assert parser().parse_args(["scan"]).mode == "shadow"


def test_cli_failure_is_explicit(tmp_path, capsys):
    assert main(["--db", str(tmp_path / "empty.db"), "report"]) == 1
    assert '"event":"job_failed"' in capsys.readouterr().err
