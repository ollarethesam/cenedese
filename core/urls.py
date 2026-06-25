from django.urls import path
from . import views

urlpatterns = [
    # Main screen (barcode + search)
    path("",                                                     views.main_view,               name="main"),

    # AJAX: bagni dropdown for manual search
    path("client/<str:codcli>/bagni/",                           views.bagni_by_client,         name="bagni_by_client"),

    # NOTE: BAGNO codes can contain '/' (e.g. "2026/346"), hence <path:bagno>.
    # The bare detail route must stay LAST among the bagno/ routes: <path:>
    # is greedy and would otherwise swallow the /disposizione/ and
    # /lavorazioni/ suffixes.
    path("bagno/<str:codcli>/<path:bagno>/set-datcon/",           views.set_datcon_view,         name="set_datcon"),

    # Disposizione
    path("bagno/<str:codcli>/<path:bagno>/disposizione/",         views.disposizione_view,       name="disposizione"),

    # Lavorazioni
    path("bagno/<str:codcli>/<path:bagno>/lavorazioni/",          views.lavorazione_list_view,   name="lavorazione_list"),
    path("bagno/<str:codcli>/<path:bagno>/lavorazioni/new/",      views.lavorazione_create_view, name="lavorazione_create"),
    path("bagno/<str:codcli>/<path:bagno>/lavorazioni/<int:pk>/edit/",   views.lavorazione_edit_view,   name="lavorazione_edit"),
    path("bagno/<str:codcli>/<path:bagno>/lavorazioni/<int:pk>/delete/", views.lavorazione_delete_view, name="lavorazione_delete"),
    path("bagno/<str:codcli>/<path:bagno>/lavorazioni/<int:pk>/print/",  views.lavorazione_print_view,  name="lavorazione_print"),

    # Bagno detail (keep last — see note above)
    path("bagno/<str:codcli>/<path:bagno>/",                      views.bagno_detail_view,       name="bagno_detail"),

    # Calendar + fermi
    path("calendario/",                                           views.calendar_view,           name="calendar"),
    path("fermi/",                                                views.fermi_view,              name="fermi"),
]
