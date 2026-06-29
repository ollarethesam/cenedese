"""
utils.py — DRY helper functions used across views and templates.

Functions here are intentionally pure (no side effects) so they can be
called from both views and template tags without risk.
"""
import os
import re
import threading

from django.conf import settings
from django.core.mail import EmailMessage

from .models import (
    Bagno, Disposizione,
    STATO_DIPANATURA, STATO_ROCCATURA, STATO_ALL,
)


# ---------------------------------------------------------------------------
# Bagno status & calendar colour
# ---------------------------------------------------------------------------

# Map each STATO value to its calendar CSS colour class.
# Colours follow the spec in cenedese_analysis.md §9.4.
_STATO_COLOR = {
    # Dipanatura machines 1-5 → azzurro
    "1": "azzurro", "2": "azzurro", "3": "azzurro", "4": "azzurro", "5": "azzurro",
    # Specific dipanatura statuses
    "D": "arancione",
    "C": "rosa",
    "R": "viola",
    # Shared — 'M' via lavorazione stays grey (red is only for DATCON-set, never-worked batches)
    "S": "grigio",
    "M": "grigio",
    # Roccatura machines
    "A": "giallo", "P": "giallo", "MA": "giallo", "MO": "giallo",
    # Shipped is handled separately by the QUAUSC check
}


def _is_spedito(bagno: Bagno) -> bool:
    """A batch counts as shipped as soon as any quantity has exited."""
    return bagno.QUAUSC is not None and bagno.QUAUSC > 0


def _last_lavorazione(bagno: Bagno):
    """
    Most recent lavorazione, or None.
    Uses .all() (already ordered by Meta '-DATORA') so a prefetch_related
    cache is honoured — an explicit order_by() here would force a new query
    per bagno on the calendar/fermi pages.
    """
    lavs = bagno.lavorazioni.all()
    return lavs[0] if lavs else None


def get_bagno_status(bagno: Bagno) -> str:
    """
    Derive the display status of a bagno. Never stored — always computed.

    Priority chain (from cenedese_analysis.md §6):
      1. QUAUSC > 0            → "SPEDITO"
      2. Has lavorazione rows  → STATO of the most recent lavorazione
      3. DATCON is filled      → "MAGAZZINO"
      4. None of the above     → "FERMO"
    """
    if _is_spedito(bagno):
        return "SPEDITO"

    last_lav = _last_lavorazione(bagno)
    if last_lav:
        return last_lav.STATO

    if bagno.DATCON:
        return "MAGAZZINO"

    return "FERMO"


def is_bagno_visible_to_tipo(bagno: Bagno, tipo) -> bool:
    """
    Whether a batch is shown to an operator of the given type ('D', 'R', or None),
    based on the processing flags. A flag counts as set if True on the Bagno OR
    its Artico:
      Roccatura  → visible if STRAUT or ROCMAN;
      Dipanatura → visible if DIPANA or STRDIP;
      neither relevant flag set → visible to nobody.
    tipo=None (admin) → always visible.
    """
    if tipo not in ("D", "R"):
        return True
    artico = bagno.CODART

    def flag(name):
        return getattr(bagno, name) or (getattr(artico, name) if artico else False)

    if tipo == "R":
        return bool(flag("STRAUT") or flag("ROCMAN"))
    return bool(flag("DIPANA") or flag("STRDIP"))


def get_bagno_color_class(bagno: Bagno) -> str:
    """
    Return the CSS class name for the calendar cell of this bagno.
    Classes map directly to colour variables defined in style.css.
    """
    if _is_spedito(bagno):
        return "verde"

    last_lav = _last_lavorazione(bagno)
    if last_lav:
        return _STATO_COLOR.get(last_lav.STATO, "grigio")

    if bagno.DATCON:
        return "rosso"

    return "fermo"   # no colour / muted


# ---------------------------------------------------------------------------
# Processing flags display
# ---------------------------------------------------------------------------

# (flag_field_name, display_label) — order matches spec
_FLAG_LABELS = [
    ("STRAUT", "STRIBBIA AUTOMATICA"),
    ("STRDIP", "STRIBBIARE IN DIPANA"),
    ("DIPANA", "DIPANATO"),
    ("OLIARE", "OLIARE"),
    ("METRAR", "METRARE"),
    ("IMBALL", "IMBALLO"),
    ("CONDIZ", "CONDIZIONATURA"),
    ("ROCMAN", "ROCCA MANUALE"),
]


def get_active_flags(obj) -> str:
    """
    Return a comma-separated string of labels for all flags that are True.
    Works with any object that has the 8 processing flag fields (Artico or Bagno).
    Returns an empty string when no flags are set.

    Example: STRDIP=True, CONDIZ=True → "STRIBBIARE IN DIPANA, CONDIZIONATURA"
    """
    active = [label for field, label in _FLAG_LABELS if getattr(obj, field, False)]
    return ", ".join(active)


