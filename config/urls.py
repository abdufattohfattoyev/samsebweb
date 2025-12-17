# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    # Admin panel
    path('admin/', admin.site.urls),

    # API endpoints
    path('api/payments/', include('payments.urls')),

    # Root redirect
    path('', RedirectView.as_view(url='/admin/', permanent=False)),
]

# Static va Media files (development)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin panel sozlamalari
admin.site.site_header = "Sebmarket Phone Pricing"
admin.site.site_title = "Sebmarket Admin"
admin.site.index_title = "Boshqaruv paneli"