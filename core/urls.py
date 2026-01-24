# core/urls.py
from django.urls import path
from . import views
from django.urls import path, include
from django.contrib.auth.views import LoginView, LogoutView
from usuarios.views import custom_login

app_name = 'core'  # ✅ APENAS UMA VEZ!

urlpatterns = [
    # Dashboard administrativo
     # LOGIN - Usa a view personalizada
    path('accounts/login/', custom_login, name='login'),
    
    # LOGOUT
    path('accounts/logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path('', views.dashboard, name='dashboard'),
    
    # Relatórios Gerais
    path('relatorios/', views.relatorios_gerais, name='relatorios_gerais'),
    path('relatorios/profissional/<int:profissional_id>/', views.relatorio_profissional, name='relatorio_profissional'),
    path('relatorios/profissional/<int:profissional_id>/pdf/', views.relatorio_profissional_pdf, name='relatorio_profissional_pdf'),
    
    # Histórico e Estatísticas
    path('profissional/<int:profissional_id>/historico/', views.historico_pontos_profissional, name='historico_pontos'),
    path('profissional/<int:profissional_id>/horas/', views.horas_trabalhadas_profissional, name='horas_trabalhadas'),
    path('profissional/<int:profissional_id>/frequencia/', views.analise_frequencia_profissional, name='analise_frequencia'),
    path('profissional/<int:profissional_id>/consolidado/', views.relatorio_consolidado_profissional, name='relatorio_consolidado'),
    
    # Perfil do usuário
    path('meu-perfil/', views.meu_perfil, name='meu_perfil'),
]