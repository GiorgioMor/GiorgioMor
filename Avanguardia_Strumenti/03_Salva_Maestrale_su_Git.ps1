# AVANGUARDIA - Passo 3: dopo aver provato Maestrale in editor, salva tutto con un commit Git.
#
# Uso: doppio clic su 03_Salva_Maestrale_su_Git.bat (meglio a editor chiuso, dopo aver salvato tutto).

param(
    [string]$Progetto = ""
)

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "_comune.ps1")

Scrivi-Titolo "AVANGUARDIA - Passo 3: commit di Maestrale"

$uproject = Trova-Progetto $Progetto
if (-not $uproject) {
    Scrivi-Errore "Non trovo il file .uproject. Rilancia con -Progetto G:\Progetto_FPS"
    exit 1
}
$cartella = Split-Path $uproject -Parent
if (-not (Test-Path (Join-Path $cartella ".git"))) {
    Scrivi-Errore "Il progetto non e' ancora sotto Git: esegui prima 01_Proteggi_progetto.bat."
    exit 1
}
if (Editor-Aperto) {
    Scrivi-Avviso "L'editor e' aperto: assicurati di aver salvato tutto (File > Salva tutto) prima di continuare."
    Read-Host "Premi Invio per continuare"
}

$titolo = "Aggiunge Maestrale, primo fucile d'assalto di Avanguardia"
$corpo = @"
Maestrale e' una copia del fucile di Lyra in Plugins/GameFeatures/ShooterCore/Content/Weapons/Maestrale
(definizione oggetto, equipaggiamento, istanza arma, set di abilita', abilita' di fuoco, effetto di danno,
dati del raccoglibile e curva di calo del danno). Gli asset originali del fucile di Lyra non sono modificati.

Statistiche (documento di design, fase 1):
- danno 30 a breve distanza, 20 a lunga distanza
- 750 colpi/min (0,08 s tra un colpo e l'altro), automatico
- caricatore 30 colpi, munizioni di riserva come il fucile Lyra
- ricarica 2,2 s
- mira con l'ottica 0,25 s: rimandata (in Lyra e' comune a tutte le armi)

In Elimination il giocatore ha Maestrale al posto del fucile di Lyra.
Dettagli nel resoconto Saved/Avanguardia/maestrale_report.txt (non versionato).
"@

Push-Location $cartella
try {
    Git-Esegui add -A
    & git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        Scrivi-Avviso "Non ci sono modifiche da salvare."
        exit 0
    }
    Scrivi-Info "File che verranno salvati:"
    & git diff --cached --stat
    Git-Esegui commit -q -m $titolo -m $corpo
    Scrivi-Ok "Commit fatto:"
    & git log --oneline -3
} catch {
    Scrivi-Errore $_.Exception.Message
    exit 2
} finally {
    Pop-Location
}
