"""Check renamed/concurrent setup launches and wait for complete Qt shutdown."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time
import uuid
from integration import ROOT

parser = argparse.ArgumentParser()
parser.add_argument('--setup', type=Path, required=True)
args = parser.parse_args()
work = ROOT / '.test-work' / ('single-instance-' + uuid.uuid4().hex[:8])
game = work / 'minecraft'
game.mkdir(parents=True)
control = (ROOT / 'installer/controller.qs').read_text(encoding='utf-8')
control = control.replace('__BACKGROUND_REPOSITORY__', json.dumps(json.loads((ROOT / 'pack.json').read_text())['repository_url']))
control += r'''
var originalWelcome = Controller.prototype.DynamicWelcomePageCallback;
Controller.prototype.DynamicWelcomePageCallback = function() {
    originalWelcome.call(this);
    var root = installer.value("TargetDir");
    if (root.indexOf("/.test-work/single-instance-") < 0) throw new Error("Unsafe destination");
    installer.performOperation("AppendFile", [root + "/ready.txt", "READY\n"]);
    installer.setMessageBoxAutomaticAnswer("cancelInstallation", QMessageBox.Yes);
    gui.clickButton(buttons.CancelButton, 18000);
};
'''
script = work / 'hold.qs'
script.write_text(control, encoding='utf-8')
primary = None
children = []
try:
    with (work / 'primary.log').open('wb') as log:
        primary = subprocess.Popen([str(args.setup.resolve()), '--script', str(script),
                                    '--cache-path', str(work / 'cache'), 'PreviewTargetDir=' + game.as_posix()],
                                   stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 60
        while not (game / 'ready.txt').exists() and time.monotonic() < deadline:
            if primary.poll() is not None:
                raise AssertionError('Setup exited before the welcome page')
            time.sleep(0.2)
        assert (game / 'ready.txt').exists(), (work / 'primary.log').read_text(errors='replace')
        for name in ('NewHorizon-Setup-copy.exe', 'Instalador-renomeado.exe', 'NewHorizon-Setup-99.0.exe'):
            copy = work / name
            shutil.copyfile(args.setup, copy)
            children.append(subprocess.Popen([str(copy), '--script', str(script),
                                               'PreviewTargetDir=' + game.as_posix()],
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for child in children:
            assert child.wait(timeout=10) == 0
        assert primary.poll() is None, 'Duplicate launch closed the original installer'
        assert (game / 'ready.txt').read_text() == 'READY\n', 'Multiple installer windows reached the welcome page'
        primary.wait(timeout=30)
        assert not (game / '.newhorizon').exists(), 'Installation started without consent'
    # The lock is released on normal shutdown, allowing a clean later opening.
    result = subprocess.run([str(args.setup.resolve()), '--version'], capture_output=True, timeout=15)
    assert result.returncode == 0 and b'IFW Version' in result.stdout
    print('PASS: one instance across simultaneous renamed copies, original kept open, real exit and reopening. Logs:', work)
finally:
    for child in children + ([primary] if primary else []):
        if child.poll() is None:
            subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'], capture_output=True)
