# Hand-written migration (not autodetected): the Infinito ERP added a new
# roccatura-only cone-type column (CONROC, C/N/P/R). The webapp previously
# reused CONI (dipanatura, C/N/P) for the R disposition by mistake — this
# migration renames Disposizione.CONI to CONROC in place (preserving all
# saved R values) and adds CONROC as new master data on Bagno/Artico, leaving
# CONI there untouched as dipanatura-only master data.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_artico_codlav_artico_colafa_bagno_codlav_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='disposizione',
            old_name='CONI',
            new_name='CONROC',
        ),
        migrations.AddField(
            model_name='bagno',
            name='CONROC',
            field=models.CharField(blank=True, choices=[('C', 'Cartone cliente'), ('N', 'Cartone nostri'), ('P', 'Plastica'), ('R', 'Rotopress')], max_length=1, verbose_name='Coni roccatura'),
        ),
        migrations.AddField(
            model_name='artico',
            name='CONROC',
            field=models.CharField(blank=True, choices=[('C', 'Cartone cliente'), ('N', 'Cartone nostri'), ('P', 'Plastica'), ('R', 'Rotopress')], max_length=1, verbose_name='Coni roccatura'),
        ),
        migrations.AlterField(
            model_name='disposizione',
            name='CONROC',
            field=models.CharField(blank=True, choices=[('C', 'Cartone cliente'), ('N', 'Cartone nostri'), ('P', 'Plastica'), ('R', 'Rotopress')], max_length=1, verbose_name='Coni roccatura'),
        ),
        migrations.AlterField(
            model_name='bagno',
            name='CONI',
            field=models.CharField(blank=True, choices=[('C', 'Cartone cliente'), ('N', 'Cartone nostri'), ('P', 'Plastica')], max_length=1, verbose_name='Coni'),
        ),
        migrations.AlterField(
            model_name='artico',
            name='CONI',
            field=models.CharField(blank=True, choices=[('C', 'Cartone cliente'), ('N', 'Cartone nostri'), ('P', 'Plastica')], max_length=1, verbose_name='Coni'),
        ),
    ]
