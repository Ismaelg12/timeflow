# core/views.py
import logging
from collections import defaultdict
from datetime import datetime, date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Count, Q, Sum, Max, Avg
from weasyprint import HTML

from estabelecimentos.models import Estabelecimento
from ponto.models import RegistroPonto
from usuarios.models import Profissional

logger = logging.getLogger(__name__)


# ======================
# FUNÇÕES AUXILIARES
# ======================

def is_admin(user):
    """Verifica se o usuário é admin"""
    return user.is_superuser or user.is_staff


def formatar_horas(timedelta_obj):
    """Formata um timedelta para HH:MM"""
    if not timedelta_obj:
        return "00:00"
    total_segundos = int(abs(timedelta_obj.total_seconds()))
    horas = total_segundos // 3600
    minutos = (total_segundos % 3600) // 60
    return f"{horas:02d}:{minutos:02d}"


def formatar_saldo_horas(minutos):
    """Formata saldo de horas com sinal"""
    if minutos >= 0:
        sinal = "+"
    else:
        sinal = "-"
        minutos = abs(minutos)
    horas = int(minutos // 60)
    minutos_restantes = int(minutos % 60)
    return f"{sinal}{horas:02d}:{minutos_restantes:02d}"


def calcular_dias_uteis(data_inicio, data_fim):
    """Calcula dias úteis (segunda a sexta) entre duas datas"""
    dias_uteis = 0
    data_atual = data_inicio
    while data_atual <= data_fim:
        if data_atual.weekday() < 5:
            dias_uteis += 1
        data_atual += timedelta(days=1)
    return dias_uteis


def calcular_dias_no_periodo(data_inicio, data_fim):
    """Calcula todos os dias no período"""
    return (data_fim - data_inicio).days + 1


def obter_carga_horaria_timedelta(carga):
    """Converte carga horária para timedelta"""
    if not carga:
        return timedelta(hours=8)
    if isinstance(carga, timedelta):
        return carga
    if isinstance(carga, str):
        try:
            horas, minutos = map(int, carga.split(':'))
            return timedelta(hours=horas, minutes=minutos)
        except:
            return timedelta(hours=8)
    return timedelta(hours=8)


def calcular_horas_trabalhadas_dia(registros_dia):
    """Calcula horas trabalhadas em um dia específico"""
    if not registros_dia:
        return timedelta()
    
    registros_ordenados = sorted(registros_dia, key=lambda x: x.horario)
    horas_trabalhadas = timedelta()
    entrada_atual = None
    data_entrada = None
    
    for registro in registros_ordenados:
        if registro.tipo == 'ENTRADA':
            entrada_atual = registro.horario
            data_entrada = registro.data
        elif registro.tipo == 'SAIDA' and entrada_atual:
            entrada_dt = datetime.combine(data_entrada, entrada_atual)
            saida_dt = datetime.combine(registro.data, registro.horario)
            if saida_dt < entrada_dt:
                saida_dt += timedelta(days=1)
            horas_trabalhadas += saida_dt - entrada_dt
            entrada_atual = None
    
    return horas_trabalhadas


def calcular_horas_trabalhadas_periodo(data_inicio, data_fim, profissional):
    """Calcula horas trabalhadas em um período"""
    registros = RegistroPonto.objects.filter(
        profissional=profissional,
        data__gte=data_inicio,
        data__lte=data_fim
    ).order_by('data', 'horario')
    
    registros_por_dia = defaultdict(list)
    for registro in registros:
        registros_por_dia[registro.data].append(registro)
    
    total_horas = timedelta()
    for registros_dia in registros_por_dia.values():
        total_horas += calcular_horas_trabalhadas_dia(registros_dia)
    
    return total_horas


def calcular_horas_previstas_periodo(profissional, data_inicio, data_fim):
    """Calcula horas previstas para o período respeitando o filtro"""
    carga_diaria = obter_carga_horaria_timedelta(profissional.carga_horaria_diaria)
    
    # Plantão 24h - todos os dias
    if carga_diaria.total_seconds() == 86400:
        dias = calcular_dias_no_periodo(data_inicio, data_fim)
        return timedelta(hours=24) * dias
    
    # Plantão 12h - dias úteis
    elif carga_diaria.total_seconds() == 43200:
        dias_uteis = calcular_dias_uteis(data_inicio, data_fim)
        return timedelta(hours=12) * dias_uteis
    
    # Carga normal - dias úteis
    else:
        dias_uteis = calcular_dias_uteis(data_inicio, data_fim)
        return carga_diaria * dias_uteis


def calcular_estatisticas_atrasos(registros, tolerancia_minutos):
    """Calcula métricas detalhadas de atrasos e saídas antecipadas"""
    stats = {
        'total_atrasos': 0,
        'total_saidas_antecipadas': 0,
        'atraso_excedente': 0,
        'saida_antecipada_excedente': 0,
        'registros_com_atraso': 0,
        'registros_com_saida_antecipada': 0,
        'media_atrasos': 0,
        'media_saidas_antecipadas': 0,
        'atrasos_fora_tolerancia': [],
        'saidas_fora_tolerancia': []
    }
    
    for registro in registros:
        if registro.tipo == 'ENTRADA' and registro.atraso_minutos:
            if registro.atraso_minutos > 0:
                stats['registros_com_atraso'] += 1
                stats['total_atrasos'] += registro.atraso_minutos
                excedente = max(0, registro.atraso_minutos - tolerancia_minutos)
                stats['atraso_excedente'] += excedente
                if excedente > 0:
                    stats['atrasos_fora_tolerancia'].append(registro)
        
        elif registro.tipo == 'SAIDA' and registro.saida_antecipada_minutos:
            if registro.saida_antecipada_minutos > 0:
                stats['registros_com_saida_antecipada'] += 1
                stats['total_saidas_antecipadas'] += registro.saida_antecipada_minutos
                excedente = max(0, registro.saida_antecipada_minutos - tolerancia_minutos)
                stats['saida_antecipada_excedente'] += excedente
                if excedente > 0:
                    stats['saidas_fora_tolerancia'].append(registro)
    
    if stats['registros_com_atraso'] > 0:
        stats['media_atrasos'] = stats['total_atrasos'] / stats['registros_com_atraso']
    if stats['registros_com_saida_antecipada'] > 0:
        stats['media_saidas_antecipadas'] = stats['total_saidas_antecipadas'] / stats['registros_com_saida_antecipada']
    
    return stats


def calcular_horas_por_dia_semana(registros_por_data):
    """Calcula horas trabalhadas por dia da semana"""
    dias_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
    resultado = []
    
    for i, dia_nome in enumerate(dias_semana):
        horas_total = timedelta()
        dias_com_registro = 0
        
        for data_dia, registros_dia in registros_por_data.items():
            if data_dia.weekday() == i:
                horas_dia = calcular_horas_trabalhadas_dia(registros_dia)
                if horas_dia.total_seconds() > 0:
                    horas_total += horas_dia
                    dias_com_registro += 1
        
        if horas_total.total_seconds() > 0:
            horas_decimal = horas_total.total_seconds() / 3600
            media = horas_decimal / dias_com_registro if dias_com_registro > 0 else 0
            resultado.append({
                'dia': dia_nome,
                'horas': formatar_horas(horas_total),
                'horas_decimal': round(horas_decimal, 2),
                'media': round(media, 1),
                'dias': dias_com_registro
            })
        else:
            resultado.append({
                'dia': dia_nome,
                'horas': '00:00',
                'horas_decimal': 0,
                'media': 0,
                'dias': 0
            })
    
    return resultado


def identificar_dias_incompletos(registros_por_data):
    """Identifica dias com registros incompletos"""
    dias_incompletos = []
    for data_dia, registros_dia in registros_por_data.items():
        tipos = [r.tipo for r in registros_dia]
        if ('ENTRADA' in tipos and 'SAIDA' not in tipos) or \
           ('SAIDA' in tipos and 'ENTRADA' not in tipos) or \
           len(registros_dia) == 1:
            dias_incompletos.append(data_dia)
    return dias_incompletos


# ======================
# VIEWS DE DASHBOARD
# ======================

@login_required
def dashboard(request):
    """Painel administrativo principal"""
    if not request.user.is_superuser and not request.user.is_staff:
        try:
            profissional = Profissional.objects.get(usuario=request.user)
            return redirect('core:relatorio_profissional', profissional_id=profissional.id)
        except Profissional.DoesNotExist:
            messages.error(request, "Perfil não encontrado.")
            return redirect('usuarios:login')
    
    # Filtros
    periodo = request.GET.get('periodo', 'hoje')
    estabelecimento_id = request.GET.get('estabelecimento')
    
    # Datas base
    hoje = timezone.now().date()
    ontem = hoje - timedelta(days=1)
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    inicio_mes = hoje.replace(day=1)
    
    # Determinar período
    if periodo == 'hoje':
        data_inicio = data_fim = hoje
    elif periodo == 'ontem':
        data_inicio = data_fim = ontem
    elif periodo == 'semana':
        data_inicio = inicio_semana
        data_fim = hoje
    elif periodo == 'mes':
        data_inicio = inicio_mes
        data_fim = hoje
    elif periodo == 'personalizado':
        data_inicio_str = request.GET.get('data_inicio', hoje)
        data_fim_str = request.GET.get('data_fim', hoje)
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else hoje
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else hoje
    else:
        data_inicio = data_fim = hoje
    
    # Filtro de estabelecimento
    estabelecimento_filtrado = None
    filtros = Q()
    if estabelecimento_id:
        estabelecimento_filtrado = Estabelecimento.objects.filter(id=estabelecimento_id).first()
        filtros &= Q(estabelecimento=estabelecimento_filtrado)
    
    # Estatísticas de atrasos
    estatisticas_atrasos = calcular_estatisticas_atrasos_periodo(
        data_inicio, data_fim, estabelecimento_filtrado
    )
    
    # Totais
    total_profissionais = Profissional.objects.filter(ativo=True).count()
    total_estabelecimentos = Estabelecimento.objects.count()
    
    registros_periodo = RegistroPonto.objects.filter(
        data__range=[data_inicio, data_fim]
    ).filter(filtros)
    
    registros_hoje = RegistroPonto.objects.filter(data=hoje).filter(filtros)
    
    # Percentual dentro da tolerância
    registros_dentro_tolerancia = registros_periodo.filter(
        Q(atraso_minutos=0) & Q(saida_antecipada_minutos=0)
    ).count()
    total_registros_periodo = registros_periodo.count()
    percentual_dentro_tolerancia = (
        (registros_dentro_tolerancia / total_registros_periodo * 100)
        if total_registros_periodo > 0 else 100
    )
    
    # Rankings
    profissionais_com_atraso = RegistroPonto.objects.filter(
        data__range=[data_inicio, data_fim],
        atraso_minutos__gt=0
    ).filter(filtros).values(
        'profissional__id', 'profissional__nome', 'profissional__cpf'
    ).annotate(
        total_atraso=Sum('atraso_minutos'),
        qtd_atrasos=Count('id')
    ).order_by('-total_atraso')[:5]
    
    estabelecimentos_movimento = RegistroPonto.objects.filter(
        data__range=[data_inicio, data_fim]
    ).values(
        'estabelecimento__id', 'estabelecimento__nome'
    ).annotate(
        total_registros=Count('id'),
        total_profissionais=Count('profissional', distinct=True)
    ).order_by('-total_registros')[:5]
    
    # Informações específicas para hoje
    registros_incompletos_hoje = []
    profissionais_sem_registro_hoje = []
    maiores_atrasos_hoje = []
    alertas = []
    
    if periodo == 'hoje':
        registros_incompletos_hoje = calcular_registros_incompletos_hoje(estabelecimento_filtrado)
        profissionais_sem_registro_hoje = identificar_profissionais_sem_registro_hoje(estabelecimento_filtrado)
        maiores_atrasos_hoje = identificar_maiores_atrasos_hoje(estabelecimento_filtrado, limit=5)
        
        # Gerar alertas
        for registro in registros_incompletos_hoje[:3]:
            alertas.append({
                'tipo': 'incompleto',
                'titulo': f'{registro["profissional"].nome} com registro incompleto',
                'mensagem': f'Registrou entrada às {registro["horario_entrada"].strftime("%H:%M")} mas não registrou saída',
                'cor': 'warning',
                'link': f'/relatorios/profissional/{registro["profissional"].id}/'
            })
        
        for prof in profissionais_sem_registro_hoje[:2]:
            alertas.append({
                'tipo': 'sem_registro',
                'titulo': f'{prof.nome} sem registro hoje',
                'mensagem': 'Profissional ativo ainda não registrou ponto',
                'cor': 'danger',
                'link': f'/usuarios/profissionais/{prof.id}/'
            })
        
        for atraso in maiores_atrasos_hoje:
            if atraso.atraso_minutos > 30:
                alertas.append({
                    'tipo': 'atraso_grave',
                    'titulo': f'{atraso.profissional.nome} com atraso grave',
                    'mensagem': f'Atraso de {atraso.atraso_minutos} minutos na entrada',
                    'cor': 'danger',
                    'link': f'/relatorios/profissional/{atraso.profissional.id}/'
                })
    
    context = {
        'total_profissionais': total_profissionais,
        'total_estabelecimentos': total_estabelecimentos,
        'registros_hoje': registros_hoje.count(),
        'entradas_hoje': registros_hoje.filter(tipo='ENTRADA').count(),
        'saidas_hoje': registros_hoje.filter(tipo='SAIDA').count(),
        'estatisticas_atrasos': estatisticas_atrasos,
        'percentual_dentro_tolerancia': round(percentual_dentro_tolerancia, 1),
        'profissionais_com_atraso': profissionais_com_atraso,
        'estabelecimentos_movimento': estabelecimentos_movimento,
        'registros_incompletos_hoje': registros_incompletos_hoje,
        'profissionais_sem_registro_hoje': profissionais_sem_registro_hoje,
        'maiores_atrasos_hoje': maiores_atrasos_hoje,
        'alertas': alertas,
        'ultimos_registros': RegistroPonto.objects.select_related(
            'profissional', 'estabelecimento'
        ).filter(filtros).order_by('-data', '-horario')[:10],
        'periodo': periodo,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'estabelecimentos': Estabelecimento.objects.all(),
        'estabelecimento_selecionado': estabelecimento_filtrado,
        'hoje': hoje,
        'qtd_incompletos': len(registros_incompletos_hoje),
        'qtd_sem_registro': len(profissionais_sem_registro_hoje),
    }
    
    return render(request, 'core/dashboard.html', context)


def calcular_estatisticas_atrasos_periodo(data_inicio, data_fim, estabelecimento=None):
    """Calcula estatísticas de atrasos no período"""
    filtros = Q(data__range=[data_inicio, data_fim], tipo='ENTRADA')
    if estabelecimento:
        filtros &= Q(estabelecimento=estabelecimento)
    
    stats = RegistroPonto.objects.filter(filtros).aggregate(
        total_registros=Count('id'),
        total_atrasos=Count('id', filter=Q(atraso_minutos__gt=0)),
        total_sem_atraso=Count('id', filter=Q(atraso_minutos=0)),
        soma_atrasos=Sum('atraso_minutos'),
        media_atrasos=Avg('atraso_minutos', filter=Q(atraso_minutos__gt=0)),
        max_atraso=Max('atraso_minutos')
    )
    
    if stats['total_registros']:
        stats['percentual_atrasos'] = stats['total_atrasos'] / stats['total_registros'] * 100
        stats['percentual_pontual'] = stats['total_sem_atraso'] / stats['total_registros'] * 100
    else:
        stats['percentual_atrasos'] = 0
        stats['percentual_pontual'] = 0
    
    return stats


def calcular_registros_incompletos_hoje(estabelecimento=None):
    """Identifica profissionais com registros incompletos hoje"""
    hoje = timezone.now().date()
    filtros = Q(data=hoje)
    if estabelecimento:
        filtros &= Q(estabelecimento=estabelecimento)
    
    registros_hoje = RegistroPonto.objects.filter(filtros)
    
    profissionais_com_entrada = set(registros_hoje.filter(tipo='ENTRADA').values_list('profissional_id', flat=True))
    profissionais_com_saida = set(registros_hoje.filter(tipo='SAIDA').values_list('profissional_id', flat=True))
    profissionais_incompletos = profissionais_com_entrada - profissionais_com_saida
    
    resultado = []
    for prof_id in profissionais_incompletos:
        try:
            profissional = Profissional.objects.get(id=prof_id)
            ultima_entrada = registros_hoje.filter(
                profissional=profissional, tipo='ENTRADA'
            ).order_by('-horario').first()
            
            if ultima_entrada:
                resultado.append({
                    'profissional': profissional,
                    'ultima_entrada': ultima_entrada,
                    'horario_entrada': ultima_entrada.horario,
                    'atraso_minutos': ultima_entrada.atraso_minutos,
                    'estabelecimento': ultima_entrada.estabelecimento
                })
        except Profissional.DoesNotExist:
            continue
    
    return resultado


def identificar_profissionais_sem_registro_hoje(estabelecimento=None):
    """Identifica profissionais ativos sem registro hoje"""
    hoje = timezone.now().date()
    
    filtros = Q(ativo=True)
    if estabelecimento:
        filtros &= Q(estabelecimento=estabelecimento)
    
    profissionais_ativos = Profissional.objects.filter(filtros)
    profissionais_com_registro = set(RegistroPonto.objects.filter(
        data=hoje
    ).values_list('profissional_id', flat=True))
    
    return [p for p in profissionais_ativos if p.id not in profissionais_com_registro]


def identificar_maiores_atrasos_hoje(estabelecimento=None, limit=10):
    """Identifica os maiores atrasos do dia"""
    hoje = timezone.now().date()
    filtros = Q(data=hoje, tipo='ENTRADA', atraso_minutos__gt=0)
    if estabelecimento:
        filtros &= Q(estabelecimento=estabelecimento)
    
    return RegistroPonto.objects.filter(filtros).select_related(
        'profissional', 'estabelecimento'
    ).order_by('-atraso_minutos')[:limit]


# ======================
# RELATÓRIO PROFISSIONAL
# ======================

@login_required
def relatorio_profissional(request, profissional_id):
    """Relatório do profissional com banco de horas individual"""
    profissional = get_object_or_404(Profissional, id=profissional_id)
    
    # Verificação de permissão
    if not request.user.is_superuser and profissional.usuario != request.user:
        messages.error(request, "Acesso não autorizado.")
        return redirect('core:dashboard')
    
    # Processar filtros de data
    hoje = timezone.now().date()
    inicio_mes = hoje.replace(day=1)
    
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')
    
    try:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else inicio_mes
    except (ValueError, TypeError):
        data_inicio = inicio_mes
        data_inicio_str = inicio_mes.strftime('%Y-%m-%d')
    
    try:
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else hoje
    except (ValueError, TypeError):
        data_fim = hoje
        data_fim_str = hoje.strftime('%Y-%m-%d')
    
    if data_fim < data_inicio:
        data_fim = data_inicio
        data_fim_str = data_inicio.strftime('%Y-%m-%d')
    
    # Dados do profissional
    estabelecimento = profissional.estabelecimento
    carga_diaria = obter_carga_horaria_timedelta(profissional.carga_horaria_diaria)
    tolerancia_minutos = profissional.tolerancia_minutos or 10
    
    # Carga horária semanal formatada
    if profissional.carga_horaria_semanal:
        carga_semanal = obter_carga_horaria_timedelta(profissional.carga_horaria_semanal)
        carga_horaria_semanal_formatada = formatar_horas(carga_semanal)
    else:
        horas_semana = carga_diaria.total_seconds() / 3600 * 5
        carga_horaria_semanal_formatada = formatar_horas(timedelta(hours=horas_semana))
    
    # Buscar registros
    registros = RegistroPonto.objects.filter(
        profissional=profissional,
        data__gte=data_inicio,
        data__lte=data_fim
    ).select_related('estabelecimento').order_by('-data', '-horario')
    
    # Agrupar por data
    registros_por_data = defaultdict(list)
    for registro in registros:
        registros_por_data[registro.data].append(registro)
    
    # Calcular horas
    horas_trabalhadas = calcular_horas_trabalhadas_periodo(data_inicio, data_fim, profissional)
    horas_trabalhadas_decimal = round(horas_trabalhadas.total_seconds() / 3600, 2) if horas_trabalhadas else 0
    horas_trabalhadas_formatadas = formatar_horas(horas_trabalhadas)
    
    horas_previstas = calcular_horas_previstas_periodo(profissional, data_inicio, data_fim)
    horas_previstas_decimal = round(horas_previstas.total_seconds() / 3600, 2) if horas_previstas else 0
    horas_previstas_formatadas = formatar_horas(horas_previstas)
    
    # Banco de horas
    saldo_minutos = (horas_trabalhadas_decimal - horas_previstas_decimal) * 60
    saldo_formatado = formatar_saldo_horas(saldo_minutos)
    
    percentual_concluido = 0
    if horas_previstas_decimal > 0:
        percentual_concluido = min(100, round((horas_trabalhadas_decimal / horas_previstas_decimal) * 100, 1))
    
    # Estatísticas de atrasos
    stats_atrasos = calcular_estatisticas_atrasos(registros, tolerancia_minutos)
    
    # Estatísticas gerais
    total_registros = registros.count()
    entradas = registros.filter(tipo='ENTRADA').count()
    saidas = registros.filter(tipo='SAIDA').count()
    
    dias_uteis = calcular_dias_uteis(data_inicio, data_fim)
    dias_trabalhados = len([d for d, regs in registros_por_data.items() 
                           if any(r.tipo == 'ENTRADA' for r in regs)])
    
    dias_incompletos = identificar_dias_incompletos(registros_por_data)
    
    # Horas por dia da semana
    horas_por_dia_semana = calcular_horas_por_dia_semana(registros_por_data)
    
    # Agrupar registros para template
    registros_agrupados = []
    for data_dia, registros_dia in sorted(registros_por_data.items(), reverse=True):
        horas_dia = calcular_horas_trabalhadas_dia(registros_dia)
        
        # Calcular carga esperada do dia
        dia_util = data_dia.weekday() < 5
        if carga_diaria.total_seconds() == 86400:
            horas_esperada = timedelta(hours=24)
        elif carga_diaria.total_seconds() == 43200:
            horas_esperada = timedelta(hours=12) if dia_util else timedelta()
        else:
            horas_esperada = carga_diaria if dia_util else timedelta()
        
        saldo_dia = (horas_dia.total_seconds() - horas_esperada.total_seconds()) / 60 if horas_esperada.total_seconds() > 0 else horas_dia.total_seconds() / 60
        
        registros_agrupados.append({
            'data': data_dia,
            'data_formatada': data_dia.strftime('%d/%m/%Y'),
            'dia_semana': data_dia.strftime('%A'),
            'registros': sorted(registros_dia, key=lambda x: x.horario),
            'horas': formatar_horas(horas_dia) if horas_dia.total_seconds() > 0 else '00:00',
            'horas_decimal': round(horas_dia.total_seconds() / 3600, 2) if horas_dia.total_seconds() > 0 else 0,
            'horas_esperada': formatar_horas(horas_esperada) if horas_esperada.total_seconds() > 0 else '00:00',
            'saldo_dia': round(saldo_dia, 0),
            'saldo_formatado': formatar_saldo_horas(saldo_dia),
            'incompleto': data_dia in dias_incompletos,
        })
    
    # Paginação
    paginator = Paginator(registros, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Justificativas para modal
    justificativas = [
        ('ESQUECIMENTO', 'Esquecimento do profissional'),
        ('PROBLEMA_SISTEMA', 'Problema no sistema de ponto'),
        ('EMERGENCIA', 'Emergência/urgência médica'),
        ('REUNIAO', 'Reunião prolongada'),
        ('ATIVIDADE_EXTERNA', 'Atividade externa'),
        ('FALHA_EQUIPAMENTO', 'Falha no equipamento'),
        ('CAPACITACAO', 'Capacitação/treinamento'),
        ('OUTRO', 'Outro (especificar)'),
    ]
    
    context = {
        'profissional': profissional,
        'estabelecimento': estabelecimento,
        'carga_horaria_diaria': formatar_horas(carga_diaria),
        'carga_horaria_semanal': carga_horaria_semanal_formatada,
        'tolerancia_minutos': tolerancia_minutos,
        
        'banco_horas': {
            'saldo_minutos': saldo_minutos,
            'saldo_formatado': saldo_formatado,
            'status_cor': 'success' if saldo_minutos >= 0 else 'warning',
            'status_texto': 'Crédito' if saldo_minutos >= 0 else 'Débito',
            'horas_trabalhadas': horas_trabalhadas_formatadas,
            'horas_trabalhadas_decimal': horas_trabalhadas_decimal,
            'horas_previstas': horas_previstas_formatadas,
            'horas_previstas_decimal': horas_previstas_decimal,
            'percentual_concluido': percentual_concluido,
        },
        
        'total_atrasos': stats_atrasos['total_atrasos'],
        'total_saidas_antecipadas': stats_atrasos['total_saidas_antecipadas'],
        'atraso_excedente': stats_atrasos['atraso_excedente'],
        'saida_antecipada_excedente': stats_atrasos['saida_antecipada_excedente'],
        'registros_com_atraso': stats_atrasos['registros_com_atraso'],
        'registros_com_saida_antecipada': stats_atrasos['registros_com_saida_antecipada'],
        'media_atrasos': round(stats_atrasos['media_atrasos'], 1),
        'media_saidas_antecipadas': round(stats_atrasos['media_saidas_antecipadas'], 1),
        
        'registros': registros,
        'page_obj': page_obj,
        'registros_agrupados': registros_agrupados,
        'total_registros': total_registros,
        'entradas': entradas,
        'saidas': saidas,
        
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'data_inicio_str': data_inicio_str,
        'data_fim_str': data_fim_str,
        'dias_uteis': dias_uteis,
        'dias_trabalhados': dias_trabalhados,
        'dias_incompletos': dias_incompletos,
        'total_dias_incompletos': len(dias_incompletos),
        
        'horas_por_dia': horas_por_dia_semana,
        
        'is_plantao_12h': carga_diaria.total_seconds() == 43200,
        'is_plantao_24h': carga_diaria.total_seconds() == 86400,
        
        'diferenca_horas_decimal': round(horas_trabalhadas_decimal - horas_previstas_decimal, 2),
        'horas_trabalhadas': horas_trabalhadas_formatadas,
        'horas_trabalhadas_decimal': horas_trabalhadas_decimal,
        
        'justificativas': justificativas,
        'hoje': hoje,
    }
    
    return render(request, 'core/relatorio_profissional.html', context)


@login_required
def relatorio_profissional_pdf(request, profissional_id):
    """Gera PDF do relatório do profissional"""
    try:
        profissional = get_object_or_404(Profissional, id=profissional_id)
        
        if not request.user.is_superuser and profissional.usuario != request.user:
            messages.error(request, "Acesso não autorizado.")
            return redirect('core:dashboard')
        
        # Processar filtros
        hoje = timezone.now().date()
        inicio_mes = hoje.replace(day=1)
        
        data_inicio_str = request.GET.get('data_inicio')
        data_fim_str = request.GET.get('data_fim')
        
        try:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else inicio_mes
        except (ValueError, TypeError):
            data_inicio = inicio_mes
        
        try:
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else hoje
        except (ValueError, TypeError):
            data_fim = hoje
        
        if data_fim < data_inicio:
            data_fim = data_inicio
        
        # Buscar dados
        registros = RegistroPonto.objects.filter(
            profissional=profissional,
            data__range=[data_inicio, data_fim]
        ).order_by('data', 'horario')
        
        horas_trabalhadas = calcular_horas_trabalhadas_periodo(data_inicio, data_fim, profissional)
        horas_previstas = calcular_horas_previstas_periodo(profissional, data_inicio, data_fim)
        
        # Agrupar por dia
        registros_por_data = defaultdict(list)
        for registro in registros:
            registros_por_data[registro.data].append(registro)
        
        horas_por_dia = []
        for data_dia, regs_dia in sorted(registros_por_data.items()):
            horas_dia = calcular_horas_trabalhadas_dia(regs_dia)
            horas_por_dia.append({
                'data': data_dia.strftime('%d/%m/%Y'),
                'dia_semana': data_dia.strftime('%A'),
                'horas': formatar_horas(horas_dia),
                'horas_decimal': round(horas_dia.total_seconds() / 3600, 2),
            })
        
        context = {
            'profissional': profissional,
            'registros': registros,
            'horas_por_dia': horas_por_dia,
            'horas_trabalhadas': formatar_horas(horas_trabalhadas),
            'horas_trabalhadas_decimal': round(horas_trabalhadas.total_seconds() / 3600, 2),
            'carga_horaria_diaria': formatar_horas(obter_carga_horaria_timedelta(profissional.carga_horaria_diaria)),
            'carga_horaria_semanal': formatar_horas(obter_carga_horaria_timedelta(profissional.carga_horaria_semanal)) if profissional.carga_horaria_semanal else '40:00',
            'carga_horaria_esperada': formatar_horas(horas_previstas),
            'diferenca_horas_decimal': round((horas_trabalhadas.total_seconds() - horas_previstas.total_seconds()) / 3600, 2),
            'total_registros': registros.count(),
            'entradas': registros.filter(tipo='ENTRADA').count(),
            'saidas': registros.filter(tipo='SAIDA').count(),
            'data_inicio': data_inicio.strftime('%d/%m/%Y'),
            'data_fim': data_fim.strftime('%d/%m/%Y'),
            'gerado_em': timezone.now(),
            'usuario': request.user.get_full_name() or request.user.username,
        }
        
        html_string = render_to_string('core/relatorio_profissional_pdf.html', context)
        
        response = HttpResponse(content_type='application/pdf')
        filename = f"relatorio_{profissional.cpf}_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
        
        return response
        
    except Exception as e:
        messages.error(request, f"Erro ao gerar PDF: {str(e)}")
        return redirect('core:relatorio_profissional', profissional_id=profissional_id)


# ======================
# RELATÓRIOS GERAIS
# ======================

@login_required
@user_passes_test(is_admin)
def relatorios_gerais(request):
    """Relatórios gerais de ponto"""
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    estabelecimento_id = request.GET.get('estabelecimento_id')
    
    # Base query
    registros = RegistroPonto.objects.select_related('profissional', 'estabelecimento').all()
    
    if data_inicio:
        registros = registros.filter(data__gte=data_inicio)
    if data_fim:
        registros = registros.filter(data__lte=data_fim)
    if estabelecimento_id:
        registros = registros.filter(estabelecimento_id=estabelecimento_id)
    
    # Estatísticas gerais
    total_registros = registros.count()
    entradas = registros.filter(tipo='ENTRADA').count()
    saidas = registros.filter(tipo='SAIDA').count()
    
    # Paginação dos registros
    registros_ordenados = registros.order_by('-data', '-horario')
    paginator_registros = Paginator(registros_ordenados, 20)
    page_registros = paginator_registros.get_page(request.GET.get('page_registros', 1))
    
    # Estatísticas por profissional
    profissionais_ids = registros.values_list('profissional_id', flat=True).distinct()
    por_profissional = []
    
    for prof_id in profissionais_ids[:50]:  # Limitar para performance
        try:
            prof = Profissional.objects.get(id=prof_id)
            registros_prof = registros.filter(profissional=prof)
            
            if data_inicio and data_fim:
                data_incio_date = datetime.strptime(data_inicio, '%Y-%m-%d').date() if isinstance(data_inicio, str) else data_inicio
                data_fim_date = datetime.strptime(data_fim, '%Y-%m-%d').date() if isinstance(data_fim, str) else data_fim
                horas_prof = calcular_horas_trabalhadas_periodo(data_incio_date, data_fim_date, prof)
            else:
                horas_prof = timedelta()
            
            por_profissional.append({
                'profissional': prof,
                'total_registros': registros_prof.count(),
                'entradas': registros_prof.filter(tipo='ENTRADA').count(),
                'saidas': registros_prof.filter(tipo='SAIDA').count(),
                'horas_trabalhadas': horas_prof,
            })
        except Profissional.DoesNotExist:
            continue
    
    # Paginação dos profissionais
    paginator_profissionais = Paginator(por_profissional, 15)
    page_profissionais = paginator_profissionais.get_page(request.GET.get('page_profissionais', 1))
    
    context = {
        'page_registros': page_registros,
        'page_profissionais': page_profissionais,
        'total_registros': total_registros,
        'entradas': entradas,
        'saidas': saidas,
        'por_profissional': por_profissional,
        'estabelecimentos': Estabelecimento.objects.all(),
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'estabelecimento_id': estabelecimento_id,
    }
    
    return render(request, 'core/relatorios_gerais.html', context)


# ======================
# PERFIL DO USUÁRIO
# ======================

@login_required
def meu_perfil(request):
    """Perfil do próprio usuário"""
    if not hasattr(request.user, 'profissional'):
        messages.error(request, 'Você não tem um perfil profissional.')
        return redirect('core:dashboard')
    
    profissional = request.user.profissional
    trinta_dias_atras = timezone.now().date() - timedelta(days=30)
    
    registros = RegistroPonto.objects.filter(
        profissional=profissional,
        data__gte=trinta_dias_atras
    ).select_related('estabelecimento').order_by('-data', '-horario')[:30]
    
    inicio_mes = timezone.now().replace(day=1).date()
    horas_mes = calcular_horas_trabalhadas_periodo(inicio_mes, timezone.now().date(), profissional)
    
    context = {
        'profissional': profissional,
        'registros': registros,
        'horas_mes': horas_mes,
    }
    
    return render(request, 'core/meu_perfil.html', context)


# ======================
# HISTÓRICO E ANÁLISES
# ======================

@login_required
@user_passes_test(is_admin)
def historico_pontos_profissional(request, profissional_id):
    """Histórico completo de pontos de um profissional"""
    profissional = get_object_or_404(Profissional, id=profissional_id)
    
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    estabelecimento_id = request.GET.get('estabelecimento_id')
    
    registros = RegistroPonto.objects.filter(profissional=profissional).select_related('estabelecimento')
    
    if data_inicio:
        registros = registros.filter(data__gte=data_inicio)
    if data_fim:
        registros = registros.filter(data__lte=data_fim)
    if estabelecimento_id:
        registros = registros.filter(estabelecimento_id=estabelecimento_id)
    
    registros = registros.order_by('-data', '-horario')
    
    # Agrupar por dia
    registros_por_dia = defaultdict(list)
    for registro in registros:
        registros_por_dia[registro.data].append(registro)
    
    horas_por_dia = {}
    for data_dia, regs_dia in registros_por_dia.items():
        horas_por_dia[data_dia] = calcular_horas_trabalhadas_dia(regs_dia)
    
    horas_trabalhadas = sum(horas_por_dia.values(), timedelta())
    dias_trabalhados = len(horas_por_dia)
    
    context = {
        'profissional': profissional,
        'registros': registros,
        'registros_por_dia': dict(registros_por_dia),
        'horas_por_dia': horas_por_dia,
        'total_registros': registros.count(),
        'entradas': registros.filter(tipo='ENTRADA').count(),
        'saidas': registros.filter(tipo='SAIDA').count(),
        'horas_trabalhadas': horas_trabalhadas,
        'dias_trabalhados': dias_trabalhados,
        'media_horas_dia': horas_trabalhadas / dias_trabalhados if dias_trabalhados > 0 else timedelta(),
        'estabelecimentos': Estabelecimento.objects.all(),
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'estabelecimento_id': estabelecimento_id,
    }
    
    return render(request, 'core/historico_pontos.html', context)


@login_required
@user_passes_test(is_admin)
def horas_trabalhadas_profissional(request, profissional_id):
    """Relatório detalhado de horas trabalhadas"""
    profissional = get_object_or_404(Profissional, id=profissional_id)
    
    mes = request.GET.get('mes')
    ano = request.GET.get('ano', timezone.now().year)
    
    if mes:
        data_inicio = date(int(ano), int(mes), 1)
        if int(mes) == 12:
            data_fim = date(int(ano) + 1, 1, 1) - timedelta(days=1)
        else:
            data_fim = date(int(ano), int(mes) + 1, 1) - timedelta(days=1)
    else:
        data_fim = timezone.now().date()
        data_inicio = data_fim - timedelta(days=30)
    
    registros = RegistroPonto.objects.filter(
        profissional=profissional,
        data__gte=data_inicio,
        data__lte=data_fim
    ).order_by('data', 'horario')
    
    registros_por_data = defaultdict(list)
    for registro in registros:
        registros_por_data[registro.data].append(registro)
    
    dias_trabalho = []
    for data_dia in (data_inicio + timedelta(n) for n in range((data_fim - data_inicio).days + 1)):
        if data_dia in registros_por_data:
            horas_dia = calcular_horas_trabalhadas_dia(registros_por_data[data_dia])
            if horas_dia.total_seconds() > 0:
                dias_trabalho.append({
                    'data': data_dia,
                    'horas': horas_dia,
                    'horas_decimal': horas_dia.total_seconds() / 3600,
                    'registros': registros_por_data[data_dia]
                })
    
    total_horas = sum((d['horas'] for d in dias_trabalho), timedelta())
    
    context = {
        'profissional': profissional,
        'dias_trabalho': dias_trabalho,
        'total_horas': total_horas,
        'total_horas_decimal': total_horas.total_seconds() / 3600,
        'media_horas_dia': total_horas / len(dias_trabalho) if dias_trabalho else timedelta(),
        'dias_uteis': calcular_dias_uteis(data_inicio, data_fim),
        'mes': mes,
        'ano': ano,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
    }
    
    return render(request, 'core/horas_trabalhadas.html', context)


@login_required
@user_passes_test(is_admin)
def analise_frequencia_profissional(request, profissional_id):
    """Análise de frequência e faltas"""
    profissional = get_object_or_404(Profissional, id=profissional_id)
    
    mes = request.GET.get('mes')
    ano = request.GET.get('ano', timezone.now().year)
    
    if mes:
        data_inicio = date(int(ano), int(mes), 1)
        if int(mes) == 12:
            data_fim = date(int(ano) + 1, 1, 1) - timedelta(days=1)
        else:
            data_fim = date(int(ano), int(mes) + 1, 1) - timedelta(days=1)
    else:
        hoje = timezone.now().date()
        data_inicio = hoje.replace(day=1)
        data_fim = hoje
    
    dias_uteis = calcular_dias_uteis(data_inicio, data_fim)
    dias_com_registro = RegistroPonto.objects.filter(
        profissional=profissional,
        data__gte=data_inicio,
        data__lte=data_fim
    ).values('data').distinct().count()
    
    faltas = max(0, dias_uteis - dias_com_registro)
    percentual_frequencia = (dias_com_registro / dias_uteis * 100) if dias_uteis > 0 else 0
    
    # Dias incompletos
    dias_incompletos = 0
    data_atual = data_inicio
    while data_atual <= data_fim:
        if data_atual.weekday() < 5:
            registros_dia = RegistroPonto.objects.filter(
                profissional=profissional,
                data=data_atual
            )
            entradas = registros_dia.filter(tipo='ENTRADA').count()
            saidas = registros_dia.filter(tipo='SAIDA').count()
            if (entradas > 0 and saidas == 0) or (entradas == 0 and saidas > 0):
                dias_incompletos += 1
        data_atual += timedelta(days=1)
    
    context = {
        'profissional': profissional,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'dias_uteis': dias_uteis,
        'dias_trabalhados': dias_com_registro,
        'faltas': faltas,
        'percentual_frequencia': percentual_frequencia,
        'dias_incompletos': dias_incompletos,
        'mes': mes,
        'ano': ano,
    }
    
    return render(request, 'core/analise_frequencia.html', context)


def get_client_ip(request):
    """Obtém o IP do cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

@login_required
@user_passes_test(is_admin)
def relatorio_consolidado_profissional(request, profissional_id):
    """Relatório consolidado com todos os dados"""
    profissional = get_object_or_404(Profissional, id=profissional_id)
    
    mes = request.GET.get('mes')
    ano = request.GET.get('ano', timezone.now().year)
    
    if mes:
        data_inicio = date(int(ano), int(mes), 1)
        if int(mes) == 12:
            data_fim = date(int(ano) + 1, 1, 1) - timedelta(days=1)
        else:
            data_fim = date(int(ano), int(mes) + 1, 1) - timedelta(days=1)
    else:
        data_fim = timezone.now().date()
        data_inicio = data_fim - timedelta(days=30)
    
    horas_trabalhadas = calcular_horas_trabalhadas_periodo(data_inicio, data_fim, profissional)
    
    dias_uteis = calcular_dias_uteis(data_inicio, data_fim)
    dias_trabalhados = RegistroPonto.objects.filter(
        profissional=profissional,
        data__gte=data_inicio,
        data__lte=data_fim
    ).values('data').distinct().count()
    
    registros = RegistroPonto.objects.filter(
        profissional=profissional,
        data__gte=data_inicio,
        data__lte=data_fim
    )
    total_registros = registros.count()
    entradas = registros.filter(tipo='ENTRADA').count()
    saidas = registros.filter(tipo='SAIDA').count()
    
    context = {
        'profissional': profissional,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'horas_trabalhadas': horas_trabalhadas,
        'dias_uteis': dias_uteis,
        'dias_trabalhados': dias_trabalhados,
        'faltas': dias_uteis - dias_trabalhados,
        'total_registros': total_registros,
        'entradas': entradas,
        'saidas': saidas,
        'mes': mes,
        'ano': ano,
    }
    
    if 'pdf' in request.GET:
        return gerar_pdf_relatorio_consolidado(request, context)
    
    return render(request, 'core/relatorio_consolidado.html', context)


def gerar_pdf_relatorio_consolidado(request, context):
    """Gera PDF do relatório consolidado"""
    try:
        context['gerado_em'] = timezone.now()
        context['usuario_gerador'] = request.user.get_full_name() or request.user.username
        
        html_string = render_to_string('core/relatorio_consolidado_pdf.html', context)
        
        response = HttpResponse(content_type='application/pdf')
        filename = f"relatorio_consolidado_{context['profissional'].cpf}_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
        
        return response
        
    except Exception as e:
        messages.error(request, "Erro ao gerar PDF")
        return redirect(request.META.get('HTTP_REFERER', 'core:relatorio_profissional'))