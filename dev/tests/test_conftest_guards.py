# INFRASTRUCTURE
import subprocess
import tempfile
from pathlib import Path

import pytest
from _pytest.outcomes import Failed


# FUNCTIONS

def test_osascript_call_is_trapped():
    with pytest.raises(Failed):
        subprocess.run(["osascript", "-e", "return 1"], capture_output=True, text=True)


def test_non_osascript_subprocess_passes_through():
    result = subprocess.run(["echo", "ok"], capture_output=True, text=True)
    assert result.stdout.strip() == "ok"


def test_mkdtemp_lands_under_the_isolated_tempdir(tmp_path_factory):
    created = Path(tempfile.mkdtemp(prefix="guard-"))
    assert created.parent == Path(tempfile.gettempdir())
    assert tmp_path_factory.getbasetemp() in created.parents
