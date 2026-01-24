# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# Importe de views.py
from .views import (
    ProfissionalViewSet, 
    EstabelecimentoViewSet, 
    RegistroPontoViewSet, 
    verificar_cpf_mobile, 
    registrar_ponto_por_cpf,
    buscar_registros_historico
)

# Importe de views_comprovantes.py (se criou arquivo separado)
from .views_comprovantes import (
    comprovante_completo,
    gerar_comprovante_pdf,
    gerar_qr_code,
    validar_registro
)

router = DefaultRouter()
router.register(r'profissionais', ProfissionalViewSet, basename='profissionais')
router.register(r'estabelecimentos', EstabelecimentoViewSet, basename='estabelecimentos')
router.register(r'registros', RegistroPontoViewSet, basename='registros')

urlpatterns = [
    # Autenticação JWT
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # URLs PÚBLICAS para o Flutter
    path('verificar-cpf-mobile/', verificar_cpf_mobile, name='verificar_cpf_mobile'),
    path('registrar-ponto-por-cpf/', registrar_ponto_por_cpf, name='registrar_ponto_por_cpf'),
    
    # ENDPOINT DE HISTÓRICO
    path('buscar-registros-historico/', buscar_registros_historico, name='buscar_registros_historico'),
    
    # ✅ NOVOS ENDPOINTS PARA COMPROVANTES (PORTARIA 671)
    path('comprovante/<int:registro_id>/', comprovante_completo, name='comprovante_completo'),
    path('comprovante/<int:registro_id>/pdf/', gerar_comprovante_pdf, name='comprovante_pdf'),
    path('comprovante/<int:registro_id>/qr-code/', gerar_qr_code, name='qr_code'),
    path('comprovante/<int:registro_id>/validar/', validar_registro, name='validar_registro'),
    
    # API endpoints protegidos (ViewSets)
    path('', include(router.urls)),
]