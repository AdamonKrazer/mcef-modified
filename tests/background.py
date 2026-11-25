"""Real background update + scheduled task lifecycle in an isolated game folder."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid
import zipfile
from integration import ROOT, PROFILE, run

PS = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'


def ps(script, *arguments, success=True):
    result = subprocess.run([str(PS), '-NoLogo', '-NoProfile', '-NonInteractive',
                             '-ExecutionPolicy', 'Bypass', '-File', str(script), *map(str, arguments)],
                            capture_output=True, timeout=180)
    if (result.returncode == 0) != success:
        raise AssertionError(result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))
    return result.stdout.decode('utf-8-sig', errors='replace')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--setup', type=Path, help='Exercise graphical migration with the new setup executable')
    parser.add_argument('--next-repository', type=Path, help='Update the worker itself through its scheduled task')
    args = parser.parse_args()
    work = ROOT / '.test-work' / ('background-' + uuid.uuid4().hex[:8])
    game = work / 'Minecraft espacos ç'
    game.mkdir(parents=True)
    existing = Path(os.environ['APPDATA']) / '.minecraft'
    with zipfile.ZipFile(ROOT / 'assets/forge-1.20.1-47.4.0-installer.jar') as archive:
        profile = json.loads(archive.read('version.json'))
    paths = [f'versions/{PROFILE}/{PROFILE}.json']
    paths += ['libraries/' + lib['downloads']['artifact']['path'] for lib in profile['libraries'] if lib.get('downloads', {}).get('artifact')]
    for relative in paths:
        target = game / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(existing / relative, target)
    (game / 'mods').mkdir()
    (game / 'mods/newhorizon-mod.jar').write_bytes(b'original user mod')
    (game / 'mods/unrelated.jar').write_bytes(b'keep other mods')
    task_script = ROOT / 'installer/background-task.ps1'
    worker = ROOT / 'installer/background-update.ps1'
    source = args.repository.resolve().as_uri()
    maintenance = game / 'NewHorizonMaintenance.exe'
    task = None
    fake_game = None
    try:
        old_repository = work / 'old-repository'
        with zipfile.ZipFile(ROOT / 'dist/github-release-1.2.2.1/NewHorizon-repository-1.2.2.1.zip') as archive:
            archive.extractall(old_repository)
        run(ROOT / 'dist/NewHorizon-Setup-1.2.2.1.exe',
            ['--set-temp-repository', old_repository.as_uri(), '--root', str(game), 'install'], work / 'install.log')
        assert (game / 'Atualizar New Horizon.lnk').exists()
        (game / 'mods/newhorizon-mod.jar').write_bytes(b'outdated mod')
        if args.setup:
            control = (ROOT / 'installer/controller.qs').read_text(encoding='utf-8')
            control = control.replace('__BACKGROUND_REPOSITORY__', json.dumps(source))
            control += '''
Controller.prototype.finishBackgroundSetup = function(status) {
    var root = installer.value("TargetDir");
    if (root.indexOf("/.test-work/background-") < 0) throw new Error("Unsafe test destination");
    installer.performOperation("AppendFile", [root + "/migration-result.json", JSON.stringify(status)]);
};
'''
            script = work / 'migration.qs'
            script.write_text(control, encoding='utf-8')
            marker = game / 'migration-result.json'
            with (work / 'migration.log').open('wb') as log:
                migration = subprocess.Popen([str(args.setup.resolve()), '--script', str(script),
                                               '--cache-path', str(work / 'gui-cache'),
                                               'PreviewTargetDir=' + game.as_posix()], stdout=log, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline and not marker.exists():
                    time.sleep(0.25)
                if not marker.exists():
                    migration.kill()
                    raise AssertionError('GUI migration failed: ' + (work / 'migration.log').read_text(errors='replace')[-4000:])
                migration.wait(timeout=15)
                # IFW may restart its native process; let the closing wizard
                # release its locks before another background invocation.
                time.sleep(1)
            assert json.loads(marker.read_text())['status'] == 'updated', marker.read_text()
        else:
            ps(worker, '-MinecraftDir', game, '-RepositoryUrl', source)
        state = game / '.newhorizon-state/status.json'
        assert json.loads(state.read_text(encoding='utf-8-sig'))['status'] == 'updated', state.read_text(encoding='utf-8-sig')
        assert not (game / 'Atualizar New Horizon.lnk').exists()
        for name in ('newhorizon-mod.jar', 'newhorizon-mcef.jar'):
            assert (game / 'mods' / name).read_bytes() == (ROOT / 'assets' / name).read_bytes()
        task = json.loads(ps(task_script, '-MinecraftDir', game, '-Mode', 'Status'))
        assert task['registered'] and 'PT30M' in task['xml'] and 'InteractiveToken' in task['xml']
        assert 'HighestAvailable' not in task['xml'] and '-WindowStyle Hidden' in task['xml']
        ps(worker, '-MinecraftDir', game, '-RepositoryUrl', source)
        assert json.loads(state.read_text(encoding='utf-8-sig'))['status'] == 'current'
        # A real process named java.exe with a Minecraft command line exercises
        # the same process discovery as a running game, without launching Minecraft.
        stub = work / 'java.cs'
        stub.write_text('class Game { static void Main(string[] args) { System.Threading.Thread.Sleep(120000); } }')
        fake_java = work / 'java.exe'
        compiler = Path(os.environ['SystemRoot']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        subprocess.run([str(compiler), '/nologo', '/target:exe', '/out:' + str(fake_java), str(stub)], check=True)
        fake_game = subprocess.Popen([str(fake_java), 'net.minecraft.client.main.Main'], creationflags=subprocess.CREATE_NO_WINDOW)
        ps(worker, '-MinecraftDir', game, '-RepositoryUrl', source)
        assert json.loads(state.read_text(encoding='utf-8-sig'))['status'] == 'deferred'
        fake_game.terminate()
        fake_game.wait()
        fake_game = None
        ps(worker, '-MinecraftDir', game, '-RepositoryUrl', (work / 'unavailable').as_uri(), success=False)
        assert json.loads(state.read_text(encoding='utf-8-sig'))['status'] == 'error'
        assert (game / 'mods/newhorizon-mod.jar').read_bytes() == (ROOT / 'assets/newhorizon-mod.jar').read_bytes()
        # Launch the registered task itself, not just its script.
        if args.next_repository:
            manifest_path = game / '.newhorizon/manifest.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['repository_url'] = args.next_repository.resolve().as_uri()
            manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        schedule = work / 'run-task.ps1'
        schedule.write_text("$s = New-Object -ComObject Schedule.Service\n$s.Connect()\n$t = $s.GetFolder('\\').GetTask('" + task['name'] + "')\n$t.Run($null) | Out-Null\n")
        before = state.read_bytes()
        ps(schedule)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if state.exists() and state.read_bytes() != before:
                status = json.loads(state.read_text(encoding='utf-8-sig'))['status']
                if status in ('current', 'updated'):
                    break
            time.sleep(0.5)
        else:
            raise AssertionError('Scheduled task did not finish: ' + state.read_text(encoding='utf-8-sig'))
        if args.next_repository:
            assert status == 'updated'
            assert json.loads(ps(task_script, '-MinecraftDir', game, '-Mode', 'Status'))['registered']
        run(maintenance, ['purge'], work / 'uninstall.log')
        assert not json.loads(ps(task_script, '-MinecraftDir', game, '-Mode', 'Status'))['registered']
        assert (game / 'mods/newhorizon-mod.jar').read_bytes() == b'original user mod'
        assert (game / 'mods/unrelated.jar').read_bytes() == b'keep other mods'
        print('PASS: automatic update, hashes, no shortcut, scheduled task, no-update, running-game deferral, offline retry, uninstall cleanup. Logs:', work)
    finally:
        if fake_game:
            fake_game.terminate()
            fake_game.wait()
        if maintenance.exists():
            run(maintenance, ['purge'], work / 'cleanup.log')
        ps(task_script, '-MinecraftDir', game, '-Mode', 'Unregister')


if __name__ == '__main__':
    main()
