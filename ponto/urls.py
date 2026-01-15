from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views


router = DefaultRouter()
router.register(r'registros', views.RegistroPontoViewSet)

urlpatterns = [
    path('', include(router.urls)),
    
    # URLs para interface web
    path('tela-registro/', views.tela_registro_ponto, name='tela_registro_ponto'),
    path('registrar/', views.registrar_ponto_view, name='registrar_ponto'),
    path('verificar-cpf/', views.verificar_cpf, name='verificar_cpf'),
]