"""
middleware.py — Request-level access control.

CameraOperatorMiddleware locks a camera operator's session to the barcode scan
page. Keeping the rule here (rather than as a per-view decorator) means a view
added later cannot forget it.
"""
from django.shortcuts import redirect


class CameraOperatorMiddleware:
    """
    A camera operator (UserProfile.tipo == 'C') may only reach the scan page and
    log out; every other route redirects back to the scanner. Superusers bypass
    the rule so the Django admin stays reachable.
    """

    ALLOWED_URL_NAMES = {"camera_scan", "camera_scan_save", "logout"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Runs once the URL has resolved, so request.resolver_match is set."""
        user = request.user
        if not user.is_authenticated or user.is_superuser:
            return None

        profile = getattr(user, "profile", None)
        if profile is None or profile.tipo != "C":
            return None

        match = request.resolver_match
        if match and match.url_name in self.ALLOWED_URL_NAMES:
            return None

        return redirect("camera_scan")
