"""Exercise the real IFW executable only in an isolated workspace directory.

Reads an existing Forge installation to prepare the fixture. Never installs into it.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
import uuid
import xml.etree.ElementTree as ET
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "1.20.1-forge-47.4.0"


def run(executable, arguments, log, success=True, timeout=180):
    with log.open("wb") as output:
        result = subprocess.run([str(executable), "--cache-path", str(log.parent / "cache"),
                                 "--auto-answer", "installationErrorWithCancel=Cancel,installationErrorWithIgnore=Ignore,OverwriteTargetDirectory=Yes", "--accept-messages", "--accept-licenses",
                                 "--confirm-command", *arguments], stdout=output,
                                stderr=subprocess.STDOUT, timeout=timeout)
    result.stdout = log.read_bytes()
    if (result.returncode == 0) != success:
        raise AssertionError(f"Unexpected exit {result.returncode}: {log}\n{result.stdout.decode(errors='replace')[-6000:]}")
    return result.stdout.decode(errors="replace")


def main():
    parser = argparse.ArgumentParser()
    version = json.loads((ROOT / 'pack.json').read_text())["version"]
    parser.add_argument("--setup", type=Path, default=ROOT / f"dist/NewHorizon-Setup-{version}.exe")
    update = parser.add_mutually_exclusive_group()
    update.add_argument("--update-repository", type=Path)
    update.add_argument("--update-url", help="Real HTTPS repository to persist and test")
    args = parser.parse_args()
    test_root = ROOT / ".test-work"
    test_root.mkdir(exist_ok=True)
    work = test_root / ("integration-" + uuid.uuid4().hex[:8])
    work.mkdir()
    game = work / "Minecraft com espacos e acentos ç"
    game.mkdir()
    existing = Path(os.environ["APPDATA"]) / ".minecraft"
    with zipfile.ZipFile(ROOT / "assets/forge-1.20.1-47.4.0-installer.jar") as archive:
        profile = json.loads(archive.read("version.json"))
    paths = [f"versions/{PROFILE}/{PROFILE}.json"]
    paths += ["libraries/" + lib["downloads"]["artifact"]["path"] for lib in profile["libraries"] if lib.get("downloads", {}).get("artifact")]
    for relative in paths:
        destination = game / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(existing / relative, destination)
    (game / "mods").mkdir()
    (game / "saves").mkdir()
    (game / "saves/world.txt").write_text("world kept")
    (game / "mods/unrelated.jar").write_bytes(b"unrelated user mod")
    (game / "mods/newhorizon-mod.jar").write_bytes(b"previous user version")
    output = run(args.setup, ["--root", str(game), "install"], work / "install.log")
    assert "ja instalado e verificado" in output, output[-3000:]
    for name in ("newhorizon-mod.jar", "newhorizon-mcef.jar"):
        assert (game / "mods" / name).read_bytes() == (ROOT / "assets" / name).read_bytes()
    maintenance = game / "NewHorizonMaintenance.exe"
    assert maintenance.is_file()
    assert (game / "Atualizar New Horizon.lnk").is_file()
    if args.update_repository or args.update_url:
        repository_url = args.update_url or args.update_repository.resolve().as_uri()
        if args.update_url:
            with urlopen(repository_url.rstrip("/") + "/Updates.xml", timeout=60) as response:
                expected_version = ET.fromstring(response.read()).findtext("PackageUpdate/Version")
            run(maintenance, ["--add-repository", repository_url, "check-updates"], work / "check-updates.log")
            output = run(maintenance, ["update"], work / "update.log")
        else:
            output = run(maintenance, ["--set-temp-repository", repository_url, "update"], work / "update.log")
            expected_version = ET.parse(args.update_repository / "Updates.xml").findtext("PackageUpdate/Version")
        assert expected_version in (game / "newhorizon-components.xml").read_text(encoding="utf-8")
        for name in ("newhorizon-mod.jar", "newhorizon-mcef.jar"):
            assert (game / "mods" / name).read_bytes() == (ROOT / "assets" / name).read_bytes()
    run(maintenance, ["purge"], work / "uninstall.log")
    assert (game / "mods/newhorizon-mod.jar").read_bytes() == b"previous user version"
    assert not (game / "mods/newhorizon-mcef.jar").exists()
    assert (game / "mods/unrelated.jar").read_bytes() == b"unrelated user mod"
    assert (game / "saves/world.txt").read_text() == "world kept"
    assert (game / f"versions/{PROFILE}/{PROFILE}.json").exists()
    # Missing Minecraft must fail and roll back the extracted payload, without installing mods.
    missing = work / "missing-minecraft"
    missing.mkdir()
    (missing / "keep.txt").write_text("keep")
    run(args.setup, ["--root", str(missing), "install"], work / "missing.log", success=False)
    assert not (missing / "mods/newhorizon-mod.jar").exists()
    assert (missing / "keep.txt").read_text() == "keep"
    print(f"PASS: install, integrity, update={bool(args.update_repository or args.update_url)}, uninstall, preservation, failure rollback. Logs: {work}")


if __name__ == "__main__":
    main()
