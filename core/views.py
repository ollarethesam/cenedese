"""
views.py — All views for the Cenedese demo.

Every view requires login.  The logged-in user's UserProfile.tipo ('D' or 'R')
drives which form variant is shown and which TIPDIS code is used when saving.

Helper pattern: _get_bagno(codcli, bagno) is used by every bagno-specific
view to resolve the Bagno instance and raise 404 if not found.
"""
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import pdf
from .models import (
    Bagno, Client, Disposizione, Lavorazione, UserProfile,
    CONI_CHOICES, PARAFF_CHOICES, NODI_CHOICES,
    STRIBB_CHOICES, TIPPAR_CHOICES,
    SENSTR_CHOICES, OTTICA_CHOICES,
)
from .forms import DisposizioneForm, LavorazioneForm
from .utils import (
    get_bagno_status,
    get_bagno_color_class,
    is_bagno_visible_to_tipo,
    get_active_flags,
    get_disposition_defaults,
    get_lavorazione_defaults,
    apply_disposizione_to_record,
    apply_stribb_flags,
    mark_pending,
    parse_titolo,
    log_modifica,
    _WRITEBACK_FIELDS,
    _STRIBB_FLAGS,
    get_previous_lavorazione,
    get_latest_lavorazioni_by_stato,
    stato_label,
    check_lavorazione_notification_needed,
    send_lavorazione_notification,
)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_profile(request):
    """Return the UserProfile for the logged-in user (or raise Http404)."""
    try:
        return request.user.profile
    except UserProfile.DoesNotExist:
        raise Http404("Profilo operatore non trovato per questo utente.")


def _get_profile_or_none(request):
    """Return the UserProfile, or None (e.g. a superuser without a profile)."""
    try:
        return request.user.profile
    except UserProfile.DoesNotExist:
        return None


def _effective_tipo(request):
    """
    (effective_tipo, show_switch) for visibility filtering.
    D/R operators are locked to their own tipo. Admins (tipo None) see all by
    default but may impersonate a type via ?as=D / ?as=R.
    """
    profile = _get_profile_or_none(request)
    own = profile.tipo if profile else None
    if own in ("D", "R"):
        return own, False
    if own == "M":
        # Magazzino sees every batch (like admin "Tutti"), with no switch.
        return None, False
    requested = request.GET.get("as")
    return (requested if requested in ("D", "R") else None), True


def _work_tipo(profile):
    """The tipo used for the form variant, TIPDIS/TIPO and the edit lock.
    A magazzino (M) operator works exactly as a dipanatura (D) operator."""
    return "D" if profile.tipo == "M" else profile.tipo


def _can_act_on_lav(request, lav, profile=None) -> bool:
    """
    Own-type rule: an operator may act on a lavorazione only when its TIPO
    matches the operator's own type. Superusers bypass the restriction.
    """
    if request.user.is_superuser:
        return True
    if profile is None:
        profile = _get_profile_or_none(request)
    return profile is not None and lav.TIPO == _work_tipo(profile)


def _lav_type_block(request, b, lav, action_verb):
    """
    Guard for lavorazione actions: returns a redirect to the list (with an
    error message) when the operator may not act on this record, else None.
    """
    if _can_act_on_lav(request, lav):
        return None
    messages.error(
        request,
        f"Non puoi {action_verb} una lavorazione di {lav.get_TIPO_display().lower()}.",
    )
    return redirect("lavorazione_list", codcli=b.CODCLI_id, bagno=b.BAGNO)


def _get_bagno(codcli: str, bagno_code: str) -> Bagno:
    """Resolve a Bagno by its composite key. Raises 404 if not found."""
    return get_object_or_404(
        Bagno.objects.select_related("CODCLI", "CODART"),
        CODCLI_id=codcli,
        BAGNO=bagno_code,
    )


def _fermo_redirect(request, b: Bagno):
    """
    FERMO gate: a fermo batch needs a delivery date before any disposizione
    or lavorazione can be created. Returns a redirect to the detail page
    (whose modal collects DATCON), or None when the batch may proceed.
    """
    if get_bagno_status(b) == "FERMO":
        messages.error(request, "Bagno fermo: inserisci la data di consegna per continuare.")
        return redirect("bagno_detail", codcli=b.CODCLI_id, bagno=b.BAGNO)
    return None


