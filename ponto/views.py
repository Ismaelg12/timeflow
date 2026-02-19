# ponto/views.py
from datetime import datetime, timedelta
import pytz
import json
import logging

from django.db import IntegrityError
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.views.decorators.http import require_POST

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from estabelecimentos.models import Estabelecimento
from usuarios.models import Profissional
from .models import RegistroPonto, RegistroManual
from .utils import calcular_tolerancia, determinar_proximo_tipo, verificar_registro_duplicado
from api.serializers import RegistroPontoSerializer, RegistroPontoCreateSerializer

# Configurar logger
logger = logging.getLogger(__name__)

# Constante de justificativas predefinidas
JUSTIFICATIVAS_PREDEFINIDAS = [
    ('', 'Selecione uma justificativa'),
    ('ESQUECIMENTO', 'Esquecimento do profissional'),
    ('PROBLEMA_SISTEMA', 'Problema no sistema de ponto'),
    ('EMERGENCIA', 'Emergência/urgência médica'),
    ('REUNIAO', 'Reunião prolongada'),
    ('ATIVIDADE_EXTERNA', 'Atividade externa'),
    ('FALHA_EQUIPAMENTO', 'Falha no equipamento'),
    ('CAPACITACAO', 'Capacitação/treinamento'),
    ('OUTRO', 'Outro (especificar)'),
]

# ============================================================================
# VIEWS EXISTENTES - MANTENHA ESSAS
# ============================================================================

