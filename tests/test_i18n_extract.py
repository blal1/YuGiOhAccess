import subprocess


def test_babel_extract_finds_src_strings(tmp_path):
    from scripts import i18n_extract

    pot_file = tmp_path / "messages.pot"
    cmd = [
        *i18n_extract.pybabel_cmd(),
        "extract",
        "-F",
        str(i18n_extract.BABEL_CFG),
        "-o",
        str(pot_file),
        "-k",
        "_",
        "-k",
        "ngettext:1,2",
        "-k",
        "pgettext:1c,2",
        "src/",
    ]

    result = subprocess.run(cmd, cwd=str(i18n_extract.ROOT), capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    template = pot_file.read_text(encoding="utf-8")
    assert 'msgid "Main Menu"' in template
    assert 'msgid "Duel Starting"' in template
    assert template.count("\nmsgid ") > 100


def test_i18n_compile_uses_pybabel_command():
    from scripts import i18n_compile

    cmd = i18n_compile.pybabel_cmd()
    assert cmd
    assert "babel" in " ".join(cmd).lower()