# ---------------------------------------------------------------------------
# Main screen — barcode scanner + manual search
# ---------------------------------------------------------------------------

@login_required
def main_view(request):
    """
    Entry point of the webapp.

    GET:  Show a tab UI with two modes:
            - 'scan'   → camera barcode scanner (html5-qrcode)
            - 'search' → manual: choose client then pick batch

    POST (mode='scan'):
            Barcode string → split first 5 chars as CODCLI, rest as BAGNO.
            Redirect to bagno_detail if found; show error if not.

    POST (mode='search'):
            codcli + bagno submitted via the manual form.
            Redirect to bagno_detail.
    """
    clients = Client.objects.all().order_by("CODCLI")
    error   = None

    if request.method == "POST":
        mode = request.POST.get("mode", "scan")

        if mode == "scan":
            raw = request.POST.get("barcode", "").strip()
            if len(raw) < 6:
                error = "Codice a barre non valido."
            else:
                codcli     = raw[:5]
                bagno_code = raw[5:]
                # Verify the batch exists before redirecting
                if Bagno.objects.filter(CODCLI_id=codcli, BAGNO=bagno_code).exists():
                    return redirect("bagno_detail", codcli=codcli, bagno=bagno_code)
                error = f"Bagno '{bagno_code}' non trovato per il cliente '{codcli}'."

        elif mode == "search":
            codcli     = request.POST.get("codcli", "").strip()
            bagno_code = request.POST.get("bagno",  "").strip()
            if codcli and bagno_code:
                if Bagno.objects.filter(CODCLI_id=codcli, BAGNO=bagno_code).exists():
                    return redirect("bagno_detail", codcli=codcli, bagno=bagno_code)
                error = f"Bagno '{bagno_code}' non trovato per il cliente '{codcli}'."
            else:
                error = "Seleziona cliente e bagno."

    # Build bagni list for the manual search dropdown (filtered by client if provided)
    selected_client = request.GET.get("codcli", "")
    bagni = (
        Bagno.objects.filter(CODCLI_id=selected_client)
        if selected_client
        else Bagno.objects.none()
    )

    return render(request, "core/main.html", {
        # Normalised {value, label} lists consumed by the combobox component
        "clients_data":    [{"value": c.CODCLI, "label": f"{c.CODCLI} — {c.RAGSOC}"} for c in clients],
        "bagni_data":      [{"value": b.BAGNO, "label": b.BAGNO} for b in bagni],
        "selected_client": selected_client,
        "error":           error,
    })


@login_required
def bagni_by_client(request, codcli):
    """
    AJAX-friendly view: return bagni for a client as JSON.
    Used by the manual search form to populate the bagno combobox.
    """
    bagni = Bagno.objects.filter(CODCLI_id=codcli).order_by("BAGNO")
    return JsonResponse({"bagni": [b.BAGNO for b in bagni]})


# ---------------------------------------------------------------------------
# Bagno detail
# ---------------------------------------------------------------------------

@login_required
def bagno_detail_view(request, codcli, bagno):
    """
    Read-only summary of a batch.

    Shows:
      - Article info joined from BAGNI + ARTICO
      - Processing flags (comma-separated labels for flags=True)
      - Derived status (from utils.get_bagno_status)
      - Buttons to open Disposizione and Lavorazione forms
    """
    b       = _get_bagno(codcli, bagno)
    profile = _get_profile(request)
    status  = get_bagno_status(b)

    return render(request, "core/bagno_detail.html", {
        "bagno":        b,
        "artico":       b.CODART,
        "flags_label":  get_active_flags(b) or get_active_flags(b.CODART),
        "status":       status,
        "status_label": stato_label(status),
        "is_fermo":     status == "FERMO",
        "profile":      profile,
        "work_tipo":    _work_tipo(profile),
    })


