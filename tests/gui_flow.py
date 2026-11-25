"""Run the graphical wizard against a workspace fixture, never the real game."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid
import zipfile
import time
from integration import ROOT, PROFILE, run

parser = argparse.ArgumentParser()
parser.add_argument("--setup", type=Path, required=True)
parser.add_argument("--hold-finish", action="store_true")
args = parser.parse_args()
work = ROOT / ".test-work" / ("gui-flow-" + uuid.uuid4().hex[:8])
game = work / "minecraft"
game.mkdir(parents=True)
existing = Path(os.environ["APPDATA"]) / ".minecraft"
with zipfile.ZipFile(ROOT / "assets/forge-1.20.1-47.4.0-installer.jar") as archive:
    profile = json.loads(archive.read("version.json"))
paths = [f"versions/{PROFILE}/{PROFILE}.json"]
paths += ["libraries/" + lib["downloads"]["artifact"]["path"] for lib in profile["libraries"] if lib.get("downloads", {}).get("artifact")]
for relative in paths:
    target = game / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(existing / relative, target)
(game / "keep.txt").write_text("keep")
test_script = (ROOT / "installer/controller.qs").read_text(encoding="utf-8") + r'''
var originalWelcome = Controller.prototype.DynamicWelcomePageCallback;
var originalFinished = Controller.prototype.FinishedPageCallback;
Controller.prototype.DynamicWelcomePageCallback = function() {
    originalWelcome.call(this);
    var root = installer.value("TargetDir");
    if (root.indexOf("/.test-work/gui-flow-") < 0) throw new Error("Unsafe test destination");
    if (installer.value("NewHorizonConfirmed") === "true" || installer.fileExists(root + "/.newhorizon/manifest.json"))
        throw new Error("Installation began before confirmation");
    installer.performOperation("AppendFile", [root + "/flow-results.txt", "TEST_WELCOME_NO_WRITES\n"]);
    // Exercise the real Commit action and the page validator, with a test fixture only.
    gui.clickButton(buttons.CommitButton, 1000);
};
Controller.prototype.FinishedPageCallback = function() {
    originalFinished.call(this);
    if (installer.status !== QInstaller.Success) throw new Error("GUI install failed");
    if (installer.value("NewHorizonConfirmed") !== "true") throw new Error("Missing explicit confirmation");
    installer.performOperation("AppendFile", [installer.value("TargetDir") + "/flow-results.txt", "TEST_GUI_FINISHED_SUCCESS\n"]);
    __CLOSE__
};
'''
test_script = test_script.replace("__CLOSE__", "" if args.hold_finish else "gui.clickButton(buttons.FinishButton, 500);")
script = work / "flow.qs"
script.write_text(test_script, encoding="utf-8")
log = work / "gui.log"
print(f"Graphical test: {work}", flush=True)
with log.open("wb") as output:
    process = subprocess.Popen([str(args.setup.resolve()), "--cache-path", str(work / "cache"),
                             "--script", str(script), "PreviewTargetDir=" + game.as_posix()],
                            stdout=output, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 60
    marker = game / "flow-results.txt"
    while time.monotonic() < deadline:
        if marker.exists() and "TEST_GUI_FINISHED_SUCCESS" in marker.read_text():
            break
        time.sleep(0.25)
    else:
        process.kill()
        raise AssertionError("GUI flow did not complete: " + log.read_text(errors="replace")[-3000:])
transcript = marker.read_text()
assert "TEST_WELCOME_NO_WRITES" in transcript, transcript[-3000:]
assert "TEST_GUI_FINISHED_SUCCESS" in transcript, transcript[-3000:]
assert "TypeError" not in log.read_text(errors="replace")
for name in ("newhorizon-mod.jar", "newhorizon-mcef.jar"):
    assert (game / "mods" / name).read_bytes() == (ROOT / "assets" / name).read_bytes()
if not args.hold_finish:
    time.sleep(1)
    run(game / "NewHorizonMaintenance.exe", ["purge"], work / "uninstall.log")
assert (game / "keep.txt").read_text() == "keep"
print(f"PASS: branded GUI, no writes before confirmation, commit, installation and completion. Logs: {work}")
