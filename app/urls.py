"""URL configuration for app project.

The urlpatterns list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/

Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.templatetags.static import static
from django.urls import include, path
from django.views.generic import RedirectView


urlpatterns = [
    # Keep favicon available even when static is served separately.
    path(
        "favicon.ico",
        RedirectView.as_view(url=static("favicon.ico"), permanent=False),
    ),
    path("admin/", admin.site.urls),
    path("impersonate/", include("impersonate.urls")),
    path("academics/", include("app.academics.urls")),
    path("", include("app.website.urls")),  # this points to your landing page
]

handler400 = "app.website.views.errors.bad_request"
handler401 = "app.website.views.errors.unauthorized"
handler403 = "app.website.views.errors.forbidden"
handler404 = "app.website.views.errors.not_found"
handler408 = "app.website.views.errors.request_timeout"
handler429 = "app.website.views.errors.too_many_requests"
