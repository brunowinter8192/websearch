from src.scraper import camoufox_scrape


# ---------------------------------------------------------------------------
# No-focus-steal launch (milestone 3, Half A) — _find_app_bundle / _ensure_no_focus_steal.
# Uses a real tmp_path .app-shaped bundle + real plistlib round-trip (no fakes needed: plistlib is
# pure Python, no camoufox/OS dependency), pinning the exact mechanism verified empirically this
# session (real osascript/System Events focus-poll: LSUIElement=true stopped Camoufox from ever
# becoming the frontmost application across a real try_scrape_camoufox call).
# ---------------------------------------------------------------------------

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


def test_ensure_no_focus_steal_sets_lsuielement(tmp_path, monkeypatch):
    """Fresh bundle, no LSUIElement key -> set to True."""
    import plistlib
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "darwin")
    executable, plist_path = _make_fake_app_bundle(tmp_path)

    camoufox_scrape._ensure_no_focus_steal(executable)

    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    assert data["LSUIElement"] is True


def test_ensure_no_focus_steal_idempotent(tmp_path, monkeypatch):
    """Already-True bundle -> no write attempted (no exception, value unchanged either way)."""
    import plistlib
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "darwin")
    executable, plist_path = _make_fake_app_bundle(
        tmp_path, existing_plist={"CFBundleName": "Camoufox", "LSUIElement": True})

    camoufox_scrape._ensure_no_focus_steal(executable)

    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    assert data["LSUIElement"] is True


def test_ensure_no_focus_steal_noop_on_non_macos(tmp_path, monkeypatch):
    """Non-darwin platform -> no-op, no exception, plist untouched."""
    import plistlib
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "linux")
    executable, plist_path = _make_fake_app_bundle(tmp_path)

    camoufox_scrape._ensure_no_focus_steal(executable)

    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    assert "LSUIElement" not in data


def test_ensure_no_focus_steal_noop_when_executable_path_missing(monkeypatch):
    monkeypatch.setattr(camoufox_scrape.sys, "platform", "darwin")
    camoufox_scrape._ensure_no_focus_steal(None)  # must not raise
    camoufox_scrape._ensure_no_focus_steal("")     # must not raise


# ---------------------------------------------------------------------------
# Focus-steal launch fix — the LSUIElement plist patch above only suppresses the OS's PASSIVE
# default activation-on-launch policy; playwright#41306 states Firefox's Playwright launcher
# unconditionally injects an EXPLICIT "-foreground" Cocoa activation arg whenever headless=False,
# which overrides that patch. ignore_default_args=["-foreground"] (_build_camoufox_kwargs) is
# playwright's own public opt-out for it. A previously-suspected window-creation-time residual
# (an in-process AXMain-keyed watchdog, _key_window_steal_watchdog, once reclaimed it) was removed
# 2026-08-27 after live human verification found no measurable effect from the watchdog either way
# (process-docs/camoufox_lane/2026-08-26_axmain_is_not_an_activation_signal.md) — AXMain=true on
# this LSUIElement accessory process does not imply real activation.
# ---------------------------------------------------------------------------

def test_build_camoufox_kwargs_ignores_foreground_default_arg():
    """ignore_default_args drops Firefox's own launch-time -foreground activation call — the
    launch-time half of the fix, playwright#41306's documented opt-out mechanism."""
    kwargs = camoufox_scrape._build_camoufox_kwargs(block_images=False)
    assert kwargs["ignore_default_args"] == ["-foreground"]
