# -*- coding: utf-8 -*-
"""
AVANGUARDIA - crea l'arma "Maestrale" (fucile d'assalto bilanciato) copiando il fucile di Lyra.

COME SI ESEGUE
  - Consigliato, a editor CHIUSO: doppio clic su 02_Crea_Maestrale.bat
    (lancia UnrealEditor-Cmd.exe <progetto> -run=pythonscript -script=<questo file>)
  - Oppure a editor aperto: File > Esegui script Python... > scegli questo file.
    Chiudi prima gli editor degli asset del fucile, se li hai aperti.

COSA FA
  1. Parte da ID_Rifle e segue i riferimenti per trovare tutti gli asset del fucile di Lyra
     (equipaggiamento WID_, istanza dell'arma B_WeaponInstance_, set di abilita', abilita'
     di fuoco e ricarica GA_, effetto di danno GE_, dati del raccoglibile, animazione di ricarica).
  2. Li copia in /ShooterCore/Weapons/Maestrale con "Maestrale" al posto di "Rifle".
     Gli asset originali di Lyra NON vengono modificati.
  3. Fa puntare le copie alle copie (non agli originali).
  4. Imposta le statistiche di Maestrale (vedi CONFIGURAZIONE).
  5. In Elimination sostituisce il fucile di Lyra con Maestrale (inventario iniziale e armi a terra).
  6. Ricontrolla tutto e scrive un resoconto in Saved/Avanguardia/maestrale_report.txt

Si puo' rieseguire: gli asset gia' creati vengono riusati e le statistiche reimpostate
(utile per provare valori diversi). Per ricominciare da zero si torna indietro con Git.
"""

import os
import re
import traceback

import unreal

# =====================================================================================
# CONFIGURAZIONE (valori dal documento di design, fase 1)
# =====================================================================================
NOME_ARMA = "Maestrale"
CARTELLA_ORIGINE = "/ShooterCore/Weapons/Rifle"         # = Plugins/GameFeatures/ShooterCore/Content/Weapons/Rifle
CARTELLA_DESTINAZIONE = "/ShooterCore/Weapons/Maestrale"
NOME_ID_ORIGINE = "ID_Rifle"                             # da qui parte la ricerca

DANNO_VICINO = 30.0          # danno per colpo a breve distanza
DANNO_LONTANO = 20.0         # danno per colpo a lunga distanza
# Il documento non fissa le distanze: valori di partenza da tarare nei playtest.
CALO_INIZIA_CM = 2500.0      # fino a 25 m: danno pieno (30)
CALO_FINISCE_CM = 4500.0     # da 45 m in poi: danno minimo (20); in mezzo scende in modo lineare
MOLTIPLICATORE_TESTA = 1.4   # colpo alla testa x1,4 (sezione "Gameplay di base")

INTERVALLO_COLPI_S = 0.08    # 750 colpi al minuto
CARICATORE = 30              # colpi nel caricatore (le munizioni di riserva restano quelle di Lyra)
RICARICA_S = 2.2             # durata della ricarica

AGGIORNA_INVENTARIO_INIZIALE = True     # sostituisce ID_Rifle con ID_Maestrale dove Lyra da' le armi iniziali
AGGIUNGI_SE_FUCILE_ASSENTE = True       # se l'inventario iniziale non ha il fucile, aggiunge Maestrale
AGGIORNA_ARMI_A_TERRA = True            # sostituisce il fucile sulle piattaforme delle armi...
MAPPE_ELIMINATION = ["L_Convolution_Blockout"]   # ...solo in queste mappe (Elimination di Lyra)
RE_DA_NON_TOCCARE = re.compile(r"test|gym|debug|cheat", re.IGNORECASE)  # asset di prova di Lyra

# =====================================================================================
# RESOCONTO
# =====================================================================================


def _cartella_report():
    try:
        saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    except Exception:
        saved = os.path.join(os.getcwd(), "Saved")
    p = os.path.join(saved, "Avanguardia")
    os.makedirs(p, exist_ok=True)
    return p


CARTELLA_REPORT = _cartella_report()


class Resoconto(object):
    def __init__(self):
        self.righe = []
        self.dettagli = []
        self.conteggi = {}

    def _scrivi(self, etichetta, testo):
        riga = "[%s] %s" % (etichetta, testo) if etichetta else testo
        self.righe.append(riga)
        if etichetta:
            self.conteggi[etichetta] = self.conteggi.get(etichetta, 0) + 1
        if etichetta == "ERRORE":
            unreal.log_error("AVANGUARDIA " + riga)
        elif etichetta in ("AVVISO", "MANUALE"):
            unreal.log_warning("AVANGUARDIA " + riga)
        else:
            unreal.log("AVANGUARDIA " + riga)

    def titolo(self, t):
        self._scrivi("", "")
        self._scrivi("", "=== %s ===" % t)

    def ok(self, t):
        self._scrivi("OK", t)

    def info(self, t):
        self._scrivi("INFO", t)

    def avviso(self, t):
        self._scrivi("AVVISO", t)

    def errore(self, t):
        self._scrivi("ERRORE", t)

    def manuale(self, t):
        self._scrivi("MANUALE", t)

    def dettaglio(self, t):
        self.dettagli.append(t)

    def salva(self):
        percorso = os.path.join(CARTELLA_REPORT, "maestrale_report.txt")
        with open(percorso, "w", encoding="utf-8") as f:
            f.write("\n".join(self.righe))
            f.write("\n\n=== DETTAGLI (proprieta' lette dagli asset, per Claude) ===\n")
            f.write("\n".join(self.dettagli))
            f.write("\n")
        return percorso


R = Resoconto()

# =====================================================================================
# STRUMENTI UNREAL
# =====================================================================================
EAS = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
AR = unreal.AssetRegistryHelpers.get_asset_registry()
ATOOLS = unreal.AssetToolsHelpers.get_asset_tools()
_SENZA = object()


def leggi(o, nome, default=None):
    try:
        return o.get_editor_property(nome)
    except Exception:
        return default


def opzioni_dipendenze():
    o = unreal.AssetRegistryDependencyOptions()
    for n, v in (("include_soft_package_references", True), ("include_hard_package_references", True),
                 ("include_searchable_names", False), ("include_soft_management_references", False),
                 ("include_hard_management_references", False)):
        try:
            o.set_editor_property(n, v)
        except Exception:
            try:
                setattr(o, n, v)
            except Exception:
                pass
    return o


def referenti(pkg):
    try:
        return [str(x) for x in (AR.get_referencers(pkg, opzioni_dipendenze()) or [])]
    except Exception as e:
        R.avviso("Non riesco a leggere chi usa %s: %s" % (pkg, e))
        return []


def dipendenze(pkg):
    try:
        return [str(x) for x in (AR.get_dependencies(pkg, opzioni_dipendenze()) or [])]
    except Exception:
        return []


def classe_asset(ad):
    try:
        return str(ad.asset_class_path.asset_name)
    except Exception:
        try:
            return str(ad.asset_class)
        except Exception:
            return "?"


def dati_pacchetto(pkg):
    try:
        ads = AR.get_assets_by_package_name(pkg) or []
        return ads[0] if len(ads) else None
    except Exception:
        return None


def classe_pacchetto(pkg):
    ad = dati_pacchetto(pkg)
    return classe_asset(ad) if ad else "?"


_cache_cartelle = {}


def assets_in(cartella):
    if cartella not in _cache_cartelle:
        try:
            _cache_cartelle[cartella] = list(AR.get_assets_by_path(cartella, recursive=True) or [])
        except Exception:
            _cache_cartelle[cartella] = []
    return _cache_cartelle[cartella]


def trova_asset_per_nome(nome, radici=("/ShooterCore", "/Game")):
    for radice in radici:
        for ad in assets_in(radice):
            if str(ad.asset_name) == nome:
                return ad
    return None


def nome_da_pkg(pkg):
    return pkg.rsplit("/", 1)[-1]


def pkg_di(obj):
    return obj.get_outermost().get_name()


def classe_bp(asset):
    """Classe generata (..._C) di un Blueprint."""
    p = pkg_di(asset)
    n = nome_da_pkg(p)
    c = None
    try:
        c = unreal.load_object(None, "%s.%s_C" % (p, n))
    except Exception:
        c = None
    if c is None:
        try:
            c = asset.generated_class()
        except Exception:
            c = None
    return c


