# AVANGUARDIA - funzioni comuni agli script PowerShell.
# Non va eseguito da solo: lo caricano gli altri script.

function Scrivi-Titolo([string]$Testo) {
    Write-Host ""
    Write-Host "=== $Testo ===" -ForegroundColor Cyan
}
function Scrivi-Ok([string]$Testo)     { Write-Host "[OK] $Testo" -ForegroundColor Green }
function Scrivi-Info([string]$Testo)   { Write-Host "     $Testo" }
function Scrivi-Avviso([string]$Testo) { Write-Host "[AVVISO] $Testo" -ForegroundColor Yellow }
function Scrivi-Errore([string]$Testo) { Write-Host "[ERRORE] $Testo" -ForegroundColor Red }

# Trova il file .uproject. Ordine: parametro -Progetto, cartelle sopra a questi
# script (se li hai copiati dentro il progetto), infine G:\Progetto_FPS.
function Trova-Progetto([string]$Progetto) {
    $candidati = @()
    if ($Progetto) {
        $candidati += $Progetto
    } else {
        $d = $PSScriptRoot
        for ($i = 0; $i -lt 4 -and $d; $i++) {
            $candidati += $d
            $d = Split-Path $d -Parent
        }
        $candidati += "G:\Progetto_FPS"
    }
    foreach ($c in $candidati) {
        if ($c -and (Test-Path $c -PathType Leaf) -and $c.ToLower().EndsWith(".uproject")) {
            return (Resolve-Path $c).Path
        }
        if ($c -and (Test-Path $c -PathType Container)) {
            $f = Get-ChildItem -Path $c -Filter *.uproject -File -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($f) { return $f.FullName }
        }
    }
    return $null
}

# Trova la cartella di installazione di Unreal Engine usata dal progetto.
function Trova-Motore([string]$UProject) {
    $versione = $null
    try {
        $json = Get-Content -Path $UProject -Raw -Encoding UTF8 | ConvertFrom-Json
        $versione = $json.EngineAssociation
    } catch { }
    $candidati = @()
    if ($versione) {
        foreach ($chiave in @("HKLM:\SOFTWARE\EpicGames\Unreal Engine\$versione",
                              "HKLM:\SOFTWARE\WOW6432Node\EpicGames\Unreal Engine\$versione")) {
            try {
                $v = (Get-ItemProperty -Path $chiave -Name InstalledDirectory -ErrorAction Stop).InstalledDirectory
                if ($v) { $candidati += $v }
            } catch { }
        }
        try {
            $v = (Get-ItemProperty -Path "HKCU:\Software\Epic Games\Unreal Engine\Builds" -Name $versione -ErrorAction Stop).$versione
            if ($v) { $candidati += $v }
        } catch { }
        $dat = "C:\ProgramData\Epic\UnrealEngineLauncher\LauncherInstalled.dat"
        if (Test-Path $dat) {
            try {
                $lista = (Get-Content $dat -Raw | ConvertFrom-Json).InstallationList
                foreach ($e in $lista) {
                    if ($e.AppName -eq "UE_$versione") { $candidati += $e.InstallLocation }
                }
            } catch { }
        }
        $candidati += "C:\Program Files\Epic Games\UE_$versione"
    }
    foreach ($c in $candidati) {
        if ($c -and (Test-Path (Join-Path $c "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"))) {
            return $c
        }
    }
    return $null
}

# Cerca il file .uplugin di un plugin del motore (es. PythonScriptPlugin).
function Trova-PluginMotore([string]$Motore, [string]$Nome) {
    $base = Join-Path $Motore "Engine\Plugins"
    foreach ($sotto in @("Experimental", "Editor", "Scripting", "Runtime", "")) {
        $p = Join-Path (Join-Path $base $sotto) "$Nome\$Nome.uplugin"
        if (Test-Path $p) { return $p }
    }
    $f = Get-ChildItem -Path $base -Filter "$Nome.uplugin" -Recurse -Depth 3 -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($f) { return $f.FullName }
    return $null
}

# True se l'editor di Unreal e' aperto.
function Editor-Aperto {
    $p = Get-Process -Name "UnrealEditor", "UnrealEditor-Cmd" -ErrorAction SilentlyContinue
    return [bool]$p
}

# Esegue git e si ferma se fallisce.
function Git-Esegui {
    & git @args
    if ($LASTEXITCODE -ne 0) {
        throw "Il comando 'git $($args -join ' ')' e' fallito (codice $LASTEXITCODE)."
    }
}

# Legge un valore di configurazione git (vuoto se non c'e').
function Git-Leggi([string]$Chiave) {
    $v = & git config --get $Chiave 2>$null
    if ($LASTEXITCODE -ne 0) { return "" }
    return "$v".Trim()
}

# Scrive un file di testo in UTF-8 senza BOM.
function Scrivi-FileUtf8([string]$Percorso, [string]$Testo) {
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Percorso, $Testo, $enc)
}