@login_required
@require_POST
def set_datcon_view(request, codcli, bagno):
    """
    FERMO gate target: save the delivery date entered in the detail-page modal,
    then continue to the form the operator originally asked for.
    """
    b = _get_bagno(codcli, bagno)

    next_view = request.POST.get("next", "")

    raw = request.POST.get("datcon", "").strip()
    try:
        b.DATCON = date.fromisoformat(raw)
    except ValueError:
        messages.error(request, "Data di consegna non valida.")
        if next_view == "fermi":
            return redirect("fermi")
        return redirect("bagno_detail", codcli=codcli, bagno=bagno)

    mark_pending(b, ["DATCON"])
    b.save()
    log_modifica(b, request.user.username, f"Data consegna impostata: {b.DATCON:%d/%m/%Y}")

    # Continue to the requested form (token, not a raw URL — no open redirect)
    if next_view == "fermi":
        return redirect("fermi")
    if next_view in ("disposizione", "lavorazione_create"):
        return redirect(next_view, codcli=codcli, bagno=bagno)
    return redirect("bagno_detail", codcli=codcli, bagno=bagno)


# ---------------------------------------------------------------------------
# Disposizione form
# ---------------------------------------------------------------------------

@login_required
def disposizione_view(request, codcli, bagno):
    """
    Create or edit the Disposizione for this batch + user type.

    GET:
      - If a record already exists → pre-fill form with saved values.
      - If not → pre-fill with defaults from Bagno/Artico via get_disposition_defaults().

    POST (submit button name 'action' selects the behaviour):
      - 'salva'             → save the Disposizione + audit row.
      - 'aggiorna_bagno'    → save, then copy the values onto the Bagno row.
      - 'aggiorna_articolo' → save, then copy the values onto the Artico row.
      All paths redirect to bagno detail on success.
    """
    b       = _get_bagno(codcli, bagno)
    profile = _get_profile(request)
    tipdis  = _work_tipo(profile)

    gate = _fermo_redirect(request, b)
    if gate:
        return gate

    # Try to load an existing disposition record
    try:
        instance = Disposizione.objects.get(bagno=b, TIPDIS=tipdis)
        is_new   = False
    except Disposizione.DoesNotExist:
        instance = None
        is_new   = True

    if request.method == "POST":
        form = DisposizioneForm(request.POST, instance=instance, tipo=tipdis)
        if form.is_valid():
            # update_or_create closes the race of two concurrent first saves
            disp, _created = Disposizione.objects.update_or_create(
                bagno=b, TIPDIS=tipdis,
                defaults={f: form.cleaned_data[f] for f in form.fields},
            )

            action_done = "creata" if is_new else "aggiornata"
            log_modifica(b, request.user.username, f"Disposizione {tipdis} {action_done}")

            action = request.POST.get("action", "salva")
            if action == "aggiorna_bagno":
                apply_disposizione_to_record(disp, b, tipdis)
                names = list(_WRITEBACK_FIELDS[tipdis])
                if tipdis == "D":
                    # STRIBB drives the STRAUT/STRDIP/ROCMAN flags (D-only field)
                    apply_stribb_flags(disp, b)
                    names += _STRIBB_FLAGS
                mark_pending(b, names)
                b.save()
                log_modifica(b, request.user.username, "Valori disposizione copiati sul bagno")
            elif action == "aggiorna_articolo":
                artico = b.CODART
                apply_disposizione_to_record(disp, artico, tipdis)
                # PESROC/PEROFI on Artico are derived from the DBF UNIMIS column and
                # cannot round-trip, so they are never queued for the article push.
                artico_names = [f for f in _WRITEBACK_FIELDS[tipdis]
                                if f not in ("PESROC", "PEROFI")]
                if tipdis == "D":
                    apply_stribb_flags(disp, artico)
                    artico_names += _STRIBB_FLAGS
                mark_pending(artico, artico_names)
                artico.save()
                log_modifica(b, request.user.username,
                             f"Valori disposizione copiati sull'articolo {artico.CODART}")

            return redirect("bagno_detail", codcli=codcli, bagno=bagno)
    else:
        # Pre-fill with saved data or computed defaults
        initial = {} if instance else get_disposition_defaults(b, tipdis)
        form    = DisposizioneForm(instance=instance, initial=initial, tipo=tipdis)

    def fval(name):
        """Current form value (POST > initial > instance) for Alpine seeding."""
        return form[name].value() if name in form.fields else None

    titolo_pair = parse_titolo(b.CODART.TITOLO)

    return render(request, "core/disposizione_form.html", {
        "form":    form,
        "bagno":   b,
        "artico":  b.CODART,
        "tipdis":  tipdis,
        "is_new":  is_new,
        # Alpine seeds — taken from the form so a failed POST keeps the user's input
        "initial_paraff": fval("PARAFF") or "",
        "initial_tippar": fval("TIPPAR") or "",
        "initial_senstr": fval("SENSTR") or "",
        "initial_numroc": fval("NUMROC"),
        "initial_pesroc": fval("PESROC"),
        "initial_metroc": fval("METROC"),
        # Inputs of the live PESROC/METROC calc chain, as JS literals
        # (it-IT localisation would render 50.0 as "50,0" and break the script)
        "quaent_js": repr(float(b.QUAENT)) if b.QUAENT is not None else "null",
        "t1_js":     repr(titolo_pair[0]) if titolo_pair else "null",
        "t2_js":     repr(titolo_pair[1]) if titolo_pair else "null",
    })