def cdo_di(asset):
    """Per un Blueprint restituisce l'oggetto di default (CDO), che contiene i valori della classe.
    Per un Data Asset restituisce l'asset stesso."""
    if isinstance(asset, unreal.Blueprint):
        c = classe_bp(asset)
        return unreal.get_default_object(c) if c else None
    return asset


def e_sottoclasse(c, padre):
    try:
        return bool(unreal.MathLibrary.class_is_child_of(c, padre))
    except Exception:
        return False


_RE_PROP_DOC = re.compile(r"^\s*-\s*``(\w+)``\s*\(", re.M)
_cache_nomi = {}
# Proprieta' di Lyra/GAS che servono sempre: si provano anche se non compaiono nella documentazione Python.
_NOMI_NOTI = ["fragments", "equipment_definition", "initial_item_stats", "display_name_when_equipped",
              "display_name", "instance_type", "ability_sets_to_grant", "actors_to_spawn",
              "granted_gameplay_abilities", "granted_gameplay_effects", "distance_damage_falloff",
              "material_damage_multiplier", "max_damage_range", "inventory_item_definition", "executions",
              "weapon_definition", "rate_scale", "blend_time", "fire_delay_time_secs", "reload_montage",
              "initial_inventory_items", "default_pawn_data", "action_sets", "actions"]


def nomi_proprieta(obj):
    """Nomi (stile Python) delle proprieta' modificabili di un oggetto o struct Unreal."""
    t = type(obj)
    if t in _cache_nomi:
        return _cache_nomi[t]
    nomi, visti = [], set()
    for c in getattr(t, "__mro__", (t,)):
        doc = None
        try:
            doc = c.__dict__.get("__doc__")
        except Exception:
            doc = None
        if not isinstance(doc, str):
            doc = getattr(c, "__doc__", None)
        if not isinstance(doc, str):
            continue
        for m in _RE_PROP_DOC.finditer(doc):
            n = m.group(1)
            if n not in visti:
                visti.add(n)
                nomi.append(n)
    for n in dir(t):
        if n.startswith("_") or n in visti:
            continue
        try:
            a = getattr(t, n, None)
        except Exception:
            continue
        if type(a).__name__ in ("getset_descriptor", "member_descriptor", "property"):
            visti.add(n)
            nomi.append(n)
    for n in _NOMI_NOTI:
        if n not in visti:
            visti.add(n)
            nomi.append(n)
    _cache_nomi[t] = nomi
    return nomi


def nome_tag(t):
    if t is None:
        return ""
    try:
        return str(unreal.BlueprintGameplayTagLibrary.get_tag_name(t))
    except Exception:
        pass
    try:
        return str(t.get_editor_property("tag_name"))
    except Exception:
        pass
    try:
        m = re.search(r'TagName="([^"]*)"', t.export_text())
        return m.group(1) if m else ""
    except Exception:
        return str(t)


def breve(v, prof=0):
    try:
        if v is None:
            return "None"
        if isinstance(v, unreal.Object):
            return v.get_path_name()
        if isinstance(v, unreal.Text):
            return '"%s"' % str(v)
        if isinstance(v, unreal.StructBase):
            try:
                t = v.export_text()
            except Exception:
                t = str(v)
            return t if len(t) <= 400 else t[:400] + "..."
        if isinstance(v, unreal.Array):
            el = list(v)
            parti = [breve(x, prof + 1) for x in el[:12]]
            if len(el) > 12:
                parti.append("... (+%d)" % (len(el) - 12))
            return "[" + ", ".join(parti) + "]"
        if isinstance(v, unreal.Map):
            parti = ["%s: %s" % (breve(k, prof + 1), breve(v[k], prof + 1)) for k in list(v.keys())[:12]]
            return "{" + ", ".join(parti) + "}"
        s = repr(v)
        return s if len(s) <= 400 else s[:400] + "..."
    except Exception as e:
        return "<non leggibile: %s>" % e


def dump(obj, titolo):
    if obj is None:
        return
    try:
        R.dettaglio("--- %s: %s (%s)" % (titolo, obj.get_path_name(), obj.get_class().get_name()))
    except Exception:
        R.dettaglio("--- %s" % titolo)
    for n in nomi_proprieta(obj):
        v = leggi(obj, n, _SENZA)
        if v is _SENZA:
            continue
        R.dettaglio("    %s = %s" % (n, breve(v)))


def testo_valore(v):
    """Valore -> testo nel formato di Unreal (per import_text)."""
    if v is None:
        return "None"
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return "%.6f" % v
    if isinstance(v, unreal.Object):
        return '"%s"' % v.get_path_name()
    if isinstance(v, unreal.StructBase):
        return v.export_text()
    if isinstance(v, (unreal.Array, list, tuple)):
        return "(" + ",".join(testo_valore(x) for x in v) + ")"
    raise ValueError("tipo non gestito: %s" % type(v))


def imposta_campo(s, nome_py, nome_cpp, valore):
    """Imposta un campo di una struct. Alcune struct di Lyra/GAS permettono la modifica solo
    "nei default": se set_editor_property rifiuta, si usa l'import di testo di Unreal."""
    try:
        s.set_editor_property(nome_py, valore)
        return s
    except Exception as e1:
        errore1 = e1
    try:
        esito = s.import_text("(%s=%s)" % (nome_cpp, testo_valore(valore)))
    except Exception as e2:
        raise RuntimeError("non riesco a impostare %s (%s / %s)" % (nome_cpp, errore1, e2))
    if esito is False:
        raise RuntimeError("non riesco a impostare %s (%s / import di testo rifiutato)" % (nome_cpp, errore1))
    return s


def compila(bp):
    try:
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        return True
    except Exception as e:
        R.dettaglio("compilazione non riuscita per %s: %s" % (bp.get_name(), e))
        return False


def salva(asset):
    try:
        return bool(EAS.save_loaded_asset(asset, False))
    except Exception as e:
        R.errore("Salvataggio di %s non riuscito: %s" % (asset.get_name(), e))
        return False


# =====================================================================================
# RIMAPPATURA DEI RIFERIMENTI (le copie devono puntare alle copie)
# =====================================================================================
NESSUNO, SUL_POSTO, SOSTITUITO = 0, 1, 2


class Rimappa(object):
    def __init__(self):
        self.oggetti = {}   # percorso originale -> oggetto nuovo
        self.regole = []    # (regex, sostituzione) per i testi
        self.cambi = []
        self.errori = []

    def aggiungi(self, pkg_orig, pkg_nuovo, asset_nuovo):
        n_orig, n_nuovo = nome_da_pkg(pkg_orig), nome_da_pkg(pkg_nuovo)
        self.oggetti["%s.%s" % (pkg_orig, n_orig)] = asset_nuovo
        if isinstance(asset_nuovo, unreal.Blueprint):
            c = classe_bp(asset_nuovo)
            if c:
                self.oggetti["%s.%s_C" % (pkg_orig, n_orig)] = c
        self.regole.append((re.compile(re.escape("%s.Default__%s_C" % (pkg_orig, n_orig))),
                            "%s.Default__%s_C" % (pkg_nuovo, n_nuovo)))
        self.regole.append((re.compile(re.escape("%s.%s_C" % (pkg_orig, n_orig)) + r"(?![\w])"),
                            "%s.%s_C" % (pkg_nuovo, n_nuovo)))
        self.regole.append((re.compile(re.escape("%s.%s" % (pkg_orig, n_orig)) + r"(?![\w])"),
                            "%s.%s" % (pkg_nuovo, n_nuovo)))

    def testo(self, t):
        for rx, sost in self.regole:
            t = rx.sub(sost, t)
        return t


