"""The setup and start scripts, held to what macOS's own bash will accept.

A Mac runs these with Apple's `/bin/bash`, which is bash 3.2.57, and on a Mac
the C library calls the first byte of a full-width character a LETTER (it
classifies bytes 0x80-0xFF by their Latin-1 meaning even in a UTF-8 locale:
0xEF is 'ï'). So bash 3.2 reads `"$PY）"` as a variable named `PY` plus that
byte, and under `set -u` the first run of setup.sh on a real Mac died with

    ./scripts/setup.sh: line 66: PY?: unbound variable

Linux's bash never does this, which is why it reached a user. Reproduced
since with Apple's bash-144 source built on Linux and a locale that classifies
bytes the way macOS does: unfixed, that exact line fails; braced, the whole
script runs. The rule that would have caught it is below, along with the
rest of what a script has to get right on a Mac.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = sorted([*(REPO / "scripts").glob("*.sh"), REPO / "JARVIS.command"])
# The Python that reads or writes `.env` on the scripts' behalf.
PYTHON_HELPERS = sorted(p for p in (REPO / "scripts").glob("*.py")
                        if ".env" in p.read_text(encoding="utf-8"))

# `$NAME` with a byte above 0x7F right after it. `${NAME}` is the fix, and
# `$(...)`, `$1` and `$?` cannot swallow a byte, so they never match.
UNBRACED_BEFORE_NON_ASCII = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*(?=[^\x00-\x7f])")


def test_there_are_scripts_to_check():
    assert len(SCRIPTS) >= 3, SCRIPTS


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_no_variable_runs_into_chinese_text(script):
    """The bug itself: every variable next to non-ASCII text is braced.
    A comment is never expanded, so one may quote the pattern."""
    found = [
        f"{script.name}:{n}: {line.strip()}"
        for n, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1)
        if not line.lstrip().startswith("#") and UNBRACED_BEFORE_NON_ASCII.search(line)
    ]
    assert not found, ("macOS's bash 3.2 reads the first byte of the next "
                       "character as part of the name — write ${NAME}:\n"
                       + "\n".join(found))


def test_the_rule_catches_the_line_that_broke():
    broken = """ok "Python $(python -V)（$PY）\""""
    fixed = """ok "Python $(python -V)（${PY}）\""""
    assert UNBRACED_BEFORE_NON_ASCII.search(broken)
    assert not UNBRACED_BEFORE_NON_ASCII.search(fixed)


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_every_script_parses(script):
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("no bash on PATH")
    result = subprocess.run([bash, "-n", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_every_script_is_executable_and_says_which_shell(script):
    """`./scripts/setup.sh` is what the guide tells people to type."""
    assert script.stat().st_mode & 0o111, f"{script.name} is not executable"
    assert script.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash\n")


def test_the_dotenv_helpers_are_found():
    assert any(p.name == "doctor.py" for p in PYTHON_HELPERS), PYTHON_HELPERS


@pytest.mark.parametrize("path", [*SCRIPTS, *PYTHON_HELPERS], ids=lambda p: p.name)
def test_dotenv_is_read_and_written_as_utf8(path):
    """`.env` carries Chinese comments. Read in a locale's own encoding — a
    Latin-1 one, say — the 0x85 byte inside 內 or 腦 decodes to NEL, and
    `splitlines()` cuts the line in two: measured, the file came back with
    three comments broken across lines."""
    bad = [
        f"{path.name}:{n}: {line.strip()}"
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"\.(read_text|write_text)\(", line) and "encoding=" not in line
    ]
    assert not bad, "\n".join(bad)


def test_the_bash_3_features_the_scripts_avoid():
    """bash 3.2 has no `declare -A`, no `mapfile`, no `${var,,}`, no `|&`
    and no `&>>` — none of which fails on the Linux bash the suite runs
    under, so they are refused by pattern here instead."""
    banned = [r"declare -A", r"\bmapfile\b", r"\breadarray\b", r"\$\{[A-Za-z_]+,,",
              r"\$\{[A-Za-z_]+\^\^", r"\|&", r"&>>", r"\bcoproc\b"]
    for script in SCRIPTS:
        text = script.read_text(encoding="utf-8")
        for pattern in banned:
            assert not re.search(pattern, text), f"{script.name}: {pattern}"


if __name__ == "__main__":          # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
