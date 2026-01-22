# api/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils import timezone
from datetime import datetime, date, time as time_type
from django.db import IntegrityError
import pytz

from usuarios.models import Profissional
from ponto.models import RegistroPonto
from estabelecimentos.models import Estabelecimento
from .serializers import (
    ProfissionalSerializer, EstabelecimentoSerializer,
    RegistroPontoSerializer, RegistroPontoCreateSerializer
)

# ✅ ViewSet para Profissionais (apenas para usuários autenticados)
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

# ✅ ViewSet para Estabelecimentos
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

# ✅ ViewSet para RegistroPonto
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


# ✅ ADICIONE ESTES IMPORTS NO TOPO DO ARQUIVO views.py
import logging
logger = logging.getLogger(__name__)

from django.db.models import Q  # ✅ ADICIONE ESTE IMPORT

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def verificar_cpf_mobile(request):
    """
    Endpoint para verificar CPF e retornar dados do profissional
    Usado pelo app mobile - usuário digita apenas CPF
    """
    # ✅ LOG 1: Request completa
    logger.info("=" * 50)
    logger.info("📱 NOVA REQUISIÇÃO verificar_cpf_mobile")
    logger.info(f"📦 Dados recebidos: {request.data}")
    
    cpf = request.data.get('cpf')
    
    # ✅ LOG 2: CPF recebido
    logger.info(f"📋 CPF recebido na request (raw): '{cpf}'")
    
    if not cpf:
        logger.error("❌ ERRO: CPF não fornecido na requisição")
        return Response(
            {'sucesso': False, 'erro': 'CPF é obrigatório'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # ✅ Limpar e validar CPF
    cpf_original = cpf
    cpf = ''.join(filter(str.isdigit, cpf))
    
    # ✅ LOG 3: CPF após limpeza
    logger.info(f"🧹 CPF após limpeza: '{cpf}'")
    logger.info(f"📏 Tamanho do CPF limpo: {len(cpf)} dígitos")
    
    if len(cpf) != 11:
        logger.error(f"❌ ERRO: CPF inválido. Tem {len(cpf)} dígitos, precisa ter 11")
        return Response(
            {'sucesso': False, 'erro': 'CPF inválido. Deve conter 11 dígitos'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # ✅✅✅ CORREÇÃO AQUI: Criar a versão formatada do CPF
        cpf_formatado = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        logger.info(f"🎯 CPF formatado para busca: '{cpf_formatado}'")
        
        # ✅ LOG 4: Tentando buscar no banco com AMBAS as versões
        logger.info(f"🔍 Buscando profissional com:")
        logger.info(f"   1. CPF='{cpf}' (sem formatação) E ativo=True")
        logger.info(f"   2. CPF='{cpf_formatado}' (com formatação) E ativo=True")
        
        # ✅✅✅ BUSCA CORRIGIDA: Procurar por AMBAS as formatações
        profissional = Profissional.objects.filter(
            Q(cpf=cpf) | Q(cpf=cpf_formatado),  # ✅ Busca por AMBOS os formatos
            ativo=True
        ).first()  # ✅ Usar .first() em vez de .get()
        
        if not profissional:
            logger.error(f"❌ Nenhum profissional encontrado com CPF '{cpf}' ou '{cpf_formatado}' e ativo=True")
            
            # Verificar se existe mas está inativo
            prof_inativo = Profissional.objects.filter(
                Q(cpf=cpf) | Q(cpf=cpf_formatado)
            ).first()
            
            if prof_inativo:
                logger.error(f"   ⚠️ Profissional EXISTE mas ativo={prof_inativo.ativo}")
                return Response({
                    'sucesso': False,
                    'erro': f'Profissional inativo (status: {prof_inativo.ativo})'
                }, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'sucesso': False,
                'erro': 'CPF não encontrado ou profissional inativo'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # ✅ LOG 5: Profissional encontrado
        logger.info(f"✅ PROFISSIONAL ENCONTRADO!")
        logger.info(f"   ID: {profissional.id}")
        logger.info(f"   Nome: {profissional.nome} {profissional.sobrenome}")
        logger.info(f"   CPF no banco: '{profissional.cpf}'")  # Vai mostrar '000.689.053-94'
        logger.info(f"   Ativo: {profissional.ativo}")
        
        # Verificar se tem estabelecimento
        if not profissional.estabelecimento:
            logger.error("❌ ERRO: Profissional não tem estabelecimento vinculado")
            return Response({
                'sucesso': False,
                'erro': 'Profissional não vinculado a um estabelecimento'
            })
        
        # Determinar próximo tipo de registro
        hoje = timezone.now().date()
        estabelecimento = profissional.estabelecimento
        
        # Importar funções utilitárias
        from ponto.utils import determinar_proximo_tipo
        proximo_tipo = determinar_proximo_tipo(profissional, estabelecimento, hoje)
        
        # Verificar se já bateu o ponto hoje
        registros_hoje = RegistroPonto.objects.filter(
            profissional=profissional,
            data=hoje
        ).count()
        
        # ✅ LOG 6: Dados completos para resposta
        logger.info(f"🏢 Estabelecimento: {estabelecimento.nome}")
        logger.info(f"📅 Data atual: {hoje}")
        logger.info(f"🎯 Próximo tipo: {proximo_tipo}")
        logger.info(f"📊 Registros hoje: {registros_hoje}")
        logger.info("=" * 50)
        
        # Preparar resposta
        return Response({
            'sucesso': True,
            'mensagem': 'Profissional encontrado',
            'dados': {
                'profissional_id': profissional.id,
                'nome_completo': f"{profissional.nome} {profissional.sobrenome}",
                'cpf': profissional.cpf,  # Vai retornar '000.689.053-94'
                'cpf_limpo': cpf,  # Adiciona também a versão sem formatação
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
        
    except Exception as e:
        logger.error(f"💥 ERRO INTERNO: {str(e)}")
        logger.error(f"   Tipo do erro: {type(e)}")
        import traceback
        logger.error(f"   Traceback: {traceback.format_exc()}")
        logger.error("=" * 50)
        
        return Response({
            'sucesso': False,
            'erro': f'Erro interno: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
# ✅ ADICIONE ESTE IMPORT NO TOPO DO ARQUIVO (views.py)
from django.db.models import Q

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def registrar_ponto_por_cpf(request):
    """
    Endpoint público para registro de ponto apenas com CPF.
    Latitude e longitude são capturadas automaticamente pelo GPS do dispositivo.
    """
    # ✅ LOG 1: Request completa
    logger.info("=" * 70)
    logger.info("📍🔥 NOVA REQUISIÇÃO registrar_ponto_por_cpf 🔥📍")
    logger.info(f"📦 Dados recebidos: {request.data}")
    logger.info(f"🔧 Método: {request.method}")
    logger.info(f"🌐 Path: {request.path}")
    
    # Dados da requisição
    cpf = request.data.get('cpf')
    latitude = request.data.get('latitude')
    longitude = request.data.get('longitude')
    
    # Validações básicas
    if not cpf:
        logger.error("❌ ERRO: CPF não fornecido")
        return Response(
            {'sucesso': False, 'erro': 'CPF é obrigatório'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not latitude or not longitude:
        logger.error("❌ ERRO: Latitude ou longitude não fornecidas")
        return Response(
            {'sucesso': False, 'erro': 'Localização não capturada. Ative o GPS.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # ✅ Validação de horário comercial (proteção)
    tz_brasilia = pytz.timezone('America/Sao_Paulo')
    agora = timezone.now().astimezone(tz_brasilia)
    hora_atual = agora.time()
    
    # ✅ LOG 2: Horário atual
    logger.info(f"🕒 Horário atual: {hora_atual}")
    logger.info(f"📅 Data atual: {agora.date()}")
    
    # Permitir registro das 5h às 23h
    if hora_atual < time_type(5, 0) or hora_atual > time_type(23, 0):
        logger.error(f"❌ ERRO: Horário fora do permitido: {hora_atual}")
        return Response(
            {'sucesso': False, 'erro': 'Registro fora do horário permitido (05:00 - 23:00)'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # ✅ Limpar e validar CPF
    cpf_original = cpf
    cpf_limpo = ''.join(filter(str.isdigit, str(cpf)))
    
    # ✅ LOG 3: CPF processado
    logger.info(f"🔢 CPF original: '{cpf_original}'")
    logger.info(f"🧹 CPF limpo: '{cpf_limpo}'")
    logger.info(f"📏 Tamanho CPF limpo: {len(cpf_limpo)} dígitos")
    
    if len(cpf_limpo) != 11:
        logger.error(f"❌ ERRO: CPF inválido, tamanho: {len(cpf_limpo)}")
        return Response(
            {'sucesso': False, 'erro': 'CPF inválido. Deve conter 11 dígitos'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # ✅✅✅ CORREÇÃO CRÍTICA: Buscar profissional com formatação flexível
        
        # Gerar versão formatada do CPF (000.689.053-94)
        cpf_formatado = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"
        logger.info(f"🎯 Buscando profissional com:")
        logger.info(f"   1. CPF limpo: '{cpf_limpo}'")
        logger.info(f"   2. CPF formatado: '{cpf_formatado}'")
        
        # ✅ BUSCA FLEXÍVEL: Procurar por AMBAS as formatações
        profissional = Profissional.objects.filter(
            Q(cpf=cpf_limpo) | Q(cpf=cpf_formatado),  # ✅ Busca por AMBOS os formatos
            ativo=True
        ).first()  # ✅ Usar .first() em vez de .get()
        
        if not profissional:
            logger.error(f"❌ Nenhum profissional encontrado com CPF '{cpf_limpo}' ou '{cpf_formatado}' e ativo=True")
            
            # Verificar se existe mas está inativo (para debug)
            prof_inativo = Profissional.objects.filter(
                Q(cpf=cpf_limpo) | Q(cpf=cpf_formatado)
            ).first()
            
            if prof_inativo:
                logger.error(f"   ⚠️ Profissional EXISTE mas ativo={prof_inativo.ativo}")
                logger.error(f"   📊 Detalhes: ID={prof_inativo.id}, Nome={prof_inativo.nome}")
                return Response(
                    {
                        'sucesso': False, 
                        'erro': f'Profissional inativo (status: {prof_inativo.ativo})',
                        'debug_info': {
                            'cpf_buscado': cpf_limpo,
                            'cpf_formatado_buscado': cpf_formatado,
                            'cpf_no_banco': prof_inativo.cpf,
                            'profissional_id': prof_inativo.id,
                            'nome': prof_inativo.nome
                        }
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Listar TODOS os profissionais para debug
            logger.error(f"   📋 Listando TODOS os profissionais no banco:")
            todos = Profissional.objects.all()
            for p in todos:
                logger.error(f"      ID:{p.id} | CPF:'{p.cpf}' | Nome:{p.nome} | Ativo:{p.ativo}")
            
            return Response(
                {
                    'sucesso': False, 
                    'erro': 'CPF não encontrado ou profissional inativo',
                    'debug_info': {
                        'cpf_buscado': cpf_limpo,
                        'cpf_formatado_buscado': cpf_formatado,
                        'sugestao': 'Verifique logs do servidor para mais detalhes'
                    }
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # ✅ LOG 5: Profissional encontrado
        logger.info(f"✅✅ PROFISSIONAL ENCONTRADO! ✅✅")
        logger.info(f"   📊 ID: {profissional.id}")
        logger.info(f"   👤 Nome: {profissional.nome} {profissional.sobrenome}")
        logger.info(f"   🔢 CPF no banco: '{profissional.cpf}'")  # Vai mostrar '000.689.053-94'
        logger.info(f"   ✅ Ativo: {profissional.ativo}")
        logger.info(f"   📌 Formato encontrado: {'Formatado' if '.' in str(profissional.cpf) else 'Sem formatação'}")
        
        if not profissional.estabelecimento:
            logger.error("❌ ERRO: Profissional sem estabelecimento vinculado")
            return Response(
                {
                    'sucesso': False, 
                    'erro': 'Profissional sem estabelecimento vinculado',
                    'profissional': {
                        'id': profissional.id,
                        'nome': profissional.get_full_name()
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        estabelecimento = profissional.estabelecimento
        logger.info(f"🏢 Estabelecimento: {estabelecimento.nome} (ID: {estabelecimento.id})")
        logger.info(f"📍 Endereço: {estabelecimento.endereco}")
        logger.info(f"📡 Coordenadas: {estabelecimento.latitude}, {estabelecimento.longitude}")
        logger.info(f"🎯 Raio permitido: {estabelecimento.raio_permitido}m")
        
        # ✅ Validar localização
        def validar_localizacao(estab, lat, lng):
            try:
                lat_estab = float(estab.latitude)
                lng_estab = float(estab.longitude)
                lat_req = float(lat)
                lng_req = float(lng)
                
                lat_diff = lat_estab - lat_req
                lng_diff = lng_estab - lng_req
                distancia = (lat_diff**2 + lng_diff**2)**0.5 * 111000  # metros
                
                logger.info(f"📍 Cálculo distância:")
                logger.info(f"   Estabelecimento: {lat_estab}, {lng_estab}")
                logger.info(f"   Dispositivo: {lat_req}, {lng_req}")
                logger.info(f"   Diferenças: lat_diff={lat_diff:.6f}, lng_diff={lng_diff:.6f}")
                logger.info(f"   Distância calculada: {distancia:.2f}m")
                logger.info(f"   Raio permitido: {estab.raio_permitido}m")
                logger.info(f"   Dentro do raio? {distancia <= estab.raio_permitido}")
                
                return distancia <= estab.raio_permitido
            except (TypeError, ValueError) as e:
                logger.error(f"❌ ERRO no cálculo de distância: {e}")
                logger.error(f"   Tipo latitude: {type(lat)}, valor: '{lat}'")
                logger.error(f"   Tipo longitude: {type(lng)}, valor: '{lng}'")
                return False
        
        if not validar_localizacao(estabelecimento, latitude, longitude):
            logger.error(f"❌ ERRO: Localização fora do raio permitido")
            return Response(
                {
                    'sucesso': False, 
                    'erro': f'Fora do raio permitido. Máximo: {estabelecimento.raio_permitido}m',
                    'estabelecimento': {
                        'nome': estabelecimento.nome,
                        'endereco': estabelecimento.endereco,
                        'latitude': estabelecimento.latitude,
                        'longitude': estabelecimento.longitude,
                        'raio_permitido': estabelecimento.raio_permitido
                    },
                    'localizacao_dispositivo': {
                        'latitude': latitude,
                        'longitude': longitude
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determinar tipo de registro
        hoje = agora.date()
        horario_atual = agora.time()
        logger.info(f"📅 Data do registro: {hoje}")
        logger.info(f"🕒 Horário do registro: {horario_atual}")
        
        # ✅ Importar funções utilitárias
        try:
            from ponto.utils import determinar_proximo_tipo, verificar_registro_duplicado, calcular_tolerancia
            
            # ✅ Determinar próximo tipo
            tipo = determinar_proximo_tipo(profissional, estabelecimento, hoje)
            logger.info(f"🎯 Tipo de registro determinado: {tipo}")
            
            # ✅ Verificar se já existe registro do mesmo tipo
            if verificar_registro_duplicado(profissional, estabelecimento, hoje, tipo):
                tipo_oposto = 'SAIDA' if tipo == 'ENTRADA' else 'ENTRADA'
                logger.error(f"❌ ERRO: Registro duplicado do tipo {tipo}")
                
                # Buscar registros do dia para mostrar
                registros_hoje = RegistroPonto.objects.filter(
                    profissional=profissional,
                    data=hoje
                ).order_by('horario')
                
                return Response(
                    {
                        'sucesso': False, 
                        'erro': f'Já registrou {tipo.lower()} hoje. Próximo: {tipo_oposto.lower()}',
                        'registros_hoje': RegistroPontoSerializer(registros_hoje, many=True).data if registros_hoje.exists() else [],
                        'total_registros': registros_hoje.count()
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # ✅ Calcular tolerâncias e atrasos
            atraso_minutos, dentro_tolerancia = calcular_tolerancia(
                profissional, horario_atual, tipo
            )
            logger.info(f"⏰ Atraso/antecipação: {atraso_minutos}min")
            logger.info(f"✅ Dentro da tolerância? {dentro_tolerancia}")
            
        except ImportError as e:
            logger.error(f"❌ ERRO: Não foi possível importar funções utilitárias: {e}")
            # Valores padrão se não conseguir importar
            tipo = 'ENTRADA'  # Valor padrão
            atraso_minutos = 0
            dentro_tolerancia = True
            logger.warning(f"⚠️ Usando valores padrão: tipo={tipo}, atraso={atraso_minutos}min")
        
        # ✅ Criar registro
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
        
        # Salvar
        registro.save()
        logger.info(f"💾 Registro salvo com ID: {registro.id}")
        logger.info(f"📝 Detalhes do registro:")
        logger.info(f"   Tipo: {tipo}")
        logger.info(f"   Data: {hoje}")
        logger.info(f"   Horário: {horario_atual}")
        logger.info(f"   Localização: {latitude}, {longitude}")
        
        # ✅ Mensagem de sucesso
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
        
        # Adicionar informação do próximo registro
        proximo_tipo = 'SAÍDA' if tipo == 'ENTRADA' else 'ENTRADA'
        mensagem_completa = f'{mensagem} | Próximo: {proximo_tipo}'
        
        # Buscar registros do dia para resposta
        registros_hoje = RegistroPonto.objects.filter(
            profissional=profissional,
            data=hoje
        ).order_by('horario')
        
        serializer = RegistroPontoSerializer(registros_hoje, many=True)
        
        logger.info(f"✅ Registro concluído com sucesso!")
        logger.info(f"📤 Mensagem: {mensagem_completa}")
        logger.info(f"📊 Total de registros hoje: {registros_hoje.count()}")
        logger.info("=" * 70)
        
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
                'cpf_limpo': cpf_limpo,  # Adiciona versão sem formatação
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
        
    except ValueError as e:
        logger.error(f"❌ ERRO de validação: {str(e)}")
        import traceback
        logger.error(f"   Traceback: {traceback.format_exc()}")
        logger.error("=" * 70)
        
        return Response(
            {'sucesso': False, 'erro': f'Erro de validação: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except IntegrityError as e:
        logger.error(f"❌ ERRO: Registro duplicado (IntegrityError): {e}")
        logger.error("   Provavelmente já existe um registro com os mesmos dados")
        logger.error("=" * 70)
        
        return Response(
            {
                'sucesso': False, 
                'erro': 'Registro duplicado. Já bateu ponto agora.',
                'debug_info': str(e)
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"💥 ERRO INTERNO INESPERADO: {str(e)}")
        logger.error(f"   📌 Tipo do erro: {type(e)}")
        import traceback
        logger.error(f"   📝 Traceback completo:")
        logger.error(traceback.format_exc())
        logger.error("=" * 70)
        
        return Response(
            {
                'sucesso': False, 
                'erro': f'Erro interno: {str(e)}',
                'debug_trace': traceback.format_exc()
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )