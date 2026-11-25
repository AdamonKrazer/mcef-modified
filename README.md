# Instalador New Horizon

Instalador Windows criado com **Qt Installer Framework 4.7**, com interface gráfica e ferramenta de manutenção do próprio Qt.

## Executar

Baixe o instalador na release mais recente com nome **New Horizon - Mods** em [Releases](https://github.com/AdamonKrazer/mcef-modified/releases), ou abra o executável gerado em `dist/`. O destino padrão é `%APPDATA%\.minecraft`; o botão **Alterar** permite escolher outra pasta usada pelo launcher.

A interface usa a arte original do servidor (o arquivo de 804.805 bytes indicado em Downloads), tema escuro e detalhes laranja. A primeira tela reúne os mods incluídos, a pasta de destino e o botão **Instalar agora**. Seleção de componentes, menu Iniciar e confirmação redundante foram removidos. A tela final orienta a abertura do perfil Forge. Os catálogos de tradução do Qt são incluídos no executável para que os controles apareçam em português brasileiro independentemente do idioma do Windows.

O pacote contém:

| Componente | Versão |
| --- | --- |
| Minecraft compatível | 1.20.1 |
| Forge | 47.4.0 |
| newhorizon-mod.jar (modId: webdisplays) | 2.0.1-1.20.1 |
| newhorizon-mcef.jar (modId: mcef) | 2.1.6-1.20.1 |

Os dois mods foram copiados da instalação local indicada pelo usuário. O Forge veio do Maven oficial e seu SHA256 está fixado em `pack.json`.

1. Abra o Minecraft 1.20.1 pelo launcher pelo menos uma vez e feche o jogo.
2. Execute o instalador e selecione a pasta `.minecraft`.
3. Se o Forge correto estiver completo, ele será reutilizado. Caso contrário, o assistente executa o instalador oficial com `--installClient`.
4. No launcher, escolha o perfil **1.20.1-forge-47.4.0**. O diretório de jogo desse perfil deve ser a mesma pasta selecionada na instalação.

Para instalar o Forge, é necessário **Java 17** e acesso à internet para baixar as bibliotecas. O assistente procura Java no PATH, JAVA_HOME, Eclipse Adoptium, Java/Microsoft em Program Files e runtimes do launcher. É possível definir `NEW_HORIZON_JAVA` com o caminho completo de `java.exe`. O usuário final não precisa de Python ou Qt instalados.

O assistente verifica os hashes dos arquivos empacotados e das bibliotecas oficiais do Forge. Os mods são copiados depois da preparação do Forge. Os arquivos anteriores com os mesmos nomes ficam em `.newhorizon-backups` durante a instalação; uma operação reversível do Qt os restaura na desinstalação e em caso de falha. Não apague essa pasta enquanto o pacote estiver instalado. Mundos, configurações e mods com outros nomes não são gerenciados. A desinstalação mantém o Forge e suas bibliotecas, que podem ser compartilhados por outros perfis. Arquivos baixados pelo próprio Forge não fazem parte do rollback do Qt.

Feche o jogo antes de instalar, atualizar ou desinstalar. Os dois nomes de arquivo do pacote devem permanecer estáveis entre versões. Outras cópias de MCEF/WebDisplays com nomes diferentes precisam ser removidas pelo usuário para evitar mods duplicados.

## Atualizações

O instalador cria `NewHorizonMaintenance.exe` e `Atualizar New Horizon.lnk` dentro de `.minecraft`. O atalho abre a tela de atualizações do Qt. Não há atualização automática em segundo plano.

O instalador está conectado ao catálogo Qt publicado na branch **mods** de [AdamonKrazer/mcef-modified](https://github.com/AdamonKrazer/mcef-modified/tree/mods):

```text
https://raw.githubusercontent.com/AdamonKrazer/mcef-modified/refs/heads/mods/repository
```

Para publicar novos mods:

1. Na branch `mods`, substitua `assets/newhorizon-mod.jar` e/ou `assets/newhorizon-mcef.jar` pelos novos JARs, mantendo os nomes.
2. Faça commit e push para essa branch (ou use o upload de arquivos do GitHub).
3. Aguarde o workflow **Publicar mods New Horizon** terminar em **Actions**. Ele valida os JARs, gera o instalador, atualiza `repository/` e cria uma release `mods-vVERSAO` com os dois mods, instalador, catálogo ZIP e hashes SHA256.
4. Os jogadores abrem **Atualizar New Horizon** com o jogo fechado para instalar a nova versão.

As versões de publicação são automáticas: `MAJOR.MINOR.NUMERO_DA_EXECUCAO.TENTATIVA`, usando os dois primeiros números de `pack.json`. Não é preciso mudar a versão interna dos mods. Alterações no instalador, no manifesto ou nos scripts de publicação também geram release; alterações somente na documentação não geram. O workflow usa o token do próprio GitHub, sem segredo adicional. A branch `main` e as releases Minecraft/JCEF existentes são independentes.

O cache público do GitHub pode levar alguns minutos para refletir a nova versão depois que o workflow termina. Nesse intervalo, o atualizador pode ainda informar que não há atualizações; basta abri-lo novamente após a propagação.

O código-fonte dos mods não está neste repositório: o workflow distribui os JARs enviados para `assets/`, sem compilar os mods. O catálogo mantém os arquivos de versões anteriores para atender clientes com metadados em cache. Não edite `repository/` manualmente. Faça pull antes de novos pushes, pois o workflow grava um commit nessa branch.

Instalações feitas com o antigo instalador 1.1.0 não têm a URL embutida: adicione o endereço acima em **Configurações / Repositórios** da ferramenta de manutenção. Os novos instaladores já vêm conectados. A consulta acontece ao abrir o instalador ou a ferramenta de atualização, sem serviço em segundo plano.

## Gerar novamente

Requisitos de desenvolvimento: Windows, Python 3.11+ e Qt Installer Framework. As ferramentas usadas nesta máquina estão em `tools/qtifw/`.

```powershell
python tools/build.py --version 1.2.0

# Com endereço de atualização:
python tools/build.py --version 1.2.1 --repository-url https://raw.githubusercontent.com/AdamonKrazer/mcef-modified/refs/heads/mods/repository

# Com outra instalação do Qt IFW:
python tools/build.py --ifw-bin C:/Qt/Tools/QtInstallerFramework/4.7/bin --version 1.2.2
```

`tools/bootstrap-qt.ps1` baixa e extrai a distribuição oficial das ferramentas (exige 7-Zip). `QTIFW_BIN` também pode apontar para a pasta de executáveis. O gerador valida os JARs e seus modIds, confere o hash do Forge, gera os metadados e chama `repogen` e `binarycreator`. Cada compilação deixa a estrutura Qt em uma nova pasta `build/qtifw-*` para inspeção. Use uma nova versão ou uma pasta `--output` diferente se o repositório daquela versão já existir.

## Verificação

```powershell
# Baseline anterior ao pacote publicado, para testar a URL embutida:
python tools/build.py --version 1.2.0 --output .test-work/baseline
python tests/integration.py --setup .test-work/baseline/NewHorizon-Setup-1.2.0.exe --install-repository .test-work/baseline/repository-1.2.0 --update-default

# Fluxo gráfico real em uma pasta de teste, incluindo a confirmação:
python tests/gui_flow.py --setup dist/NewHorizon-Setup-1.2.2.1.exe

# Teste adicional com download real das bibliotecas do Forge:
python tests/fresh_forge.py
```

O teste usa uma cópia das bibliotecas do Forge existente em `%APPDATA%\.minecraft` e executa instalação, atualização e desinstalação reais em `.test-work/`. Verifica a restauração de um mod anterior, preservação de arquivos externos, caminhos com espaços/acentos e falha controlada quando Minecraft não existe. Nunca usa a instalação real como destino.

## Interface e traduções

`installer/WelcomePage.ui` e `installer/FinishPanel.ui` definem as telas; `installer/style.qss` define o tema. A logo é incorporada como recurso Qt, sem modificar a imagem original. `installer/translations/` contém os catálogos oficiais do [Qt IFW 4.7](https://github.com/qtproject/installer-framework/blob/4.7/src/sdk/translations/ifw_pt_BR.ts) e [Qt Base](https://github.com/qt/qttranslations/blob/5.15/translations/qtbase_pt_BR.ts), com ajustes para o New Horizon. Os `.qm` compilados são versionados e usados diretamente no build. Para recompilar após editar traduções: `python tools/localize.py`, usando `lrelease.exe` de `tools/qt-python/PySide6/` (ferramenta de desenvolvimento, não distribuída ao usuário). Mensagens técnicas emitidas pelo instalador oficial do Forge permanecem no idioma original nos detalhes do log.

## Referências

- [Qt Installer Framework](https://doc.qt.io/qtinstallerframework/ifw-overview.html)
- [Operações e rollback do Qt](https://doc.qt.io/qtinstallerframework/operations.html)
- [Repositórios e ferramentas de geração](https://doc.qt.io/qtinstallerframework/ifw-tools.html)
- [Instalador oficial do Forge](https://github.com/MinecraftForge/Installer/tree/2.0)

Os componentes de terceiros mantêm suas próprias licenças e os metadados dos JARs originais. O executável gerado não possui assinatura Authenticode.
