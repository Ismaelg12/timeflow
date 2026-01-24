# api/views.py
import logging
from datetime import datetime, date, time as time_type

from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
import pytz
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication

from estabelecimentos.models import Estabelecimento
from ponto.models import RegistroPonto
from usuarios.models import Profissional
from .serializers import (
    ProfissionalSerializer, EstabelecimentoSerializer,
    RegistroPontoSerializer, RegistroPontoCreateSerializer
)

logger = logging.getLogger(__name__)


class ProfissionalViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ProfissionalSerializer
    
    def get_queryset(self):
        if hasattr(self.request.user, 'profissional'):
            return Profissional.objects.filter(usuario=self.request.user)
        return Profissional.objects.none()
    
    @action(detail=False, methods=['get'])
    def me(self, request):
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
        except Exception:
            logger.error("Erro ao buscar dados do profissional")
            return Response(
                {'error': 'Erro ao buscar dados'},
                status=status.HTTP_400_BAD_REQUEST
            )


class EstabelecimentoViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = EstabelecimentoSerializer
    
    def get_queryset(self):
        if hasattr(self.request.user, 'profissional'):
            profissional = self.request.user.profissional
            if profissional.estabelecimento:
                return Estabelecimento.objects.filter(id=profissional.estabelecimento.id)
        return Estabelecimento.objects.none()


class RegistroPontoViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = RegistroPontoSerializer
    
    def get_queryset(self):
        if hasattr(self.request.user, 'profissional'):
            profissional = self.request.user.profissional
            return RegistroPonto.objects.filter(
                profissional=profissional
            ).order_by('-data', '-horario')
        return RegistroPonto.objects.none()
    
    @action(detail=False, methods=['get'])
    def registros_hoje(self, request):
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
            
        except Exception:
            logger.error("Erro ao buscar registros do dia")
            return Response(
                {'error': 'Erro ao buscar registros'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def verificar_cpf_mobile(request):
    logger.info(f"Requisição verificar_cpf_mobile - Dados: {request.data}")
    
    cpf = request.data.get('cpf')
    
    if not cpf:
        return Response(
            {'sucesso': False, 'erro': 'CPF é obrigatório'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    cpf = ''.join(filter(str.isdigit, cpf))
    
    if len(cpf) != 11:
        return Response(
            {'sucesso': False, 'erro': 'CPF inválido. Deve conter 11 dígitos'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        cpf_formatado = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        
        profissional = Profissional.objects.filter(
            Q(cpf=cpf) | Q(cpf=cpf_formatado),
            ativo=True
        ).first()
        
        if not profissional:
            prof_inativo = Profissional.objects.filter(
                Q(cpf=cpf) | Q(cpf=cpf_formatado)
            ).first()
            
            if prof_inativo:
                return Response({
                    'sucesso': False,
                    'erro': f'Profissional inativo'
                }, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'sucesso': False,
                'erro': 'CPF não encontrado ou profissional inativo'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if not profissional.estabelecimento:
            return Response({
                'sucesso': False,
                'erro': 'Profissional não vinculado a um estabelecimento'
            }, status=status.HTTP_404_NOT_FOUND)
        
        hoje = timezone.now().date()
        estabelecimento = profissional.estabelecimento
        
        from ponto.utils import determinar_proximo_tipo
        proximo_tipo = determinar_proximo_tipo(profissional, estabelecimento, hoje)
        
        registros_hoje = RegistroPonto.objects.filter(
            profissional=profissional,
            data=hoje
        ).count()
        
        return Response({
            'sucesso': True,
            'mensagem': 'Profissional encontrado',
            'dados': {
                'profissional_id': profissional.id,
                'nome_completo': f"{profissional.nome}",
                'cpf': profissional.cpf,
                'cpf_limpo': cpf,
                'profissao': profissional.profissao.profissao if profissional.profissao else 'Não informado',
                'estabelecimento_id': estabelecimento.id,
                'estabelecimento_nome': estabelecimento.nome,
                'endereco': estabelecimento.endereco,
                'proximo_tipo': proximo_tipo,
                'proximo_tipo_formatado': 'ENTRADA' if proximo_tipo == 'ENTRADA' else 'SAÍDA',
                'horario_entrada': profissional.horario_entrada.strftime('%H:%M') if profissional.horario_entrada else '08:00',
                'horario_saida': profissional.horario_saida.strftime('%H:%M') if profissional.horario_saida else '17:00',
                'tolerancia_minutos': profissional.tolerancia_minutos or 10,
                'registros_hoje': registros_hoje,
                'latitude_estabelecimento': estabelecimento.latitude,
                'longitude_estabelecimento': estabelecimento.longitude,
                'raio_permitido': estabelecimento.raio_permitido
            },
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception:
        logger.error("Erro interno em verificar_cpf_mobile")
        return Response({
            'sucesso': False,
            'erro': 'Erro interno no servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def registrar_ponto_por_cpf(request):
    logger.info(f"Requisição registrar_ponto_por_cpf - Dados: {request.data}")
    
    cpf = request.data.get('cpf')
    latitude = request.data.get('latitude')
    longitude = request.data.get('longitude')
    
    if not cpf:
        return Response(
            {'sucesso': False, 'erro': 'CPF é obrigatório'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not latitude or not longitude:
        return Response(
            {'sucesso': False, 'erro': 'Localização não capturada. Ative o GPS.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    tz_brasilia = pytz.timezone('America/Sao_Paulo')
    agora = timezone.now().astimezone(tz_brasilia)
    hora_atual = agora.time()
    
    if hora_atual < time_type(5, 0) or hora_atual > time_type(23, 0):
        return Response(
            {'sucesso': False, 'erro': 'Registro fora do horário permitido (05:00 - 23:00)'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    cpf_limpo = ''.join(filter(str.isdigit, str(cpf)))
    
    if len(cpf_limpo) != 11:
        return Response(
            {'sucesso': False, 'erro': 'CPF inválido. Deve conter 11 dígitos'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        cpf_formatado = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"
        
        profissional = Profissional.objects.filter(
            Q(cpf=cpf_limpo) | Q(cpf=cpf_formatado),
            ativo=True
        ).first()
        
        if not profissional:
            prof_inativo = Profissional.objects.filter(
                Q(cpf=cpf_limpo) | Q(cpf=cpf_formatado)
            ).first()
            
            if prof_inativo:
                return Response(
                    {
                        'sucesso': False, 
                        'erro': f'Profissional inativo'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            return Response(
                {
                    'sucesso': False, 
                    'erro': 'CPF não encontrado ou profissional inativo'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not profissional.estabelecimento:
            return Response(
                {
                    'sucesso': False, 
                    'erro': 'Profissional sem estabelecimento vinculado'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        estabelecimento = profissional.estabelecimento
        
        def validar_localizacao(estab, lat, lng):
            try:
                lat_estab = float(estab.latitude)
                lng_estab = float(estab.longitude)
                lat_req = float(lat)
                lng_req = float(lng)
                
                lat_diff = lat_estab - lat_req
                lng_diff = lng_estab - lng_req
                distancia = (lat_diff**2 + lng_diff**2)**0.5 * 111000
                
                return distancia <= estab.raio_permitido
            except (TypeError, ValueError):
                logger.error("Erro no cálculo de distância")
                return False
        
        if not validar_localizacao(estabelecimento, latitude, longitude):
            return Response(
                {
                    'sucesso': False, 
                    'erro': f'Fora do raio permitido. Máximo: {estabelecimento.raio_permitido}m'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        hoje = agora.date()
        horario_atual = agora.time()
        
        from ponto.utils import determinar_proximo_tipo, verificar_registro_duplicado, calcular_tolerancia
        
        tipo = determinar_proximo_tipo(profissional, estabelecimento, hoje)
        
        if verificar_registro_duplicado(profissional, estabelecimento, hoje, tipo):
            tipo_oposto = 'SAIDA' if tipo == 'ENTRADA' else 'ENTRADA'
            
            registros_hoje = RegistroPonto.objects.filter(
                profissional=profissional,
                data=hoje
            ).order_by('horario')
            
            return Response(
                {
                    'sucesso': False, 
                    'erro': f'Já registrou {tipo.lower()} hoje. Próximo: {tipo_oposto.lower()}'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        atraso_minutos, dentro_tolerancia = calcular_tolerancia(
            profissional, horario_atual, tipo
        )
        
        registro = RegistroPonto(
            profissional=profissional,
            estabelecimento=estabelecimento,
            data=hoje,
            horario=horario_atual,
            tipo=tipo,
            latitude=latitude,
            longitude=longitude,
            atraso_minutos=atraso_minutos if tipo == 'ENTRADA' else 0,
            saida_antecipada_minutos=atraso_minutos if tipo == 'SAIDA' else 0,
            dentro_tolerancia=dentro_tolerancia
        )
        
        registro.save()
        
        tipo_formatado = 'ENTRADA' if tipo == 'ENTRADA' else 'SAÍDA'
        horario_formatado = horario_atual.strftime('%H:%M')
        
        if dentro_tolerancia:
            mensagem = f'{tipo_formatado} registrada às {horario_formatado}'
            status_registro = 'success'
        else:
            if tipo == 'ENTRADA':
                mensagem = f'Entrada registrada às {horario_formatado} ({atraso_minutos}min atraso)'
                status_registro = 'warning'
            else:
                mensagem = f'Saída registrada às {horario_formatado} ({atraso_minutos}min antecipada)'
                status_registro = 'warning'
        
        proximo_tipo = 'SAÍDA' if tipo == 'ENTRADA' else 'ENTRADA'
        mensagem_completa = f'{mensagem} | Próximo: {proximo_tipo}'
        
        registros_hoje = RegistroPonto.objects.filter(
            profissional=profissional,
            data=hoje
        ).order_by('horario')
        
        serializer = RegistroPontoSerializer(registros_hoje, many=True)
        
        response_data = {
            'sucesso': True,
            'mensagem': mensagem_completa,
            'status': status_registro,
            'dados': {
                'tipo': tipo,
                'tipo_formatado': tipo_formatado,
                'horario': horario_formatado,
                'data': hoje.strftime('%d/%m/%Y'),
                'dentro_tolerancia': dentro_tolerancia,
                'atraso_minutos': atraso_minutos if tipo == 'ENTRADA' else 0,
                'saida_antecipada_minutos': atraso_minutos if tipo == 'SAIDA' else 0,
                'proximo_tipo': 'SAIDA' if tipo == 'ENTRADA' else 'ENTRADA',
                'proximo_tipo_formatado': proximo_tipo,
                'registros_hoje': serializer.data,
                'total_registros_hoje': registros_hoje.count()
            },
            'profissional': {
                'id': profissional.id,
                'nome': profissional.get_full_name(),
                'cpf': profissional.cpf,
                'cpf_limpo': cpf_limpo,
                'profissao': profissional.profissao.profissao if profissional.profissao else 'Não informado'
            },
            'estabelecimento': {
                'id': estabelecimento.id,
                'nome': estabelecimento.nome,
                'endereco': estabelecimento.endereco,
                'latitude': estabelecimento.latitude,
                'longitude': estabelecimento.longitude,
                'raio_permitido': estabelecimento.raio_permitido
            },
            'registro': {
                'id': registro.id,
                'latitude': latitude,
                'longitude': longitude
            },
            'timestamp': agora.isoformat()
        }
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except ValueError:
        logger.error("Erro de validação em registrar_ponto_por_cpf")
        return Response(
            {'sucesso': False, 'erro': 'Erro de validação dos dados'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except IntegrityError:
        logger.error("Erro de integridade: Registro duplicado")
        return Response(
            {
                'sucesso': False, 
                'erro': 'Registro duplicado. Já bateu ponto agora.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception:
        logger.error("Erro interno em registrar_ponto_por_cpf")
        return Response(
            {
                'sucesso': False, 
                'erro': 'Erro interno no servidor'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def buscar_registros_historico(request):
    logger.info(f"Requisição buscar_registros_historico - Parâmetros: {request.GET}")
    
    cpf = request.GET.get('cpf')
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')
    
    if not cpf:
        return Response({
            'sucesso': False,
            'erro': 'CPF é obrigatório'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    cpf_limpo = ''.join(filter(str.isdigit, str(cpf)))
    
    if len(cpf_limpo) != 11:
        return Response({
            'sucesso': False,
            'erro': 'CPF inválido. Deve conter 11 dígitos'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        cpf_formatado = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"
        
        profissional = Profissional.objects.filter(
            Q(cpf=cpf_limpo) | Q(cpf=cpf_formatado),
            ativo=True
        ).first()
        
        if not profissional:
            return Response({
                'sucesso': False,
                'erro': 'Profissional não encontrado ou inativo'
            }, status=status.HTTP_404_NOT_FOUND)
        
        registros = RegistroPonto.objects.filter(
            profissional=profissional
        ).order_by('-data', '-horario')
        
        if data_inicio_str:
            try:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
                registros = registros.filter(data__gte=data_inicio)
            except ValueError:
                return Response({
                    'sucesso': False,
                    'erro': 'Formato de data_inicio inválido. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        if data_fim_str:
            try:
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
                registros = registros.filter(data__lte=data_fim)
            except ValueError:
                return Response({
                    'sucesso': False,
                    'erro': 'Formato de data_fim inválido. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        total_registros = registros.count()
        
        if total_registros > 500:
            registros = registros[:500]
        
        if total_registros == 0:
            return Response({
                'sucesso': True,
                'total_registros': 0,
                'mensagem': 'Nenhum registro encontrado para o período selecionado',
                'dados': []
            })
        
        serializer = RegistroPontoSerializer(registros, many=True, context={'request': request})
        
        registros_completo = RegistroPonto.objects.filter(
            profissional=profissional
        )
        
        if data_inicio_str:
            try:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
                registros_completo = registros_completo.filter(data__gte=data_inicio)
            except ValueError:
                pass
        
        if data_fim_str:
            try:
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
                registros_completo = registros_completo.filter(data__lte=data_fim)
            except ValueError:
                pass
        
        entradas = registros_completo.filter(tipo='ENTRADA').count()
        saidas = registros_completo.filter(tipo='SAIDA').count()
        
        profissional_data = {
            'id': profissional.id,
            'nome': profissional.nome,
            'cpf': profissional.cpf,
            'profissao': profissional.profissao.profissao if profissional.profissao else 'Não informado',
            'estabelecimento_nome': profissional.estabelecimento.nome if profissional.estabelecimento else None,
            'estabelecimento_cnpj': profissional.estabelecimento.cnpj if profissional.estabelecimento else None
        }
        
        return Response({
            'sucesso': True,
            'total_registros': total_registros,
            'total_entradas': entradas,
            'total_saidas': saidas,
            'profissional': profissional_data,
            'dados': serializer.data,
            'periodo': {
                'data_inicio': data_inicio_str,
                'data_fim': data_fim_str
            }
        })
        
    except Exception:
        logger.error("Erro interno em buscar_registros_historico")
        return Response({
            'sucesso': False,
            'erro': 'Erro interno no servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)