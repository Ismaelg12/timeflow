from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Relatórios Gerais
    path('relatorios/', views.relatorios_gerais, name='relatorios_gerais'),
    path('relatorios/profissional/<int:profissional_id>/', views.relatorio_profissional, name='relatorio_profissional'),
    path('relatorios/profissional/<int:profissional_id>/pdf/', views.relatorio_profissional_pdf, name='relatorio_profissional_pdf'),  # ✅ NOVA URL
    
    # Histórico e Estatísticas
    path('profissional/<int:profissional_id>/historico/', views.historico_pontos_profissional, name='historico_pontos'),
    path('profissional/<int:profissional_id>/horas/', views.horas_trabalhadas_profissional, name='horas_trabalhadas'),
    path('profissional/<int:profissional_id>/frequencia/', views.analise_frequencia_profissional, name='analise_frequencia'),
    path('profissional/<int:profissional_id>/consolidado/', views.relatorio_consolidado_profissional, name='relatorio_consolidado'),
    
    # Perfil
    path('meu-perfil/', views.meu_perfil, name='meu_perfil'),
]