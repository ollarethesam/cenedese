from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_alter_lavorazione_difett_alter_lavorazione_notdr'),
    ]

    operations = [
        # PENDING è popolata dall'app (clic "aggiorna bagno/articolo") e svuotata
        # dal sync dopo aver riflesso le modifiche sui DBF. Il sync inserisce le
        # righe nuove con INSERT grezzo (psycopg2), bypassando il default Django
        # (default=list): serve quindi un default a livello DB perché la colonna
        # NOT NULL riceva '{}' sulle INSERT che la omettono. Le UPDATE non la
        # toccano mai (PENDING resta fuori dalle colonne mappate).
        migrations.RunSQL(
            sql=[
                'ALTER TABLE core_artico ALTER COLUMN "PENDING" SET DEFAULT \'{}\';',
                'ALTER TABLE core_bagno ALTER COLUMN "PENDING" SET DEFAULT \'{}\';',
            ],
            reverse_sql=[
                'ALTER TABLE core_artico ALTER COLUMN "PENDING" DROP DEFAULT;',
                'ALTER TABLE core_bagno ALTER COLUMN "PENDING" DROP DEFAULT;',
            ],
        ),
    ]
