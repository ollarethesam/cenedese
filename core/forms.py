"""
forms.py — Django forms for Disposizione and Lavorazione.

Both forms accept a 'tipo' keyword argument at initialisation.
The tipo ('D' or 'R') determines which fields are included and which
STATO choices are offered, keeping the form class DRY.
"""
from django import forms
from .models import (
    Disposizione, Lavorazione, Dipendente,
    PARAFF_CHOICES, NODI_CHOICES,
    CAMERA_CHOICES, STRIBB_CHOICES, TIPPAR_CHOICES,
    SENSTR_CHOICES, OTTICA_CHOICES, TURNO_CHOICES,
    STATO_DIPANATURA, STATO_ROCCATURA,
)


# ---------------------------------------------------------------------------
# Shared widget defaults
# ---------------------------------------------------------------------------

def _select(attrs=None):
    base = {"class": "form-select"}
    if attrs:
        base.update(attrs)
    return forms.Select(attrs=base)


def _text(placeholder="", attrs=None):
    base = {"class": "form-input", "placeholder": placeholder}
    if attrs:
        base.update(attrs)
    return forms.TextInput(attrs=base)


def _number(attrs=None):
    base = {"class": "form-input"}
    if attrs:
        base.update(attrs)
    return forms.NumberInput(attrs=base)


# Alpine @change handler for FOTO inputs: show a live preview of the chosen file
# and drop any inherited photo (keep=false) in the per-slot scope.
_PHOTO_PREVIEW = "const f=$event.target.files[0]; if(f){ preview=URL.createObjectURL(f); keep=false }"


# ---------------------------------------------------------------------------
# Disposizione form
# ---------------------------------------------------------------------------

class DisposizioneForm(forms.ModelForm):
    """
    Form for creating or editing a Disposizione record.

    Fields are split by operator type:
      - Shared fields:  CONI, PARAFF, NODI
      - D-only fields:  CAMERA, STRIBB, PEROFI, MATROC
      - R-only fields:  NUMROC, PESROC, METROC, TOLLER, COLCON,
                        TIPPAR, COLPAR, VELOCI, TENSIO, SENSTR, OTTICA

    Conditional visibility of TIPPAR (only if PARAFF='S') and
    OTTICA (only if SENSTR='O') is handled in the template via Alpine.js.
    """

    class Meta:
        model  = Disposizione
        fields = "__all__"   # all fields loaded; unwanted ones removed in __init__
        widgets = {
            "CONI":   _select(),
            "PARAFF": _select(),
            "NODI":   _select(),
            "CAMERA": _select(),
            "STRIBB": _select(),
            "PEROFI": _text("es. 1KG"),
            "MATROC": _number(),
            "COLCON": _text("Colore cono"),
            "COLPAR": _text("Colore paraffina"),
            "TIPPAR": _select(),
            "SENSTR": _select(),
            "OTTICA": _select(),
            # x-model.number feeds the live PESROC/METROC calc chain in the template
            "NUMROC": _number({"x-model.number": "numroc"}),
            "PESROC": _number({"x-model.number": "pesroc"}),
            "METROC": _number({"x-model.number": "metroc"}),
            "VELOCI": _number(),
            "TOLLER": _number(),
            "TENSIO": _number(),
        }

    def __init__(self, *args, tipo="D", **kwargs):
        super().__init__(*args, **kwargs)

        # --- shared fields always present ---
        shared = ["CONI", "PARAFF", "NODI"]

        # --- type-specific fields ---
        if tipo == "D":
            type_fields = ["CAMERA", "STRIBB", "PEROFI", "MATROC"]
        else:
            type_fields = [
                "NUMROC", "PESROC", "METROC", "TOLLER",
                "COLCON", "TIPPAR", "COLPAR", "VELOCI",
                "TENSIO", "SENSTR", "OTTICA",
            ]

        self.tipo = tipo
        active_fields = shared + type_fields

        # Drop FK fields set by the view, not the user
        for field_name in list(self.fields):
            if field_name not in active_fields:
                del self.fields[field_name]

        # CONI: all codes (incl. Rotopress) available to both D and R — no restriction.

        # Restrict NODI choices based on tipo
        if "NODI" in self.fields:
            if tipo == "R":
                self.fields["NODI"].choices = [
                    c for c in NODI_CHOICES if c[0] not in ("C", "A")
                ]

        # Restrict PARAFF choices based on tipo
        if "PARAFF" in self.fields:
            if tipo == "D":
                self.fields["PARAFF"].choices = [
                    c for c in PARAFF_CHOICES if c[0] not in ("S",)
                ]
            else:
                self.fields["PARAFF"].choices = [
                    c for c in PARAFF_CHOICES if c[0] not in ("1", "2")
                ]


