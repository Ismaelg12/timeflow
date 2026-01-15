# api/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils import timezone
from datetime import datetime, date
import pytz

from usuarios.models import Profissional
from ponto.models import RegistroPonto
from estabelecimentos.models import Estabelecimento
from .serializers import (
    ProfissionalSerializer, EstabelecimentoSerializer,
    RegistroPontoSerializer, RegistroPontoCreateSerializer
)

class ProfissionalViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ProfissionalSerializer
    
    def get_queryset(self):
        # ✅ CORREÇÃO: Verifica se o usuário tem perfil profissional
        if hasattr(self.request.user, 'profissional'):
            return Profissional.objects.filter(usuario=self.request.user)
        return Profissional.objects.none()
    
    # ✅ NOVO: Endpoint para obter dados do profissional logado
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Retorna dados do profissional logado"""
        try:
            if hasattr(request.user, 'profissional'):
                profissional = request.user.profissional
                serializer = self.get_serializer(profissional)
                return Response(serializer.data)
            else:
                return Response(
                    {'error': 'Usuário não possui perfil profissional'},
                    status=status.HTTP_404_NOT_FOUND
                )
        except Exception as e:
            return Response(
                {'error': f'Erro ao buscar dados: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

class EstabelecimentoViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = EstabelecimentoSerializer
    
    def get_queryset(self):
        # ✅ CORREÇÃO: Retorna estabelecimento do profissional
        if hasattr(self.request.user, 'profissional'):
            profissional = self.request.user.profissional
            if profissional.estabelecimento:
                return Estabelecimento.objects.filter(id=profissional.estabelecimento.id)
        return Estabelecimento.objects.none()

class RegistroPontoViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'registrar_ponto']:
            return RegistroPontoCreateSerializer
        return RegistroPontoSerializer
    
    def get_queryset(self):
        # ✅ CORREÇÃO: Filtra registros do profissional logado
        if hasattr(self.request.user, 'profissional'):
            profissional = self.request.user.profissional
            return RegistroPonto.objects.filter(
                profissional=profissional
            ).order_by('-data', '-horario')
        return RegistroPonto.objects.none()
    
    def perform_create(self, serializer):
        # ✅ CORREÇÃO: Define profissional automaticamente
        if hasattr(self.request.user, 'profissional'):
            profissional = self.request.user.profissional
            # ✅ Define estabelecimento do profissional automaticamente
            serializer.save(
                profissional=profissional,
                estabelecimento=profissional.estabelecimento
            )
    
    # ✅ CORREÇÃO: Endpoint simplificado para registrar ponto
    @action(detail=False, methods=['post'])
    def registrar_ponto(self, request):
        """Endpoint simplificado para registrar ponto"""
        try:
            if not hasattr(request.user, 'profissional'):
                return Response(
                    {'error': 'Usuário não possui perfil profissional'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            profissional = request.user.profissional
            estabelecimento = profissional.estabelecimento
            
            # ✅ CORREÇÃO: Verifica se o profissional tem estabelecimento
            if not estabelecimento:
                return Response(
                    {'error': 'Profissional não vinculado a um estabelecimento'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obtém dados da requisição
            tipo = request.data.get('tipo')
            latitude = request.data.get('latitude')
            longitude = request.data.get('longitude')
            
            # ✅ CORREÇÃO: Validações mais robustas
            if not tipo:
                return Response(
                    {'error': 'Tipo de registro é obrigatório'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            tipo = tipo.upper()
            if tipo not in ['ENTRADA', 'SAIDA']:
                return Response(
                    {'error': 'Tipo de registro inválido. Use ENTRADA ou SAIDA.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if latitude is None or longitude is None:
                return Response(
                    {'error': 'Coordenadas de localização são obrigatórias.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                latitude = float(latitude)
                longitude = float(longitude)
            except (TypeError, ValueError):
                return Response(
                    {'error': 'Coordenadas devem ser números válidos.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # ✅ CORREÇÃO: Timezone do Brasil
            tz_brasilia = pytz.timezone('America/Sao_Paulo')
            agora = timezone.now().astimezone(tz_brasilia)
            
            # ✅ CORREÇÃO: Verifica se já existe registro do mesmo tipo no mesmo dia
            registro_existente = RegistroPonto.objects.filter(
                profissional=profissional,
                data=agora.date(),
                tipo=tipo
            ).exists()
            
            if registro_existente:
                return Response(
                    {'error': f'Já existe um registro de {tipo.lower()} para hoje'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # ✅ CORREÇÃO: Cria o registro usando o serializer
            serializer = RegistroPontoCreateSerializer(data={
                'profissional': profissional.id,
                'estabelecimento': estabelecimento.id,
                'data': agora.date(),
                'horario': agora.time(),
                'tipo': tipo,
                'latitude': latitude,
                'longitude': longitude
            })
            
            if serializer.is_valid():
                registro = serializer.save()
                response_serializer = RegistroPontoSerializer(registro)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {'error': 'Dados inválidos', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except Exception as e:
            return Response(
                {'error': f'Erro ao registrar ponto: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def registros_hoje(self, request):
        """Retorna os registros do dia atual"""
        try:
            if not hasattr(request.user, 'profissional'):
                return Response(
                    {'error': 'Usuário não possui perfil profissional'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            profissional = request.user.profissional
            hoje = timezone.now().date()
            
            registros = RegistroPonto.objects.filter(
                profissional=profissional,
                data=hoje
            ).order_by('horario')
            
            serializer = RegistroPontoSerializer(registros, many=True)
            return Response({
                'data': serializer.data,
                'total': registros.count(),
                'data_consulta': hoje.isoformat()
            })
            
        except Exception as e:
            return Response(
                {'error': f'Erro ao buscar registros: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def status_hoje(self, request):
        """Retorna o status do ponto hoje (último registro)"""
        try:
            if not hasattr(request.user, 'profissional'):
                return Response(
                    {'error': 'Usuário não possui perfil profissional'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            profissional = request.user.profissional
            hoje = timezone.now().date()
            
            ultimo_registro = RegistroPonto.objects.filter(
                profissional=profissional,
                data=hoje
            ).order_by('-horario').first()
            
            registros_hoje = RegistroPonto.objects.filter(
                profissional=profissional,
                data=hoje
            )
            
            status_info = {
                'ultimo_registro': None,
                'proximo_tipo': 'ENTRADA',  # Se não há registros, próximo é entrada
                'registros_hoje': registros_hoje.count(),
                'data_hoje': hoje.isoformat(),
                'horarios_esperados': {
                    'entrada': profissional.horario_entrada.strftime('%H:%M') if profissional.horario_entrada else None,
                    'saida': profissional.horario_saida.strftime('%H:%M') if profissional.horario_saida else None,
                    'tolerancia_minutos': profissional.tolerancia_minutos
                }
            }
            
            if ultimo_registro:
                serializer = RegistroPontoSerializer(ultimo_registro)
                status_info['ultimo_registro'] = serializer.data
                status_info['proximo_tipo'] = 'SAIDA' if ultimo_registro.tipo == 'ENTRADA' else 'ENTRADA'
            
            return Response(status_info)
            
        except Exception as e:
            return Response(
                {'error': f'Erro ao buscar status: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # ✅ NOVO: Endpoint para relatório por período
    @action(detail=False, methods=['get'])
    def relatorio(self, request):
        """Retorna relatório de registros por período"""
        try:
            if not hasattr(request.user, 'profissional'):
                return Response(
                    {'error': 'Usuário não possui perfil profissional'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            profissional = request.user.profissional
            
            # Parâmetros de data
            data_inicio = request.GET.get('data_inicio')
            data_fim = request.GET.get('data_fim') or timezone.now().date().isoformat()
            
            if not data_inicio:
                # Padrão: início do mês atual
                hoje = timezone.now().date()
                data_inicio = hoje.replace(day=1).isoformat()
            
            # Filtra registros
            registros = RegistroPonto.objects.filter(
                profissional=profissional,
                data__gte=data_inicio,
                data__lte=data_fim
            ).order_by('-data', '-horario')
            
            serializer = RegistroPontoSerializer(registros, many=True)
            
            # Estatísticas básicas
            total_registros = registros.count()
            entradas = registros.filter(tipo='ENTRADA').count()
            saidas = registros.filter(tipo='SAIDA').count()
            
            return Response({
                'data_inicio': data_inicio,
                'data_fim': data_fim,
                'registros': serializer.data,
                'estatisticas': {
                    'total_registros': total_registros,
                    'entradas': entradas,
                    'saidas': saidas
                }
            })
            
        except Exception as e:
            return Response(
                {'error': f'Erro ao gerar relatório: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )