"""
models.py — All database tables for the Cenedese demo.

Tables are split into two groups:
  - Synced tables  : CLIENT, ARTICO, BAGNI
                     Populated by EXE sync scripts in production.
                     Read-only from the webapp; managed here only for the demo.
  - Webapp tables  : UserProfile, Dipendente, Disposizione, Lavorazione, Modifica
                     Created and managed entirely by the Django app.
"""
from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField


# ---------------------------------------------------------------------------
# Shared choice lists
# ---------------------------------------------------------------------------

TIPO_CHOICES = [("D", "Dipanatura"), ("R", "Roccatura")]
# User type adds Magazzino (M); it works as a D operator but is never written to
# Disposizione.TIPDIS / Lavorazione.TIPO, which stay constrained to TIPO_CHOICES.
USER_TIPO_CHOICES = TIPO_CHOICES + [("M", "Magazzino")]

CONI_CHOICES = [
    ("C", "Cartone cliente"),
    ("N", "Cartone nostri"),
    ("P", "Plastica"),
    ("R", "Rotopress"),       # available to both D and R (artico: CONI is DR)
]

PARAFF_CHOICES = [
    ("S", "Sì"),
    ("N", "No"),
    ("1", "1"),               # Dipanatura only
    ("2", "2"),               # Dipanatura only
]

NODI_CHOICES = [
    ("S", "Splicer"),
    ("M", "Mano"),
    ("C", "Code lunghe"),     # Dipanatura only
    ("A", "Con acqua"),       # Dipanatura only
]

STRIBB_CHOICES = [
    ("N", "No"),
    ("D", "Stribbiare in dipana"),
    ("R", "Stribbiare in rocca"),
]

TIPPAR_CHOICES = [("S", "Solida"), ("L", "Liquida")]

SENSTR_CHOICES = [
    ("O", "Ottica"),
    ("M", "Meccanica"),
    ("G", "Grossi e fini"),
]

OTTICA_CHOICES = [("F", "Fiamme e bottoni"), ("M", "Materie strane")]

TURNO_CHOICES = [("1", "Turno 1"), ("2", "Turno 2"), ("3", "Turno 3")]

# STATO choices split by user type (used in forms and validation)
STATO_DIPANATURA = [
    ("1",  "Macchina 1"),
    ("2",  "Macchina 2"),
    ("3",  "Macchina 3"),
    ("4",  "Macchina 4"),
    ("5",  "Macchina 5"),
    ("M",  "Magazzino"),
    ("S",  "Sospeso"),
    ("D",  "Dipanato da stribbiare"),
    ("C",  "Camera"),
    ("R",  "Riroccare per tensione"),
]

STATO_ROCCATURA = [
    ("M",  "Magazzino"),
    ("S",  "Sospeso"),
    ("A",  "AC6"),
    ("P",  "Polar"),
    ("MA", "Manuale"),
    ("MO", "Macchina olio"),
    ("PC", "Pronto per camera"),
    ("PS", "Pronto per spedizione"),
]

# Full combined list — deduplicated by code (M and S appear in both types)
STATO_ALL = list(dict(STATO_DIPANATURA + STATO_ROCCATURA).items())


# ---------------------------------------------------------------------------
# Mixin: processing flags
# All 8 boolean flags appear identically in both Artico and Bagno.
# ---------------------------------------------------------------------------

class ProcessingFlagsMixin(models.Model):
    """
    8 boolean processing flags shared by Artico and Bagno.
    Display rule: show label only for flags set to True.
    """
    STRAUT = models.BooleanField(default=False, verbose_name="Stribbia automatica")
    STRDIP = models.BooleanField(default=False, verbose_name="Stribbiare in dipana")
    DIPANA = models.BooleanField(default=False, verbose_name="Dipanato")
    OLIARE = models.BooleanField(default=False, verbose_name="Oliare")
    METRAR = models.BooleanField(default=False, verbose_name="Metrare")
    IMBALL = models.BooleanField(default=False, verbose_name="Imballo")
    CONDIZ = models.BooleanField(default=False, verbose_name="Condizionatura")
    ROCMAN = models.BooleanField(default=False, verbose_name="Rocca manuale")

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Mixin: default disposition values
# Default values for the disposition form — appear in both Artico and Bagno.
# Bagno-level values override Artico-level values.
# ---------------------------------------------------------------------------

