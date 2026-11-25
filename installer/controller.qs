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
    }
}

Controller.prototype.IntroductionPageCallback = function() {
    if (installer.isInstaller()) {
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
