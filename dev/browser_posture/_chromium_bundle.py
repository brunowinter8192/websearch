# INFRASTRUCTURE
import plistlib
import subprocess
from pathlib import Path

CHROMIUM_REVISION_TAG = "chromium-1228"


# FUNCTIONS

def resolve_and_verify_bundle(executable_path: str | None) -> Path:
    if not executable_path:
        raise RuntimeError("Run B captured no browser process — cannot resolve bundle for the plist step")
    bundle = find_app_bundle(executable_path)
    if bundle is None:
        raise RuntimeError(f"No .app bundle found above {executable_path}")
    if CHROMIUM_REVISION_TAG not in str(bundle):
        raise RuntimeError(
            f"Resolved bundle {bundle} is NOT {CHROMIUM_REVISION_TAG} — refusing to touch its plist"
        )
    return bundle


def read_lsuielement(plist_path: Path) -> bool | None:
    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    return data.get("LSUIElement")


def set_lsuielement(plist_path: Path, value: bool, original_bytes: bytes) -> None:
    data = plistlib.loads(original_bytes)
    data["LSUIElement"] = value
    fmt = plistlib.FMT_BINARY if original_bytes.startswith(b"bplist00") else plistlib.FMT_XML
    with open(plist_path, "wb") as f:
        plistlib.dump(data, f, fmt=fmt)


def read_codesign_status(bundle_path: Path) -> dict:
    dv = subprocess.run(["codesign", "-dv", str(bundle_path)], capture_output=True, text=True)
    verify = subprocess.run(["codesign", "--verify", "--deep", "--strict", str(bundle_path)], capture_output=True, text=True)
    flags_line = next((l for l in dv.stderr.splitlines() if l.startswith("CodeDirectory") or l.startswith("Signature")), "")
    return {"verify_returncode": verify.returncode, "verify_stderr": verify.stderr.strip(), "signature_line": flags_line}


def find_app_bundle(executable_path: str) -> Path | None:
    for parent in Path(executable_path).parents:
        if parent.suffix == ".app":
            return parent
    return None
