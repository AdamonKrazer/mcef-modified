function Component() {
    if (installer.isInstaller() && !installer.isCommandLineInstance()) {
        component.loaded.connect(this, Component.prototype.setupWelcome);
    }
}

Component.prototype.setupWelcome = function() {
    installer.addWizardPage(component, "WelcomePage", QInstaller.TargetDirectory);
    var widget = gui.pageWidgetByObjectName("DynamicWelcomePage");
    widget.windowTitle = "";
    widget.commit = true;
    var pathField = gui.findChild(widget, "MinecraftPath");
    var browse = gui.findChild(widget, "BrowseFolder");
    pathField.text = installer.toNativeSeparators(installer.value("TargetDir"));
    browse.clicked.connect(function() {
        var path = QFileDialog.getExistingDirectory("Escolha a pasta do Minecraft", pathField.text);
        if (path) {
            installer.setValue("TargetDir", installer.fromNativeSeparators(path));
            pathField.text = installer.toNativeSeparators(path);
        }
    });
    installer.setValidatorForCustomPage(component, "WelcomePage", "validateWelcome");
    installer.addWizardPageItem(component, "FinishPanel", QInstaller.InstallationFinished);
    installer.setDefaultPageVisible(QInstaller.TargetDirectory, false);
    installer.setDefaultPageVisible(QInstaller.ComponentSelection, false);
    installer.setDefaultPageVisible(QInstaller.StartMenuSelection, false);
    installer.setDefaultPageVisible(QInstaller.ReadyForInstallation, false);
};

Component.prototype.validateWelcome = function() {
    installer.setValue("NewHorizonConfirmed", "true");
    return true;
};

Component.prototype.createOperations = function() {
    if (installer.isInstaller() && !installer.isCommandLineInstance() && installer.value("NewHorizonConfirmed") !== "true") {
        throw new Error("Confirme a instalação na tela do New Horizon antes de continuar.");
    }
    component.createOperations();
    var payload = "@TargetDir@/.newhorizon";
    var powershell = installer.environmentVariable("SystemRoot") +
        "/System32/WindowsPowerShell/v1.0/powershell.exe";
    component.addOperation("Execute", ["{0}", powershell,
        "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", payload + "/ensure-forge.ps1", "-MinecraftDir", "@TargetDir@",
        "errormessage=Não foi possível preparar o Forge e os backups. Abra os detalhes para ver o erro.",
        "UNDOEXECUTE", powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", payload + "/ensure-forge.ps1", "-MinecraftDir", "@TargetDir@", "-RestoreBackup"]);
    component.addOperation("Mkdir", "@TargetDir@/mods");
    // Persistent originals are restored by UNDOEXECUTE after these Copy operations are undone.
    // __MOD_COPY_OPERATIONS__
    component.addOperation("CreateShortcut", "@TargetDir@/NewHorizonMaintenance.exe",
        "@TargetDir@/Atualizar New Horizon.lnk", "--start-updater",
        "workingDirectory=@TargetDir@", "description=Atualizar os mods do New Horizon");
};
