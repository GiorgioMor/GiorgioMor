# AVANGUARDIA - Passo 1: mette il progetto sotto Git (con Git LFS) e attiva il plugin Python.
#
# Cosa fa:
#   1. controlla che Git e Git LFS siano installati
#   2. crea .gitignore (esclude Binaries, Intermediate, Saved, DerivedDataCache...) e .gitattributes (LFS)
#   3. inizializza il repository locale e fa il primo commit con il progetto cosi' com'e' ora
#   4. attiva "Python Editor Script Plugin" nel .uproject e fa un secondo commit
#
# Uso: doppio clic su 01_Proteggi_progetto.bat (a editor CHIUSO).
# Opzioni: -Progetto "G:\Progetto_FPS"   -SenzaLFS (sconsigliato)

param(
    [string]$Progetto = "",
    [switch]$SenzaLFS
)

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "_comune.ps1")

$gitignore = @'
# AVANGUARDIA - file che Git deve ignorare (Unreal Engine)
# Sono tutti file rigenerati dal motore o da Visual Studio.

# Cartelle generate del progetto
/Binaries/
/Intermediate/
/Saved/
/DerivedDataCache/

# Le stesse cartelle dentro i plugin (es. Plugins/GameFeatures/ShooterCore)
/Plugins/**/Binaries/
/Plugins/**/Intermediate/
/Plugins/**/Saved/

# Visual Studio / Rider (si rigenerano con "Generate Visual Studio project files")
.vs/
.idea/
*.sln
*.suo
*.sdf
*.opensdf
*.VC.db
*.VC.opendb
.vsconfig

# File temporanei di Windows
Thumbs.db
Desktop.ini
*.tmp
'@

$gitattributes = @'
# AVANGUARDIA - file binari pesanti salvati con Git LFS
# (servira' quando il progetto andra' su GitHub: i file grandi non entrano in un repository normale)

# Asset e mappe di Unreal
*.uasset filter=lfs diff=lfs merge=lfs -text
*.umap   filter=lfs diff=lfs merge=lfs -text

# Modelli 3D e animazioni
*.fbx    filter=lfs diff=lfs merge=lfs -text
*.abc    filter=lfs diff=lfs merge=lfs -text
*.blend  filter=lfs diff=lfs merge=lfs -text

# Immagini
*.png    filter=lfs diff=lfs merge=lfs -text
*.jpg    filter=lfs diff=lfs merge=lfs -text
*.jpeg   filter=lfs diff=lfs merge=lfs -text
*.tga    filter=lfs diff=lfs merge=lfs -text
*.bmp    filter=lfs diff=lfs merge=lfs -text
*.psd    filter=lfs diff=lfs merge=lfs -text
*.exr    filter=lfs diff=lfs merge=lfs -text
*.hdr    filter=lfs diff=lfs merge=lfs -text
*.tif    filter=lfs diff=lfs merge=lfs -text
*.tiff   filter=lfs diff=lfs merge=lfs -text
*.dds    filter=lfs diff=lfs merge=lfs -text
*.ico    filter=lfs diff=lfs merge=lfs -text

# Audio e video
*.wav    filter=lfs diff=lfs merge=lfs -text
*.mp3    filter=lfs diff=lfs merge=lfs -text
*.ogg    filter=lfs diff=lfs merge=lfs -text
*.flac   filter=lfs diff=lfs merge=lfs -text
*.mp4    filter=lfs diff=lfs merge=lfs -text
*.mov    filter=lfs diff=lfs merge=lfs -text
*.bk2    filter=lfs diff=lfs merge=lfs -text

# Font e archivi
*.ttf    filter=lfs diff=lfs merge=lfs -text
*.otf    filter=lfs diff=lfs merge=lfs -text
*.zip    filter=lfs diff=lfs merge=lfs -text
*.7z     filter=lfs diff=lfs merge=lfs -text
'@

