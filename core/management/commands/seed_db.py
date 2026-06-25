"""
seed_db.py — Management command to populate the database with mock data.

Run with:  python manage.py seed_db

Covers every test case:
  - All 8 calendar colour states
  - Disposition defaults cascade (from Bagno, from Artico, special CAMERA rule)
  - Calculated PESROC/METROC defaults from QUAENT/NUMROC/TITOLO
  - Pre-existing dispositions (D and R)
  - Multiple lavorazioni on one batch (latest wins for status)
  - QUAUSC > 0 (spedito) overriding lavorazione status
  - Batches in the "fermi" list
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    Client, Artico, Bagno,
    UserProfile, Dipendente,
    Disposizione, Lavorazione,
)


class Command(BaseCommand):
    help = "Seed the database with mock data covering all test cases."

    def handle(self, *args, **options):
        self.stdout.write("Seeding database...")

        self._clear()
        self._seed_users()
        self._seed_employees()
        self._seed_clients()
        self._seed_articles()
        self._seed_batches()

        self.stdout.write(self.style.SUCCESS("Done! Database seeded successfully."))
        self.stdout.write("")
        self.stdout.write("  Login credentials:")
        self.stdout.write("    operatore_d / pass123  (Dipanatura)")
        self.stdout.write("    operatore_r / pass123  (Roccatura)")

    # ── Helpers ──────────────────────────────────────────────────────────

    def _clear(self):
        """Remove all existing demo data (safe to re-run)."""
        Lavorazione.objects.all().delete()
        Disposizione.objects.all().delete()
        Bagno.objects.all().delete()
        Artico.objects.all().delete()
        Client.objects.all().delete()
        Dipendente.objects.all().delete()
        UserProfile.objects.all().delete()
        User.objects.filter(username__in=["operatore_d", "operatore_r"]).delete()
        self.stdout.write("  Cleared existing data.")

    def _make_user(self, username, tipo):
        user = User.objects.create_user(username=username, password="pass123")
        UserProfile.objects.create(user=user, tipo=tipo)
        return user

    def _lav(self, bagno, stato, tipo="D", turno="1", collabo=None, **kwargs):
        """Shorthand to create a Lavorazione record."""
        return Lavorazione.objects.create(
            bagno=bagno, STATO=stato, TIPO=tipo, TURNO=turno, COLLABO=collabo, **kwargs
        )

    # ── Seed methods ─────────────────────────────────────────────────────

    def _seed_users(self):
        self._make_user("operatore_d", "D")
        self._make_user("operatore_r", "R")
        self.stdout.write("  Users created.")

    def _seed_employees(self):
        employees = [
            ("EMP01", "Mario Rossi"),
            ("EMP02", "Lucia Bianchi"),
            ("EMP03", "Giuseppe Verdi"),
            ("EMP04", "Anna Neri"),
        ]
        for coddip, nome in employees:
            Dipendente.objects.create(CODDIP=coddip, NOME=nome)
        self.stdout.write("  Employees created.")

    def _seed_clients(self):
        Client.objects.create(CODCLI="AB123", RAGSOC="Tessitura Rossi 2024-01-15")
        Client.objects.create(CODCLI="CD456", RAGSOC="Filatura Bianchi 2024-03-01")
        Client.objects.create(CODCLI="EF789", RAGSOC="Maglificio Verde 2023-11-20")
        self.stdout.write("  Clients created.")

    def _seed_articles(self):
        """
        6 articles with varying flags and defaults.
        ART001+B has '+' in its code, which triggers CAMERA default='S'.
        """
        Artico.objects.create(
            CODART="ART001",
            DESCRI="Lana merino 100%",
            COMPO1="100% Lana merino",
            TITOLO="Nm 2/28",
            PEROFI="1KG",
            # Flags
            STRROC=True, CONDIZ=True,
            # Disposition defaults
            CONI="C",
            PARAFF="N", NODI="S",
            CAMERA="N",
            NUMROC=10, PESROC=500, METROC=2000, TOLLER=5,
            VELOCI=800, TENSIO=12, SENSTR="O", OTTICA="F",
        )
        Artico.objects.create(
            CODART="ART001+B",       # '+' in code → CAMERA default = 'S'
            DESCRI="Lana/seta mista",
            COMPO1="60% Lana",
            COMPO2="40% Seta",
            TITOLO="Nm 2/60",
            PEROFI="500G",
            STRDIP=True, OLIARE=True,
            CONI="P",
            PARAFF="S", NODI="M",
            TIPPAR="L",
            NUMROC=20, PESROC=250,
        )
        Artico.objects.create(
            CODART="ART002",
            DESCRI="Cotone pettinato",
            COMPO1="100% Cotone",
            TITOLO="Ne 40/2",
            PESROC=400,
            PEROFI="1KG",
            METRAR=True, IMBALL=True,
            CONI="N",
            PARAFF="N", NODI="S",
            NUMROC=12, METROC=3000,
        )
        Artico.objects.create(
            CODART="ART003",
            DESCRI="Acrilico tinto",
            COMPO1="100% Acrilico",
            TITOLO="Nm 1/14",
            PEROFI="2KG",
            ROCAUT=True, FONCON=True,
            CONI="R",
            PARAFF="S", TIPPAR="S",
            NUMROC=8, PESROC=1000,
            VELOCI=600, SENSTR="M",
        )
        Artico.objects.create(
            CODART="ART004",
            DESCRI="Poliestere riciclato",
            COMPO1="100% Poliestere",
            TITOLO="Dtex 167/2",
            PESROC=750,
            PEROFI="1.5KG",
            STRROC=True, STRDIP=True,  # both flags → test STRIBB default logic
            CONDIZ=True,
            CONI="N",
            NUMROC=6, TOLLER=10,
        )
        Artico.objects.create(
            CODART="ART005",
            DESCRI="Cashmere puro",
            COMPO1="100% Cashmere",
            TITOLO="Nm 2/48",
            PEROFI="240G",
            OLIARE=True,
            CONI="C",
            PARAFF="N", NODI="C",
            CAMERA="S",
            NUMROC=24, PESROC=120, VELOCI=400,
        )
        self.stdout.write("  Articles created.")

    def _seed_batches(self):
        """
        15 batches — each designed to test a specific case.
        Lavorazioni are created immediately after the batch they belong to.
        """
        today      = date.today()
        emp1       = Dipendente.objects.get(CODDIP="EMP01")
        emp2       = Dipendente.objects.get(CODDIP="EMP02")
        art1       = Artico.objects.get(CODART="ART001")
        art1b      = Artico.objects.get(CODART="ART001+B")
        art2       = Artico.objects.get(CODART="ART002")
        art3       = Artico.objects.get(CODART="ART003")
        art4       = Artico.objects.get(CODART="ART004")
        art5       = Artico.objects.get(CODART="ART005")
        cli_ab     = Client.objects.get(CODCLI="AB123")
        cli_cd     = Client.objects.get(CODCLI="CD456")
        cli_ef     = Client.objects.get(CODCLI="EF789")

        # ── TEST CASE: Verde — QUAUSC > 0 (spedito) overrides everything ──
        b001 = Bagno.objects.create(
            CODCLI=cli_ab, BAGNO="B001", CODART=art1,
            INTERN="INT001", ANNO=2025, COLORE="Blu navy",
            DATDDT=today - timedelta(days=30),
            DATCON=today - timedelta(days=2),   # past delivery date
            QUAENT=50, QUAUSC=50,                # fully shipped → Verde, rimanenza 0
            STRROC=True, CONDIZ=True,
            CONI="C", PARAFF="N", NODI="S",
            NUMROC=10, PESROC=500, METROC=2000, VELOCI=800, TENSIO=12,
            SENSTR="O", OTTICA="F",
        )
        # Add a lavorazione too — status should still be SPEDITO (QUAUSC wins)
        self._lav(b001, "M", tipo="R", collabo=emp1)

        # ── TEST CASE: Azzurro — last lavorazione on dipanatura machine 1 ──
        b002 = Bagno.objects.create(
            CODCLI=cli_ab, BAGNO="B002", CODART=art2,
            INTERN="INT002", ANNO=2025, COLORE="Bianco",
            DATDDT=today - timedelta(days=15),
            DATCON=today + timedelta(days=3),
            QUAENT=48,
            CONI="N", NUMROC=12,
        )
        self._lav(b002, "1", collabo=emp1, VELDIP=750, PASSAG="2", NOTDR1="Prima passata ok")

        # ── TEST CASE: Arancione — dipanato da stribbiare ────────────────
        b003 = Bagno.objects.create(
            CODCLI=cli_ab, BAGNO="B003", CODART=art4,
            INTERN="INT003", ANNO=2025, COLORE="Grigio melange",
            DATDDT=today - timedelta(days=20),
            DATCON=today + timedelta(days=1),
            QUAENT=30,
            STRROC=True, STRDIP=True,
            CONI="N",
        )
        self._lav(b003, "D", DIFETT="Leggera irregolarità")

        # ── TEST CASE: Giallo — last lavorazione on roccatura machine (AC6) ─
        b004 = Bagno.objects.create(
            CODCLI=cli_cd, BAGNO="B004", CODART=art3,
            INTERN="INT004", ANNO=2025, COLORE="Rosso vivo",
            DATDDT=today - timedelta(days=10),
            DATCON=today + timedelta(days=4),
            QUAENT=80,
            PARAFF="S", TIPPAR="S",
            CONI="R",
            NUMROC=8, PESROC=1000, VELOCI=600, SENSTR="M",
        )
        self._lav(b004, "A", tipo="R", collabo=emp2, QUAPRO=7500, SCARTI=12)

        # ── TEST CASE: Rosa — camera ──────────────────────────────────────
        b005 = Bagno.objects.create(
            CODCLI=cli_cd, BAGNO="B005", CODART=art5,
            INTERN="INT005", ANNO=2025, COLORE="Camel",
            DATDDT=today - timedelta(days=8),
            DATCON=today + timedelta(days=2),
            QUAENT=29,
            CAMERA="S",
            CONI="C", NUMROC=24, PESROC=120, VELOCI=400,
        )
        self._lav(b005, "C")

        # ── TEST CASE: Viola — riroccare per tensione ─────────────────────
        b006 = Bagno.objects.create(
            CODCLI=cli_ef, BAGNO="B006", CODART=art1,
            INTERN="INT006", ANNO=2025, COLORE="Blu navy",
            DATDDT=today - timedelta(days=12),
            DATCON=today + timedelta(days=5),
            QUAENT=50,
            STRROC=True,
            CONI="C",
            NUMROC=10, PESROC=500, VELOCI=800, SENSTR="O", OTTICA="F",
        )
        self._lav(b006, "R", NOTDR1="Tensione fuori tolleranza, necessario riroccare")

        # ── TEST CASE: Grigio — sospeso ───────────────────────────────────
        b007 = Bagno.objects.create(
            CODCLI=cli_ef, BAGNO="B007", CODART=art2,
            INTERN="INT007", ANNO=2025, COLORE="Bianco",
            DATDDT=today - timedelta(days=25),
            DATCON=today + timedelta(days=6),
            QUAENT=48,
            CONI="N", NUMROC=12,
        )
        self._lav(b007, "S", NOTDR2="In attesa di istruzioni dal cliente")

        # ── TEST CASE: Rosso — DATCON set, no lavorazioni ─────────────────
        Bagno.objects.create(
            CODCLI=cli_ab, BAGNO="B008", CODART=art3,
            INTERN="INT008", ANNO=2025, COLORE="Rosso vivo",
            DATDDT=today - timedelta(days=5),
            DATCON=today,                        # due today, not started → Rosso
            QUAENT=80,
            PARAFF="S", TIPPAR="S",
            CONI="R",
            NUMROC=8, PESROC=1000,
        )

        # ── TEST CASE: Fermo — no DATCON, no lavorazioni ──────────────────
        Bagno.objects.create(
            CODCLI=cli_cd, BAGNO="B009", CODART=art5,
            INTERN="INT009", ANNO=2025, COLORE="Camel",
            DATDDT=today - timedelta(days=45),
            # DATCON intentionally null → Fermo
            QUAENT=24,
            NOTE="In attesa di conferma data consegna",
            CONI="C",
        )

        # ── TEST CASE: Verde — QUAUSC overrides existing lavorazione ──────
        # Partially shipped (rimanenza > 0) still counts as SPEDITO
        b010 = Bagno.objects.create(
            CODCLI=cli_ef, BAGNO="B010", CODART=art4,
            INTERN="INT010", ANNO=2025, COLORE="Grigio melange",
            DATDDT=today - timedelta(days=60),
            DATCON=today - timedelta(days=1),
            QUAENT=30, QUAUSC=18,
            CONI="N",
        )
        # Even though last lavorazione is on machine 2 (Azzurro), QUAUSC wins
        self._lav(b010, "2", VELDIP=700)

        # ── TEST CASE: Azzurro — multiple lavs, latest on machine 2 ───────
        b011 = Bagno.objects.create(
            CODCLI=cli_cd, BAGNO="B011", CODART=art1,
            INTERN="INT011", ANNO=2025, COLORE="Blu navy",
            DATDDT=today - timedelta(days=18),
            DATCON=today + timedelta(days=7),
            QUAENT=50,
            STRROC=True,
            CONI="C",
            NUMROC=10, PESROC=500,
        )
        # First session on machine 3, second (later) on machine 2
        # → status should be Azzurro (machine 2 is the most recent)
        self._lav(b011, "3", COLAFA="FAD", NOTDR1="Prima lavorazione")
        self._lav(b011, "2", collabo=emp1, CODLAV="LAV-2024-011", NOTDR1="Trasferito su macchina 2")

        # ── TEST CASE: CAMERA default = 'S' (CODART contains '+') ─────────
        b012 = Bagno.objects.create(
            CODCLI=cli_ab, BAGNO="B012", CODART=art1b,
            INTERN="INT012", ANNO=2025, COLORE="Bianco naturale", COLOR1="Crema",
            DATDDT=today - timedelta(days=7),
            DATCON=today + timedelta(days=2),
            QUAENT=40,
            STRDIP=True, OLIARE=True,
            CONI="P",
            PARAFF="S", TIPPAR="L",
        )
        # No disposizione yet — opening the D form should propose CAMERA='S'
        self._lav(b012, "1", collabo=emp2, VELDIP=400, PASSAG="1")

        # ── TEST CASE: Pre-existing Dipanatura disposition ────────────────
        b013 = Bagno.objects.create(
            CODCLI=cli_ef, BAGNO="B013", CODART=art4,
            INTERN="INT013", ANNO=2025, COLORE="Grigio melange",
            DATDDT=today - timedelta(days=3),
            DATCON=today + timedelta(days=10),
            QUAENT=30,
            STRROC=True, STRDIP=True,
            CONI="N",
        )
        Disposizione.objects.create(
            bagno=b013, TIPDIS="D",
            CONI="C", PARAFF="N", NODI="S",
            CAMERA="N", STRIBB="R",
            PEROFI="1KG", MATROC=4,
        )
        self._lav(b013, "4", VELDIP=850, NOTDR1="Tutto regolare")

        # ── TEST CASE: Pre-existing Roccatura disposition ─────────────────
        b014 = Bagno.objects.create(
            CODCLI=cli_cd, BAGNO="B014", CODART=art3,
            INTERN="INT014", ANNO=2025, COLORE="Rosso vivo",
            DATDDT=today - timedelta(days=9),
            DATCON=today + timedelta(days=3),
            QUAENT=80,
            PARAFF="S", TIPPAR="S",
            CONI="R",
            NUMROC=8, PESROC=1000, VELOCI=600, SENSTR="M",
        )
        Disposizione.objects.create(
            bagno=b014, TIPDIS="R",
            CONI="R", PARAFF="S", NODI="S",
            NUMROC=8, PESROC=1000, METROC=1500,
            TOLLER=5, COLCON="Nero",
            TIPPAR="S", COLPAR="Bianco",
            VELOCI=600, TENSIO=10, SENSTR="M",
        )
        self._lav(b014, "P", tipo="R", collabo=emp2, QUAPRO=7800, SCARTI=8)

        # ── TEST CASE: Calculated PESROC/METROC defaults ──────────────────
        # No PESROC/METROC stored at bagno level; art1 TITOLO "Nm 2/28" parses
        # to (2, 28). Opening the R disposizione must propose:
        #   PESROC = (48 × 100) / 8 = 600   (≠ artico's stored 500)
        #   METROC = (28 / 2) × 600 = 8400  (≠ artico's stored 2000)
        Bagno.objects.create(
            CODCLI=cli_ab, BAGNO="B015", CODART=art1,
            INTERN="INT015", ANNO=2025, COLORE="Blu navy",
            DATDDT=today - timedelta(days=4),
            DATCON=today + timedelta(days=4),
            QUAENT=48,
            CONI="C",
            NUMROC=8,
        )

        self.stdout.write("  Batches created (15 records, all test cases covered).")