class DispositionDefaultsMixin(models.Model):
    """
    Default values used to pre-fill the disposition form when no saved
    Disposizione record exists yet. Present on both Artico and Bagno.
    """
    # --- shared D+R ---
    CONI    = models.CharField(max_length=1,  blank=True, choices=CONI_CHOICES,   verbose_name="Coni")
    PARAFF  = models.CharField(max_length=1,  blank=True, choices=PARAFF_CHOICES, verbose_name="Paraffina")
    NODI    = models.CharField(max_length=1,  blank=True, choices=NODI_CHOICES,   verbose_name="Nodi")

    # --- dipanatura defaults ---
    PEROFI  = models.CharField(max_length=10, blank=True, verbose_name="Peso rocca finita")
    MATROC  = models.IntegerField(null=True, blank=True, verbose_name="Matasse per rocca")

    # --- roccatura defaults ---
    NUMROC  = models.IntegerField(null=True, blank=True, verbose_name="Numero rocche")
    PESROC  = models.IntegerField(null=True, blank=True, verbose_name="Peso per rocca (g)")
    METROC  = models.IntegerField(null=True, blank=True, verbose_name="Metri per rocca")
    TOLLER  = models.IntegerField(null=True, blank=True, verbose_name="Tolleranza")
    COLCON  = models.CharField(max_length=20, blank=True, verbose_name="Colore cono")
    TIPPAR  = models.CharField(max_length=1,  blank=True, choices=TIPPAR_CHOICES, verbose_name="Tipo paraffina")
    COLPAR  = models.CharField(max_length=20, blank=True, verbose_name="Colore paraffina")
    VELOCI  = models.IntegerField(null=True, blank=True, verbose_name="Velocità")
    TENSIO  = models.IntegerField(null=True, blank=True, verbose_name="Tensione")
    SENSTR  = models.CharField(max_length=1,  blank=True, choices=SENSTR_CHOICES, verbose_name="Sensibilità stribbia")
    OTTICA  = models.CharField(max_length=1,  blank=True, choices=OTTICA_CHOICES, verbose_name="Ottica")

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Mixin: lavorazione defaults
# CODLAV/COLAFA master values used to pre-fill the Lavorazione form.
# Synced read-only from the DBF; Bagno value overrides Artico (cascade).
# ---------------------------------------------------------------------------

class LavorazioneDefaultsMixin(models.Model):
    CODLAV = models.CharField(max_length=3, blank=True, verbose_name="Codice lavorazione")
    COLAFA = models.CharField(max_length=3, blank=True, verbose_name="Codice lavorazione Fadis")

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Synced tables
# ---------------------------------------------------------------------------

class Client(models.Model):
    """
    Customer registry. Populated by EXE sync script from Infinito CLIENTI table.
    CODCLI: 5-char primary key.  RAGSOC: company name (+ update date appended).
    """
    CODCLI = models.CharField(max_length=5,  primary_key=True, verbose_name="Codice cliente")
    RAGSOC = models.CharField(max_length=61, verbose_name="Ragione sociale")

    class Meta:
        verbose_name        = "Cliente"
        verbose_name_plural = "Clienti"
        ordering            = ["CODCLI"]

    def __str__(self):
        return f"{self.CODCLI} — {self.RAGSOC}"


class Artico(ProcessingFlagsMixin, DispositionDefaultsMixin, LavorazioneDefaultsMixin):
    """
    Article / product master data. Populated by EXE sync from Infinito ARTICO table.
    Also carries default disposition values (overridable at batch level).
    """
    CODART  = models.CharField(max_length=16, primary_key=True, verbose_name="Codice articolo")
    DESCRI  = models.CharField(max_length=50, blank=True, verbose_name="Descrizione")
    COMPO1  = models.CharField(max_length=50, blank=True, verbose_name="Composizione 1")
    COMPO2  = models.CharField(max_length=50, blank=True, verbose_name="Composizione 2")
    TITOLO  = models.CharField(max_length=20, blank=True, verbose_name="Titolo")
    NOTROC  = models.CharField(max_length=50, blank=True, verbose_name="Note rocca")

    # Column NAMES (never values) awaiting push back to the DBF by the sync daemon.
    PENDING = ArrayField(models.CharField(max_length=20), default=list, blank=True, db_column="PENDING")

    class Meta:
        verbose_name        = "Articolo"
        verbose_name_plural = "Articoli"
        ordering            = ["CODART"]

    def __str__(self):
        return f"{self.CODART} — {self.DESCRI}"


