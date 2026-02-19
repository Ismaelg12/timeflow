# ponto/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'registros', views.RegistroPontoViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('ajuste-manual/', views.ajuste_manual_registro, name='ajuste_manual'),
    path('ajuste-manual/<int:profissional_id>/', views.ajuste_manual_registro, name='ajuste_manual_profissional'),
    path('meus-ajustes/', views.meus_ajustes_solicitados, name='meus_ajustes'),
    path('lista-ajustes/', views.lista_ajustes_manuais, name='lista_ajustes_manuais'),
    path('registro-manual/saida/', views.registro_manual_saida, name='registro_manual_saida'),
    path('api/dias-incompletos/<int:profissional_id>/', 
         views.verificar_dias_incompletos_api, name='api_dias_incompletos'),
    path('api/registro/<int:registro_id>/', 
         views.get_detalhes_registro_api, name='api_detalhes_registro'),
    path('registro-manual/excluir/<int:registro_id>/', 
         views.excluir_registro_manual, name='excluir_registro_manual'),
    path('api/dias-incompletos-batch/', 
         views.verificar_dias_incompletos_batch, name='api_dias_incompletos_batch'),
]