def rimappa_valore(v, rm, radice, visti, prof):
    if v is None:
        return v, NESSUNO
    if isinstance(v, unreal.Object):
        try:
            p = v.get_path_name()
        except Exception:
            return v, NESSUNO
        if p in rm.oggetti:
            return rm.oggetti[p], SOSTITUITO
        if prof < 4 and not isinstance(v, unreal.Class) and p not in visti:
            try:
                fuori = pkg_di(v)
            except Exception:
                fuori = None
            if fuori == radice:   # sotto-oggetto dell'asset stesso (es. i "frammenti" di un ID_)
                visti.add(p)
                if rimappa_oggetto(v, rm, radice, visti, prof + 1):
                    return v, SUL_POSTO
        return v, NESSUNO
    if isinstance(v, unreal.StructBase):
        try:
            t = v.export_text()
        except Exception:
            t = None
        if t is not None:
            nt = rm.testo(t)
            if nt == t:
                return v, NESSUNO
            try:
                if v.import_text(nt) is not False:
                    dopo = v.export_text()
                    if rm.testo(dopo) == dopo:     # nessun riferimento agli originali rimasto
                        return v, SOSTITUITO
            except Exception:
                pass
        # Piano B: campo per campo
        stato = NESSUNO
        for n in nomi_proprieta(v):
            x = leggi(v, n, _SENZA)
            if x is _SENZA:
                continue
            nx, s = rimappa_valore(x, rm, radice, visti, prof + 1)
            if s == SOSTITUITO:
                try:
                    v.set_editor_property(n, nx)
                    stato = SOSTITUITO
                except Exception as e:
                    rm.errori.append("struct %s.%s: %s" % (type(v).__name__, n, e))
        return v, stato
    if isinstance(v, unreal.Array):
        stato = NESSUNO
        for i in range(len(v)):
            nv, s = rimappa_valore(v[i], rm, radice, visti, prof + 1)
            if s == SOSTITUITO:
                v[i] = nv
                stato = SOSTITUITO
            elif s == SUL_POSTO and stato == NESSUNO:
                stato = SUL_POSTO
        return v, stato
    if isinstance(v, unreal.Map):
        stato = NESSUNO
        for k in list(v.keys()):
            nv, s = rimappa_valore(v[k], rm, radice, visti, prof + 1)
            if s == SOSTITUITO:
                v[k] = nv
                stato = SOSTITUITO
            elif s == SUL_POSTO and stato == NESSUNO:
                stato = SUL_POSTO
        return v, stato
    return v, NESSUNO


def rimappa_oggetto(obj, rm, radice, visti=None, prof=0):
    """Sostituisce, nelle proprieta' di obj, i riferimenti agli originali con le copie."""
    if visti is None:
        visti = set()
    cambiato = False
    for n in nomi_proprieta(obj):
        v = leggi(obj, n, _SENZA)
        if v is _SENZA:
            continue
        nv, s = rimappa_valore(v, rm, radice, visti, prof)
        if s == SOSTITUITO:
            try:
                obj.set_editor_property(n, nv)
                cambiato = True
                rm.cambi.append("%s.%s" % (obj.get_name(), n))
            except Exception as e:
                rm.errori.append("%s.%s: %s" % (obj.get_name(), n, e))
        elif s == SUL_POSTO:
            cambiato = True
    return cambiato


def componenti_bp(bp):
    """Modelli dei componenti aggiunti nel pannello Components di un Blueprint."""
    out = []
    try:
        sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
        for h in sds.k2_gather_subobject_data_for_blueprint(bp) or []:
            d = sds.k2_find_subobject_data_from_handle(h)
            if isinstance(d, tuple):
                d = d[-1]
            o = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(d)
            if o is not None and isinstance(o, unreal.ActorComponent):
                out.append(o)
    except Exception as e:
        R.dettaglio("componenti di %s non leggibili: %s" % (bp.get_name(), e))
    return out


# =====================================================================================
# STATO DEL LAVORO
# =====================================================================================
COPIE = {}           # pacchetto originale -> pacchetto copia
RM = Rimappa()


def nuovo_nome(nome):
    if "Rifle" in nome:
        return nome.replace("Rifle", NOME_ARMA)
    return "%s_%s" % (nome, NOME_ARMA)


def copia_di(pkg_orig):
    p = COPIE.get(pkg_orig)
    return EAS.load_asset(p) if p else None


def assicura_copia(pkg_orig, ruolo):
    if pkg_orig in COPIE:
        return copia_di(pkg_orig)
    if pkg_orig.startswith("/Script/"):
        R.errore("%s: %s e' una classe C++, non un asset: non si puo' copiare." % (ruolo, pkg_orig))
        return None
    dest = "%s/%s" % (CARTELLA_DESTINAZIONE, nuovo_nome(nome_da_pkg(pkg_orig)))
    if EAS.does_asset_exist(dest):
        asset = EAS.load_asset(dest)
        R.info("%s: %s esiste gia', la riuso" % (ruolo, nome_da_pkg(dest)))
    else:
        asset = EAS.duplicate_asset(pkg_orig, dest)
        if asset is None:
            R.errore("%s: copia di %s non riuscita" % (ruolo, pkg_orig))
            return None
        R.ok("%s: creato %s (copia di %s)" % (ruolo, nome_da_pkg(dest), nome_da_pkg(pkg_orig)))
    COPIE[pkg_orig] = dest
    RM.aggiungi(pkg_orig, dest, asset)
    return asset


# =====================================================================================
# FASE 1 - SCOPERTA
# =====================================================================================
def scegli_abilita(abilita, parola):
    for c, tag, _s in abilita:
        if parola in tag.lower():
            return c
    for c, tag, _s in abilita:
        if parola in c.get_name().lower():
            return c
    return None


def classi_ge(obj):
    """Proprieta' che contengono una classe di Gameplay Effect (escluse costo e cooldown)."""
    out = []
    padre = unreal.GameplayEffect.static_class()
    for n in nomi_proprieta(obj):
        if re.search(r"cost|cooldown", n, re.I):
            continue
        v = leggi(obj, n, _SENZA)
        if isinstance(v, unreal.Class) and e_sottoclasse(v, padre):
            out.append((n, v))
    return out


def montaggi_ricarica(obj):
    out = []
    if obj is None:
        return out
    for n in nomi_proprieta(obj):
        v = leggi(obj, n, _SENZA)
        if isinstance(v, unreal.AnimMontage) and ("reload" in n.lower() or "reload" in v.get_name().lower()):
            out.append((n, v))
    return out


_RE_TEMPO_RICARICA = re.compile(r"reload.*(time|duration|length)|(time|duration).*reload", re.I)


def tempi_ricarica(obj):
    out = []
    if obj is None:
        return out
    for n in nomi_proprieta(obj):
        if _RE_TEMPO_RICARICA.search(n):
            v = leggi(obj, n, _SENZA)
            if isinstance(v, float):
                out.append((n, v))
    return out


def padre_bp(pkg):
    """Pacchetto del Blueprint genitore (es. GA_Weapon_Fire per GA_Weapon_Fire_Rifle)."""
    ad = dati_pacchetto(pkg)
    if ad is None:
        return None
    for tag in ("ParentClass", "ParentClassPackage"):
        try:
            v = ad.get_tag_value(tag)
            if isinstance(v, tuple):
                v = v[-1]
            for m in re.finditer(r"(/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)+)\.", str(v or "")):
                if not m.group(1).startswith("/Script/"):
                    return m.group(1)
        except Exception:
            pass
    return None


def montaggi_nelle_dipendenze(pkgs):
    out = []
    for p in pkgs:
        if not p:
            continue
        for d in dipendenze(p):
            if classe_pacchetto(d) == "AnimMontage" and "reload" in d.lower():
                out.append(d)
    # preferisci quello del fucile
    out.sort(key=lambda d: 0 if "rifle" in d.lower() else 1)
    return out


