"""Compile the bundled Qt translations with New Horizon UI wording."""
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
TEXT = {
    "Commit": "Instalar agora",
    "%1 Setup": "%1 · Instalação",
    "Welcome": "Boas-vindas",
    "Finished": "Concluído",
    "Installing": "Instalando",
    "Updating": "Atualizando",
    "Uninstalling": "Desinstalando",
    "Finished the %1 Setup": "%1 está pronto!",
    "Click %1 to exit the %2 Setup.": "Clique em %1 para fechar o instalador do %2.",
    "The %1 Setup failed.": "Não foi possível concluir a instalação do %1.",
    "Ready to Update": "Pronto para atualizar",
    "Fetching latest update information...": "Buscando atualizações...",
    "Loading component scripts...": "Preparando o instalador...",
    "Preparing to unpack components...": "Preparando os arquivos...",
    "Unpacking components...": "Extraindo os arquivos...",
    "%1 of %2 operations completed.": "%1 de %2 etapas concluídas.",
    "%1 of %2 operations rolled back.": "%1 de %2 etapas desfeitas.",
    "Rollbacks complete.": "Alterações desfeitas.",
    "%1 of %2 components installed.": "%1 de %2 componentes instalados.",
    "All components installed.": "Todos os componentes foram instalados.",
    "Canceling the Installer": "Cancelando a instalação",
    "Removal completed successfully.": "Desinstalação concluída.",
    "Removal aborted.": "Desinstalação cancelada.",
    "Cannot prepare removal": "Não foi possível preparar a desinstalação",
    "Cannot start removal": "Não foi possível iniciar a desinstalação",
    "Error during removal process:\n%1": "Erro durante a desinstalação:\n%1",
    "Do you want to cancel the removal process?": "Deseja cancelar a desinstalação?",
    "Search": "Buscar",
    "Select": "Selecionar",
    "Create Offline Installer": "Criar instalador offline",
    "&Create Offline Installer": "Criar instalador offline",
    "Ready to Create Offline Installer": "Pronto para criar o instalador",
    "Creating Offline Installer": "Criando instalador offline",
    "Creating Offline Installer for %1": "Criando instalador de %1",
    "Local cache": "Arquivos temporários",
    "Path for cache:": "Pasta de arquivos temporários:",
    "Clear cache": "Limpar arquivos temporários",
    "Clearing cache...": "Limpando arquivos temporários...",
    "Cache cleared successfully!": "Arquivos temporários limpos!",
    "Deletes the contents of the cache directory": "Apaga os arquivos temporários do instalador",
    "Cannot initialize cache: %1": "Não foi possível preparar os arquivos temporários: %1",
    'Cannot create directory "%1" for cache.': 'Não foi possível criar a pasta temporária "%1".',
    "Specify proxy settings and configure repositories for add-on components.": "Configurar conexão e endereços de atualização.",
    "Browse file system to choose the installation directory.": "Escolher a pasta de instalação.",
    "About %1 installer": "Sobre o instalador do %1",
    "About %1 Maintenance Tool": "Sobre as atualizações do %1",
    "Metadata download canceled.": "Download das informações cancelado.",
    "Retry count (%1) exceeded": "O limite de %1 tentativas foi atingido",
    "Retry count exceeded": "O limite de tentativas foi atingido",
    "Invalid": "Inválido",
}

for path in (ROOT / "installer/translations").glob("*.ts"):
    tree = ET.parse(path)
    tree.getroot().set("language", "pt_BR")
    for message in tree.findall(".//message"):
        source = message.findtext("source", "")
        replacement = TEXT.get(source)
        if source.startswith("All required information is now available to begin removing"):
            replacement = "Os mods do New Horizon serão removidos. Arquivos anteriores serão restaurados. Seus mundos e os demais mods serão mantidos."
        if replacement is not None:
            translation = message.find("translation")
            if translation is None:
                translation = ET.SubElement(message, "translation")
            translation.attrib.pop("type", None)
            translation.text = replacement
    ET.indent(tree)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    subprocess.run([str(ROOT / "tools/qt-python/PySide6/lrelease.exe"),
                    str(path), "-qm", str(path.with_suffix(".qm"))], check=True)
