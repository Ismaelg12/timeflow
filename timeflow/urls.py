# from django.contrib import admin
# from django.urls import path, include
# from django.views.generic import TemplateView
# from django.conf import settings
# from django.contrib.auth import views as auth_views
# from django.conf.urls.static import static

# urlpatterns = [
#     # Página inicial pública
#     path('', TemplateView.as_view(template_name='home.html'), name='home'),
    
#     # ✅ Logout na raiz
#     path('sair/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    
#     # ✅ CORREÇÃO: Incluir usuarios.urls APENAS UMA VEZ
#     path('', include('usuarios.urls')),  # Isso inclui login, profissionais, etc. na raiz
    
#     # Outras URLs
#     path('admin/', admin.site.urls),
#     path('api/ponto/', include('ponto.urls')),
#     path('ponto/', include('ponto.urls')),
#     path('bemvindo/', include('core.urls')),
#     # Acesso API
#     path('api/', include('api.urls')),  
# ]

# if settings.DEBUG:
#     urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
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
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)