class Bagno(ProcessingFlagsMixin, DispositionDefaultsMixin, LavorazioneDefaultsMixin):
    """
    Batch record. Populated by EXE sync from Infinito MATE20XX tables.
    Primary key is the composite (CODCLI, BAGNO).
    Disposition defaults here override those on Artico.
    QUAUSC > 0 means the batch has been shipped (replaces the old SPEDIT flag).
    """
    CODCLI  = models.ForeignKey(Client, on_delete=models.PROTECT, db_column="CODCLI", verbose_name="Cliente")
    BAGNO   = models.CharField(max_length=20, verbose_name="Bagno")
    CODART  = models.ForeignKey(Artico, on_delete=models.PROTECT, db_column="CODART", verbose_name="Articolo")
    INTERN  = models.CharField(max_length=20, blank=True, verbose_name="Interno")
    ANNO    = models.IntegerField(null=True,  blank=True, verbose_name="Anno")
    DATDDT  = models.DateField(null=True,     blank=True, verbose_name="Data DDT")
    DATCON  = models.DateField(null=True,     blank=True, verbose_name="Data consegna")
    NOTE    = models.CharField(max_length=80, blank=True, verbose_name="Note")
    NOTE1   = models.CharField(max_length=80, blank=True, verbose_name="Note 2")
    NOTROC  = models.CharField(max_length=50, blank=True, verbose_name="Note rocca")
    COLORE  = models.CharField(max_length=20, blank=True, verbose_name="Colore")
    COLOR1  = models.CharField(max_length=20, blank=True, verbose_name="Colore 2")
    QUAENT  = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Quantità in entrata")
    QUAUSC  = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Quantità in uscita")

    # Column NAMES (never values) awaiting push back to the DBF by the sync daemon.
    PENDING = ArrayField(models.CharField(max_length=20), default=list, blank=True, db_column="PENDING")

    class Meta:
        verbose_name        = "Bagno"
        verbose_name_plural = "Bagni"
        unique_together     = [("CODCLI", "BAGNO")]
        ordering            = ["CODCLI", "BAGNO"]

    def __str__(self):
        return f"{self.CODCLI_id}/{self.BAGNO}"

    def rimanenza(self):
        """QUAENT − QUAUSC; None when QUAENT is unknown. A null QUAUSC counts as 0."""
        if self.QUAENT is None:
            return None
        return self.QUAENT - (self.QUAUSC or 0)


# ---------------------------------------------------------------------------
# Webapp tables
# ---------------------------------------------------------------------------