# ---------------------------------------------------------------------------
# Lavorazione form
# ---------------------------------------------------------------------------

class LavorazioneForm(forms.ModelForm):
    """
    Form for recording a new Lavorazione (work session).

    The operator's tipo determines:
      - Which STATO choices are shown
      - Which type-specific fields are included (D: CODLAV/COLAFA/VELDIP/PASSAG/PESI;
        R: QUAPRO/SCARTI)

    Further conditional visibility within dipanatura fields (CODLAV only if
    STATO=1/2, COLAFA only if STATO=3) is handled in the template via Alpine.js.
    """

    class Meta:
        model  = Lavorazione
        fields = "__all__"   # all fields loaded; unwanted ones removed in __init__
        widgets = {
            "TURNO":  _select(),
            "STATO":  _select({"x-model": "stato"}),   # Alpine binding for conditionals
            "COLLABO": forms.Select(attrs={"class": "form-select"}),
            "CODLAV": _text("Codice lavorazione"),
            "COLAFA": _text("Codice Fadis"),
            "VELDIP": _number(),
            "PASSAG": _text("Passaggio"),
            "PESI":   _text("es. 500g"),
            "PESFR1": _text("es. 500g"),
            "PESFR2": _text("es. 500g"),
            "QUAPRO": _number({"step": "0.01"}),
            "SCARTI": _number(),
            "DIFETT": _text("Descrivi i difetti"),
            "NOTDR1": _text("Nota 1"),
            "NOTDR2": _text("Nota 2"),
            "NOTDR3": _text("Nota 3"),
            # Plain FileInput (not Clearable) so the styled .photo-input wrapper works;
            # an empty input on edit keeps the existing file.
            # x-ref/@change resolve to the per-slot Alpine scope in the template:
            # choosing a file shows a live preview and drops any inherited photo.
            "FOTO1": forms.FileInput(attrs={"accept": "image/*", "capture": "environment", "x-ref": "file", "@change": _PHOTO_PREVIEW}),
            "FOTO2": forms.FileInput(attrs={"accept": "image/*", "capture": "environment", "x-ref": "file", "@change": _PHOTO_PREVIEW}),
            "FOTO3": forms.FileInput(attrs={"accept": "image/*", "capture": "environment", "x-ref": "file", "@change": _PHOTO_PREVIEW}),
        }

    def __init__(self, *args, tipo="D", **kwargs):
        super().__init__(*args, **kwargs)

        self.tipo = tipo

        # --- base fields always present ---
        base_fields = [
            "TURNO", "STATO", "COLLABO", "DIFETT", "NOTDR1", "NOTDR2", "NOTDR3",
            "FOTO1", "FOTO2", "FOTO3",
        ]

        # --- type-specific fields ---
        if tipo == "D":
            type_fields = ["CODLAV", "COLAFA", "VELDIP", "PASSAG", "PESI", "PESFR1", "PESFR2"]
        else:
            type_fields = ["QUAPRO", "SCARTI"]

        active_fields = base_fields + type_fields

        # Drop FK fields set by the view and fields for the other tipo
        for field_name in list(self.fields):
            if field_name not in active_fields:
                del self.fields[field_name]

        # Set STATO choices for this tipo
        if "STATO" in self.fields:
            self.fields["STATO"].choices = [("", "— Seleziona —")] + (
                STATO_DIPANATURA if tipo == "D" else STATO_ROCCATURA
            )

        # Populate collaborator dropdown
        if "COLLABO" in self.fields:
            self.fields["COLLABO"].queryset = Dipendente.objects.all()
            self.fields["COLLABO"].required = False
            self.fields["COLLABO"].empty_label = "— Nessuno —"
