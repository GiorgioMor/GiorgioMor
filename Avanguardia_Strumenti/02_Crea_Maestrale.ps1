# AVANGUARDIA - Passo 2: crea l'arma Maestrale eseguendo lo script Python
# nell'editor di Unreal in modalita' "senza interfaccia" (UnrealEditor-Cmd).
#
# Uso: doppio clic su 02_Crea_Maestrale.bat (a editor CHIUSO).
# Opzioni: -Progetto "G:\Progetto_FPS"

param(
    [string]$Progetto = ""
)

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "_comune.ps1")

Scrivi-Titolo "AVANGUARDIA - Passo 2: crea Maestrale"

$uproject = Trova-Progetto $Progetto
if (-not $uproject) {
    Scrivi-Errore "Non trovo il file .uproject. Rilancia con -Progetto G:\Progetto_FPS"
    exit 1
}
$cartella = Split-Path $uproject -Parent
Scrivi-Ok "Progetto: $uproject"

if (Editor-Aperto) {
    Scrivi-Errore "L'editor di Unreal e' aperto. Chiudilo e rilancia (oppure esegui lo script Python dall'editor: File > Esegui script Python)."
    exit 1
}

$motore = Trova-Motore $uproject
if (-not $motore) {
    Scrivi-Errore "Non trovo Unreal Engine (UnrealEditor-Cmd.exe). Puoi eseguire lo script dall'editor: File > Esegui script Python."
    exit 1
}
$exe = Join-Path $motore "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
Scrivi-Ok "Motore: $motore"

# Il plugin Python deve essere attivo (lo fa il passo 1)
$json = Get-Content -Path $uproject -Raw -Encoding UTF8 | ConvertFrom-Json
$py = $json.Plugins | Where-Object { $_.Name -eq "PythonScriptPlugin" -and $_.Enabled -eq $true }
if (-not $py) {
    Scrivi-Errore "Il plugin Python non e' attivo nel .uproject. Esegui prima 01_Proteggi_progetto.bat."
    exit 1
}

# Lo script viene copiato in Saved\Avanguardia (percorso senza spazi, richiesto da -script=)
$saved = Join-Path $cartella "Saved\Avanguardia"
New-Item -ItemType Directory -Force -Path $saved | Out-Null
$script = Join-Path $saved "avanguardia_crea_maestrale.py"
Copy-Item -Force (Join-Path $PSScriptRoot "Python\avanguardia_crea_maestrale.py") $script
$log = Join-Path $saved "crea_maestrale_log.txt"
$report = Join-Path $saved "maestrale_report.txt"
if (Test-Path $report) { Remove-Item -Force $report }
if ($script.Contains(" ") -or $uproject.Contains(" ")) {
    Scrivi-Avviso "Il percorso del progetto contiene spazi: se lo script non parte, eseguilo dall'editor (File > Esegui script Python)."
}

Scrivi-Info "Avvio Unreal senza interfaccia: carica Lyra, crea gli asset e salva."
Scrivi-Info "Ci vogliono alcuni minuti; vedrai scorrere molte righe di log, e' normale."
$inizio = Get-Date
& $exe $uproject "-run=pythonscript" "-script=$script" "-unattended" "-nosplash" "-nop4" "-abslog=$log"
$codice = $LASTEXITCODE
$durata = [math]::Round(((Get-Date) - $inizio).TotalMinutes, 1)

Scrivi-Titolo "Risultato (durata $durata min, codice $codice)"
if (Test-Path $report) {
    Get-Content -Path $report -Encoding UTF8 | ForEach-Object {
        $riga = [string]$_
        if ($riga.Contains("[ERRORE]")) { Write-Host $riga -ForegroundColor Red }
        elseif ($riga.Contains("[AVVISO]") -or $riga.Contains("[MANUALE]")) { Write-Host $riga -ForegroundColor Yellow }
        elseif ($riga.Contains("[OK]")) { Write-Host $riga -ForegroundColor Green }
        else { Write-Host $riga }
    }
    Scrivi-Info ""
    Scrivi-Ok "Resoconto completo: $report"
    Scrivi-Info "Log di Unreal:      $log"
    Scrivi-Info "Manda il resoconto a Claude se ci sono righe [ERRORE] o [MANUALE] che non ti sono chiare."
} else {
    Scrivi-Errore "Lo script Python non ha prodotto il resoconto. Guarda il log: $log"
    Scrivi-Info   "Cerca le righe con 'LogPython' o 'Error'. In alternativa esegui lo script dall'editor:"
    Scrivi-Info   "File > Esegui script Python > Avanguardia_Strumenti\Python\avanguardia_crea_maestrale.py"
    exit 2
}
