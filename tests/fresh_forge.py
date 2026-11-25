"""Network integration: install missing Forge into a disposable Minecraft directory."""
import argparse
import json
import os
from pathlib import Path
import shutil
import uuid
from integration import ROOT, PROFILE, run


parser = argparse.ArgumentParser()
version = json.loads((ROOT / 'pack.json').read_text())["version"]
parser.add_argument("--setup", type=Path, default=ROOT / f"dist/NewHorizon-Setup-{version}.exe")
args = parser.parse_args()
work = ROOT / ".test-work" / ("fresh-" + uuid.uuid4().hex[:8])
game = work / "minecraft"
vanilla = game / "versions/1.20.1"
vanilla.mkdir(parents=True)
existing = Path(os.environ["APPDATA"]) / ".minecraft"
for name in ("1.20.1.jar", "1.20.1.json"):
    shutil.copyfile(existing / "versions/1.20.1" / name, vanilla / name)
(game / "launcher_profiles.json").write_text('{"profiles":{}}')
(game / "keep.txt").write_text("keep")
output = run(args.setup.resolve(), ["--root", str(game), "install"], work / "install.log", timeout=900)
assert "Forge instalado e verificado" in output
assert (game / f"versions/{PROFILE}/{PROFILE}.json").is_file()
for name in ("newhorizon-mod.jar", "newhorizon-mcef.jar"):
    assert (game / "mods" / name).read_bytes() == (ROOT / "assets" / name).read_bytes()
run(game / "NewHorizonMaintenance.exe", ["purge"], work / "uninstall.log")
assert (game / "keep.txt").read_text() == "keep"
assert (game / f"versions/{PROFILE}/{PROFILE}.json").is_file()
assert not (game / "mods/newhorizon-mod.jar").exists()
print(f"PASS: missing Forge installed through official installer; mods installed; uninstall preserved Forge. Logs: {work}")