# ---------------------------------------------------------------------------
# Disposition defaults cascade
# ---------------------------------------------------------------------------

def derive_stribb(bagno: Bagno) -> str:
    """
    STRIBB default derived from the processing flags, read with the
    Bagno-OR-Artico cascade (same rule as is_bagno_visible_to_tipo).
    STRDIP wins → 'D'; else STRAUT/ROCMAN → 'R'; else 'N'.
    """
    artico = bagno.CODART

    def flag(name):
        return getattr(bagno, name) or (getattr(artico, name) if artico else False)

    if flag("STRDIP"):
        return "D"
    if flag("STRAUT") or flag("ROCMAN"):
        return "R"
    return "N"


def get_disposition_defaults(bagno: Bagno, tipdis: str) -> dict:
    """
    Build a dict of default values to pre-fill the disposition form when no
    saved Disposizione record exists yet.

    Source priority:
      1. Bagno-level defaults (set per batch in Infinito)
      2. Artico-level defaults (article master)

    Special logic (from cenedese_analysis.md §7):
      - PESROC → (QUAENT × 100) / NUMROC when both available (wins over stored values)
      - METROC → (t2/t1) × PESROC from the TITOLO 't1/t2' pair (wins over stored values)
    """
    b = bagno
    a = bagno.CODART     # Artico instance

    def pick(bagno_val, artico_val):
        """Return bagno value if non-empty, otherwise fall back to artico."""
        return bagno_val if bagno_val else artico_val

    defaults = {}

    # PARAFF, NODI: shared D+R; same field name in bagno and artico
    defaults["PARAFF"] = pick(b.PARAFF, a.PARAFF)
    defaults["NODI"]   = pick(b.NODI,   a.NODI)

    if tipdis == "D":
        # STRIBB default derived from the processing flags (see derive_stribb).
        # Only used when no saved Disposizione exists; a saved value still wins.
        defaults["STRIBB"] = derive_stribb(b)
        defaults["PEROFI"] = pick(b.PEROFI, a.PEROFI)
        defaults["MATROC"] = pick(b.MATROC, a.MATROC)

    if tipdis == "R":
        # CONI: roccatura-only
        defaults["CONI"]   = pick(b.CONI, a.CONI)
        defaults["NUMROC"] = b.NUMROC if b.NUMROC is not None else a.NUMROC
        defaults["PESROC"] = b.PESROC if b.PESROC is not None else a.PESROC
        defaults["METROC"] = b.METROC if b.METROC is not None else a.METROC

        # Calculated defaults take precedence over the stored cascade
        calc = compute_roccatura_values(b.QUAENT, defaults["NUMROC"], a.TITOLO)
        if calc["PESROC"] is not None:
            defaults["PESROC"] = calc["PESROC"]
        if calc["METROC"] is not None:
            defaults["METROC"] = calc["METROC"]

        defaults["TOLLER"] = b.TOLLER if b.TOLLER is not None else a.TOLLER
        defaults["COLCON"] = pick(b.COLCON, a.COLCON)
        defaults["TIPPAR"] = pick(b.TIPPAR, a.TIPPAR)
        defaults["COLPAR"] = pick(b.COLPAR, a.COLPAR)
        defaults["VELOCI"] = b.VELOCI if b.VELOCI is not None else a.VELOCI
        defaults["TENSIO"] = b.TENSIO if b.TENSIO is not None else a.TENSIO
        defaults["SENSTR"] = pick(b.SENSTR, a.SENSTR)
        defaults["OTTICA"] = pick(b.OTTICA, a.OTTICA)

    return defaults


def get_lavorazione_defaults(bagno: Bagno) -> dict:
    """CODLAV/COLAFA master defaults for the new-lavorazione form (Bagno→Artico)."""
    b, a = bagno, bagno.CODART
    return {
        "CODLAV": b.CODLAV or a.CODLAV,
        "COLAFA": b.COLAFA or a.COLAFA,
    }


# ---------------------------------------------------------------------------
# Calculated roccatura values (PESROC / METROC)
# ---------------------------------------------------------------------------

def parse_titolo(titolo: str):
    """
    Extract the (t1, t2) pair from a TITOLO string like "Nm 2/28" or "Ne 40/2".
    Returns a (float, float) tuple, or None when no 'number/number' pair exists.
    """
    if not titolo:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)", titolo)
    if not m:
        return None
    t1 = float(m.group(1).replace(",", "."))
    t2 = float(m.group(2).replace(",", "."))
    if t1 == 0:
        return None
    return (t1, t2)


