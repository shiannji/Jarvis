"""scripts/doctor.py, run the way people actually run it.

The guide said `.venv/bin/python scripts/doctor.py`. On a Mac with mise, a
user typed `python scripts/doctor.py`, and got

    File ".../tts.py", line 25, in <module>
        import httpx
    ModuleNotFoundError: No module named 'httpx'

— the project's packages live in `.venv`, and nothing else has them. Two
things were wrong, and both are pinned here: doctor now hands itself over to
`.venv/bin/python` whenever there is one, and the modules it imports no
longer need anything outside the standard library (`tts.py` imports httpx
only inside the one function that makes a request).
"""

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOCTOR = REPO / "scripts" / "doctor.py"


def _load_doctor():
    spec = importlib.util.spec_from_file_location("jarvis_doctor", DOCTOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)          # never hands over: not __main__
    return module


doctor = _load_doctor()

# Run a snippet with httpx made unimportable, as on a Python outside .venv.
NO_HTTPX = "import sys; sys.modules['httpx'] = None\n"


def _run(code: str, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", NO_HTTPX + code], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=120)


def _isolated_env(tmp_path: Path) -> dict:
    """No `claude`, `osascript` or anything else to find, and no real home:
    the machine checks report what is missing instead of running it."""
    (tmp_path / "empty-bin").mkdir(exist_ok=True)
    (tmp_path / "home").mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("JARVIS_", "FISH_", "ANTHROPIC_", "CLAUDE"))}
    env.update(PATH=str(tmp_path / "empty-bin"), HOME=str(tmp_path / "home"),
               JARVIS_LANGUAGE="en", PYTHONDONTWRITEBYTECODE="1")
    return env


def test_the_modules_doctor_needs_import_without_httpx(tmp_path):
    result = _run(f"sys.path.insert(0, {str(REPO)!r})\n"
                  "import i18n, preflight, tts\n"
                  "print(tts.voice_mode(''))\n", tmp_path, _isolated_env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "browser"


def test_the_server_still_reaches_fish_audio_through_httpx():
    """The import moved, it did not go: synthesis still uses httpx."""
    import inspect
    import tts
    assert "import httpx" in inspect.getsource(tts.synthesize_chunk)


# --- handing over to the project's interpreter --------------------------------

def _repo_with_venv(tmp_path: Path) -> Path:
    repo = tmp_path / "jarvis"
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "python").symlink_to(sys.executable)
    return repo


def test_a_global_python_hands_over_to_the_project_venv(tmp_path):
    repo = _repo_with_venv(tmp_path)
    assert doctor.should_hand_over("/opt/mise/python/3.13", {}, repo)


def test_the_project_venv_runs_it_itself(tmp_path):
    repo = _repo_with_venv(tmp_path)
    assert not doctor.should_hand_over(str(repo / ".venv"), {}, repo)


def test_it_hands_over_once_and_never_bounces(tmp_path):
    repo = _repo_with_venv(tmp_path)
    assert not doctor.should_hand_over("/opt/mise/python/3.13", {doctor.REEXEC_FLAG: "1"}, repo)


def test_without_a_venv_it_runs_where_it_is(tmp_path):
    assert not doctor.should_hand_over("/usr", {}, tmp_path / "jarvis")


def test_a_broken_venv_is_not_handed_to(tmp_path):
    repo = tmp_path / "jarvis"
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "python").symlink_to(tmp_path / "gone" / "python3.13")
    assert not doctor.should_hand_over("/usr", {}, repo)


# --- what it says is installed ----------------------------------------------

def _statuses(report):
    return [status for status, _what, _remedy in report]


def test_a_checkout_that_was_never_set_up_names_everything_missing(tmp_path):
    repo = tmp_path / "jarvis"
    repo.mkdir()
    report = doctor.install_report(False, repo, prefix="/usr", find_spec=lambda name: None)
    assert _statuses(report) == [doctor.FAIL, doctor.FAIL, doctor.FAIL, doctor.FAIL, doctor.WARN]
    assert "has not been made yet" in report[0][1]
    assert all("setup.sh" in remedy for _s, _w, remedy in report)
    assert "httpx" in report[1][1]


def test_a_finished_setup_is_all_green(tmp_path):
    repo = _repo_with_venv(tmp_path)
    (repo / "frontend" / "node_modules").mkdir(parents=True)
    for name in ("cert.pem", "key.pem", ".env"):
        (repo / name).write_text("x")
    report = doctor.install_report(False, repo, prefix=str(repo / ".venv"),
                                   find_spec=lambda name: object())
    assert _statuses(report) == [doctor.OK] * 5, report


def test_a_broken_venv_says_how_to_rebuild_it(tmp_path):
    repo = tmp_path / "jarvis"
    (repo / ".venv" / "bin").mkdir(parents=True)
    report = doctor.install_report(True, repo, prefix="/usr", find_spec=lambda name: object())
    status, what, remedy = report[0]
    assert status == doctor.FAIL and "壞了" in what
    assert "rm -rf .venv" in remedy


# --- end to end: the exact command that failed ------------------------------

def test_python_scripts_doctor_py_without_httpx_reports_instead_of_crashing(tmp_path):
    """A copy of the checkout with no .venv, run by a Python that has no
    httpx: it must print its report and exit 1, never a traceback."""
    checkout = tmp_path / "jarvis-new"
    (checkout / "scripts").mkdir(parents=True)
    for module in REPO.glob("*.py"):
        shutil.copy2(module, checkout / module.name)
    shutil.copy2(DOCTOR, checkout / "scripts" / "doctor.py")
    script = checkout / "scripts" / "doctor.py"
    result = _run("import runpy\n"
                  f"sys.argv = [{str(script)!r}]\n"
                  f"runpy.run_path({str(script)!r}, run_name='__main__')\n",
                  checkout, _isolated_env(tmp_path))
    output = result.stdout + result.stderr
    assert "Traceback" not in output, output
    assert result.returncode == 1, output
    assert "has not been made yet" in output
    assert "Missing Python packages" in output and "httpx" in output
    assert "claude_cli" in output, "the machine checks ran too"
