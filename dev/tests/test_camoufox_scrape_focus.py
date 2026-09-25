# INFRASTRUCTURE
import pytest

from src.scraper import camoufox_scrape


# FUNCTIONS

def test_find_app_bundle_locates_dotapp_ancestor(tmp_path):
    app = tmp_path / "Camoufox.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    executable = app / "Contents" / "MacOS" / "camoufox"
    executable.write_text("")
    assert camoufox_scrape._find_app_bundle(str(executable)) == app


def test_find_app_bundle_returns_none_when_not_in_a_bundle(tmp_path):
    bare = tmp_path / "some_binary"
    bare.write_text("")
    assert camoufox_scrape._find_app_bundle(str(bare)) is None


def test_ensure_no_focus_steal_sets_lsuielement(tmp_path, monkeypatch):
    import plistlib
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "darwin")
    executable, plist_path = _make_fake_app_bundle(tmp_path)

    camoufox_scrape._ensure_no_focus_steal(executable)

    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    assert data["LSUIElement"] is True


def test_ensure_no_focus_steal_idempotent(tmp_path, monkeypatch):
    import plistlib
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "darwin")
    executable, plist_path = _make_fake_app_bundle(
        tmp_path, existing_plist={"CFBundleName": "Camoufox", "LSUIElement": True})

    camoufox_scrape._ensure_no_focus_steal(executable)

    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    assert data["LSUIElement"] is True


def test_ensure_no_focus_steal_noop_on_non_macos(tmp_path, monkeypatch):
    import plistlib
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "linux")
    executable, plist_path = _make_fake_app_bundle(tmp_path)

    camoufox_scrape._ensure_no_focus_steal(executable)

    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    assert "LSUIElement" not in data


def test_ensure_no_focus_steal_noop_when_executable_path_missing(monkeypatch):
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "darwin")
    camoufox_scrape._ensure_no_focus_steal(None)
    camoufox_scrape._ensure_no_focus_steal("")


def test_build_camoufox_kwargs_ignores_foreground_default_arg():
    kwargs = camoufox_scrape._build_camoufox_kwargs(block_images=False)
    assert kwargs["ignore_default_args"] == ["-foreground"]


def test_ensure_no_focus_steal_unreadable_plist_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "darwin")
    app = tmp_path / "Camoufox.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    executable = app / "Contents" / "MacOS" / "camoufox"
    executable.write_text("")
    with pytest.raises(FileNotFoundError):
        camoufox_scrape._ensure_no_focus_steal(str(executable))


def _make_fake_app_bundle(tmp_path, existing_plist: dict | None = None):
    import plistlib
    app = tmp_path / "Camoufox.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    executable = app / "Contents" / "MacOS" / "camoufox"
    executable.write_text("")
    plist_path = app / "Contents" / "Info.plist"
    with open(plist_path, "wb") as f:
        plistlib.dump(existing_plist or {"CFBundleName": "Camoufox"}, f)
    return str(executable), plist_path
