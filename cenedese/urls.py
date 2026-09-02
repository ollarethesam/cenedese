from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

urlpatterns = [
    path("admin/",  admin.site.urls),
    path("login/",  auth_views.LoginView.as_view(template_name="core/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("",        include("core.urls")),
]

# MEDIA_URL carries the /cenedese prefix so templates emit public URLs, but
# Caddy strips it before Django sees the request — so the route itself must
# match the unprefixed path.
_media_route = "/media/" if settings.FORCE_SCRIPT_NAME else settings.MEDIA_URL
urlpatterns += static(_media_route, document_root=settings.MEDIA_ROOT)