def fase_scoperta():
    R.titolo("1. Scopro come Lyra definisce il fucile")
    try:
        R.info("Unreal Engine %s" % unreal.SystemLibrary.get_engine_version())
    except Exception:
        pass
    F = {}

    ad = None
    for ad_ in assets_in(CARTELLA_ORIGINE):
        if str(ad_.asset_name) == NOME_ID_ORIGINE:
            ad = ad_
    if ad is None:
        ad = trova_asset_per_nome(NOME_ID_ORIGINE)
    if ad is None:
        R.errore("Non trovo %s. Le cartelle di ShooterCore sono caricate? Prova a eseguire lo script "
                 "dall'editor (File > Esegui script Python)." % NOME_ID_ORIGINE)
        return None
    F["id"] = str(ad.package_name)
    R.ok("Definizione oggetto: %s" % F["id"])
    R.info("Contenuto di %s: %s" % (CARTELLA_ORIGINE, ", ".join(sorted(
        "%s (%s)" % (a.asset_name, classe_asset(a)) for a in assets_in(CARTELLA_ORIGINE)))))

    id_cdo = cdo_di(EAS.load_asset(F["id"]))
    dump(id_cdo, "ID")
    wid_cls = None
    for fr in leggi(id_cdo, "fragments", []) or []:
        if fr is None:
            continue
        dump(fr, "frammento di ID")
        v = leggi(fr, "equipment_definition")
        if v is not None:
            wid_cls = v
        stats = leggi(fr, "initial_item_stats")
        if stats is not None:
            R.info("Statistiche iniziali del fucile Lyra: " + ", ".join(
                "%s=%s" % (nome_tag(k), stats[k]) for k in stats.keys()))
    if wid_cls is None:
        R.errore("In %s non trovo il frammento con l'equipaggiamento (EquipmentDefinition)." % F["id"])
        return None
    F["wid"] = pkg_di(wid_cls)
    R.ok("Equipaggiamento: %s" % F["wid"])

    wid_cdo = unreal.get_default_object(wid_cls)
    dump(wid_cdo, "WID")
    inst_cls = leggi(wid_cdo, "instance_type")
    if inst_cls is None:
        R.errore("In %s non trovo InstanceType (istanza dell'arma)." % F["wid"])
        return None
    F["istanza"] = pkg_di(inst_cls)
    R.ok("Istanza dell'arma: %s (classe C++ %s)" % (F["istanza"], inst_cls.get_name()))
    inst_cdo = unreal.get_default_object(inst_cls)
    dump(inst_cdo, "Istanza")

    abilita = []
    F["set_tutti"] = []
    for s in list(leggi(wid_cdo, "ability_sets_to_grant", []) or []):
        if s is None:
            continue
        dump(s, "Set di abilita'")
        nel_set = []
        for g in leggi(s, "granted_gameplay_abilities", []) or []:
            c = leggi(g, "ability")
            t = nome_tag(leggi(g, "input_tag"))
            if c is not None:
                abilita.append((c, t, pkg_di(s)))
                nel_set.append(pkg_di(c))
                R.info("Set %s concede %s (tasto %s)" % (s.get_name(), c.get_name(), t or "-"))
        F["set_tutti"].append((pkg_di(s), nel_set))
    fuoco = scegli_abilita(abilita, "fire")
    if fuoco is None:
        R.errore("Non trovo l'abilita' di fuoco nei set di %s." % F["wid"])
        return None
    F["ga_fuoco"] = pkg_di(fuoco)
    R.ok("Abilita' di fuoco: %s" % F["ga_fuoco"])
    fuoco_cdo = unreal.get_default_object(fuoco)
    dump(fuoco_cdo, "GA fuoco")

    ricarica = scegli_abilita(abilita, "reload")
    F["ga_ricarica"] = pkg_di(ricarica) if ricarica else None
    ric_cdo = unreal.get_default_object(ricarica) if ricarica else None
    if ricarica:
        R.ok("Abilita' di ricarica: %s" % F["ga_ricarica"])
        dump(ric_cdo, "GA ricarica")
    else:
        R.avviso("Non trovo l'abilita' di ricarica nei set del fucile (forse e' tra le abilita' dell'eroe).")

    # Effetto di danno
    F["ge_danno"], F["ge_in_proprieta"] = None, False
    candidati = [("GA fuoco", n, c) for n, c in classi_ge(fuoco_cdo)] + \
                [("Istanza", n, c) for n, c in classi_ge(inst_cdo)]
    candidati.sort(key=lambda x: 0 if "damage" in x[2].get_name().lower() else 1)
    for dove, n, c in candidati:
        R.info("Effetto trovato in %s, proprieta' %s: %s" % (dove, n, c.get_name()))
    if candidati:
        F["ge_danno"], F["ge_in_proprieta"] = pkg_di(candidati[0][2]), True
    else:
        for p in (F["ga_fuoco"], padre_bp(F["ga_fuoco"])):
            if not p:
                continue
            for d in dipendenze(p):
                if "damage" in nome_da_pkg(d).lower() and nome_da_pkg(d).startswith("GE_"):
                    F["ge_danno"] = d
                    break
            if F["ge_danno"]:
                break
    if F["ge_danno"]:
        R.ok("Effetto di danno: %s" % F["ge_danno"])
        dump(cdo_di(EAS.load_asset(F["ge_danno"])), "GE danno")
    else:
        R.errore("Non trovo l'effetto di danno (GE_...) usato dall'abilita' di fuoco.")

    # Ricarica: dove sta l'animazione (montage) o il tempo?
    F["montaggio"], F["montaggio_dove"], F["montaggio_prop"] = None, None, None
    F["tempo_ricarica_dove"] = None
    m_inst, m_ga = montaggi_ricarica(inst_cdo), montaggi_ricarica(ric_cdo)
    t_inst, t_ga = tempi_ricarica(inst_cdo), tempi_ricarica(ric_cdo)
    if t_inst:
        F["tempo_ricarica_dove"] = ("istanza", t_inst)
    elif t_ga:
        F["tempo_ricarica_dove"] = ("ga_ricarica", t_ga)
    if m_inst:
        F["montaggio_dove"], F["montaggio_prop"], m = "istanza", m_inst[0][0], m_inst[0][1]
        F["montaggio"] = pkg_di(m)
    elif m_ga:
        F["montaggio_dove"], F["montaggio_prop"], m = "ga_ricarica", m_ga[0][0], m_ga[0][1]
        F["montaggio"] = pkg_di(m)
    elif F["ga_ricarica"]:
        dal_grafo = montaggi_nelle_dipendenze([F["ga_ricarica"], padre_bp(F["ga_ricarica"]), F["istanza"]])
        if dal_grafo:
            F["montaggio_dove"], F["montaggio"] = "grafo", dal_grafo[0]
    if F["montaggio"]:
        R.ok("Animazione di ricarica: %s (riferita da: %s%s)" % (
            F["montaggio"], F["montaggio_dove"], ", proprieta' " + F["montaggio_prop"] if F["montaggio_prop"] else ""))
    elif not F["tempo_ricarica_dove"]:
        R.avviso("Non trovo ne' l'animazione ne' un tempo di ricarica: la ricarica restera' quella di Lyra.")
    if F["tempo_ricarica_dove"]:
        R.info("Tempo di ricarica trovato in %s: %s" % F["tempo_ricarica_dove"])

    nome_ric = (nome_da_pkg(F["ga_ricarica"]) if F["ga_ricarica"] else "").lower()
    F["copia_ga_ricarica"] = bool(F["ga_ricarica"]) and (
        F["montaggio_dove"] == "ga_ricarica"
        or (F["tempo_ricarica_dove"] or ("",))[0] == "ga_ricarica"
        or (F["montaggio_dove"] == "grafo" and "rifle" in nome_ric))

    # Raccoglibili (piattaforme delle armi) che danno il fucile
    F["pickup"] = []
    for ref in referenti(F["id"]):
        cl = classe_pacchetto(ref)
        if "pickup" in cl.lower() or "pickup" in nome_da_pkg(ref).lower():
            if not RE_DA_NON_TOCCARE.search(ref):
                F["pickup"].append(ref)
                dump(EAS.load_asset(ref), "Raccoglibile")
    R.info("Dati delle armi a terra con il fucile: %s" % (", ".join(F["pickup"]) or "nessuno"))
    return F


def fase_info_extra():
    """Solo lettura: informazioni utili per i prossimi passi (mira, esperienza Elimination)."""
    R.titolo("Informazioni per i prossimi passi (solo lettura)")
    for radice in ("/ShooterCore", "/Game"):
        for ad in assets_in(radice):
            n = str(ad.asset_name)
            if re.match(r"(GA_.*ADS|CM_.*ADS)", n):
                try:
                    o = cdo_di(EAS.load_asset(str(ad.package_name)))
                    bt = leggi(o, "blend_time", None)
                    R.info("Mira: %s%s" % (ad.package_name, "  (BlendTime=%.2f s)" % bt if isinstance(bt, float) else ""))
                    dump(o, "Mira")
                except Exception:
                    pass
            if re.search(r"Elimination", n) and classe_asset(ad) in ("Blueprint", "LyraExperienceDefinition"):
                R.info("Esperienza: %s" % ad.package_name)
                try:
                    dump(cdo_di(EAS.load_asset(str(ad.package_name))), "Esperienza")
                except Exception:
                    pass


