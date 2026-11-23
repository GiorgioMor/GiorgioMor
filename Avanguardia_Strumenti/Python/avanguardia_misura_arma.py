# -*- coding: utf-8 -*-
"""
AVANGUARDIA - misuratore dell'arma durante il Play in editor.

COME SI USA
  1. Apri il progetto nell'editor e avvia una partita Elimination (Play).
  2. File > Esegui script Python... > scegli questo file (si puo' fare anche mentre giochi).
  3. Gioca: sullo schermo e nell'Output Log compaiono le misure.
  4. Per spegnerlo, esegui di nuovo lo stesso script.

COSA MISURA
  - Arma in mano e colpi nel caricatore.
  - Cadenza: tieni premuto il fuoco per almeno 5 colpi; quando ti fermi stampa
    l'intervallo medio e i colpi al minuto (obiettivo Maestrale: 0,08 s = 750 colpi/min).
  - Ricarica: dall'inizio dell'animazione di ricarica al momento in cui il caricatore
    si riempie (obiettivo: circa 2,2 s).
  - Danno: per ogni bot colpito stampa il danno, la distanza e, quando muore,
    in quanti colpi e' stato eliminato (obiettivo: 4 colpi da vicino, salute 100).
"""

import builtins
import re

import unreal

TAG_MUNIZIONI = "Lyra.ShooterGame.Weapon.MagazineAmmo"
PAUSA_FINE_RAFFICA_S = 0.4
COLORE = unreal.LinearColor(1.0, 0.85, 0.2, 1.0)


def _mostra(mondo, testo, durata=6.0):
    unreal.log("AVANGUARDIA MISURA " + testo)
    try:
        unreal.SystemLibrary.print_string(mondo, testo, True, False, COLORE, durata)
    except Exception:
        pass


def _nome_tag(t):
    try:
        return str(unreal.BlueprintGameplayTagLibrary.get_tag_name(t))
    except Exception:
        pass
    try:
        m = re.search(r'TagName="([^"]*)"', t.export_text())
        return m.group(1) if m else ""
    except Exception:
        return ""


def _crea_tag(nome):
    try:
        t = unreal.GameplayTag()
        t.import_text('(TagName="%s")' % nome)
        if _nome_tag(t) == nome:
            return t
    except Exception:
        pass
    # In alternativa prendo il tag dalle statistiche della definizione dell'arma
    for p in ("/ShooterCore/Weapons/Maestrale/ID_Maestrale", "/ShooterCore/Weapons/Rifle/ID_Rifle"):
        try:
            n = p.rsplit("/", 1)[1]
            cdo = unreal.get_default_object(unreal.load_object(None, "%s.%s_C" % (p, n)))
            for fr in cdo.get_editor_property("fragments") or []:
                try:
                    stats = fr.get_editor_property("initial_item_stats")
                except Exception:
                    continue
                for k in stats.keys():
                    if _nome_tag(k) == nome:
                        return k
        except Exception:
            continue
    return None


def _mondo_di_gioco():
    mondi = []
    try:
        mondi = list(unreal.EditorLevelLibrary.get_pie_worlds(False) or [])
    except Exception:
        pass
    if not mondi:
        try:
            w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            if w:
                mondi = [w]
        except Exception:
            pass
    for w in mondi:
        try:
            if unreal.GameplayStatics.get_player_pawn(w, 0):
                return w
        except Exception:
            continue
    return mondi[0] if mondi else None