def compute_roccatura_values(quaent, numroc, titolo: str) -> dict:
    """
    Formula defaults for the R disposition (mirrored client-side in Alpine):
      PESROC = round((QUAENT × 100) / NUMROC)
      METROC = round((t2 / t1) × PESROC)   with (t1, t2) parsed from TITOLO
    Each value is None when its inputs are missing.
    """
    pesroc = None
    if quaent is not None and numroc:
        pesroc = round((float(quaent) * 100) / numroc)

    metroc = None
    pair = parse_titolo(titolo)
    if pesroc is not None and pair:
        t1, t2 = pair
        metroc = round((t2 / t1) * pesroc)

    return {"PESROC": pesroc, "METROC": metroc}


# ---------------------------------------------------------------------------
# Disposizione → Bagno/Artico write-back ("aggiorna" buttons)
# ---------------------------------------------------------------------------

# Disposizione fields that map 1:1 onto Bagno/Artico columns, per type
_WRITEBACK_FIELDS = {
    "D": ["PARAFF", "NODI", "PEROFI", "MATROC"],
    "R": ["CONI", "PARAFF", "NODI", "NUMROC", "PESROC", "METROC", "TOLLER",
          "COLCON", "TIPPAR", "COLPAR", "VELOCI", "TENSIO", "SENSTR", "OTTICA"],
}


# Flag columns driven by the D-disposition STRIBB select (see apply_stribb_flags).
# DIPANA is deliberately excluded — it is never touched by STRIBB write-back.
_STRIBB_FLAGS = ["STRAUT", "STRDIP", "ROCMAN"]


def apply_disposizione_to_record(disp: Disposizione, record, tipdis: str) -> None:
    """
    Copy a saved Disposizione's values onto a Bagno or Artico instance
    (both carry the same default columns via the shared mixins).
    Most processing flags are master data and are NOT written here; the only
    exception is the STRAUT/STRDIP/ROCMAN trio, handled separately via
    apply_stribb_flags() on the D write-back path.
    Mutates `record`; the caller saves it and writes the audit row.
    """
    for field in _WRITEBACK_FIELDS[tipdis]:
        setattr(record, field, getattr(disp, field))


def apply_stribb_flags(disp: Disposizione, record) -> None:
    """
    Translate a D Disposizione's STRIBB into the flag booleans on a Bagno/Artico:
    R → STRAUT=1; D → STRDIP=1; else all 0. ROCMAN and the others reset to 0.
    DIPANA is never touched. Mutates `record`; caller saves it and queues PENDING.
    """
    record.STRAUT = disp.STRIBB == "R"
    record.STRDIP = disp.STRIBB == "D"
    record.ROCMAN = False


def mark_pending(record, names) -> None:
    """
    Union the given column NAMES into record.PENDING (de-duplicated, sorted),
    flagging them for the sync daemon to push back into the DBF. Mutates
    `record`; the caller saves it. Stores names only — never values.
    """
    record.PENDING = sorted(set(record.PENDING) | set(names))


# ---------------------------------------------------------------------------
# Audit log helper
# ---------------------------------------------------------------------------

def log_modifica(bagno: Bagno, utente_username: str, descrizione: str) -> None:
    """Write one row to the Modifica audit log."""
    from .models import Modifica
    Modifica.objects.create(bagno=bagno, utente=utente_username, descrizione=descrizione)


def get_previous_lavorazione(bagno: Bagno, tipo: str):
    """Most recent Lavorazione of the given operator type for this batch, or None.
    Source for pre-filling a new lavorazione's DIFETT/FOTO from the prior session."""
    return bagno.lavorazioni.filter(TIPO=tipo).order_by("-DATORA").first()


def get_latest_lavorazioni_by_stato(bagno: Bagno, tipo: str) -> dict:
    """Most recent Lavorazione of the given operator type per distinct STATO.

    Returns ``{STATO: Lavorazione}`` keyed by machine/status code. Source for the
    per-macchina autofill on the new-lavorazione form: picking a STATO that already
    has a prior record pre-fills the whole form from that record."""
    latest: dict = {}
    for lav in bagno.lavorazioni.filter(TIPO=tipo).order_by("-DATORA"):
        latest.setdefault(lav.STATO, lav)
    return latest


# ---------------------------------------------------------------------------
# STATO label helpers
# ---------------------------------------------------------------------------

def stato_choices_for_tipo(tipo: str) -> list:
    """Return the STATO choice list appropriate for the given operator type."""
    return STATO_DIPANATURA if tipo == "D" else STATO_ROCCATURA


def stato_label(stato_code: str) -> str:
    """Return the human-readable label for a STATO code."""
    all_choices = dict(STATO_DIPANATURA + STATO_ROCCATURA)
    return all_choices.get(stato_code, stato_code)


