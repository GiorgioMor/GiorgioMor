# Avanguardia – Strumenti per creare Maestrale

Questa cartella contiene gli script che creano **Maestrale**, il primo fucile d'assalto di Avanguardia, partendo dal fucile di Lyra. Gli asset originali di Lyra non vengono modificati: le copie stanno in `Plugins/GameFeatures/ShooterCore/Content/Weapons/Maestrale`.

| File | A cosa serve |
|---|---|
| `01_Proteggi_progetto.bat` | Mette il progetto sotto Git (con Git LFS), fa il primo commit e attiva il plugin Python dell'editor |
| `02_Crea_Maestrale.bat` | Avvia Unreal senza interfaccia ed esegue `Python/avanguardia_crea_maestrale.py` |
| `03_Salva_Maestrale_su_Git.bat` | Dopo la prova in editor, salva tutto con un commit |
| `Python/avanguardia_crea_maestrale.py` | Crea le copie, imposta le statistiche, mette Maestrale in Elimination, scrive il resoconto |
| `Python/avanguardia_misura_arma.py` | Durante il Play misura cadenza, ricarica, danno e colpi per uccidere |

## Prima di iniziare

1. Copia questa cartella dentro il progetto: `G:\Progetto_FPS\Avanguardia_Strumenti`. Così gli script trovano il progetto da soli e finiscono anche in Git.
2. **Chiudi l'editor di Unreal** (salvando il lavoro). Gli script 01 e 02 si rifiutano di partire se è aperto.

I file `.bat` si avviano con un doppio clic. Se Windows mostra l'avviso "PC protetto da Windows", scegli *Ulteriori informazioni → Esegui comunque*: sono script di testo che puoi aprire con il Blocco note.

## Passo 1 – Proteggi il progetto (`01_Proteggi_progetto.bat`)

- Controlla che **Git** e **Git LFS** siano installati. Se Git manca si ferma senza toccare nulla: dimmi come preferisci procedere (per esempio installare *Git for Windows*, che include Git LFS).
- Crea `.gitignore`: esclude `Binaries`, `Intermediate`, `Saved`, `DerivedDataCache`, anche dentro i plugin, e i file di Visual Studio, che si rigenerano.
- Crea `.gitattributes`: `.uasset`, `.umap` e gli altri file binari vanno in **Git LFS**, come previsto dal documento di design. Servirà quando il progetto andrà su GitHub.
- Fa il **primo commit** con il progetto com'è ora. Lyra pesa diversi GB, quindi servono alcuni minuti e altrettanto spazio libero sul disco.
- Attiva **Python Editor Script Plugin** nel file `Avanguardia.uproject` e fa un secondo commit. Questo plugin permette di creare e modificare gli asset con script Python invece che a mano. Se all'apertura l'editor chiede di ricompilare dei moduli, rispondi Sì.

Se Git non conosce ancora il tuo nome e la tua email, te li chiede: valgono solo per questo progetto.

## Passo 2 – Crea Maestrale (`02_Crea_Maestrale.bat`)

Lo script avvia `UnrealEditor-Cmd.exe` senza finestra. Ci vogliono alcuni minuti e scorrono molte righe di log: è normale. Alla fine mostra il **resoconto** a colori, che viene salvato anche in `G:\Progetto_FPS\Saved\Avanguardia\maestrale_report.txt`.

- `[OK]` fatto. `[INFO]` solo informazione.
- `[AVVISO]` da guardare, ma non blocca.
- `[MANUALE]` un passaggio che lo script non può fare da solo, con le istruzioni (tipicamente un nodo dentro il grafo di un Blueprint).
- `[ERRORE]` qualcosa non è andato. In quel caso lo script **non** tocca l'inventario e le mappe di Lyra. Mandami il resoconto.

**In alternativa, dall'editor aperto:** *File → Esegui script Python…* e scegli `Python\avanguardia_crea_maestrale.py`. Il risultato è lo stesso e il resoconto finisce nello stesso file.

Lo script si può rieseguire senza problemi: riusa le copie già create e reimposta le statistiche. Per provare valori diversi basta cambiarli in cima al file `.py`, nella sezione `CONFIGURAZIONE`.

