# usuarios/urls.py
from django.urls import path
from usuarios import views

app_name = 'usuarios'

urlpatterns = [
    # ========== CADASTRO PÚBLICO ==========
    path('cadastro/', views.solicitar_cadastro, name='solicitar_cadastro'),
    path('cadastro-sucesso/<int:id>/', views.cadastro_sucesso, name='cadastro_sucesso'),
    
    # ========== GERENCIAMENTO (APENAS ADMIN) ==========
    path('profissionais/', views.listar_profissionais, name='listar_profissionais'),
    path('profissionais/<int:id>/', views.detalhar_profissional, name='detalhar_profissional'),
    path('profissionais/<int:id>/aprovar/', views.aprovar_profissional, name='aprovar_profissional'),
    path('profissionais/<int:id>/desativar/', views.desativar_profissional, name='desativar_profissional'),
    path('profissionais/<int:id>/editar/', views.editar_profissional, name='editar_profissional'),
]