Scrivi-Titolo "AVANGUARDIA - Passo 1: proteggi il progetto"

# --- Progetto ---------------------------------------------------------------
$uproject = Trova-Progetto $Progetto
if (-not $uproject) {
    Scrivi-Errore "Non trovo il file .uproject. Rilancia indicando la cartella, per esempio:"
    Scrivi-Info   "powershell -ExecutionPolicy Bypass -File 01_Proteggi_progetto.ps1 -Progetto G:\Progetto_FPS"
    exit 1
}
$cartella = Split-Path $uproject -Parent
Scrivi-Ok "Progetto: $uproject"

if (Editor-Aperto) {
    Scrivi-Errore "L'editor di Unreal e' aperto. Chiudilo (salvando il lavoro) e rilancia questo script."
    exit 1
}

# --- Git e Git LFS ------------------------------------------------------------
Scrivi-Titolo "Controllo Git"
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    Scrivi-Errore "Git non e' installato (o non e' nel PATH)."
    Scrivi-Info   "Non ho toccato nulla. Dimmi come preferisci procedere: per esempio installare"
    Scrivi-Info   "'Git for Windows' da https://git-scm.com/download/win (include Git LFS) e rilanciare."
    exit 2
}
Scrivi-Ok ((& git --version) -join " ")

$lfsOk = $false
$lfsVer = & git lfs version 2>&1
if ($LASTEXITCODE -eq 0) { $lfsOk = $true; Scrivi-Ok "Git LFS: $lfsVer" }
if (-not $lfsOk) {
    if ($SenzaLFS) {
        Scrivi-Avviso "Git LFS non trovato: procedo SENZA LFS come richiesto (-SenzaLFS)."
    } else {
        Scrivi-Errore "Git LFS non e' installato. Il documento di design prevede Git con LFS per i file pesanti."
        Scrivi-Info   "Installalo (https://git-lfs.com, oppure reinstalla Git for Windows) e rilancia."
        Scrivi-Info   "Se vuoi procedere comunque senza LFS: rilancia con l'opzione -SenzaLFS."
        exit 3
    }
}