# =====================================================================================
# FASE 2 - COPIE
# =====================================================================================
def fase_copie(F):
    R.titolo("2. Creo le copie in %s" % CARTELLA_DESTINAZIONE)
    if not EAS.does_directory_exist(CARTELLA_DESTINAZIONE):
        EAS.make_directory(CARTELLA_DESTINAZIONE)

    elenco = [("Definizione oggetto", F["id"]), ("Equipaggiamento", F["wid"]),
              ("Istanza dell'arma", F["istanza"]), ("Abilita' di fuoco", F["ga_fuoco"])]
    if F.get("ge_danno"):
        elenco.append(("Effetto di danno", F["ge_danno"]))
    if F.get("copia_ga_ricarica"):
        elenco.append(("Abilita' di ricarica", F["ga_ricarica"]))
    if F.get("montaggio"):
        elenco.append(("Animazione di ricarica", F["montaggio"]))
    for p in F.get("pickup", []):
        elenco.append(("Arma a terra (dati)", p))
    for ruolo, p in elenco:
        assicura_copia(p, ruolo)

    # Set di abilita': si copiano quelli che contengono abilita' copiate.
    # Le altre abilita' di quei set che usano un'abilita' copiata (es. ricarica automatica) si copiano a loro volta.
    cambiato = True
    while cambiato:
        cambiato = False
        for set_pkg, abilita in F["set_tutti"]:
            if not any(a in COPIE for a in abilita):
                continue
            if set_pkg not in COPIE:
                assicura_copia(set_pkg, "Set di abilita'")
                cambiato = True
            for a in abilita:
                if a in COPIE:
                    continue
                if any(d in COPIE for d in dipendenze(a)):
                    assicura_copia(a, "Abilita' collegata")
                    cambiato = True
    for set_pkg, abilita in F["set_tutti"]:
        if set_pkg not in COPIE:
            R.info("Set %s lasciato condiviso (non contiene abilita' da cambiare)" % nome_da_pkg(set_pkg))


def fase_curva():
    R.titolo("3. Curva del calo di danno con la distanza")
    nome = "Curve_%s_CaloDanno" % NOME_ARMA
    rapporto = DANNO_LONTANO / DANNO_VICINO
    csv = os.path.join(CARTELLA_REPORT, nome + ".csv")
    with open(csv, "w", newline="") as f:
        f.write("0,1.0\n%.1f,1.0\n%.1f,%.6f\n" % (CALO_INIZIA_CM, CALO_FINISCE_CM, rapporto))
    try:
        tipo = None
        for n in dir(unreal.CSVImportType):
            if "CURVE_FLOAT" in n.upper():
                tipo = getattr(unreal.CSVImportType, n)
        impost = unreal.CSVImportSettings()
        impost.set_editor_property("import_type", tipo)
        fabbrica = unreal.CSVImportFactory()
        fabbrica.set_editor_property("automated_import_settings", impost)
        task = unreal.AssetImportTask()
        for k, v in (("filename", csv), ("destination_path", CARTELLA_DESTINAZIONE), ("destination_name", nome),
                     ("replace_existing", True), ("automated", True), ("save", True), ("factory", fabbrica)):
            task.set_editor_property(k, v)
        ATOOLS.import_asset_tasks([task])
    except Exception as e:
        R.errore("Importazione della curva non riuscita: %s" % e)
    curva = EAS.load_asset("%s/%s" % (CARTELLA_DESTINAZIONE, nome))
    if not isinstance(curva, unreal.CurveFloat):
        R.errore("La curva %s non e' stata creata." % nome)
        return None
    try:
        valori = ["%d m -> %.1f" % (d / 100, DANNO_VICINO * curva.get_float_value(d))
                  for d in (0.0, CALO_INIZIA_CM, (CALO_INIZIA_CM + CALO_FINISCE_CM) / 2, CALO_FINISCE_CM, 10000.0)]
        R.ok("Curva %s creata. Danno per colpo: %s" % (nome, "; ".join(valori)))
    except Exception:
        R.ok("Curva %s creata" % nome)
    return curva


# =====================================================================================
# FASE 4 - RIFERIMENTI E STATISTICHE
# =====================================================================================
def fase_rimappa():
    R.titolo("4. Faccio puntare le copie alle copie")
    for orig, nuovo in sorted(COPIE.items()):
        a = EAS.load_asset(nuovo)
        bersaglio = cdo_di(a)
        if bersaglio is None:
            R.errore("Non riesco a leggere %s" % nuovo)
            continue
        prima = len(RM.cambi)
        rimappa_oggetto(bersaglio, RM, pkg_di(bersaglio))
        nuovi = RM.cambi[prima:]
        if nuovi:
            R.ok("%s: riferimenti aggiornati (%s)" % (nome_da_pkg(nuovo), ", ".join(sorted(set(nuovi)))))
    for e in RM.errori:
        R.avviso("Riferimento non aggiornato: %s" % e)


def imposta_float(obj, prop, valore, descrizione):
    vecchio = leggi(obj, prop)
    try:
        obj.set_editor_property(prop, float(valore))
        R.ok("%s: %s -> %s" % (descrizione, vecchio, valore))
        return True
    except Exception as e:
        R.errore("%s: impossibile impostare %s (%s)" % (descrizione, prop, e))
        return False


def statistiche_id(F):
    cdo = cdo_di(copia_di(F["id"]))
    trovato = False
    for fr in leggi(cdo, "fragments", []) or []:
        if fr is None:
            continue
        stats = leggi(fr, "initial_item_stats")
        if stats is not None:
            trovato = True
            cambi = []
            for k in list(stats.keys()):
                n = nome_tag(k)
                if n.endswith("MagazineSize") or n.endswith("MagazineAmmo"):
                    cambi.append("%s %s -> %d" % (n.rsplit(".", 1)[-1], stats[k], CARICATORE))
                    stats[k] = CARICATORE
                elif n.endswith("SpareAmmo"):
                    R.info("Munizioni di riserva: %s (come il fucile Lyra)" % stats[k])
            if cambi:
                try:
                    fr.set_editor_property("initial_item_stats", stats)
                    R.ok("Caricatore: " + "; ".join(cambi))
                except Exception as e:
                    R.errore("Caricatore non impostato: %s" % e)
            else:
                R.errore("Nelle statistiche dell'oggetto non trovo MagazineSize/MagazineAmmo.")
        for prop in ("display_name_when_equipped", "display_name"):
            if leggi(fr, prop, _SENZA) is not _SENZA:
                try:
                    fr.set_editor_property(prop, unreal.Text(NOME_ARMA))
                    R.ok("Nome mostrato (%s): %s" % (prop, NOME_ARMA))
                except Exception as e:
                    R.avviso("Nome %s non impostato: %s" % (prop, e))
    if not trovato:
        R.errore("Non trovo il frammento con le statistiche (InventoryFragment_SetStats) in %s." % COPIE[F["id"]])


def statistiche_istanza(F, curva):
    cdo = cdo_di(copia_di(F["istanza"]))
    if curva is not None:
        try:
            dd = cdo.get_editor_property("distance_damage_falloff")
            try:
                dd.set_editor_property("external_curve", curva)
            except Exception:
                dd.import_text('(ExternalCurve="%s")' % curva.get_path_name())
            cdo.set_editor_property("distance_damage_falloff", dd)
            R.ok("Calo del danno con la distanza: usa %s" % curva.get_name())
        except Exception as e:
            R.errore("Calo del danno non impostato (%s)." % e)
            R.manuale("Apri B_WeaponInstance_%s > Distance Damage Falloff > External Curve = %s"
                      % (NOME_ARMA, curva.get_name()))
    mdm = leggi(cdo, "material_damage_multiplier")
    if mdm is not None:
        cambi = []
        for k in list(mdm.keys()):
            n = nome_tag(k)
            if re.search(r"weak.?spot|head", n, re.I):
                cambi.append("%s %s -> %s" % (n, mdm[k], MOLTIPLICATORE_TESTA))
                mdm[k] = MOLTIPLICATORE_TESTA
        if cambi:
            try:
                cdo.set_editor_property("material_damage_multiplier", mdm)
                R.ok("Colpo alla testa: " + "; ".join(cambi))
            except Exception as e:
                R.avviso("Moltiplicatore testa non impostato: %s" % e)
        else:
            R.info("Moltiplicatori per zona colpita del fucile Lyra: %s (lasciati invariati)" % breve(mdm))