### Cosa crea

| Copia (in `Weapons/Maestrale`) | Originale Lyra | Cos'è | Cosa cambia |
|---|---|---|---|
| `ID_Maestrale` | `ID_Rifle` | Definizione dell'oggetto d'inventario, fatta di "frammenti" | Caricatore 30 (`Lyra.ShooterGame.Weapon.MagazineSize` e `MagazineAmmo`), nome "Maestrale"; munizioni di riserva come Lyra |
| `WID_Maestrale` | `WID_Rifle` | Equipaggiamento: cosa succede quando lo impugni | Punta all'istanza e al set di abilità di Maestrale (il modello 3D resta quello di Lyra) |
| `B_WeaponInstance_Maestrale` | `B_WeaponInstance_Rifle` | Istanza dell'arma (`LyraRangedWeaponInstance`): dispersione, gittata, calo del danno | Calo del danno: usa `Curve_Maestrale_CaloDanno`; colpo alla testa ×1,4 |
| `Curve_Maestrale_CaloDanno` | – | Curva distanza → moltiplicatore del danno | 1,0 fino a 25 m, scende fino a 0,667 a 45 m, poi resta così |
| `AbilitySet_ShooterMaestrale` | `AbilitySet_ShooterRifle` | Abilità concesse quando impugni l'arma | Punta alle abilità di Maestrale |
| `GA_Weapon_Fire_Maestrale` | `GA_Weapon_Fire_Rifle` | Abilità di fuoco | `FireDelayTimeSecs` = 0,08 s (750 colpi/min); applica `GE_Damage_Maestrale` |
| `GE_Damage_Maestrale` | effetto di danno del fucile | Effetto di danno, calcolato da `LyraDamageExecution` | `BaseDamage` = 30 |
| animazione di ricarica `…Maestrale…` | montage di ricarica del fucile | Animazione che scandisce la ricarica | Velocità impostata perché duri 2,2 s |
| `WeaponPickupData_Maestrale` | `WeaponPickupData_Rifle` | Dati delle piattaforme che danno l'arma | Dà `ID_Maestrale` |

In Elimination Maestrale prende il posto del fucile di Lyra in due punti:

- nell'**inventario iniziale**, cioè dove Lyra elenca le armi con cui si nasce;
- sulle **piattaforme delle armi** della mappa `L_Convolution_Blockout`.

Le altre mappe e modalità restano come prima.

### Dove stanno davvero i numeri (per capire Lyra)

- **Danno**: `LyraDamageExecution` calcola `BaseDamage × calo con la distanza × moltiplicatore della zona colpita`. `BaseDamage` sta nell'effetto `GE_…`. Il calo è `DistanceDamageFalloff`, una curva in cm sull'istanza dell'arma, letta da `GetDistanceAttenuation`. La zona colpita è `MaterialDamageMultiplier`, confrontato con i tag del materiale fisico (per esempio `Gameplay.Zone.WeakSpot` per la testa).
- **Caricatore**: non è una variabile dell'arma ma un "tag stack" sull'oggetto d'inventario, inizializzato dal frammento `InventoryFragment_SetStats` di `ID_`. Ogni colpo toglie 1 a `MagazineAmmo`.
- **Cadenza**: variabile Blueprint `FireDelayTimeSecs` nell'abilità di fuoco. L'abilità aspetta quel tempo, termina e si riattiva finché tieni premuto.
- **Ricarica**: la durata la decide l'animazione (montage) che l'abilità di ricarica riproduce. Per questo Maestrale ha una copia dell'animazione con velocità aumentata.

### Se il resoconto dice [MANUALE]

Il resoconto spiega cosa fare caso per caso. Ecco dove trovare ogni valore, se dovessi impostarlo a mano. Fai doppio clic sull'asset nel Content Browser, poi *Class Defaults* in alto per i Blueprint.

