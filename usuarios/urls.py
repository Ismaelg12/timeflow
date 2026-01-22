# from django.urls import path
# from usuarios import views
# from django.contrib.auth import views as auth_views
# from django.contrib.auth.views import (PasswordResetView,
#  PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView)

# # ✅ DEFINA app_name (Opção A recomendada)
# app_name = 'usuarios'

# urlpatterns = [
#     # ✅ Login agora está em /login/ (definido no usuarios.urls)
#     path('login/', views.custom_login, name='login'),
    
#     # ✅ Logout REMOVIDO daqui (já está no urls.py principal)
#     # path('sair/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    
#     # Gestão de Profissionais - agora acessíveis em:
#     # /profissionais/, /adicionar/profissional/, etc.
#     path('profissionais/', views.profissionais, name='profissionais'),
#     path('profissionais/inativos/', views.profissionais_inativos, name='profissionais_inativos'),
#     path('adicionar/profissional/', views.add_profissional, name='cadastrar_profissional'),
#     path('atualizar/profissional/<int:pk>/', views.update_profissional, name='atualizar_profissional'),
#     path('profissional/detalhe/<int:pk>/detalhe/', views.profissional_detalhe, name='profissional_detalhe'),
#     path('desativar/profissional/<int:pk>/', views.desativar_profissional, name='desativar_profissional'),
#     path('ativar/profissional/<int:pk>/', views.ativar_profissional, name='ativar_profissional'),
    
#     # Áreas de Atuação
#     path('funcao', views.areatuacao, name='atuacoes'),
#     path('funcao/adicionar/', views.adicionar_areatuacao, name='add_atuacao'),
#     path('editar/funcao/<int:atuacao_id>/', views.update_atuacao, name='editar_atuacao'),
    
#     # Senha
#     path('accounts/password/', views.change_password_user, name='change_password'),
#     path('password/reset/', PasswordResetView.as_view(
#         template_name='registration/password_reset_form.html'), name='password_reset'),
#     path('accounts/password/reset/done', PasswordResetDoneView.as_view(
#         template_name='registration/password_reset_done.html'), name='password_reset_done'),
#     path('accounts/reset_password_confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(
#         template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
#     path('accounts/password/reset/complete', PasswordResetCompleteView.as_view(
#         template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
# ]
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