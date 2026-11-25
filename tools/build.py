"""Build the Windows Qt IFW installer and its update repository (stdlib only)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tomllib
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "com.newhorizon.pack"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def xml_file(path: Path, root: ET.Element) -> None:
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def element(parent: ET.Element, name: str, value: str) -> None:
    ET.SubElement(parent, name).text = value


def find_ifw(explicit: str | None) -> Path:
    candidates = [Path(explicit)] if explicit else []
    if os.environ.get("QTIFW_BIN"):
        candidates.append(Path(os.environ["QTIFW_BIN"]))
    if shutil.which("binarycreator"):
        candidates.append(Path(shutil.which("binarycreator")).parent)
    candidates.extend(sorted((ROOT / "tools" / "qtifw").glob("**/bin"), reverse=True))
    for candidate in candidates:
        if all((candidate / f"{name}.exe").is_file() for name in ("binarycreator", "repogen", "installerbase")):
            return candidate.resolve()
    raise ValueError("Qt IFW nao encontrado. Execute tools/bootstrap-qt.ps1 ou informe --ifw-bin.")


def generate(manifest_path: Path, work: Path, version: str | None = None,
             repository_url: str | None = None) -> dict:
    pack = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    pack["version"] = version or pack["version"]
    if not re.fullmatch(r"[0-9]+(?:[.-][0-9]+)*", pack["version"]):
        raise ValueError("A versao deve ser numerica: por exemplo 1.0.1.")
    repository_url = pack["repository_url"] if repository_url is None else repository_url
    if repository_url and (urlparse(repository_url).scheme != "https" or not urlparse(repository_url).netloc):
        raise ValueError("O repositorio de producao deve usar uma URL HTTPS completa.")
    if pack["minecraft"] != "1.20.1" or pack["forge"] != "47.4.0" or pack["java_major"] != 17:
        raise ValueError("Este instalador foi preparado para Minecraft 1.20.1, Forge 47.4.0 e Java 17.")
    if not pack["mods"]:
        raise ValueError("O pacote deve conter pelo menos um mod.")
    config = work / "config"
    meta = work / "packages" / PACKAGE / "meta"
    payload = work / "packages" / PACKAGE / "data" / ".newhorizon"
    for path in (config, meta, payload / "mods"):
        path.mkdir(parents=True, exist_ok=True)
    files = []
    copies = []
    seen = set()
    mod_ids = set()
    for mod in pack["mods"]:
        source = (manifest_path.parent / mod["file"]).resolve()
        filename = source.name
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*\.jar", filename) or filename.lower() in seen:
            raise ValueError(f"Nome de mod invalido ou duplicado: {filename}")
        seen.add(filename.lower())
        with zipfile.ZipFile(source) as archive:
            metadata = tomllib.loads(archive.read("META-INF/mods.toml").decode("utf-8"))
            ids = {item["modId"] for item in metadata["mods"]}
            if mod["mod_id"] not in ids or ids & mod_ids:
                raise ValueError(f"Identificador de mod incorreto ou duplicado: {filename}")
            mod_ids.update(ids)
        target = payload / "mods" / filename
        shutil.copyfile(source, target)
        files.append({"path": f"mods/{filename}", "sha256": sha256(target)})
        copies.append('component.addOperation("Copy", ' + json.dumps(f"@TargetDir@/.newhorizon/mods/{filename}") +
                      ', ' + json.dumps(f"@TargetDir@/mods/{filename}") + ');')
    forge = (manifest_path.parent / pack["forge_installer"]).resolve()
    if sha256(forge) != pack["forge_sha256"].lower():
        raise ValueError("SHA256 do instalador oficial do Forge nao confere.")
    profile_id = f'{pack["minecraft"]}-forge-{pack["forge"]}'
    with zipfile.ZipFile(forge) as archive:
        profile = archive.read("version.json")
        if json.loads(profile)["id"] != profile_id:
            raise ValueError("O JAR do Forge nao corresponde a versao configurada.")
    shutil.copyfile(forge, payload / "forge-installer.jar")
    (payload / "forge-version.json").write_bytes(profile)
    files.extend({"path": name, "sha256": sha256(payload / name)}
                 for name in ("forge-installer.jar", "forge-version.json"))
    runtime = {"version": pack["version"], "minecraft": pack["minecraft"],
               "forge_profile": profile_id, "files": files}
    (payload / "manifest.json").write_text(json.dumps(runtime, indent=2), encoding="utf-8")
    # Windows PowerShell 5 needs BOM for non-ASCII script text.
    (payload / "ensure-forge.ps1").write_text(
        (ROOT / "installer" / "ensure-forge.ps1").read_text(encoding="utf-8"), encoding="utf-8-sig")
    script = (ROOT / "installer" / "component.qs").read_text(encoding="utf-8")
    (meta / "installscript.qs").write_text(script.replace("// __MOD_COPY_OPERATIONS__", "\n    ".join(copies)), encoding="utf-8")
    package = ET.Element("Package")
    for name, value in {
        "DisplayName": "New Horizon + MCEF + Forge",
        "Description": "Minecraft 1.20.1 / Forge 47.4.0. Instala os dois mods do New Horizon e verifica o Forge.",
        "Name": PACKAGE, "Version": pack["version"], "ReleaseDate": date.today().isoformat(),
        "Default": "true", "Script": "installscript.qs",
        "UpdateText": "Atualização do pacote New Horizon. Feche o Minecraft antes de continuar."
    }.items():
        element(package, name, value)
    interfaces = ET.SubElement(package, "UserInterfaces")
    for ui_file in ("WelcomePage.ui", "FinishPanel.ui"):
        element(interfaces, "UserInterface", ui_file)
        shutil.copyfile(ROOT / "installer" / ui_file, meta / ui_file)
    xml_file(meta / "package.xml", package)
    installer = ET.Element("Installer")
    for name, value in {
        "Name": pack["name"], "Version": pack["version"], "Title": "New Horizon",
        "Publisher": "New Horizon", "TargetDir": "@HomeDir@/AppData/Roaming/.minecraft",
        "MaintenanceToolName": "NewHorizonMaintenance", "TargetConfigurationFile": "newhorizon-components.xml",
        "LocalCacheDir": "newhorizon-installer-v2",
        "RemoveTargetDir": "false", "AllowNonAsciiCharacters": "true", "AllowSpaceInPath": "true",
        "WizardStyle": "Classic", "WizardDefaultWidth": "980", "WizardDefaultHeight": "660",
        "WizardMinimumWidth": "960", "WizardMinimumHeight": "640", "WizardShowPageList": "false",
        "InstallerWindowIcon": "window-logo.png", "TitleColor": "#ffffff",
        "ControlScript": "controller.qs", "StyleSheet": "style.qss",
        "DisableAuthorizationFallback": "true"
    }.items():
        element(installer, name, value)
    if repository_url:
        repository = ET.SubElement(ET.SubElement(installer, "RemoteRepositories"), "Repository")
        element(repository, "Url", repository_url.rstrip("/") + "/")
    translations = ET.SubElement(installer, "Translations")
    element(translations, "Translation", "newhorizon_pt_BR")
    element(translations, "Translation", "newhorizonqt_pt_BR")
    shutil.copyfile(ROOT / "assets/server-logo.png", config / "window-logo.png")
    resources = ET.Element("RCC")
    resource = ET.SubElement(resources, "qresource", prefix="/newhorizon")
    ET.SubElement(resource, "file", alias="server-logo.png").text = str(ROOT / "assets/server-logo.png")
    localized = ET.SubElement(resources, "qresource", prefix="/translations")
    for alias, filename in (("newhorizon_pt_BR.qm", "ifw_pt_BR.qm"), ("newhorizonqt_pt_BR.qm", "qt_pt_BR.qm")):
        ET.SubElement(localized, "file", alias=alias).text = str(ROOT / "installer/translations" / filename)
    xml_file(config / "branding.qrc", resources)
    xml_file(config / "config.xml", installer)
    for name in ("controller.qs", "style.qss"):
        shutil.copyfile(ROOT / "installer" / name, config / name)
    return pack


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "pack.json")
    parser.add_argument("--ifw-bin")
    parser.add_argument("--version")
    parser.add_argument("--repository-url")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    ifw = find_ifw(args.ifw_bin)
    args.output.mkdir(parents=True, exist_ok=True)
    (ROOT / "build").mkdir(exist_ok=True)
    # Each build has a unique directory; never recursively delete a user-supplied output.
    work = Path(tempfile.mkdtemp(prefix="qtifw-", dir=ROOT / "build"))
    pack = generate(args.manifest.resolve(), work, args.version, args.repository_url)
    output_repo = args.output.resolve() / f'repository-{pack["version"]}'
    if output_repo.exists():
        raise ValueError(f"O repositorio {output_repo} ja existe; use outra versao ou outra pasta --output.")
    repository = work / "repository"
    subprocess.run([str(ifw / "repogen.exe"), "-p", str(work / "packages"), str(repository)], check=True)
    executable = args.output.resolve() / f'NewHorizon-Setup-{pack["version"]}.exe'
    subprocess.run([str(ifw / "binarycreator.exe"), "-c", str(work / "config" / "config.xml"),
                    "-r", str(work / "config" / "branding.qrc"),
                    "-p", str(work / "packages"), str(executable)], check=True)
    # Versioned repository directory avoids leaving obsolete archives from a previous release.
    shutil.copytree(repository, output_repo)
    (executable.parent / (executable.name + ".sha256")).write_text(sha256(executable) + "  " + executable.name + "\n", encoding="ascii")
    print(f"\nInstalador: {executable}\nRepositorio: {output_repo}\nProjeto IFW: {work}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