def statistiche_fuoco(F):
    cdo = cdo_di(copia_di(F["ga_fuoco"]))
    rx = re.compile(r"fire.*(delay|interval|rate)|(delay|interval).*(fire|shot)|time_?between|refire", re.I)
    trovati = []
    for n in nomi_proprieta(cdo):
        if rx.search(n) and isinstance(leggi(cdo, n, _SENZA), float):
            trovati.append(n)
    if trovati:
        for n in trovati:
            imposta_float(cdo, n, INTERVALLO_COLPI_S, "Cadenza (%s)" % n)
    else:
        decimali = ["%s=%s" % (n, leggi(cdo, n)) for n in nomi_proprieta(cdo) if isinstance(leggi(cdo, n, _SENZA), float)]
        R.errore("Non trovo la variabile della cadenza nell'abilita' di fuoco. Numeri presenti: %s" % ", ".join(decimali))
        R.manuale("Apri GA_Weapon_Fire_%s > Class Defaults e cerca il tempo tra un colpo e l'altro: mettilo a %.2f"
                  % (NOME_ARMA, INTERVALLO_COLPI_S))
    for n in nomi_proprieta(cdo):
        if re.fullmatch(r"(base_?)?damage", n, re.I) and isinstance(leggi(cdo, n, _SENZA), float):
            imposta_float(cdo, n, DANNO_VICINO, "Danno nell'abilita' (%s)" % n)


def statistiche_danno(F):
    if not F.get("ge_danno"):
        return
    cdo = cdo_di(copia_di(F["ge_danno"]))
    try:
        esecuzioni = cdo.get_editor_property("executions")
    except Exception as e:
        R.errore("Non leggo le Executions dell'effetto di danno: %s" % e)
        return
    trovati = 0
    for i in range(len(esecuzioni)):
        ex = esecuzioni[i]
        mods = leggi(ex, "calculation_modifiers", None)
        if mods is None:
            continue
        for j in range(len(mods)):
            m = mods[j]
            try:
                testo = m.export_text()
            except Exception:
                testo = ""
            if "BaseDamage" not in testo:
                continue
            try:
                mag = m.get_editor_property("modifier_magnitude")
                sf = mag.get_editor_property("scalable_float_magnitude")
                vecchio = leggi(sf, "value")
                sf = imposta_campo(sf, "value", "Value", float(DANNO_VICINO))
                testo_sf = sf.export_text()
                if "CurveTable=None" not in testo_sf and "CurveTable=" in testo_sf:
                    sf.import_text('(Curve=(CurveTable=None,RowName="None"))')
                    R.avviso("Il danno del fucile usava una tabella di curve: rimossa sulla copia.")
                mag = imposta_campo(mag, "scalable_float_magnitude", "ScalableFloatMagnitude", sf)
                if "MagnitudeCalculationType=ScalableFloat" not in mag.export_text():
                    R.avviso("Il danno non e' un valore fisso (ScalableFloat): controlla il resoconto dettagliato.")
                m = imposta_campo(m, "modifier_magnitude", "ModifierMagnitude", mag)
                mods[j] = m
                trovati += 1
                R.ok("Danno base: %s -> %s" % (vecchio, DANNO_VICINO))
            except Exception as e:
                R.errore("Danno base non impostato: %s" % e)
        try:
            ex = imposta_campo(ex, "calculation_modifiers", "CalculationModifiers", mods)
            esecuzioni[i] = ex
        except Exception as e:
            R.errore("Danno base non salvato nella struttura: %s" % e)
    if trovati:
        try:
            cdo.set_editor_property("executions", esecuzioni)
        except Exception as e:
            R.errore("Executions non aggiornate: %s" % e)
    else:
        R.errore("Nell'effetto di danno non trovo il modificatore BaseDamage.")
        R.manuale("Apri GE_Damage_%s > Executions > Calculation Modifiers (BaseDamage) > Scalable Float Magnitude = %d"
                  % (NOME_ARMA, DANNO_VICINO))


def durata_montaggio(m):
    for f in (lambda: m.get_play_length(),
              lambda: unreal.AnimationLibrary.get_sequence_length(m),
              lambda: m.get_editor_property("sequence_length")):
        try:
            v = float(f())
            if v > 0:
                return v
        except Exception:
            pass
    return None


def statistiche_ricarica(F):
    fatto = False
    if F.get("montaggio") and F["montaggio"] in COPIE:
        m = copia_di(F["montaggio"])
        durata = durata_montaggio(m)
        vecchia_vel = leggi(m, "rate_scale", 1.0) or 1.0
        if durata:
            nuova_vel = durata / RICARICA_S
            try:
                m.set_editor_property("rate_scale", nuova_vel)
                R.ok("Ricarica: animazione %.2f s, velocita' %.2f -> %.3f = circa %.2f s (Lyra: circa %.2f s)"
                     % (durata, vecchia_vel, nuova_vel, RICARICA_S, durata / vecchia_vel))
                fatto = True
            except Exception as e:
                R.errore("Velocita' dell'animazione non impostata: %s" % e)
        else:
            R.errore("Non riesco a leggere la durata dell'animazione di ricarica.")
        dove, prop = F.get("montaggio_dove"), F.get("montaggio_prop")
        proprietario = None
        if dove == "istanza":
            proprietario = cdo_di(copia_di(F["istanza"]))
        elif dove == "ga_ricarica" and F["ga_ricarica"] in COPIE:
            proprietario = cdo_di(copia_di(F["ga_ricarica"]))
        if proprietario is not None and prop:
            try:
                proprietario.set_editor_property(prop, m)
                R.ok("L'arma usa l'animazione %s" % m.get_name())
            except Exception as e:
                R.errore("Animazione non collegata: %s" % e)
        elif dove == "grafo":
            if F["ga_ricarica"] in COPIE:
                R.manuale("Apri %s > Event Graph > nodo 'Play Montage and Wait' > Montage To Play: scegli %s, "
                          "poi Compila e Salva." % (nome_da_pkg(COPIE[F["ga_ricarica"]]), m.get_name()))
            else:
                R.manuale("L'abilita' di ricarica %s e' condivisa da tutte le armi e sceglie l'animazione nel grafo: "
                          "manda il resoconto a Claude per decidere come collegare %s senza toccare le altre armi."
                          % (nome_da_pkg(F["ga_ricarica"]), m.get_name()))
    tr = F.get("tempo_ricarica_dove")
    if tr:
        dove, props = tr
        pkg = F["istanza"] if dove == "istanza" else F["ga_ricarica"]
        if pkg in COPIE:
            cdo = cdo_di(copia_di(pkg))
            for n, _v in props:
                imposta_float(cdo, n, RICARICA_S, "Tempo di ricarica (%s)" % n)
                fatto = True
    if not fatto:
        R.manuale("Ricarica non impostata automaticamente: manda il resoconto a Claude.")


def fase_statistiche(F, curva):
    R.titolo("5. Imposto le statistiche di %s" % NOME_ARMA)
    for nome, funz in (("caricatore", lambda: statistiche_id(F)),
                       ("istanza", lambda: statistiche_istanza(F, curva)),
                       ("cadenza", lambda: statistiche_fuoco(F)),
                       ("danno", lambda: statistiche_danno(F)),
                       ("ricarica", lambda: statistiche_ricarica(F))):
        try:
            funz()
        except Exception:
            R.errore("Errore imprevisto (%s): %s" % (nome, traceback.format_exc()))
    R.info("Mira con l'ottica 0,25 s: RIMANDATA. In Lyra la mira (GA_ADS + modalita' camera) e' comune a "
           "tutte le armi e non ha un tempo per arma: si fara' insieme al perk Mani Rapide.")


def fase_compila_salva():
    R.titolo("6. Compilo e salvo le copie")
    for orig, nuovo in sorted(COPIE.items()):
        a = EAS.load_asset(nuovo)
        if isinstance(a, unreal.Blueprint):
            compila(a)
        if salva(a):
            R.ok("Salvato %s" % nome_da_pkg(nuovo))
    curva = EAS.load_asset("%s/Curve_%s_CaloDanno" % (CARTELLA_DESTINAZIONE, NOME_ARMA))
    if curva is not None:
        salva(curva)