# ---------------------------------------------------------------------------
# Lavorazione list
# ---------------------------------------------------------------------------

@login_required
def lavorazione_list_view(request, codcli, bagno):
    """List all work sessions for this batch, most recent first."""
    b    = _get_bagno(codcli, bagno)
    lavs = list(b.lavorazioni.select_related("COLLABO").order_by("-DATORA"))

    # Mark which lavs already have a saved Disposizione for their type, so the
    # template knows whether the Stampa action needs the "use defaults" popup.
    saved = set(b.disposizioni.values_list("TIPDIS", flat=True))
    profile = _get_profile_or_none(request)
    for lav in lavs:
        lav.has_saved_disp = lav.TIPO in saved
        lav.can_act        = _can_act_on_lav(request, lav, profile)

    return render(request, "core/lavorazione_list.html", {
        "bagno": b,
        "lavs":  lavs,
    })


# Coded fields → their choice list, for resolving raw default codes to labels.
_CODED_CHOICES = {
    "CONI":   CONI_CHOICES,
    "PARAFF": PARAFF_CHOICES,
    "NODI":   NODI_CHOICES,
    "STRIBB": STRIBB_CHOICES,
    "TIPPAR": TIPPAR_CHOICES,
    "SENSTR": SENSTR_CHOICES,
    "OTTICA": OTTICA_CHOICES,
}


@login_required
def lavorazione_print_view(request, codcli, bagno, pk):
    """
    Stream an inline PDF "scheda disposizioni" for a single lavorazione.

    Combines batch/article master data, the Disposizione parameters for the
    lavorazione's type (saved record, else computed defaults), and the values
    recorded in that session. Read-only: writes nothing, logs nothing.
    """
    b      = _get_bagno(codcli, bagno)
    lav    = get_object_or_404(b.lavorazioni, pk=pk)

    blocked = _lav_type_block(request, b, lav, "stampare")
    if blocked:
        return blocked

    tipdis = lav.TIPO

    disp = b.disposizioni.filter(TIPDIS=tipdis).first()

    if disp:
        def resolve(name):
            if name in _CODED_CHOICES:
                return getattr(disp, f"get_{name}_display")()
            return getattr(disp, name)
        source_fields = [f for f in _DISP_FIELDS[tipdis]]
        disp_values = {f: resolve(f) for f in source_fields}
    else:
        defaults = get_disposition_defaults(b, tipdis)

        def resolve(name, code):
            if name in _CODED_CHOICES:
                return dict(_CODED_CHOICES[name]).get(code, "")
            return code
        disp_values = {f: resolve(f, defaults.get(f)) for f in defaults}

    pdf_bytes = pdf.generate_lavorazione_pdf(b, lav, disp_values)

    safe_bagno = b.BAGNO.replace("/", "_")
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="disposizione_{b.CODCLI_id}_{safe_bagno}_{pk}.pdf"'
    )
    return response


