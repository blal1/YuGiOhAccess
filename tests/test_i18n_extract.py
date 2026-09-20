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
        "N_",
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


def test_game_strings_template_uses_only_english_game_strings(tmp_path):
    from scripts import game_strings_template

    source = tmp_path / "strings.conf"
    output = tmp_path / "strings.template.conf"
    source.write_text(
        "\n".join(
            [
                "# comment",
                "!system 1 Normal Summon",
                "!victory 0 The duel ended",
                "!setcode 0x1 Ignored set code",
                "!setname 0x10 Blue-Eyes",
                "ignored free text",
                "!system invalid Ignored invalid id",
            ]
        ),
        encoding="utf-8",
    )

    count = game_strings_template.write_template(source, output)

    template = output.read_text(encoding="utf-8")
    assert count == 3
    assert "!system 1 Normal Summon" in template
    assert "!victory 0 The duel ended" in template
    assert "!setname 0x10 Blue-Eyes" in template
    assert "!setcode" not in template
    assert "ignored free text" not in template
    assert "invalid" not in template
