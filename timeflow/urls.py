# urls.py principal
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API
    path('api/', include('api.urls')),
    
    # Ponto - API REST apenas (sem interface web de registro)
    path('ponto/', include('ponto.urls')),
    
    # Usuários
    path('usuarios/', include('usuarios.urls')),
    
    # Core (Dashboard administrativo)
    path('', include('core.urls')),
    
    # Logout
    path('sair/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('afd/', include('afd.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)