class Misuratore(object):
    def __init__(self):
        self.tag = _crea_tag(TAG_MUNIZIONI)
        self.reset()

    def reset(self):
        self.mondo_nome = None
        self.arma = None
        self.munizioni = None
        self.raffica = []
        self.ultimo_colpo = -100.0
        self.ricarica_inizio = None
        self.ricarica_caricata = None
        self.bot = {}
        self.salute_max_detta = False

    # --- letture -------------------------------------------------------------
    def _arma_e_munizioni(self, mondo, pawn):
        arma, mun = None, None
        try:
            em = pawn.get_component_by_class(unreal.LyraEquipmentManagerComponent)
            inst = em.get_first_instance_of_type(unreal.LyraRangedWeaponInstance) if em else None
            arma = inst.get_class().get_name() if inst else None
        except Exception:
            pass
        try:
            pc = unreal.GameplayStatics.get_player_controller(mondo, 0)
            qb = pc.get_component_by_class(unreal.LyraQuickBarComponent) if pc else None
            item = qb.get_active_slot_item() if qb else None
            if item is not None and self.tag is not None:
                mun = int(item.get_stat_tag_stack_count(self.tag))
        except Exception:
            pass
        return arma, mun

    def _montaggio_attivo(self, pawn):
        try:
            mesh = None
            try:
                mesh = pawn.get_editor_property("mesh")
            except Exception:
                mesh = pawn.get_component_by_class(unreal.SkeletalMeshComponent)
            ai = mesh.get_anim_instance() if mesh else None
            m = ai.get_current_active_montage() if ai else None
            return m.get_name() if m else None
        except Exception:
            return None

    # --- ciclo ---------------------------------------------------------------
    def tick(self, _delta):
        mondo = _mondo_di_gioco()
        if mondo is None:
            if self.mondo_nome is not None:
                self.reset()
            return
        if self.mondo_nome != mondo.get_path_name():
            self.reset()
            self.mondo_nome = mondo.get_path_name()
            _mostra(mondo, "Misuratore Avanguardia attivo (riesegui lo script per spegnerlo)", 8.0)
        pawn = unreal.GameplayStatics.get_player_pawn(mondo, 0)
        if pawn is None:
            return
        t = unreal.GameplayStatics.get_time_seconds(mondo)

        arma, mun = self._arma_e_munizioni(mondo, pawn)
        if arma != self.arma:
            self.arma = arma
            self.munizioni = mun
            self.raffica = []
            _mostra(mondo, "Arma in mano: %s, caricatore %s" % (arma, mun))
            return

        # Colpi sparati
        if mun is not None and self.munizioni is not None and mun < self.munizioni:
            for _ in range(self.munizioni - mun):
                self.raffica.append(t)
            self.ultimo_colpo = t
        # Fine raffica
        if self.raffica and t - self.raffica[-1] > PAUSA_FINE_RAFFICA_S:
            n = len(self.raffica)
            if n >= 5:
                durata = self.raffica[-1] - self.raffica[0]
                intervallo = durata / (n - 1)
                _mostra(mondo, "Raffica: %d colpi in %.2f s -> un colpo ogni %.3f s = %.0f colpi/min (obiettivo 750)"
                        % (n, durata, intervallo, 60.0 / intervallo if intervallo > 0 else 0))
            self.raffica = []

        # Ricarica
        montaggio = self._montaggio_attivo(pawn)
        in_ricarica = bool(montaggio and "reload" in montaggio.lower())
        if in_ricarica and self.ricarica_inizio is None:
            self.ricarica_inizio = t
            self.ricarica_caricata = None
        ricaricato = mun is not None and self.munizioni is not None and mun > self.munizioni
        if ricaricato:
            if self.ricarica_inizio is not None:
                if self.ricarica_caricata is None:
                    self.ricarica_caricata = t - self.ricarica_inizio
                    _mostra(mondo, "Ricarica: caricatore pieno dopo %.2f s (obiettivo 2,2 s)" % self.ricarica_caricata)
            else:
                _mostra(mondo, "Caricatore ricaricato (inizio ricarica non rilevato): %.2f s dall'ultimo colpo"
                        % (t - self.ultimo_colpo))
        if self.ricarica_inizio is not None and not in_ricarica:
            _mostra(mondo, "Ricarica: animazione finita dopo %.2f s" % (t - self.ricarica_inizio))
            self.ricarica_inizio = None
        self.munizioni = mun

        # Danno ai bot
        try:
            pedine = unreal.GameplayStatics.get_all_actors_of_class(mondo, unreal.Pawn) or []
        except Exception:
            pedine = []
        visti = set()
        mio = pawn.get_path_name()
        for p in pedine:
            if p.get_path_name() == mio:
                continue
            try:
                hc = unreal.LyraHealthComponent.find_health_component(p)
                if hc is None:
                    continue
                h, hmax = float(hc.get_health()), float(hc.get_max_health())
            except Exception:
                continue
            chiave = p.get_path_name()
            visti.add(chiave)
            if not self.salute_max_detta:
                self.salute_max_detta = True
                _mostra(mondo, "Salute massima dei bot: %.0f" % hmax)
            stato = self.bot.get(chiave)
            if stato is None:
                self.bot[chiave] = {"salute": h, "colpi": 0}
                continue
            if h < stato["salute"] - 0.01:
                stato["colpi"] += 1
                danno = stato["salute"] - h
                try:
                    dist = pawn.get_distance_to(p) / 100.0
                except Exception:
                    dist = -1
                tuo = "" if t - self.ultimo_colpo <= 0.3 else " (non tuo?)"
                msg = "%s: -%.1f a %.1f m, salute %.0f/%.0f%s" % (p.get_name(), danno, dist, h, hmax, tuo)
                if h <= 0.01:
                    msg += " -> ELIMINATO in %d colpi" % stato["colpi"]
                    stato["colpi"] = 0
                _mostra(mondo, msg)
            elif h >= hmax - 0.01:
                stato["colpi"] = 0
            stato["salute"] = h
        for k in list(self.bot.keys()):
            if k not in visti:
                del self.bot[k]


def _avvia_o_ferma():
    stato = getattr(builtins, "_avanguardia_misuratore", None)
    if stato is not None:
        try:
            unreal.unregister_slate_post_tick_callback(stato[0])
        except Exception:
            pass
        builtins._avanguardia_misuratore = None
        unreal.log("AVANGUARDIA MISURA: misuratore spento")
        return
    m = Misuratore()
    if m.tag is None:
        unreal.log_warning("AVANGUARDIA MISURA: non trovo il tag %s: niente misure su caricatore e cadenza." % TAG_MUNIZIONI)

    def _tick(delta):
        try:
            m.tick(delta)
        except Exception as e:
            unreal.log_warning("AVANGUARDIA MISURA errore: %s" % e)

    h = unreal.register_slate_post_tick_callback(_tick)
    builtins._avanguardia_misuratore = (h, m)
    unreal.log("AVANGUARDIA MISURA: misuratore acceso. Avvia il Play; riesegui lo script per spegnerlo.")


_avvia_o_ferma()
