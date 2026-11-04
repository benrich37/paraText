"""The macOS app bundle writer (the bundle layout is checked on every platform; registration only on macOS)."""

import plistlib
import shutil
import stat
import subprocess
import sys

import pytest

from paratext import __version__
from paratext.macapp import BUNDLE_ID, build_app, info_plist


def test_build_app_layout(tmp_path):
    app = build_app(tmp_path / "paraText.app", python="/opt/py/bin/python", path_env="/opt/py/bin:/usr/bin", icon=False)
    contents = app / "Contents"
    plist = plistlib.loads((contents / "Info.plist").read_bytes())
    assert plist["CFBundleIdentifier"] == BUNDLE_ID
    assert plist["CFBundleShortVersionString"] == __version__
    assert plist["CFBundleDocumentTypes"][0]["LSItemContentTypes"] == ["com.adobe.pdf"]
    assert "CFBundleIconFile" not in plist
    launcher = contents / "MacOS" / plist["CFBundleExecutable"]
    assert launcher.stat().st_mode & stat.S_IXUSR
    script = launcher.read_text()
    assert 'exec "$PARATEXT_PYTHON" -m paratext read "$@"' in script
    assert "export PATH='/opt/py/bin:/usr/bin'" in script
    assert "export PARATEXT_PYTHON='/opt/py/bin/python'" in script
    assert (contents / "PkgInfo").read_text() == "APPL????"


def test_build_app_replaces_only_bundles(tmp_path):
    build_app(tmp_path / "a.app", icon=False)
    build_app(tmp_path / "a.app", icon=False)  # replacing an existing bundle is fine
    (tmp_path / "b.app").mkdir()
    (tmp_path / "b.app" / "keep.txt").write_text("x")
    with pytest.raises(ValueError):
        build_app(tmp_path / "b.app", icon=False)
    with pytest.raises(ValueError):
        build_app(tmp_path / "notanapp", icon=False)


def test_launcher_runs_the_given_python(tmp_path):
    """The generated script must exec the interpreter with the file arguments intact."""
    app = build_app(tmp_path / "paraText.app", python=sys.executable, path_env="/usr/bin:/bin", icon=False)
    launcher = app / "Contents" / "MacOS" / "paratext"
    (tmp_path / "paratext").mkdir()  # shadow the real package so `-m paratext` just echoes its arguments
    (tmp_path / "paratext" / "__init__.py").write_text("")
    (tmp_path / "paratext" / "__main__.py").write_text("import sys; print('ARGS', sys.argv[1:])")
    env = {"PYTHONPATH": str(tmp_path), "PYTHONSAFEPATH": "1", "HOME": str(tmp_path)}
    subprocess.run([str(launcher), "my paper.pdf"], env=env, capture_output=True, text=True, check=True)
    # Finder gives the app no terminal, so the script sends output to a log file under $HOME.
    log = tmp_path / "Library" / "Logs" / "paraText.log"
    assert log.read_text().strip() == "ARGS ['read', 'my paper.pdf']"


@pytest.mark.skipif(sys.platform != "darwin" or shutil.which("iconutil") is None, reason="needs macOS iconutil")
def test_icon_is_built_on_macos(tmp_path, qapp):
    app = build_app(tmp_path / "paraText.app", icon=True)
    plist = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert plist["CFBundleIconFile"] == "paratext.icns"
    assert (app / "Contents" / "Resources" / "paratext.icns").stat().st_size > 1000


def test_info_plist_icon_flag():
    assert info_plist(True)["CFBundleIconFile"] == "paratext.icns"