# ---------------------------------------------------------------------------
# Email notification helpers (Lavorazione create/edit)
# ---------------------------------------------------------------------------

def check_lavorazione_notification_needed(lav, original_values=None, has_new_images=False):
    """
    Determine whether a notification email should be sent for a saved Lavorazione.

    Args:
        lav: the saved Lavorazione instance.
        original_values: None on create; dict with keys DIFETT/FOTO1/FOTO2/FOTO3 on update.
        has_new_images: True if any FOTO file was uploaded in this request.

    Returns:
        A non-empty list of changed field names (e.g. ['DIFETT', 'FOTO1']), or False.
    """
    from .models import Lavorazione as _Lavorazione

    changes = []

    if original_values is None:
        # --- NEW record ---
        if lav.DIFETT and lav.DIFETT.strip():
            # Dedup: skip if the same defect text already exists for this bagno
            already_exists = _Lavorazione.objects.filter(
                bagno=lav.bagno,
                DIFETT__iexact=lav.DIFETT.strip(),
            ).exclude(pk=lav.pk).exists()
            if not already_exists:
                changes.append("DIFETT")

        for foto_field in ("FOTO1", "FOTO2", "FOTO3"):
            field_val = getattr(lav, foto_field)
            if field_val and field_val.name:
                changes.append(foto_field)

    else:
        # --- UPDATE record ---
        original_difett = (original_values.get("DIFETT") or "").strip()
        current_difett  = (lav.DIFETT or "").strip()
        if original_difett != current_difett:
            changes.append("DIFETT")

        if has_new_images:
            for foto_field in ("FOTO1", "FOTO2", "FOTO3"):
                original_name = (original_values.get(foto_field) or None)
                original_name = original_name.name if original_name else None
                current_val   = getattr(lav, foto_field)
                current_name  = current_val.name if current_val else None
                if original_name != current_name and current_name:
                    changes.append(foto_field)

    return changes if changes else False


def send_lavorazione_notification(lav, operator_username, changes_detected=None):
    """
    Send a notification email for a Lavorazione create/update, in a background thread.
    Fire-and-forget: never raises.
    """
    def _send():
        try:
            subject = (
                f"Notifica Aggiornamento Lavorazione - "
                f"{lav.bagno.CODCLI_id} {lav.bagno.BAGNO}"
            )

            lines = [
                "È stata registrata una modifica su una lavorazione:",
                "",
                "Dettagli:",
                f"- Bagno: {lav.bagno.CODCLI_id} / {lav.bagno.BAGNO}",
                f"- Articolo: {lav.bagno.CODART_id}",
                f"- Stato: {dict(STATO_ALL).get(lav.STATO, lav.STATO)}",
                f"- Operatore: {operator_username}",
                f"- Tipo: {lav.TIPO}",
                f"- Turno: {lav.TURNO}",
                f"- Data: {lav.DATORA:%d/%m/%Y %H:%M}",
                "",
            ]

            # Notes block (only if a note is present)
            if lav.NOTDR:
                lines.append(f"Note: {lav.NOTDR}")
                lines.append("")

            # Defect text
            if lav.DIFETT:
                lines.append(f"Difetti: {lav.DIFETT}")
                lines.append("")

            # Attached images summary
            foto_map = [("FOTO1", "Foto 1"), ("FOTO2", "Foto 2"), ("FOTO3", "Foto 3")]
            attached_labels = [
                label for field, label in foto_map
                if getattr(lav, field) and getattr(lav, field).name
            ]
            if attached_labels:
                lines.append(f"Immagini allegate: {', '.join(attached_labels)}")
                lines.append("")

            # Changes summary
            if changes_detected:
                has_foto_change = any(
                    f in changes_detected for f in ("FOTO1", "FOTO2", "FOTO3")
                )
                lines += [
                    "Modifiche rilevate:",
                    f"- Difetti: {'Sì' if 'DIFETT' in changes_detected else 'No'}",
                    f"- Immagini: {'Sì' if has_foto_change else 'No'}",
                    "",
                ]

            message = "\n".join(lines)

            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.RECIPIENT],
            )

            # Attach image files that exist on disk
            for foto_field, _ in foto_map:
                foto_val = getattr(lav, foto_field)
                if foto_val and foto_val.name:
                    try:
                        path = foto_val.path
                        if os.path.exists(path):
                            email.attach_file(path)
                    except Exception as e:
                        print(f"Error attaching {foto_field}: {e}")

            email.send(fail_silently=False)

        except Exception as e:
            print(f"Error sending notification email: {e}")

    threading.Thread(target=_send, daemon=True).start()
