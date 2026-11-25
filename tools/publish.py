"""Publish from the GitHub Actions push workflow on branch mods."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def run(*args, capture=False):
    return subprocess.run(args, cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def main():
    if os.environ.get("GITHUB_REF") != "refs/heads/mods":
        raise SystemExit("Publicacao permitida somente pela branch mods.")
    repository = os.environ["GITHUB_REPOSITORY"]
    source = os.environ["GITHUB_SHA"]
    pack = json.loads((ROOT / "pack.json").read_text(encoding="utf-8"))
    base = ".".join(pack["version"].split(".")[:2])
    version = f'{base}.{int(os.environ["GITHUB_RUN_NUMBER"])}.{int(os.environ["GITHUB_RUN_ATTEMPT"])}'
    expected_url = f"https://raw.githubusercontent.com/{repository}/refs/heads/mods/repository"
    if pack["repository_url"] != expected_url:
        raise SystemExit("pack.json deve apontar para o repositorio desta branch mods.")
    run(sys.executable, "tools/build.py", "--version", version)
    # A retry may see only the repository commit from its previous attempt.
    run("git", "fetch", "origin", "mods")
    changed = run("git", "diff", "--name-only", source, "origin/mods", capture=True).splitlines()
    if any(not name.startswith("repository/") for name in changed):
        print("Branch alterada durante o build; a proxima execucao publicara os novos arquivos.")
        return
    run("git", "merge", "--ff-only", "origin/mods")
    current = ROOT / "repository/Updates.xml"
    if current.exists():
        previous = ET.parse(current).findtext("PackageUpdate/Version")
        if tuple(map(int, version.split("."))) <= tuple(map(int, previous.split("."))):
            raise SystemExit(f"A versao {version} deve ser maior que {previous}.")
    generated = ROOT / "dist" / f"repository-{version}"
    # Keep old versioned archives for clients with cached metadata.
    shutil.copytree(generated, ROOT / "repository", dirs_exist_ok=True)
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", "repository")
    run("git", "commit", "-m", f"Publicar catalogo New Horizon {version} [skip ci]")
    commit = run("git", "rev-parse", "HEAD", capture=True).strip()
    # No force push: a concurrent user push must abort publication.
    run("git", "push", "origin", "HEAD:refs/heads/mods")
    executable = ROOT / "dist" / f"NewHorizon-Setup-{version}.exe"
    archive = Path(shutil.make_archive(str(ROOT / "dist" / f"NewHorizon-repository-{version}"),
                                      "zip", generated))
    assets = [ROOT / mod["file"] for mod in pack["mods"]]
    assets += [executable, Path(str(executable) + ".sha256"), archive]
    checksums = ROOT / "dist/SHA256SUMS.txt"
    checksums.write_text("".join(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n"
                                 for path in assets), encoding="ascii")
    assets.append(checksums)
    notes = ROOT / "dist/release-notes.md"
    notes.write_text(f"""Instalador New Horizon para Windows, em portugues, com a arte do servidor.

- Minecraft 1.20.1 / Forge 47.4.0 (instalado somente se necessario).
- Inclui newhorizon-mod.jar e newhorizon-mcef.jar.
- Atualizacoes conectadas ao catalogo Qt da branch `mods`.

Baixe **{executable.name}**, feche o Minecraft e execute o instalador.
Depois da instalacao, os mods sao atualizados automaticamente em segundo plano, ao entrar no Windows e a cada 30 minutos, com o Minecraft fechado. Nao e necessario abrir atalhos ou o instalador novamente.
Quem ja usa uma versao anterior deve executar este instalador uma vez para ativar as atualizacoes automaticas.

Os JARs avulsos tambem estao anexados. `SHA256SUMS.txt` permite verificar os downloads.
O ZIP do repositorio e destinado a administracao; jogadores usam o instalador.

Origem: `{source}`. Versao do pacote: `{version}`.
""", encoding="utf-8")
    run("gh", "release", "create", f"mods-v{version}", *map(str, assets),
        "--repo", repository, "--target", commit, "--latest=false",
        "--title", f"New Horizon - Mods {version}", "--notes-file", str(notes))
    print(f"Publicado: https://github.com/{repository}/releases/tag/mods-v{version}")


if __name__ == "__main__":
    main()