# =====================================================================================
# FASE 7 - VERIFICA
# =====================================================================================
def verifica_uguale(descr, valore, atteso, tolleranza=0.001):
    try:
        ok = abs(float(valore) - float(atteso)) <= tolleranza
    except Exception:
        ok = (valore == atteso)
    (R.ok if ok else R.errore)("Verifica %s: %s (atteso %s)" % (descr, valore, atteso))


def verifica_punta(descr, valore, pkg_atteso):
    p = ""
    try:
        p = valore.get_path_name() if valore is not None else "None"
    except Exception:
        p = str(valore)
    ok = p.startswith(pkg_atteso + ".")
    (R.ok if ok else R.errore)("Verifica %s -> %s" % (descr, p))


def fase_verifica(F):
    R.titolo("7. Ricontrollo i valori salvati")
    try:
        id_cdo = cdo_di(copia_di(F["id"]))
        for fr in leggi(id_cdo, "fragments", []) or []:
            if fr is None:
                continue
            v = leggi(fr, "equipment_definition", _SENZA)
            if v is not _SENZA:
                verifica_punta("ID -> equipaggiamento", v, COPIE[F["wid"]])
            stats = leggi(fr, "initial_item_stats")
            if stats is not None:
                for k in stats.keys():
                    if nome_tag(k).endswith(("MagazineSize", "MagazineAmmo")):
                        verifica_uguale("caricatore %s" % nome_tag(k).rsplit(".", 1)[-1], stats[k], CARICATORE)
        wid_cdo = cdo_di(copia_di(F["wid"]))
        verifica_punta("equipaggiamento -> istanza", leggi(wid_cdo, "instance_type"), COPIE[F["istanza"]])
        for s in leggi(wid_cdo, "ability_sets_to_grant", []) or []:
            if s is not None and pkg_di(s) in COPIE.values():
                for g in leggi(s, "granted_gameplay_abilities", []) or []:
                    c = leggi(g, "ability")
                    if c is not None and ("fire" in c.get_name().lower() or "reload" in c.get_name().lower()):
                        R.info("Set %s -> %s" % (s.get_name(), c.get_path_name()))
                        if "fire" in c.get_name().lower():
                            verifica_punta("set -> abilita' di fuoco", c, COPIE[F["ga_fuoco"]])
            elif s is not None:
                R.info("Set condiviso: %s" % s.get_path_name())
        inst_cdo = cdo_di(copia_di(F["istanza"]))
        dd = leggi(inst_cdo, "distance_damage_falloff")
        ec = leggi(dd, "external_curve") if dd is not None else None
        R.info("Curva di calo del danno: %s" % (ec.get_path_name() if ec else "nessuna"))
        if ec is not None:
            for dist in (500.0, CALO_INIZIA_CM, CALO_FINISCE_CM, 8000.0):
                atteso = DANNO_VICINO if dist <= CALO_INIZIA_CM else DANNO_LONTANO if dist >= CALO_FINISCE_CM else None
                if atteso is not None:
                    verifica_uguale("danno a %d m" % (dist / 100), DANNO_VICINO * ec.get_float_value(dist), atteso, 0.05)
        fuoco_cdo = cdo_di(copia_di(F["ga_fuoco"]))
        for n in nomi_proprieta(fuoco_cdo):
            if re.search(r"fire.*(delay|interval|rate)|(delay|interval).*(fire|shot)", n, re.I) and \
                    isinstance(leggi(fuoco_cdo, n, _SENZA), float):
                verifica_uguale("cadenza %s" % n, leggi(fuoco_cdo, n), INTERVALLO_COLPI_S)
        if F.get("ge_danno") and F.get("ge_in_proprieta"):
            for n, c in classi_ge(fuoco_cdo) + classi_ge(inst_cdo):
                if "damage" in c.get_name().lower():
                    verifica_punta("abilita' di fuoco -> effetto di danno (%s)" % n, c, COPIE[F["ge_danno"]])
        if F.get("ge_danno"):
            ge_cdo = cdo_di(copia_di(F["ge_danno"]))
            testo = ""
            for ex in leggi(ge_cdo, "executions", []) or []:
                try:
                    testo += ex.export_text()
                except Exception:
                    pass
            m = re.search(r"BaseDamage.*?ScalableFloatMagnitude=\(Value=([0-9.]+)", testo)
            if m:
                verifica_uguale("danno base", float(m.group(1)), DANNO_VICINO)
            else:
                R.avviso("Non riesco a rileggere il danno base (vedi dettagli).")
        if F.get("montaggio") in COPIE:
            m = copia_di(F["montaggio"])
            d = durata_montaggio(m)
            v = leggi(m, "rate_scale", 1.0) or 1.0
            if d:
                verifica_uguale("durata ricarica (s)", round(d / v, 3), RICARICA_S, 0.01)
        for p in F.get("pickup", []):
            pk = copia_di(p)
            for n in nomi_proprieta(pk):
                v = leggi(pk, n, _SENZA)
                if isinstance(v, unreal.Class) and "ID_" in v.get_name():
                    verifica_punta("arma a terra -> oggetto", v, COPIE[F["id"]])
    except Exception:
        R.errore("Errore durante la verifica: %s" % traceback.format_exc())

    # Riferimenti rimasti agli originali (per esempio dentro i grafi dei Blueprint)
    try:
        AR.scan_paths_synchronous([CARTELLA_DESTINAZIONE], True)
    except Exception:
        pass
    rimasti = 0
    for orig, nuovo in sorted(COPIE.items()):
        for d in dipendenze(nuovo):
            if d in COPIE:
                rimasti += 1
                R.manuale("%s usa ancora l'originale %s (probabilmente in un nodo del grafo). Aprilo, cerca %s "
                          "(Ctrl+F) e sostituiscilo con %s, poi Compila e Salva."
                          % (nome_da_pkg(nuovo), nome_da_pkg(d), nome_da_pkg(d), nome_da_pkg(COPIE[d])))
    if not rimasti:
        R.ok("Nessuna copia usa piu' gli asset originali del fucile")


# =====================================================================================
# FASE 8 - ELIMINATION: INVENTARIO INIZIALE E ARMI A TERRA
# =====================================================================================
def rimappa_asset_esterno(pkg, rm):
    asset = EAS.load_asset(pkg)
    if asset is None:
        return False
    bersaglio = cdo_di(asset)
    cambiato = rimappa_oggetto(bersaglio, rm, pkg_di(bersaglio)) if bersaglio is not None else False
    if isinstance(asset, unreal.Blueprint):
        for comp in componenti_bp(asset):
            cambiato = rimappa_oggetto(comp, rm, pkg_di(comp)) or cambiato
    if cambiato:
        if isinstance(asset, unreal.Blueprint):
            compila(asset)
        salva(asset)
    return cambiato