| Valore | Asset | Campo | Valore Maestrale |
|---|---|---|---|
| Cadenza | `GA_Weapon_Fire_Maestrale` | Fire Delay Time Secs | 0,08 |
| Danno | `GE_Damage_Maestrale` | Executions → Calculation Modifiers → (BaseDamage) → Modifier Magnitude → Scalable Float Magnitude | 30 |
| Calo danno | `B_WeaponInstance_Maestrale` | Weapon Config → Distance Damage Falloff → External Curve | `Curve_Maestrale_CaloDanno` |
| Caricatore | `ID_Maestrale` | Fragments → Inventory Fragment Set Stats → Initial Item Stats → MagazineSize e MagazineAmmo | 30 |
| Ricarica | animazione `…Maestrale…Reload` | Rate Scale | durata dell'animazione ÷ 2,2 (il resoconto ti dà il numero) |
| Arma a terra | mappa `L_Convolution_Blockout`, piattaforme del fucile | Weapon Definition | `WeaponPickupData_Maestrale` |

Per un riferimento dentro un grafo, apri il Blueprint, premi **Ctrl+F**, cerca il nome indicato, cambia l'asset nel nodo, poi premi **Compila** e **Salva**.

## Passo 3 – Prova in editor

1. Apri il progetto e avvia una partita Elimination come hai fatto la prima volta.
2. Mentre giochi: *File → Esegui script Python…* → `Python\avanguardia_misura_arma.py`. Le misure compaiono in giallo sullo schermo e nell'Output Log. Riesegui lo script per spegnerlo.
3. Controlla:
   - [ ] l'arma in mano è `B_WeaponInstance_Maestrale` e il caricatore mostra **30**;
   - [ ] tenendo premuto il fuoco, il misuratore dice circa **750 colpi/min** (vedi la nota sulla cadenza qui sotto);
   - [ ] la ricarica: "caricatore pieno dopo" circa **2,2 s**;
   - [ ] un bot da vicino perde **30** a colpo e viene eliminato in **4 colpi** (100 → 70 → 40 → 10 → 0); un colpo alla testa toglie 42;
   - [ ] oltre 45 m il danno scende a **20** (5 colpi per eliminare);
   - [ ] il suono degli spari va a tempo con i colpi.

**Salute dei bot.** In Lyra è 100 per giocatori e bot, come nel documento di design. Il misuratore la stampa all'inizio ("Salute massima dei bot"). Se vedi un valore diverso, mandamelo. Si allinea in uno di due modi: si cambia il valore iniziale dell'attributo `LyraHealthSet` per l'eroe, oppure, se Lyra usa un effetto di inizializzazione, si cambia quello.

## Limiti noti

- **Cadenza legata ai frame.** In Lyra l'abilità di fuoco aspetta `FireDelayTimeSecs`, termina e si riattiva al frame successivo. L'intervallo reale quindi è un po' più lungo: a 60 fps, 0,08 s può diventare circa 0,083–0,1 s (600–720 colpi/min). Il misuratore mostra il valore vero. Per il prototipo si può compensare abbassando un po' il valore. La soluzione pulita è una piccola modifica C++ al ciclo di fuoco, da fare più avanti.
- **Suono.** Il suono a raffica del fucile Lyra ha un suo intervallo (`ShotInterval` nel MetaSound). Se non va a tempo con 750 colpi/min, segnalamelo: si sistema copiando anche il suono.
- **Mira con l'ottica in 0,25 s: rimandata.** In Lyra la mira (`GA_ADS` più la modalità di camera ADS) è la stessa per tutte le armi e non ha un tempo per arma. Si farà insieme al perk Mani Rapide, che deve proprio accelerarla.
- Lyra è in **terza persona**, mentre il documento di design prevede la prima persona: è una scelta da affrontare più avanti.

## Passo 4 – Salva su Git (`03_Salva_Maestrale_su_Git.bat`)

Quando la prova va bene, chiudi l'editor e lancia lo script: mostra i file cambiati e fa il commit con un messaggio che descrive Maestrale.

## Tornare indietro

Prima di qualsiasi commit, puoi annullare tutto quello che ha fatto il passo 2. Chiudi l'editor e, in un terminale aperto in `G:\Progetto_FPS`, esegui:

```powershell
git reset --hard HEAD
git clean -fd "Plugins/GameFeatures/ShooterCore/Content/Weapons/Maestrale"
```

Attenzione: `git reset --hard` cancella **tutte** le modifiche non ancora salvate con un commit, comprese quelle fatte a mano in editor.