class RegistroPontoViewSet(viewsets.ModelViewSet):
    queryset = RegistroPonto.objects.all()
    serializer_class = RegistroPontoSerializer
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'])
    def registrar(self, request):
        """API para registro de ponto via mobile"""
        serializer = RegistroPontoCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        cpf = serializer.validated_data['cpf']
        estabelecimento_id = serializer.validated_data['estabelecimento_id']
        latitude = serializer.validated_data['latitude']
        longitude = serializer.validated_data['longitude']
        
        try:
            profissional = Profissional.objects.get(cpf=cpf, ativo=True)
            estabelecimento = Estabelecimento.objects.get(id=estabelecimento_id)
            
            if not self.validar_localizacao(estabelecimento, latitude, longitude):
                return Response(
                    {'erro': 'Fora do raio permitido para registro'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            hoje = timezone.now().date()
            horario_atual = timezone.now().time()
            tipo = determinar_proximo_tipo(profissional, estabelecimento, hoje)
            
            if verificar_registro_duplicado(profissional, estabelecimento, hoje, tipo):
                tipo_oposto = 'SAIDA' if tipo == 'ENTRADA' else 'ENTRADA'
                return Response(
                    {'erro': f'Registro duplicado detectado. Próximo: {tipo_oposto.lower()}'}, 
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
            
            if dentro_tolerancia:
                mensagem = f'Registro realizado com sucesso'
            else:
                if tipo == 'ENTRADA':
                    mensagem = f'Entrada registrada com {atraso_minutos}min de atraso'
                else:
                    mensagem = f'Saída registrada com {atraso_minutos}min de antecipação'
            
            if tipo == 'ENTRADA':
                mensagem += ' | Próximo registro: Saída'
            else:
                mensagem += ' | Registro do dia concluído'
            
            response_serializer = RegistroPontoSerializer(registro)
            return Response({
                'sucesso': True,
                'mensagem': mensagem,
                'registro': response_serializer.data,
                'proximo_tipo': 'saída' if tipo == 'ENTRADA' else 'entrada',
                'dentro_tolerancia': dentro_tolerancia,
                'dia_concluido': tipo == 'SAIDA'
            })
            
        except Profissional.DoesNotExist:
            return Response(
                {'erro': 'Profissional não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Estabelecimento.DoesNotExist:
            return Response(
                {'erro': 'Estabelecimento não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except IntegrityError:
            return Response(
                {'erro': 'Registro duplicado'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception:
            return Response(
                {'erro': 'Erro interno no servidor'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def historico(self, request):
        """API para buscar histórico de registros por período"""
        cpf = request.GET.get('cpf')
        if not cpf:
            return Response(
                {'erro': 'CPF é obrigatório'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            profissional = Profissional.objects.get(cpf=cpf, ativo=True)
        except Profissional.DoesNotExist:
            return Response(
                {'erro': 'Profissional não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        registros = RegistroPonto.objects.filter(profissional=profissional)
        
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        
        if data_inicio:
            try:
                data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                registros = registros.filter(data__gte=data_inicio_dt)
            except ValueError:
                return Response(
                    {'erro': 'Formato de data_inicio inválido. Use YYYY-MM-DD'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if data_fim:
            try:
                data_fim_dt = datetime.strptime(data_fim, '%Y-%m-%d').date()
                registros = registros.filter(data__lte=data_fim_dt)
            except ValueError:
                return Response(
                    {'erro': 'Formato de data_fim inválido. Use YYYY-MM-DD'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        registros = registros.order_by('-data', '-horario')
        serializer = RegistroPontoSerializer(registros, many=True)
        
        total_registros = registros.count()
        total_entradas = registros.filter(tipo='ENTRADA').count()
        total_saidas = registros.filter(tipo='SAIDA').count()
        
        return Response({
            'sucesso': True,
            'total_registros': total_registros,
            'total_entradas': total_entradas,
            'total_saidas': total_saidas,
            'dados': serializer.data
        })
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def ultimos_registros(self, request):
        """API para buscar últimos registros"""
        cpf = request.GET.get('cpf')
        if not cpf:
            return Response(
                {'erro': 'CPF é obrigatório'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            profissional = Profissional.objects.get(cpf=cpf, ativo=True)
        except Profissional.DoesNotExist:
            return Response(
                {'erro': 'Profissional não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            dias = int(request.GET.get('dias', '30'))
            data_inicio = timezone.now().date() - timezone.timedelta(days=dias)
        except ValueError:
            dias = 30
            data_inicio = timezone.now().date() - timezone.timedelta(days=dias)
        
        registros = RegistroPonto.objects.filter(
            profissional=profissional,
            data__gte=data_inicio
        ).order_by('-data', '-horario')[:50]
        
        serializer = RegistroPontoSerializer(registros, many=True)
        
        return Response({
            'sucesso': True,
            'dados': serializer.data,
            'periodo': f'Últimos {dias} dias'
        })
    
    def validar_localizacao(self, estabelecimento, lat, lng):
        """Valida se a localização está dentro do raio permitido"""
        try:
            lat_diff = estabelecimento.latitude - float(lat)
            lng_diff = estabelecimento.longitude - float(lng)
            distancia = (lat_diff**2 + lng_diff**2)**0.5 * 111000
            return distancia <= estabelecimento.raio_permitido
        except (TypeError, ValueError):
            return False

# ============================================================================
# VIEWS EXISTENTES DE AJUSTE MANUAL - MANTENHA ESSAS
# ============================================================================

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def ajuste_manual_registro(request, profissional_id=None):
    """
    View para ajuste manual de registros (esquecimento de ponto)
    """
    if profissional_id:
        profissional = get_object_or_404(Profissional, id=profissional_id)
    else:
        profissional = None
    
    if request.method == 'POST':
        from .forms import RegistroManualForm
        form = RegistroManualForm(request.POST)
        if form.is_valid():
            try:
                # Obter dados do formulário
                profissional = form.cleaned_data['profissional']
                data_registro = form.cleaned_data['data']
                horario_registro = form.cleaned_data['horario']
                tipo_registro = form.cleaned_data['tipo']
                motivo = form.cleaned_data['motivo']
                
                # Converter para timezone de Brasília
                tz_brasilia = pytz.timezone('America/Sao_Paulo')
                
                # Criar registro manual
                registro_manual = RegistroManual(
                    profissional=profissional,
                    data=data_registro,
                    horario=horario_registro,
                    tipo=tipo_registro,
                    motivo=motivo,
                    ajustado_por=request.user,
                    latitude=0,  # Definir valores padrão
                    longitude=0
                )
                
                # Verificar se já existe registro no mesmo dia/tipo
                registro_existente = RegistroPonto.objects.filter(
                    profissional=profissional,
                    data=data_registro,
                    tipo=tipo_registro
                ).exists()
                
                if registro_existente:
                    messages.warning(request, 
                        f"Já existe um registro de {tipo_registro.lower()} para {profissional.nome} em {data_registro.strftime('%d/%m/%Y')}. "
                        f"O novo registro substituirá o anterior.")
                    
                    # Remover registro anterior
                    RegistroPonto.objects.filter(
                        profissional=profissional,
                        data=data_registro,
                        tipo=tipo_registro
                    ).delete()
                
                # Calcular tolerância (simplificado)
                atraso_minutos = 0
                dentro_tolerancia = True
                
                if tipo_registro == 'ENTRADA':
                    horario_previsto = profissional.horario_entrada
                else:
                    horario_previsto = profissional.horario_saida
                
                if horario_previsto:
                    # Calcular diferença
                    horario_previsto_dt = datetime.combine(data_registro, horario_previsto)
                    horario_registro_dt = datetime.combine(data_registro, horario_registro)
                    
                    if tipo_registro == 'ENTRADA':
                        if horario_registro_dt > horario_previsto_dt:
                            diferenca = horario_registro_dt - horario_previsto_dt
                            atraso_minutos = int(diferenca.total_seconds() / 60)
                            dentro_tolerancia = atraso_minutos <= (profissional.tolerancia_minutos or 10)
                    else:  # SAIDA
                        if horario_registro_dt < horario_previsto_dt:
                            diferenca = horario_previsto_dt - horario_registro_dt
                            atraso_minutos = int(diferenca.total_seconds() / 60)
                            dentro_tolerancia = atraso_minutos <= (profissional.tolerancia_minutos or 10)
                
                # Criar registro de ponto real
                registro_ponto = RegistroPonto(
                    profissional=profissional,
                    estabelecimento=profissional.estabelecimento,
                    data=data_registro,
                    horario=horario_registro,
                    tipo=tipo_registro,
                    latitude=0,  # GPS não disponível para ajuste manual
                    longitude=0,
                    atraso_minutos=atraso_minutos if tipo_registro == 'ENTRADA' else 0,
                    saida_antecipada_minutos=atraso_minutos if tipo_registro == 'SAIDA' else 0,
                    dentro_tolerancia=dentro_tolerancia,
                    ajuste_manual=True  # ✅ NOVO CAMPO PARA IDENTIFICAR AJUSTE
                )
                
                registro_ponto.save()
                registro_manual.save()
                
                messages.success(request, 
                    f"Registro {tipo_registro.lower()} ajustado com sucesso para {profissional.nome} "
                    f"em {data_registro.strftime('%d/%m/%Y')} às {horario_registro.strftime('%H:%M')}.")
                
                return redirect('ponto:lista_ajustes_manuais')
                
            except Exception as e:
                messages.error(request, f"Erro ao ajustar registro: {str(e)}")
    else:
        from .forms import RegistroManualForm
        initial = {}
        if profissional:
            initial['profissional'] = profissional
        
        hoje = timezone.now().date()
        horario_atual = timezone.now().time()
        
        initial['data'] = hoje
        initial['horario'] = horario_atual
        
        form = RegistroManualForm(initial=initial)
    
    profissionais = Profissional.objects.filter(ativo=True).order_by('nome')
    
    return render(request, 'ponto/ajuste_manual.html', {
        'form': form,
        'profissionais': profissionais,
        'profissional_selecionado': profissional
    })


@login_required
def meus_ajustes_solicitados(request):
    """
    Lista de ajustes solicitados pelo próprio profissional
    """
    if not hasattr(request.user, 'profissional'):
        messages.error(request, 'Você não tem um perfil profissional.')
        return redirect('core:dashboard')
    
    profissional = request.user.profissional
    ajustes = RegistroManual.objects.filter(
        profissional=profissional
    ).order_by('-data', '-horario')[:30]
    
    return render(request, 'ponto/meus_ajustes.html', {
        'ajustes': ajustes,
        'profissional': profissional
    })


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def lista_ajustes_manuais(request):
    """
    Lista de todos os ajustes manuais (apenas admin)
    """
    ajustes = RegistroManual.objects.all().order_by('-data', '-horario')[:100]
    
    return render(request, 'ponto/lista_ajustes_manuais.html', {
        'ajustes': ajustes
    })

# ============================================================================
# NOVAS VIEWS PARA REGISTRO MANUAL DE SAÍDA
# ============================================================================

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
@require_POST
def registro_manual_saida(request):
    """
    View ESPECÍFICA para registrar APENAS SAÍDA manualmente
    """
    try:
        # Extrair dados do formulário
        profissional_id = request.POST.get('profissional_id')
        data_str = request.POST.get('data')
        horario_saida_str = request.POST.get('horario_saida')
        justificativa = request.POST.get('justificativa')
        justificativa_outro = request.POST.get('justificativa_outro', '')
        observacoes = request.POST.get('observacoes', '')
        
        # Log dos dados recebidos para debug
        logger.info(f"Registro manual saída - Dados recebidos: profissional_id={profissional_id}, data={data_str}, horario={horario_saida_str}, justificativa={justificativa}")
        
        # Validações básicas
        if not all([profissional_id, data_str, horario_saida_str, justificativa]):
            messages.error(request, "❌ Todos os campos obrigatórios devem ser preenchidos.")
            return redirect(request.META.get('HTTP_REFERER', 'core:dashboard'))
        
        if justificativa == 'OUTRO' and not justificativa_outro:
            messages.error(request, "❌ É necessário especificar a justificativa quando selecionar 'Outro'.")
            return redirect(request.META.get('HTTP_REFERER', 'core:dashboard'))
        
        # Converter dados
        profissional = get_object_or_404(Profissional, id=profissional_id)
        data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
        horario_saida = datetime.strptime(horario_saida_str, '%H:%M').time()
        
        # ✅ Verificar se já tem saída neste dia
        saida_existente = RegistroPonto.objects.filter(
            profissional=profissional,
            data=data_obj,
            tipo='SAIDA'
        ).exists()
        
        if saida_existente:
            messages.warning(request, 
                f"⚠️ Já existe uma saída registrada para {profissional.nome} em {data_obj.strftime('%d/%m/%Y')}. "
                f"Para alterar, delete a saída existente primeiro.")
            return redirect('core:relatorio_profissional', profissional_id=profissional_id)
        
        # ✅ Verificar entrada do dia
        entrada = RegistroPonto.objects.filter(
            profissional=profissional,
            data=data_obj,
            tipo='ENTRADA'
        ).order_by('-horario').first()
        
        if not entrada:
            messages.error(request, 
                f"❌ Não foi encontrada entrada registrada para {data_obj.strftime('%d/%m/%Y')}. "
                f"É necessário registrar entrada primeiro.")
            return redirect('core:relatorio_profissional', profissional_id=profissional_id)
        
        # ✅ Verificar se a saída é anterior à entrada (erro lógico)
        entrada_dt = datetime.combine(data_obj, entrada.horario)
        saida_dt = datetime.combine(data_obj, horario_saida)
        
        if saida_dt <= entrada_dt:
            messages.error(request,
                f"❌ O horário da saída ({horario_saida_str}) deve ser posterior ao horário da entrada "
                f"({entrada.horario.strftime('%H:%M')}).")
            return redirect('core:relatorio_profissional', profissional_id=profissional_id)
        
        # ✅ Calcular se saída é antecipada
        saida_antecipada_minutos = 0
        dentro_tolerancia = True
        
        if profissional.horario_saida:
            # Converter para datetime para cálculo
            horario_previsto_dt = datetime.combine(data_obj, profissional.horario_saida)
            
            if saida_dt < horario_previsto_dt:
                diferenca = horario_previsto_dt - saida_dt
                saida_antecipada_minutos = int(diferenca.total_seconds() / 60)
                dentro_tolerancia = saida_antecipada_minutos <= (profissional.tolerancia_minutos or 10)
        
        # ✅ Completar justificativa
        if justificativa == 'OUTRO' and justificativa_outro:
            justificativa_completa = f"OUTRO: {justificativa_outro}"
        else:
            # Buscar o texto da justificativa predefinida
            justificativas_dict = dict(JUSTIFICATIVAS_PREDEFINIDAS[1:])  # Remove opção vazia
            justificativa_completa = justificativas_dict.get(justificativa, justificativa)
        
        # ✅ Preparar observações completas
        obs_completas = []
        if observacoes:
            obs_completas.append(observacoes)
        obs_completas.append(f"Justificativa: {justificativa_completa}")
        
        # ✅ Criar registro no histórico de ajustes manuais
        registro_manual = RegistroManual(
            profissional=profissional,
            data=data_obj,
            horario=horario_saida,
            tipo='SAIDA',
            motivo=justificativa,
            descricao='\n'.join(obs_completas),
            ajustado_por=request.user,
            latitude=0,
            longitude=0
        )
        registro_manual.save()
        
        # ✅ Calcular horas trabalhadas
        horas_trabalhadas_timedelta = saida_dt - entrada_dt
        horas_trabalhadas = horas_trabalhadas_timedelta.total_seconds() / 3600
        
        # ✅ Criar registro de ponto REAL (aparece nos relatórios)
        registro_ponto = RegistroPonto(
            profissional=profissional,
            estabelecimento=entrada.estabelecimento,  # Usar mesmo estabelecimento da entrada
            data=data_obj,
            horario=horario_saida,
            tipo='SAIDA',
            latitude=0,  # GPS não disponível para ajuste manual
            longitude=0,
            atraso_minutos=0,  # Atraso só se aplica a entrada
            saida_antecipada_minutos=saida_antecipada_minutos,
            dentro_tolerancia=dentro_tolerancia,
            ajuste_manual=True,
            justificativa_ajuste=justificativa_completa,
            observacoes='\n'.join(obs_completas)
        )
        registro_ponto.save()
        
        # ✅ Log do registro para auditoria
        logger.info(f"Registro manual criado: Profissional={profissional.nome}, Data={data_str}, "
                   f"Horário={horario_saida_str}, Justificativa={justificativa_completa}, "
                   f"Admin={request.user.username}")
        
        # ✅ Mensagem de sucesso detalhada
        msg_detalhes = []
        
        if saida_antecipada_minutos > 0:
            if dentro_tolerancia:
                msg_detalhes.append(f"saída antecipada de {saida_antecipada_minutos}min (dentro da tolerância)")
            else:
                msg_detalhes.append(f"saída antecipada de {saida_antecipada_minutos}min (fora da tolerância)")
        
        horas_trabalhadas_formatada = f"{int(horas_trabalhadas)}h{int((horas_trabalhadas % 1) * 60)}min"
        msg_detalhes.append(f"jornada de {horas_trabalhadas_formatada}")
        
        detalhes_str = " - ".join(msg_detalhes)
        
        messages.success(request,
            f"✅ Saída registrada para {profissional.nome} em "
            f"{data_obj.strftime('%d/%m/%Y')} às {horario_saida.strftime('%H:%M')}. "
            f"({detalhes_str}) | Justificativa: {justificativa_completa}")
        
        # ✅ Redirecionar de volta para o relatório
        return redirect('core:relatorio_profissional', profissional_id=profissional_id)
        
    except Profissional.DoesNotExist:
        messages.error(request, "❌ Profissional não encontrado.")
    except ValueError as e:
        messages.error(request, f"❌ Erro no formato dos dados: {str(e)}")
    except Exception as e:
        logger.error(f"Erro crítico no registro manual: {str(e)}", exc_info=True)
        messages.error(request, f"❌ Erro ao registrar saída: {str(e)}")
    
    # Se ocorrer erro, voltar para a página anterior
    return redirect(request.META.get('HTTP_REFERER', 'core:dashboard'))


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def verificar_dias_incompletos_api(request, profissional_id):
    """
    API JSON para verificar dias com apenas entrada registrada
    """
    try:
        profissional = get_object_or_404(Profissional, id=profissional_id)
        
        # Parâmetros da requisição
        dias_param = request.GET.get('dias', '30')
        try:
            dias = int(dias_param)
        except ValueError:
            dias = 30
        
        # Limitar entre 1 e 365 dias
        dias = max(1, min(dias, 365))
        
        # Calcular período
        data_fim = timezone.now().date()
        data_inicio = data_fim - timedelta(days=dias)
        
        logger.info(f"Verificando dias incompletos: profissional={profissional.nome}, "
                   f"período={data_inicio} a {data_fim}, dias={dias}")
        
        # Buscar registros do período
        registros = RegistroPonto.objects.filter(
            profissional=profissional,
            data__gte=data_inicio,
            data__lte=data_fim
        ).order_by('data', 'horario')
        
        # Agrupar por dia e identificar incompletos
        dias_incompletos = []
        
        # Criar dicionário para agrupar por data
        registros_por_data = {}
        for registro in registros:
            data_key = registro.data.isoformat()
            if data_key not in registros_por_data:
                registros_por_data[data_key] = {'entradas': [], 'saidas': []}
            
            if registro.tipo == 'ENTRADA':
                registros_por_data[data_key]['entradas'].append(registro)
            else:
                registros_por_data[data_key]['saidas'].append(registro)
        
        # Verificar cada dia
        for data_str, registros_dia in registros_por_data.items():
            entradas = registros_dia['entradas']
            saidas = registros_dia['saidas']
            
            # Tem pelo menos uma entrada mas nenhuma saída = dia incompleto
            if len(entradas) > 0 and len(saidas) == 0:
                # Usar a última entrada do dia (caso tenha múltiplas)
                ultima_entrada = entradas[-1]
                
                # Verificar se já foi feito ajuste manual
                ajustes_manuais = RegistroManual.objects.filter(
                    profissional=profissional,
                    data=ultima_entrada.data,
                    tipo='SAIDA'
                ).exists()
                
                # Verificar se já existe registro manual de ponto
                saida_manual = RegistroPonto.objects.filter(
                    profissional=profissional,
                    data=ultima_entrada.data,
                    tipo='SAIDA',
                    ajuste_manual=True
                ).exists()
                
                dias_incompletos.append({
                    'data': data_str,
                    'data_formatada': ultima_entrada.data.strftime('%d/%m/%Y'),
                    'entrada': ultima_entrada.horario.strftime('%H:%M'),
                    'entrada_id': ultima_entrada.id,
                    'estabelecimento': ultima_entrada.estabelecimento.nome if ultima_entrada.estabelecimento else 'Não informado',
                    'profissional_id': profissional_id,
                    'profissional_nome': f"{profissional.nome} {profissional.sobrenome}",
                    'horario_previsto_saida': profissional.horario_saida.strftime('%H:%M') 
                        if profissional.horario_saida else None,
                    'tolerancia_minutos': profissional.tolerancia_minutos or 10,
                    'ja_ajustado': ajustes_manuais or saida_manual,
                    'ja_ajustado_texto': 'Sim' if (ajustes_manuais or saida_manual) else 'Não'
                })
        
        # Ordenar por data (mais recente primeiro)
        dias_incompletos.sort(key=lambda x: x['data'], reverse=True)
        
        # ✅ Preparar resposta JSON
        response_data = {
            'sucesso': True,
            'profissional': {
                'id': profissional.id,
                'nome': f"{profissional.nome} {profissional.sobrenome}",
                'cpf': profissional.cpf,
                'ativo': profissional.ativo,
                'horario_entrada': profissional.horario_entrada.strftime('%H:%M') if profissional.horario_entrada else None,
                'horario_saida': profissional.horario_saida.strftime('%H:%M') if profissional.horario_saida else None,
                'tolerancia': profissional.tolerancia_minutos or 10
            },
            'dias_incompletos': dias_incompletos,
            'total': len(dias_incompletos),
            'periodo': {
                'inicio': data_inicio.strftime('%d/%m/%Y'),
                'fim': data_fim.strftime('%d/%m/%Y'),
                'dias': dias
            },
            'resumo': f"Encontrados {len(dias_incompletos)} dia(s) incompleto(s) nos últimos {dias} dias.",
            'timestamp': timezone.now().isoformat()
        }
        
        return JsonResponse(response_data, safe=False)
        
    except Exception as e:
        logger.error(f"Erro na API de dias incompletos: {str(e)}", exc_info=True)
        return JsonResponse({
            'sucesso': False, 
            'erro': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)


@login_required
def get_detalhes_registro_api(request, registro_id):
    """
    API para obter detalhes de um registro específico
    """
    try:
        registro = get_object_or_404(RegistroPonto, id=registro_id)
        
        # Verificar permissão
        if not request.user.is_superuser and not request.user.is_staff:
            if not hasattr(request.user, 'profissional') or request.user.profissional.id != registro.profissional.id:
                return JsonResponse({
                    'sucesso': False,
                    'erro': 'Permissão negada'
                }, status=403)
        
        # Buscar ajustes manuais relacionados
        ajustes_manuais = RegistroManual.objects.filter(
            profissional=registro.profissional,
            data=registro.data,
            tipo=registro.tipo
        ).order_by('-data_ajuste')
        
        ajustes_data = []
        for ajuste in ajustes_manuais:
            ajustes_data.append({
                'motivo': ajuste.motivo,
                'descricao': ajuste.descricao,
                'ajustado_por': ajuste.ajustado_por.username if ajuste.ajustado_por else 'Sistema',
                'data_ajuste': ajuste.data_ajuste.strftime('%d/%m/%Y %H:%M')
            })
        
        # Preparar resposta
        response_data = {
            'sucesso': True,
            'registro': {
                'id': registro.id,
                'profissional_nome': f"{registro.profissional.nome} {registro.profissional.sobrenome}",
                'data': registro.data.strftime('%d/%m/%Y'),
                'horario': registro.horario.strftime('%H:%M'),
                'tipo': registro.tipo,
                'tipo_display': registro.get_tipo_display(),
                'estabelecimento_nome': registro.estabelecimento.nome if registro.estabelecimento else 'Não informado',
                'atraso_minutos': registro.atraso_minutos,
                'saida_antecipada_minutos': registro.saida_antecipada_minutos,
                'dentro_tolerancia': registro.dentro_tolerancia,
                'ajuste_manual': registro.ajuste_manual,
                'justificativa_ajuste': registro.justificativa_ajuste or 'Não aplicável',
                'observacoes': registro.observacoes or 'Sem observações',
                'latitude': registro.latitude,
                'longitude': registro.longitude,
                'data_criacao': registro.created_at.strftime('%d/%m/%Y %H:%M') if hasattr(registro, 'created_at') else 'Não disponível'
            },
            'ajustes_manuais': ajustes_data,
            'total_ajustes': len(ajustes_data)
        }
        
        return JsonResponse(response_data, safe=False)
        
    except Exception as e:
        logger.error(f"Erro na API de detalhes do registro: {str(e)}", exc_info=True)
        return JsonResponse({
            'sucesso': False, 
            'erro': str(e)
        }, status=500)


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def excluir_registro_manual(request, registro_id):
    """
    Excluir um registro manual (apenas admin)
    """
    try:
        registro = get_object_or_404(RegistroPonto, id=registro_id, ajuste_manual=True)
        profissional_id = registro.profissional.id
        data_registro = registro.data
        horario_registro = registro.horario
        
        # Excluir também do histórico de ajustes manuais
        RegistroManual.objects.filter(
            profissional=registro.profissional,
            data=registro.data,
            horario=registro.horario,
            tipo=registro.tipo
        ).delete()
        
        # Excluir o registro de ponto
        registro.delete()
        
        messages.success(request,
            f"✅ Registro manual excluído: {data_registro.strftime('%d/%m/%Y')} "
            f"às {horario_registro.strftime('%H:%M')}")
        
        return redirect('core:relatorio_profissional', profissional_id=profissional_id)
        
    except Exception as e:
        messages.error(request, f"❌ Erro ao excluir registro: {str(e)}")
        return redirect(request.META.get('HTTP_REFERER', 'core:dashboard'))


def verificar_dias_incompletos_batch(request):
    """
    Verifica dias incompletos para todos os profissionais (batch)
    """
    if not request.user.is_superuser:
        return JsonResponse({'sucesso': False, 'erro': 'Permissão negada'}, status=403)
    
    try:
        dias = int(request.GET.get('dias', '7'))
        data_fim = timezone.now().date()
        data_inicio = data_fim - timedelta(days=dias)
        
        profissionais = Profissional.objects.filter(ativo=True)
        resultado = []
        
        for profissional in profissionais:
            registros = RegistroPonto.objects.filter(
                profissional=profissional,
                data__gte=data_inicio,
                data__lte=data_fim
            )
            
            # Agrupar por data
            registros_por_data = {}
            for registro in registros:
                data_key = registro.data.isoformat()
                if data_key not in registros_por_data:
                    registros_por_data[data_key] = {'entradas': [], 'saidas': []}
                
                if registro.tipo == 'ENTRADA':
                    registros_por_data[data_key]['entradas'].append(registro)
                else:
                    registros_por_data[data_key]['saidas'].append(registro)
            
            # Verificar dias incompletos para este profissional
            dias_incompletos = []
            for data_str, registros_dia in registros_por_data.items():
                if len(registros_dia['entradas']) > 0 and len(registros_dia['saidas']) == 0:
                    dias_incompletos.append(data_str)
            
            if dias_incompletos:
                resultado.append({
                    'profissional_id': profissional.id,
                    'profissional_nome': f"{profissional.nome} {profissional.sobrenome}",
                    'cpf': profissional.cpf,
                    'dias_incompletos': dias_incompletos,
                    'total': len(dias_incompletos)
                })
        
        resultado.sort(key=lambda x: x['total'], reverse=True)
        
        return JsonResponse({
            'sucesso': True,
            'total_profissionais': len(resultado),
            'periodo': {
                'inicio': data_inicio.strftime('%d/%m/%Y'),
                'fim': data_fim.strftime('%d/%m/%Y')
            },
            'resultados': resultado
        })
        
    except Exception as e:
        logger.error(f"Erro no batch de dias incompletos: {str(e)}", exc_info=True)
        return JsonResponse({'sucesso': False, 'erro': str(e)}, status=500)

# ============================================================================
# VIEW PARA REGISTRO MANUAL DE SAÍDA (USADA PELO MODAL)
# ============================================================================

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
@require_POST
def registro_manual_saida(request):
    """
    View ESPECÍFICA para registrar APENAS SAÍDA manualmente
    Chamada pelo modal de registro manual no relatório do profissional
    """
    try:
        # Extrair dados do formulário
        profissional_id = request.POST.get('profissional_id')
        data_str = request.POST.get('data')
        horario_saida_str = request.POST.get('horario')
        justificativa = request.POST.get('justificativa')
        observacoes = request.POST.get('observacoes', '')
        
        # Log para debug
        logger.info(f"Registro manual saída - Dados: profissional={profissional_id}, data={data_str}, horario={horario_saida_str}, justificativa={justificativa}")
        
        # Validações básicas
        if not all([profissional_id, data_str, horario_saida_str, justificativa]):
            messages.error(request, "❌ Todos os campos obrigatórios devem ser preenchidos.")
            return redirect(request.META.get('HTTP_REFERER', 'core:dashboard'))
        
        # Converter dados
        profissional = get_object_or_404(Profissional, id=profissional_id)
        data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
        horario_saida = datetime.strptime(horario_saida_str, '%H:%M').time()
        
        # ✅ VERIFICAR SE JÁ EXISTE SAÍDA NESTE DIA
        saida_existente = RegistroPonto.objects.filter(
            profissional=profissional,
            data=data_obj,
            tipo='SAIDA'
        ).exists()
        
        if saida_existente:
            messages.warning(request, 
                f"⚠️ Já existe uma saída registrada para {profissional.nome} em {data_obj.strftime('%d/%m/%Y')}. "
                f"Para alterar, utilize a edição manual ou delete o registro existente.")
            return redirect('core:relatorio_profissional', profissional_id=profissional_id)
        
        # ✅ VERIFICAR SE EXISTE ENTRADA NESTE DIA
        entrada = RegistroPonto.objects.filter(
            profissional=profissional,
            data=data_obj,
            tipo='ENTRADA'
        ).order_by('-horario').first()
        
        if not entrada:
            messages.error(request, 
                f"❌ Não foi encontrada entrada registrada para {data_obj.strftime('%d/%m/%Y')}. "
                f"É necessário registrar a entrada primeiro.")
            return redirect('core:relatorio_profissional', profissional_id=profissional_id)
        
        # ✅ VERIFICAR SE HORÁRIO É POSTERIOR À ENTRADA
        entrada_dt = datetime.combine(data_obj, entrada.horario)
        saida_dt = datetime.combine(data_obj, horario_saida)
        
        if saida_dt <= entrada_dt:
            messages.error(request,
                f"❌ O horário da saída ({horario_saida_str}) deve ser posterior ao horário da entrada "
                f"({entrada.horario.strftime('%H:%M')}).")
            return redirect('core:relatorio_profissional', profissional_id=profissional_id)
        
        # ✅ CALCULAR SAÍDA ANTECIPADA
        saida_antecipada_minutos = 0
        dentro_tolerancia = True
        
        if profissional.horario_saida:
            horario_previsto_dt = datetime.combine(data_obj, profissional.horario_saida)
            
            if saida_dt < horario_previsto_dt:
                diferenca = horario_previsto_dt - saida_dt
                saida_antecipada_minutos = int(diferenca.total_seconds() / 60)
                dentro_tolerancia = saida_antecipada_minutos <= (profissional.tolerancia_minutos or 10)
        
        # ✅ PREPARAR JUSTIFICATIVA COMPLETA
        justificativas_dict = dict(JUSTIFICATIVAS_PREDEFINIDAS[1:])
        justificativa_completa = justificativas_dict.get(justificativa, justificativa)
        
        if justificativa == 'OUTRO' and observacoes:
            justificativa_completa = f"OUTRO: {observacoes[:50]}"
        
        # ✅ PREPARAR OBSERVAÇÕES
        obs_completas = []
        if observacoes:
            obs_completas.append(observacoes)
        obs_completas.append(f"Justificativa: {justificativa_completa}")
        obs_completas.append(f"Registrado manualmente por: {request.user.get_full_name() or request.user.username}")
        obs_completas.append(f"Data do ajuste: {timezone.now().strftime('%d/%m/%Y %H:%M')}")
        
        # ✅ CRIAR REGISTRO NO HISTÓRICO DE AJUSTES MANUAIS
        registro_manual = RegistroManual(
            profissional=profissional,
            data=data_obj,
            horario=horario_saida,
            tipo='SAIDA',
            motivo=justificativa,
            descricao='\n'.join(obs_completas),
            ajustado_por=request.user,
            latitude=0,
            longitude=0
        )
        registro_manual.save()
        
        # ✅ CRIAR REGISTRO DE PONTO (com flag ajuste_manual)
        registro_ponto = RegistroPonto(
            profissional=profissional,
            estabelecimento=entrada.estabelecimento,  # Usar o mesmo da entrada
            data=data_obj,
            horario=horario_saida,
            tipo='SAIDA',
            latitude=0,
            longitude=0,
            atraso_minutos=0,
            saida_antecipada_minutos=saida_antecipada_minutos,
            dentro_tolerancia=dentro_tolerancia,
            ajuste_manual=True,
            justificativa_ajuste=justificativa_completa,
            observacoes='\n'.join(obs_completas)
        )
        registro_ponto.save()
        
        # ✅ LOG DE AUDITORIA
        logger.info(
            f"REGISTRO MANUAL SAÍDA | "
            f"Profissional: {profissional.nome} (ID: {profissional.id}) | "
            f"Data: {data_str} | Horário: {horario_saida_str} | "
            f"Justificativa: {justificativa_completa} | "
            f"Admin: {request.user.username} (ID: {request.user.id})"
        )
        
        # ✅ MENSAGEM DE SUCESSO
        horas_trabalhadas = (saida_dt - entrada_dt).total_seconds() / 3600
        horas_format = f"{int(horas_trabalhadas)}h{int((horas_trabalhadas % 1) * 60)}min"
        
        mensagem = f"✅ Saída registrada manualmente para {profissional.nome} em {data_obj.strftime('%d/%m/%Y')} às {horario_saida.strftime('%H:%M')}. "
        mensagem += f"Jornada: {horas_format}. "
        
        if saida_antecipada_minutos > 0:
            mensagem += f"Saída antecipada: {saida_antecipada_minutos}min "
            mensagem += f"{'(dentro da tolerância)' if dentro_tolerancia else '(fora da tolerância)'}. "
        
        mensagem += f"Justificativa: {justificativa_completa}"
        
        messages.success(request, mensagem)
        
        # ✅ REDIRECIONAR DE VOLTA PARA O RELATÓRIO
        return redirect('core:relatorio_profissional', profissional_id=profissional_id)
        
    except Profissional.DoesNotExist:
        messages.error(request, "❌ Profissional não encontrado.")
    except ValueError as e:
        messages.error(request, f"❌ Erro no formato dos dados: {str(e)}")
    except Exception as e:
        logger.error(f"Erro no registro manual de saída: {str(e)}", exc_info=True)
        messages.error(request, f"❌ Erro ao registrar saída: {str(e)}")
    
    return redirect(request.META.get('HTTP_REFERER', 'core:dashboard'))