def fase_inventario(F):
    R.titolo("8. Elimination: inventario iniziale")
    id_nuovo = copia_di(F["id"])
    rm_id = Rimappa()
    rm_id.aggiungi(F["id"], COPIE[F["id"]], id_nuovo)
    esclusi = set(COPIE.keys()) | set(COPIE.values()) | set(F.get("pickup", []))
    candidati = []
    for ref in referenti(F["id"]):
        if ref in esclusi or ref.startswith(CARTELLA_ORIGINE + "/") or ref.startswith(CARTELLA_DESTINAZIONE + "/"):
            continue
        candidati.append(ref)
    R.info("Altri asset che usano %s: %s" % (NOME_ID_ORIGINE, ", ".join(candidati) or "nessuno"))
    modificati = 0
    non_risolti = []
    for ref in candidati:
        cl = classe_pacchetto(ref)
        if RE_DA_NON_TOCCARE.search(ref):
            R.info("Salto %s (asset di prova di Lyra)" % ref)
            continue
        if cl == "World" or "__ExternalActors__" in ref:
            R.info("Salto %s (mappa: vedi passo 9)" % ref)
            continue
        try:
            if rimappa_asset_esterno(ref, rm_id):
                modificati += 1
                R.ok("%s: il fucile Lyra e' stato sostituito con %s" % (ref, nome_da_pkg(COPIE[F["id"]])))
            else:
                non_risolti.append(ref)
                R.info("%s usa %s ma non in una proprieta' modificabile (forse in un nodo del grafo)"
                       % (ref, NOME_ID_ORIGINE))
        except Exception:
            R.errore("Errore su %s: %s" % (ref, traceback.format_exc()))
    for e in rm_id.errori:
        R.errore("Inventario: %s" % e)

    if modificati:
        return
    gia = [ref for ref in referenti(COPIE[F["id"]])
           if not ref.startswith(CARTELLA_DESTINAZIONE + "/") and not RE_DA_NON_TOCCARE.search(ref)
           and classe_pacchetto(ref) != "World" and "__ExternalActors__" not in ref]
    if gia:
        R.ok("%s e' gia' nell'inventario iniziale (%s)" % (nome_da_pkg(COPIE[F["id"]]), ", ".join(gia)))
        return
    if not AGGIUNGI_SE_FUCILE_ASSENTE:
        R.manuale("Il fucile non e' stato sostituito nell'inventario iniziale. Asset da guardare: %s"
                  % (", ".join(non_risolti) or "nessuno trovato"))
        return
    # Il fucile non e' nell'inventario iniziale: aggiungo Maestrale dove Lyra mette la pistola.
    ad_pistola = trova_asset_per_nome("ID_Pistol")
    if ad_pistola is None:
        R.manuale("Non trovo dove Lyra assegna le armi iniziali: manda il resoconto a Claude.")
        return
    pkg_pistola = str(ad_pistola.package_name)
    classe_pistola = "%s.%s_C" % (pkg_pistola, nome_da_pkg(pkg_pistola))
    classe_nuova = classe_bp(id_nuovo)
    aggiunto = False
    for ref in referenti(pkg_pistola):
        if RE_DA_NON_TOCCARE.search(ref) or "/Weapons/" in ref or classe_pacchetto(ref) == "World":
            continue
        asset = EAS.load_asset(ref)
        bersagli = [cdo_di(asset)] + (componenti_bp(asset) if isinstance(asset, unreal.Blueprint) else [])
        for b in bersagli:
            if b is None:
                continue
            for n in nomi_proprieta(b):
                v = leggi(b, n, _SENZA)
                if not isinstance(v, unreal.Array):
                    continue
                percorsi = [x.get_path_name() if isinstance(x, unreal.Object) else "" for x in v]
                if classe_pistola in percorsi and classe_nuova.get_path_name() not in percorsi:
                    try:
                        v.insert(0, classe_nuova)
                    except Exception:
                        v.append(classe_nuova)
                    try:
                        b.set_editor_property(n, v)
                        aggiunto = True
                        R.ok("%s.%s: aggiunto ID_%s alle armi iniziali" % (ref, n, NOME_ARMA))
                    except Exception as e:
                        R.errore("Non riesco ad aggiungere Maestrale a %s.%s: %s" % (ref, n, e))
        if aggiunto:
            if isinstance(asset, unreal.Blueprint):
                compila(asset)
            salva(asset)
            break
    if not aggiunto:
        R.manuale("Non trovo un elenco di armi iniziali modificabile da script. Asset che usano il fucile: %s. "
                  "Manda il resoconto a Claude: ti dira' quale nodo cambiare." % (", ".join(non_risolti) or "nessuno"))


def fase_mappe(F):
    R.titolo("9. Elimination: armi a terra")
    mappe = set()
    for p in F.get("pickup", []) + [F["id"]]:
        for ref in referenti(p):
            if "__ExternalActors__" in ref:
                for nome in MAPPE_ELIMINATION:
                    if "/%s/" % nome in ref:
                        ad = trova_asset_per_nome(nome, ("/ShooterMaps", "/ShooterCore", "/Game"))
                        if ad is not None:
                            mappe.add(str(ad.package_name))
            elif classe_pacchetto(ref) == "World":
                mappe.add(ref)
    R.info("Mappe con piattaforme del fucile: %s" % (", ".join(sorted(mappe)) or "nessuna"))
    gia = set()
    for p in F.get("pickup", []):
        if p in COPIE:
            for ref in referenti(COPIE[p]):
                if classe_pacchetto(ref) == "World":
                    gia.add(nome_da_pkg(ref))
    if gia:
        R.ok("Mappe che danno gia' %s: %s" % (NOME_ARMA, ", ".join(sorted(gia))))
    da_fare = [m for m in sorted(mappe) if nome_da_pkg(m) in MAPPE_ELIMINATION]
    for m in sorted(mappe):
        if m not in da_fare:
            R.info("Lascio invariata %s (non e' una mappa di Elimination)" % m)
    if not da_fare:
        return
    try:
        les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        eas_att = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    except Exception as e:
        R.manuale("Non posso aprire le mappe da script (%s). Apri %s, seleziona le piattaforme del fucile e "
                  "imposta Weapon Definition = WeaponPickupData_%s." % (e, ", ".join(da_fare), NOME_ARMA))
        return
    for mappa in da_fare:
        try:
            if not les.load_level(mappa):
                raise RuntimeError("load_level ha restituito False")
            n = 0
            for a in eas_att.get_all_level_actors() or []:
                if not re.search(r"spawner|pickup|weapon|pad", a.get_class().get_name(), re.I):
                    continue
                prima = len(RM.cambi)
                if rimappa_oggetto(a, RM, pkg_di(a), None, 3):
                    n += 1
                    R.dettaglio("mappa %s: %s aggiornato (%s)" % (mappa, a.get_name(), RM.cambi[prima:]))
            if n:
                les.save_current_level()
                try:
                    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, False)
                except Exception:
                    pass
                R.ok("%s: %d piattaforme ora danno %s" % (nome_da_pkg(mappa), n, NOME_ARMA))
            else:
                R.avviso("%s: nessuna piattaforma del fucile trovata tra gli attori caricati." % nome_da_pkg(mappa))
        except Exception as e:
            R.manuale("Mappa %s non aggiornata da script (%s). Aprila, seleziona le piattaforme del fucile e imposta "
                      "Weapon Definition = WeaponPickupData_%s, poi salva." % (mappa, e, NOME_ARMA))


# =====================================================================================
# PROGRAMMA PRINCIPALE
# =====================================================================================
def main():
    R.titolo("AVANGUARDIA - creazione di %s" % NOME_ARMA)
    try:
        AR.search_all_assets(True)
        AR.wait_for_completion()
    except Exception:
        pass
    try:
        unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_asset_editors()
    except Exception:
        pass

    F = None
    try:
        F = fase_scoperta()
    except Exception:
        R.errore("Errore nella scoperta: %s" % traceback.format_exc())
    try:
        fase_info_extra()
    except Exception:
        R.avviso("Informazioni extra non lette: %s" % traceback.format_exc())
    if not F:
        R.errore("Mi fermo: senza gli asset del fucile non posso creare Maestrale. Nessun asset e' stato modificato.")
        return
    passi = [("copie", lambda: fase_copie(F))]
    for nome, funz in passi:
        try:
            funz()
        except Exception:
            R.errore("Errore (%s): %s" % (nome, traceback.format_exc()))
            return
    curva = None
    try:
        curva = fase_curva()
    except Exception:
        R.errore("Errore (curva): %s" % traceback.format_exc())
    for nome, funz in (("riferimenti", fase_rimappa),
                       ("statistiche", lambda: fase_statistiche(F, curva)),
                       ("salvataggio", fase_compila_salva),
                       ("verifica", lambda: fase_verifica(F))):
        try:
            funz()
        except Exception:
            R.errore("Errore (%s): %s" % (nome, traceback.format_exc()))
    if R.conteggi.get("ERRORE", 0):
        R.avviso("Ci sono errori nella creazione: NON tocco inventario e mappe di Lyra. Manda il resoconto a Claude.")
        return
    if AGGIORNA_INVENTARIO_INIZIALE:
        try:
            fase_inventario(F)
        except Exception:
            R.errore("Errore (inventario): %s" % traceback.format_exc())
    if AGGIORNA_ARMI_A_TERRA:
        try:
            fase_mappe(F)
        except Exception:
            R.errore("Errore (mappe): %s" % traceback.format_exc())


try:
    main()
except Exception:
    R.errore("Errore imprevisto: %s" % traceback.format_exc())
finally:
    c = R.conteggi
    R.titolo("RIEPILOGO: OK %d, avvisi %d, da fare a mano %d, errori %d" % (
        c.get("OK", 0), c.get("AVVISO", 0), c.get("MANUALE", 0), c.get("ERRORE", 0)))
    percorso = R.salva()
    unreal.log("AVANGUARDIA resoconto salvato in %s" % percorso)
