# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import ProfissionalViewSet, EstabelecimentoViewSet, RegistroPontoViewSet

router = DefaultRouter()
router.register(r'profissionais', ProfissionalViewSet, basename='profissionais')
router.register(r'estabelecimentos', EstabelecimentoViewSet, basename='estabelecimentos')
router.register(r'registros', RegistroPontoViewSet, basename='registros')

urlpatterns = [
    # Autenticação JWT
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # API endpoints
    path('', include(router.urls)),
]