# Disposizione field names relevant to each type, for the saved-record path.
_DISP_FIELDS = {
    "D": ["PARAFF", "NODI", "STRIBB", "PEROFI", "MATROC"],
    "R": ["CONI", "PARAFF", "NODI", "NUMROC", "PESROC", "METROC", "TOLLER",
          "COLCON", "TIPPAR", "COLPAR", "VELOCI", "TENSIO", "SENSTR", "OTTICA"],
}


# ---------------------------------------------------------------------------
# New lavorazione
# ---------------------------------------------------------------------------

def _photo_slots(form, prev=None, post=None):
    """Per-slot data for the photo grid: bound field + inherited preview url + keep flag.

    create flow (prev given): inherited url/keep come from the previous lavorazione,
    or from the resubmitted keep_* flags on an invalid POST.
    edit flow (prev None): the existing instance file drives the thumbnail.
    """
    slots = []
    for name in ("FOTO1", "FOTO2", "FOTO3"):
        field = form[name]
        inherited_url, keep = "", False
        if prev is not None:                       # create flow
            keep = (post.get("keep_" + name) == "1") if post else True
            f = getattr(prev, name)
            if keep and f:
                inherited_url = f.url
        elif field.value():                        # edit flow: existing instance file
            inherited_url = field.value().url
        slots.append({"field": field, "name": name,
                      "inherited_url": inherited_url, "keep": keep})
    return slots


def _build_autofill_map(form, lav_by_stato):
    """Serialize the per-STATO records for the client-side macchina autofill.

    Returns ``{STATO: {field: "value", …, FOTOn: {"url": …, "keep": bool}}}`` covering
    every form field except STATO (just picked) and the photo file inputs. COLLABO is
    emitted as its PK so the select can be matched; values are strings ('' for None).
    """
    value_fields = [n for n in form.fields if n not in ("STATO", "FOTO1", "FOTO2", "FOTO3")]
    autofill = {}
    for stato, lav in lav_by_stato.items():
        entry = {}
        for name in value_fields:
            if name == "COLLABO":
                val = lav.COLLABO_id
            else:
                val = getattr(lav, name)
            entry[name] = "" if val is None else str(val)
        for name in ("FOTO1", "FOTO2", "FOTO3"):
            f = getattr(lav, name)
            entry[name] = {"url": f.url if f else "", "keep": bool(f)}
        autofill[stato] = entry
    return autofill


@login_required
def lavorazione_create_view(request, codcli, bagno):
    """
    Record a new work session for this batch.

    GET:  Show form with STATO choices and fields for the user's tipo. DIFETT and
          FOTO* are pre-filled from the most recent same-tipo lavorazione.
    POST: Save the Lavorazione, write audit log, redirect to list.
    """
    b       = _get_bagno(codcli, bagno)
    profile = _get_profile(request)
    tipo    = _work_tipo(profile)

    gate = _fermo_redirect(request, b)
    if gate:
        return gate

    prev = get_previous_lavorazione(b, tipo)

    # Per-macchina autofill: most-recent lavorazione per STATO, used both to build
    # the client-side autofill map and to resolve the photo source on POST.
    lav_by_stato = get_latest_lavorazioni_by_stato(b, tipo)

    if request.method == "POST":
        form = LavorazioneForm(request.POST, request.FILES, tipo=tipo)
        # Photo source = the STATO-matched record (per-macchina autofill), falling
        # back to the baseline most-recent lavorazione before any STATO is chosen.
        source = lav_by_stato.get(request.POST.get("STATO")) or prev
        if form.is_valid():
            lav       = form.save(commit=False)
            lav.bagno = b
            lav.TIPO  = tipo

            # Carry forward inherited photos the user kept: reuse the source
            # record's stored file reference (no new upload → no duplicate on disk).
            # The keep_* field is a boolean flag only; the path is re-derived from
            # `source`, never trusted from the client.
            if source is not None:
                for name in ("FOTO1", "FOTO2", "FOTO3"):
                    if name in request.FILES:
                        continue
                    if request.POST.get("keep_" + name) != "1":
                        continue
                    f = getattr(source, name)
                    if f:
                        setattr(lav, name, f.name)

            lav.save()

            has_new_images = any(f in request.FILES for f in ("FOTO1", "FOTO2", "FOTO3"))
            changes = check_lavorazione_notification_needed(lav, None, has_new_images)
            if changes:
                send_lavorazione_notification(lav, request.user.username, changes)

            log_modifica(b, request.user.username, f"Lavorazione aggiunta: STATO={lav.STATO}")

            return redirect("lavorazione_list", codcli=codcli, bagno=bagno)
        photo_slots = _photo_slots(form, prev=source, post=request.POST)
    else:
        initial = {}
        if prev and prev.DIFETT:
            initial["DIFETT"] = prev.DIFETT
        if tipo == "D":
            initial.update(get_lavorazione_defaults(b))
        form = LavorazioneForm(tipo=tipo, initial=initial or None)
        photo_slots = _photo_slots(form, prev=prev)

    return render(request, "core/lavorazione_form.html", {
        "form":        form,
        "bagno":       b,
        "tipo":        tipo,
        "is_edit":     False,
        "photo_slots": photo_slots,
        # Seed Alpine from the form so a failed POST keeps the chosen STATO
        "initial_stato": form["STATO"].value() or "",
        # Per-macchina autofill map: {STATO: {field: value, …, FOTOn: {url, keep}}}
        "autofill": _build_autofill_map(form, lav_by_stato),
    })


@login_required
def lavorazione_edit_view(request, codcli, bagno, pk):
    """
    Edit an existing work session. The form variant follows the record's
    own TIPO (not the editor's), so D and R fields never get mixed up.
    DATORA (auto_now_add) is preserved.
    """
    b    = _get_bagno(codcli, bagno)
    lav  = get_object_or_404(Lavorazione, pk=pk, bagno=b)

    # Snapshot before the form is built: form.is_valid() mutates `lav` in place
    # (construct_instance) with the new POST data, so capturing later would lose
    # the original values and the diff would always be empty.
    original_values = {
        "DIFETT": lav.DIFETT,
        "FOTO1":  lav.FOTO1,
        "FOTO2":  lav.FOTO2,
        "FOTO3":  lav.FOTO3,
    }

    blocked = _lav_type_block(request, b, lav, "modificare")
    if blocked:
        return blocked

    tipo = lav.TIPO

    if request.method == "POST":
        form = LavorazioneForm(request.POST, request.FILES, instance=lav, tipo=tipo)
        if form.is_valid():
            has_new_images = any(f in request.FILES for f in ("FOTO1", "FOTO2", "FOTO3"))
            lav = form.save()
            changes = check_lavorazione_notification_needed(lav, original_values, has_new_images)
            if changes:
                send_lavorazione_notification(lav, request.user.username, changes)
            log_modifica(b, request.user.username, f"Lavorazione modificata: STATO={lav.STATO}")
            return redirect("lavorazione_list", codcli=codcli, bagno=bagno)
    else:
        form = LavorazioneForm(instance=lav, tipo=tipo)

    return render(request, "core/lavorazione_form.html", {
        "form":        form,
        "bagno":       b,
        "tipo":        tipo,
        "is_edit":     True,
        "lav":         lav,
        "photo_slots": _photo_slots(form),
        "initial_stato": form["STATO"].value() or "",
    })


@login_required
@require_POST
def lavorazione_delete_view(request, codcli, bagno, pk):
    """Delete a work session (confirmed client-side) and log the event."""
    b   = _get_bagno(codcli, bagno)
    lav = get_object_or_404(Lavorazione, pk=pk, bagno=b)

    blocked = _lav_type_block(request, b, lav, "eliminare")
    if blocked:
        return blocked

    descr = f"Lavorazione eliminata: STATO={lav.STATO} del {timezone.localtime(lav.DATORA):%d/%m/%Y %H:%M}"
    lav.delete()
    log_modifica(b, request.user.username, descr)

    return redirect("lavorazione_list", codcli=codcli, bagno=bagno)


# ---------------------------------------------------------------------------
# Calendar view
# ---------------------------------------------------------------------------

