function Controller() {
    // This product intentionally shares .minecraft; RemoveTargetDir=false preserves it.
    installer.setMessageBoxAutomaticAnswer("OverwriteTargetDirectory", QMessageBox.Yes);
    if (installer.isInstaller() && !installer.isCommandLineInstance()) {
        var appData = installer.environmentVariable("APPDATA");
        if (installer.value("PreviewTargetDir"))
            installer.setValue("TargetDir", installer.value("PreviewTargetDir"));
        else if (appData)
            installer.setValue("TargetDir", installer.fromNativeSeparators(appData) + "/.minecraft");
    }
    if (!installer.isCommandLineInstance()) {
        gui.showSettingsButton(!installer.isInstaller());
        installer.valueChanged.connect(function(key) {
            if (key === "NewHorizonCheckExisting" && Controller.prototype.configureExistingBackground())
                gui.rejectWithoutPrompt();
        });
    }
}

Controller.prototype.IntroductionPageCallback = function() {
    if (installer.isInstaller()) {
        if (Controller.prototype.configureExistingBackground()) {
            gui.rejectWithoutPrompt();
            return;
        }
        gui.currentPageWidget().title = "New Horizon";
        gui.currentPageWidget().MessageLabel.setText("Carregando seu instalador...");
        if (installer.value("NewHorizonIntroLoaded") !== "true") {
            installer.setValue("NewHorizonIntroLoaded", "true");
            gui.clickButton(buttons.NextButton);
        }
    } else {
        var page = gui.currentPageWidget();
        if (page.PackageManagerRadioButton) page.PackageManagerRadioButton.hide();
        gui.showSettingsButton(true);
    }
};

Controller.prototype.backgroundRepository = function() {
    return __BACKGROUND_REPOSITORY__;
};

Controller.prototype.configureExistingBackground = function() {
    var root = installer.value("TargetDir");
    if (installer.isCommandLineInstance() || !installer.fileExists(root + "/NewHorizonMaintenance.exe") ||
        !installer.fileExists(root + "/newhorizon-components.xml")) return false;
    var page = gui.currentPageWidget();
    page.title = "Preparando atualizações automáticas";
    if (page.MessageLabel) {
        page.MessageLabel.setText("Conferindo os mods e ativando as atualizações em segundo plano. Aguarde...");
        page.MessageLabel.repaint();
    }
    var temporary = installer.fromNativeSeparators(installer.environmentVariable("TEMP")) +
        "/NewHorizon-setup-" + new Date().getTime();
    var script = temporary + "/background-update.ps1";
    var status = {status: "error", message: "Não foi possível preparar a atualização. Tente novamente."};
    if (installer.performOperation("Mkdir", [temporary]) &&
        installer.performOperation("Copy", [":/newhorizon/background-update.ps1", script])) {
        var powershell = installer.environmentVariable("SystemRoot") + "/System32/WindowsPowerShell/v1.0/powershell.exe";
        var result = installer.execute(powershell, ["-NoLogo", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
            "-ExecutionPolicy", "Bypass", "-File", script, "-MinecraftDir", root, "-RepositoryUrl", Controller.prototype.backgroundRepository()]);
        if (installer.fileExists(root + "/.newhorizon-state/status.json")) {
            try { status = JSON.parse(installer.readFile(root + "/.newhorizon-state/status.json", "UTF-8").replace(/^\uFEFF/, "")); }
            catch (error) { status.message = "Não foi possível ler o resultado da atualização."; }
        }
        if (!result.length || result[1] !== 0) status.status = "error";
        installer.performOperation("Delete", [script]);
    }
    var activated = false;
    try { activated = JSON.parse(installer.readFile(root + "/.newhorizon/manifest.json", "UTF-8")).background_updates === true; }
    catch (error) {}
    if ((status.status === "updated" || status.status === "current") && !activated) {
        status = {status: "error", message: "A nova versão ainda não está disponível neste ponto de download. Tente novamente em alguns minutos."};
    }
    Controller.prototype.finishBackgroundSetup(status);
    return true;
};

Controller.prototype.finishBackgroundSetup = function(status) {
    if (status.status === "updated" || status.status === "current") {
        QMessageBox.information("NewHorizonBackgroundReady", "New Horizon",
            "Tudo pronto! Os mods serão atualizados em segundo plano ao entrar no Windows e a cada 30 minutos. Você não precisa abrir o instalador novamente.");
    } else if (status.status === "deferred") {
        QMessageBox.information("NewHorizonGameRunning", "Feche o Minecraft",
            "Feche o Minecraft e execute este instalador novamente para ativar as atualizações automáticas.");
    } else {
        QMessageBox.critical("NewHorizonBackgroundError", "Não foi possível ativar as atualizações", status.message);
    }
};

Controller.prototype.TargetDirectoryPageCallback = function() {
    gui.currentPageWidget().MessageLabel.setText(
        "Selecione a pasta .minecraft usada pelo seu launcher. Os mods serão instalados na subpasta mods.");
};

Controller.prototype.DynamicWelcomePageCallback = function() {
    gui.showSettingsButton(false);
    var page = gui.pageByObjectName("DynamicWelcomePage");
    page.title = "";
    page.subTitle = "";
    // Remove the old page only after the custom page is current. Removing the
    // active Introduction page while its Next action is pending skips a page.
    if (installer.value("NewHorizonIntroHidden") !== "true") {
        installer.setValue("NewHorizonIntroHidden", "true");
        installer.setDefaultPageVisible(QInstaller.Introduction, false);
    }
};

Controller.prototype.PerformInstallationPageCallback = function() {
    gui.showSettingsButton(false);
    var page = gui.pageById(QInstaller.PerformInstallation);
    page.title = "Preparando seu Minecraft";
    page.subTitle = "Aguarde enquanto instalamos os arquivos do New Horizon.";
};

Controller.prototype.FinishedPageCallback = function() {
    gui.showSettingsButton(false);
    var page = gui.pageById(QInstaller.InstallationFinished);
    var panel = gui.findChild(page, "FinishPanel");
    var message = gui.findChild(page, "MessageLabel");
    if (installer.status === QInstaller.Success && installer.isInstaller()) {
        page.title = "";
        page.subTitle = "";
        if (message) message.hide();
        if (panel) panel.show();
    } else {
        if (panel) panel.hide();
        if (installer.status !== QInstaller.Success) page.title = "A instalação não foi concluída";
    }
};
