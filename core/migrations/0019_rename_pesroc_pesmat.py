# Hand-written migration (rename, not autodetected as drop+add): the field
# formerly called PESROC ("Peso per rocca") is renamed to PESMAT ("Peso
# matasse") everywhere — the client renamed the source column in Infinito too.
# Renamed in place on Bagno/Artico (disposition defaults) and Disposizione so
# all saved values are preserved; the verbose_name is updated to match.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_disposizione_coni_to_conroc'),
    ]

    operations = [
        migrations.RenameField(
            model_name='bagno',
            old_name='PESROC',
            new_name='PESMAT',
        ),
        migrations.RenameField(
            model_name='artico',
            old_name='PESROC',
            new_name='PESMAT',
        ),
        migrations.RenameField(
            model_name='disposizione',
            old_name='PESROC',
            new_name='PESMAT',
        ),
        migrations.AlterField(
            model_name='bagno',
            name='PESMAT',
            field=models.IntegerField(blank=True, null=True, verbose_name='Peso matasse'),
        ),
        migrations.AlterField(
            model_name='artico',
            name='PESMAT',
            field=models.IntegerField(blank=True, null=True, verbose_name='Peso matasse'),
        ),
        migrations.AlterField(
            model_name='disposizione',
            name='PESMAT',
            field=models.IntegerField(blank=True, null=True, verbose_name='Peso matasse'),
        ),
    ]
