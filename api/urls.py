# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    ProfissionalViewSet, EstabelecimentoViewSet, 
    RegistroPontoViewSet, verificar_cpf_mobile, registrar_ponto_por_cpf
)

router = DefaultRouter()
router.register(r'profissionais', ProfissionalViewSet, basename='profissionais')
router.register(r'estabelecimentos', EstabelecimentoViewSet, basename='estabelecimentos')
router.register(r'registros', RegistroPontoViewSet, basename='registros')

urlpatterns = [
    # Autenticação JWT
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # ✅ CORREÇÃO: URLs CORRETAS para o Flutter
    path('verificar-cpf-mobile/', verificar_cpf_mobile, name='verificar_cpf_mobile'),
    path('registrar-ponto-por-cpf/', registrar_ponto_por_cpf, name='registrar_ponto_por_cpf'),
    
    # API endpoints protegidos
    path('', include(router.urls)),
]

# ✅ NÃO DEFINA app_name AQUI (já é API)