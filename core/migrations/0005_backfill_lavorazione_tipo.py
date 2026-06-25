"""
Backfill Lavorazione.TIPO for rows created before the field existed.

The schema migration defaults every row to 'D'; here we flip to 'R' the rows
whose STATO belongs only to the roccatura list. Ambiguous codes (M, S appear
in both lists) stay 'D'.
"""
from django.db import migrations

# STATO codes that exist only in STATO_ROCCATURA
R_ONLY_STATO = ["A", "P", "MA", "MO", "PC", "PS"]


def backfill_tipo(apps, schema_editor):
    Lavorazione = apps.get_model("core", "Lavorazione")
    Lavorazione.objects.filter(STATO__in=R_ONLY_STATO).update(TIPO="R")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_remove_bagno_spedit_bagno_quaent_bagno_quausc_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_tipo, migrations.RunPython.noop),
    ]
