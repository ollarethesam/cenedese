"""
admin.py — Register all models with the Django admin site.
Useful for inspecting and editing data during development.
"""
from django.contrib import admin
from .models import (
    Client, Artico, Bagno,
    UserProfile, Dipendente,
    Disposizione, Lavorazione, Modifica,
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["CODCLI", "RAGSOC"]
    search_fields = ["CODCLI", "RAGSOC"]


@admin.register(Artico)
class ArticoAdmin(admin.ModelAdmin):
    list_display = ["CODART", "DESCRI", "TITOLO", "PESROC"]
    search_fields = ["CODART", "DESCRI"]


@admin.register(Bagno)
class BagnoAdmin(admin.ModelAdmin):
    list_display  = ["BAGNO", "CODCLI", "CODART", "DATCON", "QUAENT", "QUAUSC"]
    list_filter   = ["CODCLI"]
    search_fields = ["BAGNO", "CODCLI__CODCLI"]
    raw_id_fields = ["CODCLI", "CODART"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "tipo"]


@admin.register(Dipendente)
class DipendenteAdmin(admin.ModelAdmin):
    list_display = ["CODDIP", "NOME"]


@admin.register(Disposizione)
class DisposizioneAdmin(admin.ModelAdmin):
    list_display  = ["bagno", "TIPDIS", "CONI", "PARAFF", "NODI"]
    list_filter   = ["TIPDIS"]
    raw_id_fields = ["bagno"]


@admin.register(Lavorazione)
class LavorazioneAdmin(admin.ModelAdmin):
    list_display  = ["bagno", "TIPO", "STATO", "TURNO", "COLLABO", "DATORA"]
    list_filter   = ["TIPO", "STATO", "TURNO"]
    raw_id_fields = ["bagno"]
    readonly_fields = ["DATORA"]


@admin.register(Modifica)
class ModificaAdmin(admin.ModelAdmin):
    list_display  = ["bagno", "utente", "descrizione", "DATORA"]
    readonly_fields = ["DATORA"]
    raw_id_fields = ["bagno"]