Push-Location $cartella
try {
    # --- Repository -----------------------------------------------------------
    Scrivi-Titolo "Repository"
    $nuovoRepo = -not (Test-Path (Join-Path $cartella ".git"))
    if ($nuovoRepo) {
        Git-Esegui init
        & git symbolic-ref HEAD refs/heads/main
        Scrivi-Ok "Repository Git creato in $cartella (ramo main)"
    } else {
        Scrivi-Avviso "Esiste gia' un repository Git in questa cartella: lo uso cosi' com'e'."
    }
    # Lyra ha percorsi molto lunghi: senza questa opzione Git su Windows puo' fallire.
    Git-Esegui config core.longpaths true
    if ($lfsOk) {
        Git-Esegui lfs install --local
        Scrivi-Ok "Git LFS attivato per questo repository"
    }

    # Nome e email per i commit (solo per questo repository, se mancano)
    if (-not (Git-Leggi "user.name")) {
        $n = Read-Host "Git non conosce il tuo nome. Scrivi il nome da usare nei commit"
        Git-Esegui config user.name "$n"
    }
    if (-not (Git-Leggi "user.email")) {
        $e = Read-Host "Scrivi l'email da usare nei commit"
        Git-Esegui config user.email "$e"
    }

    # --- .gitignore e .gitattributes -----------------------------------------
    $fileIgnore = Join-Path $cartella ".gitignore"
    if (Test-Path $fileIgnore) {
        Scrivi-Avviso ".gitignore esiste gia': non lo sovrascrivo. Controlla che escluda Binaries, Intermediate, Saved e DerivedDataCache."
    } else {
        Scrivi-FileUtf8 $fileIgnore ($gitignore -replace "`r?`n", "`r`n")
        Scrivi-Ok ".gitignore creato"
    }
    if ($lfsOk) {
        $fileAttr = Join-Path $cartella ".gitattributes"
        if (Test-Path $fileAttr) {
            Scrivi-Avviso ".gitattributes esiste gia': non lo sovrascrivo."
        } else {
            Scrivi-FileUtf8 $fileAttr ($gitattributes -replace "`r?`n", "`r`n")
            Scrivi-Ok ".gitattributes creato (asset e mappe in Git LFS)"
        }
    }

    # --- Primo commit ---------------------------------------------------------
    Scrivi-Titolo "Primo commit"
    $dimensione = (Get-ChildItem -Path (Join-Path $cartella "Content"), (Join-Path $cartella "Plugins") -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    $gb = [math]::Round($dimensione / 1GB, 1)
    Scrivi-Info "Contenuti da salvare: circa $gb GB. Git LFS ne tiene una copia in .git, quindi servono"
    Scrivi-Info "circa altrettanti GB liberi sul disco. Il primo commit puo' richiedere diversi minuti..."
    Git-Esegui add -A
    & git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        Scrivi-Avviso "Niente di nuovo da salvare (forse il commit e' gia' stato fatto)."
    } else {
        Git-Esegui commit -q -m "Progetto Avanguardia: stato iniziale da Lyra Starter Game" -m "Primo salvataggio prima di qualsiasi modifica (UE 5.8, progetto creato da Lyra)."
        Scrivi-Ok "Primo commit fatto"
    }

    # --- Plugin Python --------------------------------------------------------
    Scrivi-Titolo "Plugin Python dell'editor"
    $motore = Trova-Motore $uproject
    if (-not $motore) {
        Scrivi-Avviso "Non trovo la cartella di Unreal Engine: controllo i plugin solo nel .uproject."
    } else {
        Scrivi-Ok "Unreal Engine: $motore"
    }

    $json = Get-Content -Path $uproject -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not ($json.PSObject.Properties.Name -contains "Plugins")) {
        $json | Add-Member -NotePropertyName Plugins -NotePropertyValue @()
    }
    $modificato = $false
    foreach ($nome in @("PythonScriptPlugin", "EditorScriptingUtilities")) {
        if ($motore -and -not (Trova-PluginMotore $motore $nome)) {
            Scrivi-Avviso "Il plugin $nome non esiste in questa versione del motore: lo salto."
            continue
        }
        $voce = $json.Plugins | Where-Object { $_.Name -eq $nome } | Select-Object -First 1
        if ($voce) {
            if ($voce.Enabled -ne $true) {
                $voce | Add-Member -NotePropertyName Enabled -NotePropertyValue $true -Force
                $modificato = $true
                Scrivi-Ok "$nome era disattivato: ora e' attivo"
            } else {
                Scrivi-Ok "$nome era gia' attivo"
            }
        } else {
            $json.Plugins += [pscustomobject]@{ Name = $nome; Enabled = $true }
            $modificato = $true
            Scrivi-Ok "$nome aggiunto e attivato"
        }
    }
    if ($modificato) {
        $testo = $json | ConvertTo-Json -Depth 32
        Scrivi-FileUtf8 $uproject ($testo -replace "`r?`n", "`r`n")
        Git-Esegui add -- (Split-Path $uproject -Leaf)
        Git-Esegui commit -q -m "Attiva il plugin Python dell'editor (Python Editor Script Plugin)" -m "Serve per creare e modificare gli asset con gli script in Avanguardia_Strumenti."
        Scrivi-Ok "Modifica al .uproject salvata con un secondo commit"
    }

    Scrivi-Titolo "Fatto"
    & git log --oneline -5
    Scrivi-Info ""
    Scrivi-Info "Il progetto e' protetto: se qualcosa va storto si puo' tornare a questo punto con Git."
    Scrivi-Info "Prossimo passo: 02_Crea_Maestrale.bat (sempre a editor chiuso)."
} catch {
    Scrivi-Errore $_.Exception.Message
    exit 4
} finally {
    Pop-Location
}