class UserProfile(models.Model):
    """
    Extends Django's built-in User with an operator type.
    tipo='D' → dipanatura operator; tipo='R' → roccatura operator.
    The tipo determines which form variant is shown and which TIPDIS is saved.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    tipo = models.CharField(max_length=1, choices=USER_TIPO_CHOICES, verbose_name="Tipo operatore")

    class Meta:
        verbose_name        = "Profilo operatore"
        verbose_name_plural = "Profili operatori"

    def __str__(self):
        return f"{self.user.username} ({self.get_tipo_display()})"


class Dipendente(models.Model):
    """
    Employee list. Used as the collaborator selector in Lavorazione forms.
    """
    CODDIP = models.CharField(max_length=10, primary_key=True, verbose_name="Codice dipendente")
    NOME   = models.CharField(max_length=60, verbose_name="Nome")

    class Meta:
        verbose_name        = "Dipendente"
        verbose_name_plural = "Dipendenti"
        ordering            = ["NOME"]

    def __str__(self):
        return f"{self.CODDIP} — {self.NOME}"


class Disposizione(models.Model):
    """
    Processing parameters for one batch + type combination.
    At most one record per (bagno, TIPDIS) pair.
    If no record exists, the form is pre-filled with defaults from Bagno/Artico.
    """
    bagno   = models.ForeignKey(Bagno,  on_delete=models.CASCADE, related_name="disposizioni")
    TIPDIS  = models.CharField(max_length=1, choices=TIPO_CHOICES, verbose_name="Tipo disposizione")

    # --- shared D+R ---
    CONI    = models.CharField(max_length=1,  blank=True, choices=CONI_CHOICES,   verbose_name="Coni")
    PARAFF  = models.CharField(max_length=1,  blank=True, choices=PARAFF_CHOICES, verbose_name="Paraffina")
    NODI    = models.CharField(max_length=1,  blank=True, choices=NODI_CHOICES,   verbose_name="Nodi")

    # --- dipanatura only ---
    STRIBB  = models.CharField(max_length=1,  blank=True, choices=STRIBB_CHOICES, verbose_name="Stribbia")
    PEROFI  = models.CharField(max_length=10, blank=True, verbose_name="Peso rocca finita")
    MATROC  = models.IntegerField(null=True, blank=True, verbose_name="Matasse per rocca")

    # --- roccatura only ---
    NUMROC  = models.IntegerField(null=True, blank=True, verbose_name="Numero rocche")
    PESROC  = models.IntegerField(null=True, blank=True, verbose_name="Peso per rocca (g)")
    METROC  = models.IntegerField(null=True, blank=True, verbose_name="Metri per rocca")
    TOLLER  = models.IntegerField(null=True, blank=True, verbose_name="Tolleranza")
    COLCON  = models.CharField(max_length=20, blank=True, verbose_name="Colore cono")
    TIPPAR  = models.CharField(max_length=1,  blank=True, choices=TIPPAR_CHOICES, verbose_name="Tipo paraffina")
    COLPAR  = models.CharField(max_length=20, blank=True, verbose_name="Colore paraffina")
    VELOCI  = models.IntegerField(null=True, blank=True, verbose_name="Velocità")
    TENSIO  = models.IntegerField(null=True, blank=True, verbose_name="Tensione")
    SENSTR  = models.CharField(max_length=1,  blank=True, choices=SENSTR_CHOICES, verbose_name="Sensibilità stribbia")
    OTTICA  = models.CharField(max_length=1,  blank=True, choices=OTTICA_CHOICES, verbose_name="Ottica")

    class Meta:
        verbose_name        = "Disposizione"
        verbose_name_plural = "Disposizioni"
        unique_together     = [("bagno", "TIPDIS")]

    def __str__(self):
        return f"Disp. {self.bagno} ({self.TIPDIS})"


class Lavorazione(models.Model):
    """
    Work entry / session.  One row = one processing session on a batch.
    The MOST RECENT row drives the bagno's displayed status.
    Date/time is recorded automatically on creation.
    """
    bagno   = models.ForeignKey(Bagno, on_delete=models.CASCADE, related_name="lavorazioni")
    DATORA  = models.DateTimeField(auto_now_add=True, verbose_name="Data/ora")
    # Operator type that created the record; drives the edit-form variant
    TIPO    = models.CharField(max_length=1, choices=TIPO_CHOICES, default="D", verbose_name="Tipo")
    TURNO   = models.CharField(max_length=1, blank=True, choices=TURNO_CHOICES, verbose_name="Turno")
    STATO   = models.CharField(max_length=2, choices=STATO_ALL,     verbose_name="Macchina/Stato")
    COLLABO = models.ForeignKey(
        Dipendente, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Collaboratore"
    )

    # --- dipanatura fields ---
    PESMAT  = models.IntegerField(null=True, blank=True, verbose_name="Peso matasse")
    CODLAV  = models.CharField(max_length=40, blank=True, verbose_name="Codice lavorazione")   # only STATO 1/2
    COLAFA  = models.CharField(max_length=3,  blank=True, verbose_name="Codice lavorazione Fadis")  # only STATO 3
    VELDIP  = models.IntegerField(null=True, blank=True, verbose_name="Velocità")
    PASSAG  = models.CharField(max_length=40, blank=True, verbose_name="Passaggio")
    PESI    = models.CharField(max_length=40, blank=True, verbose_name="Pesi")
    PESFR1  = models.CharField(max_length=40, blank=True, verbose_name="Pesi fronte 1")   # only STATO 4/5
    PESFR2  = models.CharField(max_length=40, blank=True, verbose_name="Pesi fronte 2")   # only STATO 4/5

    # --- roccatura fields ---
    QUAPRO  = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Quantità prodotta")
    SCARTI  = models.IntegerField(null=True, blank=True, verbose_name="Scarti (gr)")

    # --- shared ---
    DIFETT  = models.CharField(max_length=255, blank=True, verbose_name="Difetti")
    NOTDR   = models.CharField(max_length=255, blank=True, verbose_name="Note")
    FOTO1   = models.ImageField(upload_to="foto/", blank=True, null=True, verbose_name="Foto 1")
    FOTO2   = models.ImageField(upload_to="foto/", blank=True, null=True, verbose_name="Foto 2")
    FOTO3   = models.ImageField(upload_to="foto/", blank=True, null=True, verbose_name="Foto 3")

    class Meta:
        verbose_name        = "Lavorazione"
        verbose_name_plural = "Lavorazioni"
        ordering            = ["-DATORA"]   # most recent first

    def __str__(self):
        return f"Lav. {self.bagno} — {self.STATO} @ {self.DATORA:%d/%m/%Y %H:%M}"


class Modifica(models.Model):
    """
    Audit log. One row per modification event on a bagno record.
    Written automatically by views whenever a Disposizione or Lavorazione is saved.
    """
    bagno       = models.ForeignKey(Bagno, on_delete=models.CASCADE, related_name="modifiche")
    DATORA      = models.DateTimeField(auto_now_add=True, verbose_name="Data/ora")
    utente      = models.CharField(max_length=150, verbose_name="Utente")
    descrizione = models.CharField(max_length=255, verbose_name="Descrizione modifica")

    class Meta:
        verbose_name        = "Modifica"
        verbose_name_plural = "Modifiche"
        ordering            = ["-DATORA"]

    def __str__(self):
        return f"{self.DATORA:%d/%m/%Y %H:%M} — {self.utente}: {self.descrizione}"