def _week_bounds(week_str):
    """
    Parse a 'YYYY-WW' week string and return (week_start, week_end) dates.
    Defaults to the current ISO week if week_str is None or invalid.
    """
    if week_str:
        try:
            year, week = map(int, week_str.split("-"))
            # Python: isoweekday 1=Mon; ISO week starts Monday
            week_start = date.fromisocalendar(year, week, 1)
        except (ValueError, AttributeError):
            week_start = date.today() - timedelta(days=date.today().weekday())
    else:
        week_start = date.today() - timedelta(days=date.today().weekday())

    week_end = week_start + timedelta(days=6)
    return week_start, week_end


@login_required
def calendar_view(request):
    """
    Weekly calendar grouped by DATCON (delivery date).

    URL params:
      ?week=YYYY-WW   navigate to a specific ISO week (default: current week)

    Each batch is annotated with its colour class (see utils.get_bagno_color_class).
    Batches without a DATCON appear in the "FERMI" section via fermi_view.
    """
    week_str              = request.GET.get("week")
    week_start, week_end  = _week_bounds(week_str)

    # Operator type drives visibility via the stribbiatura flags (None = see all)
    tipo, show_switch = _effective_tipo(request)

    # Batches with a delivery date falling in this week
    bagni = (
        Bagno.objects
        .filter(DATCON__range=(week_start, week_end))
        .select_related("CODCLI", "CODART")
        .prefetch_related("lavorazioni")
        .order_by("DATCON", "CODCLI")
    )

    # Build day-by-day structure for the template
    days = []
    for i in range(7):
        day_date = week_start + timedelta(days=i)
        day_bagni = [b for b in bagni
                     if b.DATCON == day_date and is_bagno_visible_to_tipo(b, tipo)]
        days.append({
            "date":  day_date,
            "bagni": [
                {"bagno": b, "color": get_bagno_color_class(b), "status": get_bagno_status(b)}
                for b in day_bagni
            ],
        })

    # Navigation
    prev_week = week_start - timedelta(weeks=1)
    next_week = week_start + timedelta(weeks=1)

    return render(request, "core/calendar.html", {
        "days":       days,
        "week_start": week_start,
        "week_end":   week_end,
        "prev_week":  f"{prev_week.isocalendar()[0]}-{prev_week.isocalendar()[1]:02d}",
        "next_week":  f"{next_week.isocalendar()[0]}-{next_week.isocalendar()[1]:02d}",
        "cur_week":   f"{week_start.isocalendar()[0]}-{week_start.isocalendar()[1]:02d}",
        "view_as":    tipo,
        "show_switch": show_switch,
    })


# ---------------------------------------------------------------------------
# Fermi view
# ---------------------------------------------------------------------------

@login_required
def fermi_view(request):
    """
    List batches that are 'stuck' (FERMO or SOSPESO):
      - No DATCON set, OR
      - Last lavorazione STATO = 'S' (sospeso)

    Displayed as a simple list with colour badges.
    """
    # Shipped = any outgoing quantity; everything else is a candidate
    not_shipped = Q(QUAUSC__isnull=True) | Q(QUAUSC__lte=0)

    # Operator type drives visibility via the stribbiatura flags (None = see all)
    tipo, show_switch = _effective_tipo(request)

    # All batches without a delivery date
    no_datcon = (
        Bagno.objects
        .filter(not_shipped, DATCON__isnull=True)
        .select_related("CODCLI", "CODART")
        .prefetch_related("lavorazioni")
    )

    all_fermi = [
        {"bagno": b, "color": get_bagno_color_class(b), "status": get_bagno_status(b)}
        for b in no_datcon
        if is_bagno_visible_to_tipo(b, tipo)
    ]
    seen = {entry["bagno"].pk for entry in all_fermi}

    # Add batches with DATCON but last STATO='S' (sospeso)
    with_datcon = (
        Bagno.objects
        .filter(not_shipped, DATCON__isnull=False)
        .select_related("CODCLI", "CODART")
        .prefetch_related("lavorazioni")
    )
    for b in with_datcon:
        if not is_bagno_visible_to_tipo(b, tipo):
            continue
        if get_bagno_status(b) == "S" and b.pk not in seen:
            seen.add(b.pk)
            all_fermi.append({"bagno": b, "color": "grigio", "status": "S"})

    return render(request, "core/fermi.html", {
        "fermi": all_fermi,
        "view_as": tipo,
        "show_switch": show_switch,
    })
