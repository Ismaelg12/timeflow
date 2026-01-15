from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from datetime import timedelta, datetime, date
from weasyprint import HTML

from usuarios.models import Profissional
from estabelecimentos.models import Estabelecimento
from municipio.models import Municipio
from ponto.models import RegistroPonto
from collections import defaultdict
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger




def is_admin(user):
    return user.is_superuser or user.is_staff

def registrar_log(usuario, acao, detalhes='', request=None):
    """Função placeholder para logs - pode ser implementada posteriormente"""
    pass

@login_required
def dashboard(request):
    """
    Painel administrativo principal - APENAS para superusers
    Se usuário comum tentar acessar, redireciona para seus relatórios pessoais
    """
    # ✅ VERIFICAÇÃO DE TIPO DE USUÁRIO - CORREÇÃO CRÍTICA
    if not request.user.is_superuser:
        try:
            # Redireciona usuários comuns para seus relatórios pessoais
            profissional = Profissional.objects.get(usuario=request.user)
            # ✅ CORREÇÃO: Use o nome correto da URL
            return redirect('core:relatorio_profissional', profissional_id=profissional.id)
        except Profissional.DoesNotExist:
            # Se não tem perfil profissional, faz logout
            messages.error(request, "Perfil não encontrado.")
            return redirect('logout')
    
    # ✅ APENAS SUPERUSERS CHEGAM AQUI
    # Estatísticas gerais
    total_profissionais = Profissional.objects.filter(ativo=True).count()
    total_estabelecimentos = Estabelecimento.objects.count()
    total_municipios = Municipio.objects.count()
    
    # Registros de hoje
    hoje = timezone.now().date()
    registros_hoje = RegistroPonto.objects.filter(data=hoje).count()
    entradas_hoje = RegistroPonto.objects.filter(data=hoje, tipo='ENTRADA').count()
    saidas_hoje = RegistroPonto.objects.filter(data=hoje, tipo='SAIDA').count()
    
    # Calcular horas trabalhadas hoje
    horas_hoje = calcular_horas_trabalhadas_periodo(hoje, hoje)
    
    # Últimos registros
    ultimos_registros = RegistroPonto.objects.select_related(
        'profissional', 'estabelecimento'
    ).order_by('-data', '-horario')[:10]
    
    context = {
        'total_profissionais': total_profissionais,
        'total_estabelecimentos': total_estabelecimentos,
        'total_municipios': total_municipios,
        'registros_hoje': registros_hoje,
        'entradas_hoje': entradas_hoje,
        'saidas_hoje': saidas_hoje,
        'horas_hoje': horas_hoje,
        'ultimos_registros': ultimos_registros,
    }
    return render(request, 'core/dashboard.html', context)

def calcular_horas_trabalhadas_periodo(data_inicio, data_fim, profissional=None):
    """Calcula horas trabalhadas no período"""
    filtros = Q(data__gte=data_inicio, data__lte=data_fim)
    if profissional:
        filtros &= Q(profissional=profissional)
    
    registros = RegistroPonto.objects.filter(filtros).order_by('data', 'horario')
    
    # Agrupar por dia e calcular horas trabalhadas
    horas_por_dia = {}
    dia_atual = None
    entrada_atual = None
    data_entrada_atual = None
    
    for registro in registros:
        if registro.tipo == 'ENTRADA':
            entrada_atual = registro.horario
            data_entrada_atual = registro.data
            dia_atual = registro.data
        elif registro.tipo == 'SAIDA' and entrada_atual and registro.data == dia_atual:
            if dia_atual not in horas_por_dia:
                horas_por_dia[dia_atual] = timedelta()
            
            hora_entrada = datetime.combine(data_entrada_atual, entrada_atual)
            hora_saida = datetime.combine(registro.data, registro.horario)
            horas_trabalhadas = hora_saida - hora_entrada
            
            horas_por_dia[dia_atual] += horas_trabalhadas
            entrada_atual = None
            data_entrada_atual = None
    
    total_horas = sum(horas_por_dia.values(), timedelta())
    return total_horas



@login_required
@user_passes_test(is_admin)
def relatorios_gerais(request):
    """Relatórios gerais de ponto com paginação"""
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    estabelecimento_id = request.GET.get('estabelecimento_id')
    
    # Parâmetros de paginação
    page_registros_num = request.GET.get('page_registros', 1)
    page_profissionais_num = request.GET.get('page_profissionais', 1)
    
    # Filtros
    registros = RegistroPonto.objects.select_related(
        'profissional', 'estabelecimento'
    ).all()
    
    if data_inicio:
        registros = registros.filter(data__gte=data_inicio)
    if data_fim:
        registros = registros.filter(data__lte=data_fim)
    if estabelecimento_id:
        registros = registros.filter(estabelecimento_id=estabelecimento_id)
    
    # Estatísticas
    total_registros = registros.count()
    entradas = registros.filter(tipo='ENTRADA').count()
    saidas = registros.filter(tipo='SAIDA').count()
    
    # Calcular horas trabalhadas
    if data_inicio and data_fim:
        horas_trabalhadas = calcular_horas_trabalhadas_periodo(data_inicio, data_fim)
    else:
        horas_trabalhadas = timedelta(0)
    
    # Agrupar por profissional
    profissionais_ids = registros.values_list('profissional_id', flat=True).distinct()
    por_profissional = []
    
    for prof_id in profissionais_ids:
        prof_registros = registros.filter(profissional_id=prof_id)
        profissional = Profissional.objects.get(id=prof_id)
        
        if data_inicio and data_fim:
            horas_prof = calcular_horas_trabalhadas_periodo(data_inicio, data_fim, profissional)
        else:
            horas_prof = timedelta(0)
        
        por_profissional.append({
            'profissional': profissional,
            'total_registros': prof_registros.count(),
            'entradas': prof_registros.filter(tipo='ENTRADA').count(),
            'saidas': prof_registros.filter(tipo='SAIDA').count(),
            'horas_trabalhadas': horas_prof,
        })
    
    # Paginação dos registros
    registros_ordenados = registros.order_by('-data', '-horario')
    paginator_registros = Paginator(registros_ordenados, 20)  # 20 registros por página
    
    try:
        page_registros = paginator_registros.page(page_registros_num)
    except PageNotAnInteger:
        page_registros = paginator_registros.page(1)
    except EmptyPage:
        page_registros = paginator_registros.page(paginator_registros.num_pages)
    
    # Paginação dos profissionais
    paginator_profissionais = Paginator(por_profissional, 15)  # 15 profissionais por página
    
    try:
        page_profissionais = paginator_profissionais.page(page_profissionais_num)
    except PageNotAnInteger:
        page_profissionais = paginator_profissionais.page(1)
    except EmptyPage:
        page_profissionais = paginator_profissionais.page(paginator_profissionais.num_pages)
    
    estabelecimentos = Estabelecimento.objects.all()
    
    context = {
        'page_registros': page_registros,
        'page_profissionais': page_profissionais,
        'total_registros': total_registros,
        'entradas': entradas,
        'saidas': saidas,
        'horas_trabalhadas': horas_trabalhadas,
        'por_profissional': por_profissional,
        'estabelecimentos': estabelecimentos,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'estabelecimento_id': estabelecimento_id,
    }
    return render(request, 'core/relatorios_gerais.html', context)



@login_required
def relatorio_profissional(request, profissional_id):
    """Relatório do profissional - com verificação de segurança"""
    
    profissional = get_object_or_404(Profissional, id=profissional_id)
    
    # ✅ VERIFICAÇÃO DE SEGURANÇA: Usuário comum só pode ver seus próprios dados
    if not request.user.is_superuser and profissional.usuario != request.user:
        messages.error(request, "Acesso não autorizado.")
        return redirect('core:dashboard')
    profissional = get_object_or_404(Profissional, id=profissional_id)
    
    # Obter parâmetros de data
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    
    # Definir datas padrão: início do mês atual e data atual
    hoje = timezone.now().date()
    inicio_mes = hoje.replace(day=1)  # Primeiro dia do mês atual
    
    # ✅ CORREÇÃO: Manter as datas como string para o template
    data_inicio_str = data_inicio
    data_fim_str = data_fim
    
    if not data_inicio:
        data_inicio = inicio_mes
        data_inicio_str = inicio_mes.strftime('%Y-%m-%d')
    else:
        try:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            data_inicio_str = data_inicio.strftime('%Y-%m-%d')
        except ValueError:
            data_inicio = inicio_mes
            data_inicio_str = inicio_mes.strftime('%Y-%m-%d')
    
    if not data_fim:
        data_fim = hoje
        data_fim_str = hoje.strftime('%Y-%m-%d')
    else:
        try:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
            data_fim_str = data_fim.strftime('%Y-%m-%d')
        except ValueError:
            data_fim = hoje
            data_fim_str = hoje.strftime('%Y-%m-%d')
    
    # ✅ CORREÇÃO: Use os campos diretos do Profissional
    estabelecimento = profissional.estabelecimento
    
    # ✅ CORREÇÃO CRÍTICA: Verificar se carga_horaria não é None
    carga_horaria_diaria = profissional.carga_horaria_diaria
    carga_horaria_semanal = profissional.carga_horaria_semanal
    
    # Buscar registros de ponto no período
    registros = RegistroPonto.objects.filter(
        profissional=profissional,
        data__range=[data_inicio, data_fim]
    ).order_by('data', 'horario')
    
    # ✅ PAGINAÇÃO: Adicionar paginação
    page_number = request.GET.get('page', 1)
    paginator = Paginator(registros, 20)  # 20 registros por página
    
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)

    # ✅ NOVAS ESTATÍSTICAS DE TOLERÂNCIA
    registros_com_atraso = registros.filter(atraso_minutos__gt=0).count()
    registros_com_saida_antecipada = registros.filter(saida_antecipada_minutos__gt=0).count()
    total_atrasos = sum(r.atraso_minutos for r in registros)
    total_saidas_antecipadas = sum(r.saida_antecipada_minutos for r in registros)
    
    # Calcular médias
    media_atrasos = total_atrasos / registros_com_atraso if registros_com_atraso > 0 else 0
    media_saidas_antecipadas = total_saidas_antecipadas / registros_com_saida_antecipada if registros_com_saida_antecipada > 0 else 0
    
    # Calcular estatísticas (usar todos os registros, não apenas a página)
    total_registros = registros.count()
    entradas = registros.filter(tipo='ENTRADA').count()
    saidas = registros.filter(tipo='SAIDA').count()
    
    # Agrupar registros por data para calcular horas trabalhadas
    registros_por_data = {}
    for registro in registros:
        data_str = registro.data.isoformat()
        if data_str not in registros_por_data:
            registros_por_data[data_str] = {'entrada': None, 'saida': None, 'data_obj': registro.data}
        
        if registro.tipo == 'ENTRADA':
            registros_por_data[data_str]['entrada'] = registro.horario
        elif registro.tipo == 'SAIDA':
            registros_por_data[data_str]['saida'] = registro.horario
    
    # Cálculos de horas trabalhadas
    total_horas_trabalhadas = timedelta()
    horas_por_dia_semana = {
        'Segunda': timedelta(),
        'Terça': timedelta(), 
        'Quarta': timedelta(),
        'Quinta': timedelta(),
        'Sexta': timedelta(),
        'Sábado': timedelta(),
        'Domingo': timedelta()
    }
    
    dias_trabalhados = 0
    
    for data_str, horarios in registros_por_data.items():
        entrada = horarios['entrada']
        saida = horarios['saida']
        data_obj = horarios['data_obj']
        
        if entrada and saida:
            # Converter para datetime para calcular diferença
            entrada_dt = datetime.combine(datetime.min, entrada)
            saida_dt = datetime.combine(datetime.min, saida)
            
            # Se saída for antes da entrada, assumir que é no dia seguinte
            if saida_dt < entrada_dt:
                saida_dt += timedelta(days=1)
            
            horas_trabalhadas = saida_dt - entrada_dt
            total_horas_trabalhadas += horas_trabalhadas
            dias_trabalhados += 1
            
            # Adicionar horas ao dia da semana correspondente
            dias_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
            dia_semana = dias_semana[data_obj.weekday()]
            horas_por_dia_semana[dia_semana] += horas_trabalhadas
    
    # ✅ CORREÇÃO: Calcular dias úteis com função auxiliar
    def calcular_dias_uteis(data_inicio, data_fim):
        """Calcula o número de dias úteis (segunda a sexta) no período"""
        dias_uteis = 0
        current_date = data_inicio
        
        while current_date <= data_fim:
            # Segunda = 0, Sexta = 4
            if current_date.weekday() < 5:  # Segunda a Sexta
                dias_uteis += 1
            current_date += timedelta(days=1)
        
        return dias_uteis
    
    # Calcular horas previstas
    dias_uteis = calcular_dias_uteis(data_inicio, data_fim)
    
    # ✅ CORREÇÃO CRÍTICA: Verificar se carga_horaria_diaria não é None
    if carga_horaria_diaria:
        horas_diarias_segundos = carga_horaria_diaria.total_seconds()
        horas_previstas_segundos = horas_diarias_segundos * dias_uteis
        horas_previstas = timedelta(seconds=horas_previstas_segundos)
    else:
        horas_previstas = timedelta()
    
    # Calcular saldo de horas
    saldo_horas = total_horas_trabalhadas - horas_previstas
    
    # Converter timedelta para horas legíveis
    def formatar_horas(td):
        if not td:
            return "00:00"
        total_segundos = int(td.total_seconds())
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60
        return f"{horas:02d}:{minutos:02d}"
    
    # Converter para horas decimais para cálculos
    def horas_para_decimal(td):
        if not td:
            return 0.0
        return td.total_seconds() / 3600
    
    # Preparar dados para o template
    horas_trabalhadas_decimal = horas_para_decimal(total_horas_trabalhadas)
    horas_previstas_decimal = horas_para_decimal(horas_previstas)
    diferenca_horas_decimal = horas_trabalhadas_decimal - horas_previstas_decimal
    
    # Preparar dados para gráfico
    horas_por_dia = []
    for dia, horas in horas_por_dia_semana.items():
        horas_decimal = horas_para_decimal(horas)
        horas_por_dia.append({
            'dia': dia,
            'horas': formatar_horas(horas),
            'horas_decimal': horas_decimal,
            'registros': 2 if horas_decimal > 0 else 0  # Aproximação
        })
    
    # ✅ CORREÇÃO: Formatar carga horária para exibição
    def formatar_carga_horaria(duration_field):
        """Formata DurationField para exibição"""
        if not duration_field:
            return "Não definida"
        return formatar_horas(duration_field)
    
    context = {
        'profissional': profissional,
        'estabelecimento': estabelecimento,
        'carga_horaria_diaria': formatar_carga_horaria(carga_horaria_diaria),
        'carga_horaria_semanal': formatar_carga_horaria(carga_horaria_semanal),
        'carga_horaria_diaria_raw': carga_horaria_diaria,  # Mantém o objeto original
        'carga_horaria_semanal_raw': carga_horaria_semanal,  # Mantém o objeto original
        'registros': registros,  # Mantém todos os registros para estatísticas
        'page_obj': page_obj,    # Adiciona objeto de paginação
        'data_inicio': data_inicio_str,
        'data_fim': data_fim_str,
        
         # ✅ NOVOS CAMPOS PARA TOLERÂNCIA
        'registros_com_atraso': registros_com_atraso,
        'registros_com_saida_antecipada': registros_com_saida_antecipada,
        'total_atrasos': total_atrasos,
        'total_saidas_antecipadas': total_saidas_antecipadas,
        'media_atrasos': media_atrasos,
        'media_saidas_antecipadas': media_saidas_antecipadas,

        # Estatísticas
        'total_registros': total_registros,
        'entradas': entradas,
        'saidas': saidas,
        'horas_trabalhadas': formatar_horas(total_horas_trabalhadas),
        'horas_trabalhadas_decimal': round(horas_trabalhadas_decimal, 2),
        'horas_previstas': formatar_horas(horas_previstas),
        'horas_previstas_decimal': round(horas_previstas_decimal, 2),
        'diferenca_horas_decimal': round(diferenca_horas_decimal, 2),
        'saldo_horas': formatar_horas(saldo_horas),
        'dias_uteis': dias_uteis,
        'dias_trabalhados': dias_trabalhados,
        
        # Dados para gráficos
        'horas_por_dia': horas_por_dia,
        
        # Campos que o template espera
        'carga_horaria_esperada': formatar_horas(horas_previstas),
        'vinculo': {'estabelecimento': estabelecimento} if estabelecimento else None,
    }
    
    return render(request, 'core/relatorio_profissional.html', context)

@login_required
def meu_perfil(request):
    """Perfil do próprio usuário"""
    if not hasattr(request.user, 'profissional'):
        messages.error(request, 'Você não tem um perfil profissional.')
        return redirect('core:dashboard')
    
    profissional = request.user.profissional
    
    # Histórico de pontos (últimos 30 dias)
    trinta_dias_atras = timezone.now().date() - timedelta(days=30)
    registros = RegistroPonto.objects.filter(
        profissional=profissional,
        data__gte=trinta_dias_atras
    ).select_related('estabelecimento').order_by('-data', '-horario')[:30]
    
    # Horas do mês
    inicio_mes = timezone.now().replace(day=1).date()
    horas_mes = calcular_horas_trabalhadas_periodo(inicio_mes, timezone.now().date(), profissional)
    
    context = {
        'profissional': profissional,
        'registros': registros,
        'horas_mes': horas_mes,
    }
    return render(request, 'core/meu_perfil.html', context)

# ===== FUNÇÕES AUXILIARES CORRIGIDAS =====

def calcular_dias_uteis(data_inicio, data_fim):
    """Calcula quantidade de dias úteis no período"""
    # ✅ CORREÇÃO: Esta função agora recebe objetos date, não strings
    dias_uteis = 0
    current_date = data_inicio
    
    while current_date <= data_fim:
        # Considera apenas dias de semana (segunda a sexta)
        if current_date.weekday() < 5:
            dias_uteis += 1
        current_date += timedelta(days=1)
    
    return dias_uteis

def calcular_horas_trabalhadas_por_dia_semana(data_inicio, data_fim, profissional, dia_semana):
    """Calcula horas trabalhadas para um específico dia da semana"""
    # ✅ CORREÇÃO: Esta função agora recebe objetos date, não strings
    registros = RegistroPonto.objects.filter(
        profissional=profissional,
        data__gte=data_inicio,
        data__lte=data_fim,
        data__week_day=dia_semana
    ).order_by('data', 'horario')
    
    return calcular_horas_trabalhadas_periodo(data_inicio, data_fim, profissional)

def calcular_horas_trabalhadas_dia(registros_dia):
    """Calcula horas trabalhadas em um dia específico"""
    horas_dia = timedelta()
    entrada_atual = None
    data_entrada = None
    
    for registro in sorted(registros_dia, key=lambda x: x.horario):
        if registro.tipo == 'ENTRADA':
            entrada_atual = registro.horario
            data_entrada = registro.data
        elif registro.tipo == 'SAIDA' and entrada_atual and data_entrada:
            if registro.data == data_entrada:
                hora_entrada = datetime.combine(data_entrada, entrada_atual)
                hora_saida = datetime.combine(registro.data, registro.horario)
                horas_trabalhadas = hora_saida - hora_entrada
                horas_dia += horas_trabalhadas
            entrada_atual = None
            data_entrada = None
    
    return horas_dia

def gerar_pdf_relatorio_profissional(request, profissional, registros, horas_trabalhadas,
                                   carga_horaria_diaria, carga_horaria_semanal, 
                                   data_inicio, data_fim, horas_trabalhadas_decimal,
                                   diferenca_horas_decimal, total_registros, entradas,
                                   saidas, carga_horaria_esperada, horas_por_dia):
    """Gera PDF do relatório do profissional"""
    
    context = {
        'profissional': profissional,
        'registros': registros,
        'horas_trabalhadas': horas_trabalhadas,
        'horas_trabalhadas_decimal': horas_trabalhadas_decimal,
        'carga_horaria_diaria': carga_horaria_diaria,
        'carga_horaria_semanal': carga_horaria_semanal,
        'carga_horaria_esperada': carga_horaria_esperada,
        'diferenca_horas_decimal': diferenca_horas_decimal,
        'total_registros': total_registros,
        'entradas': entradas,
        'saidas': saidas,
        'horas_por_dia': horas_por_dia,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'gerado_em': timezone.now(),
    }
    
    html_string = render_to_string('core/relatorio_profissional_pdf.html', context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_{profissional.cpf}.pdf"'
    
    HTML(string=html_string).write_pdf(response)
    
    return response

def gerar_pdf_relatorio_consolidado(request, context):
    """Gera PDF do relatório consolidado"""
    try:
        # Adicionar variáveis adicionais ao contexto
        context['gerado_em'] = timezone.now()
        context['usuario_gerador'] = request.user.get_full_name() or request.user.username
        
        html_string = render_to_string('core/relatorio_consolidado_pdf.html', context)
        
        # Configurar resposta
        response = HttpResponse(content_type='application/pdf')
        filename = f"relatorio_consolidado_{context['profissional'].cpf}_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Gerar PDF
        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
        
        return response
        
    except Exception as e:
        # Log do erro
        print(f"Erro ao gerar PDF: {str(e)}")
        
        # Retornar erro amigável
        messages.error(request, f"Erro ao gerar PDF: {str(e)}")
        return redirect(request.META.get('HTTP_REFERER', 'core:relatorio_profissional'))
# ===== VIEWS DE HISTÓRICO E ESTATÍSTICAS =====

@login_required
@user_passes_test(is_admin)
def historico_pontos_profissional(request, profissional_id):
    """Histórico completo de pontos de um profissional"""
    profissional = get_object_or_404(Profissional, id=profissional_id)
    
    # Parâmetros de filtro
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    estabelecimento_id = request.GET.get('estabelecimento_id')
    
    # Filtros
    registros = RegistroPonto.objects.filter(
        profissional=profissional
    ).select_related('estabelecimento').order_by('-data', '-horario')
    
    if data_inicio:
        registros = registros.filter(data__gte=data_inicio)
    if data_fim:
        registros = registros.filter(data__lte=data_fim)
    if estabelecimento_id:
        registros = registros.filter(estabelecimento_id=estabelecimento_id)
    
    # Agrupar registros por dia
    registros_por_dia = defaultdict(list)
    for registro in registros:
        registros_por_dia[registro.data].append(registro)
    
    # Calcular horas trabalhadas por dia
    horas_por_dia = {}
    for data_dia, registros_dia in registros_por_dia.items():
        horas_dia = calcular_horas_trabalhadas_dia(registros_dia)
        horas_por_dia[data_dia] = horas_dia
    
    # Estatísticas
    total_registros = registros.count()
    entradas = registros.filter(tipo='ENTRADA').count()
    saidas = registros.filter(tipo='SAIDA').count()
    
    # Horas trabalhadas totais
    horas_trabalhadas = sum(horas_por_dia.values(), timedelta())
    
    # Dias trabalhados
    dias_trabalhados = len(horas_por_dia)
    
    # Média de horas por dia
    media_horas_dia = horas_trabalhadas / dias_trabalhados if dias_trabalhados > 0 else timedelta()
    
    # Estabelecimentos para filtro
    estabelecimentos = Estabelecimento.objects.all()
    
    context = {
        'profissional': profissional,
        'registros': registros,
        'registros_por_dia': dict(registros_por_dia),
        'horas_por_dia': horas_por_dia,
        'total_registros': total_registros,
        'entradas': entradas,
        'saidas': saidas,
        'horas_trabalhadas': horas_trabalhadas,
        'dias_trabalhados': dias_trabalhados,
        'media_horas_dia': media_horas_dia,
        'estabelecimentos': estabelecimentos,
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
    
    # Parâmetros
    mes = request.GET.get('mes')
    ano = request.GET.get('ano', timezone.now().year)
    
    # Definir período
    if mes:
        data_inicio = date(int(ano), int(mes), 1)
        if int(mes) == 12:
            data_fim = date(int(ano) + 1, 1, 1) - timedelta(days=1)
        else:
            data_fim = date(int(ano), int(mes) + 1, 1) - timedelta(days=1)
    else:
        # Últimos 30 dias como padrão
        data_fim = timezone.now().date()
        data_inicio = data_fim - timedelta(days=30)
    
    # Calcular horas por dia
    dias_trabalho = []
    data_atual = data_inicio
    
    while data_atual <= data_fim:
        horas_dia = calcular_horas_trabalhadas_periodo(data_atual, data_atual, profissional)
        if horas_dia.total_seconds() > 0:
            dias_trabalho.append({
                'data': data_atual,
                'horas': horas_dia,
                'horas_decimal': horas_dia.total_seconds() / 3600
            })
        data_atual += timedelta(days=1)
    
    # Estatísticas
    total_horas = sum((dia['horas'] for dia in dias_trabalho), timedelta())
    total_horas_decimal = total_horas.total_seconds() / 3600
    media_horas_dia = total_horas / len(dias_trabalho) if dias_trabalho else timedelta()
    
    # Carga horária esperada
    vinculo = ProfissionalEstabelecimento.objects.filter(
        profissional=profissional, ativo=True
    ).first()
    carga_horaria_diaria = vinculo.carga_horaria_diaria if vinculo else timedelta(hours=8)
    
    # Dias úteis no período
    dias_uteis = calcular_dias_uteis(data_inicio, data_fim)
    horas_esperadas = carga_horaria_diaria * dias_uteis
    
    context = {
        'profissional': profissional,
        'dias_trabalho': dias_trabalho,
        'total_horas': total_horas,
        'total_horas_decimal': total_horas_decimal,
        'media_horas_dia': media_horas_dia,
        'carga_horaria_diaria': carga_horaria_diaria,
        'dias_uteis': dias_uteis,
        'horas_esperadas': horas_esperadas,
        'diferenca_horas': total_horas - horas_esperadas,
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
    
    # Parâmetros
    mes = request.GET.get('mes')
    ano = request.GET.get('ano', timezone.now().year)
    
    if mes:
        data_inicio = date(int(ano), int(mes), 1)
        if int(mes) == 12:
            data_fim = date(int(ano) + 1, 1, 1) - timedelta(days=1)
        else:
            data_fim = date(int(ano), int(mes) + 1, 1) - timedelta(days=1)
    else:
        # Mês atual como padrão
        hoje = timezone.now().date()
        data_inicio = hoje.replace(day=1)
        data_fim = hoje
    
    # Dias úteis no período
    dias_uteis = calcular_dias_uteis(data_inicio, data_fim)
    
    # Dias trabalhados
    dias_com_registro = RegistroPonto.objects.filter(
        profissional=profissional,
        data__gte=data_inicio,
        data__lte=data_fim
    ).values('data').distinct().count()
    
    # Faltas
    faltas = max(0, dias_uteis - dias_com_registro)
    
    # Percentual de frequência
    percentual_frequencia = (dias_com_registro / dias_uteis * 100) if dias_uteis > 0 else 0
    
    # Dias com registro incompleto (apenas entrada ou apenas saída)
    dias_incompletos = 0
    data_atual = data_inicio
    
    while data_atual <= data_fim:
        if data_atual.weekday() < 5:  # Apenas dias úteis
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

@login_required
@user_passes_test(is_admin)
def relatorio_consolidado_profissional(request, profissional_id):
    """Relatório consolidado com todos os dados"""
    profissional = get_object_or_404(Profissional, id=profissional_id)
    
    # Parâmetros
    mes = request.GET.get('mes')
    ano = request.GET.get('ano', timezone.now().year)
    
    if mes:
        data_inicio = date(int(ano), int(mes), 1)
        if int(mes) == 12:
            data_fim = date(int(ano) + 1, 1, 1) - timedelta(days=1)
        else:
            data_fim = date(int(ano), int(mes) + 1, 1) - timedelta(days=1)
    else:
        # Últimos 30 dias
        data_fim = timezone.now().date()
        data_inicio = data_fim - timedelta(days=30)
    
    # Dados de horas trabalhadas
    horas_trabalhadas = calcular_horas_trabalhadas_periodo(data_inicio, data_fim, profissional)
    
    # Dados de frequência
    dias_uteis = calcular_dias_uteis(data_inicio, data_fim)
    dias_trabalhados = RegistroPonto.objects.filter(
        profissional=profissional,
        data__gte=data_inicio,
        data__lte=data_fim
    ).values('data').distinct().count()
    
    # Carga horária
    vinculo = ProfissionalEstabelecimento.objects.filter(
        profissional=profissional, ativo=True
    ).first()
    carga_horaria_diaria = vinculo.carga_horaria_diaria if vinculo else timedelta(hours=8)
    horas_esperadas = carga_horaria_diaria * dias_uteis
    
    # Estatísticas de registros
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
        'carga_horaria_diaria': carga_horaria_diaria,
        'horas_esperadas': horas_esperadas,
        'diferenca_horas': horas_trabalhadas - horas_esperadas,
        'total_registros': total_registros,
        'entradas': entradas,
        'saidas': saidas,
        'mes': mes,
        'ano': ano,
    }
    
    # Gerar PDF se solicitado
    if 'pdf' in request.GET:
        return gerar_pdf_relatorio_consolidado(request, context)
    
    return render(request, 'core/relatorio_consolidado.html', context)

# ===== FUNÇÃO AUXILIAR PARA OBTER IP =====
def get_client_ip(request):
    """Obtém o IP do cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@login_required
def relatorio_profissional_pdf(request, profissional_id):
    """Gera PDF do relatório do profissional"""
    try:
        profissional = get_object_or_404(Profissional, id=profissional_id)
        
        # ✅ VERIFICAÇÃO DE SEGURANÇA
        if not request.user.is_superuser and profissional.usuario != request.user:
            messages.error(request, "Acesso não autorizado.")
            return redirect('core:dashboard')
        
        # Obter parâmetros de data
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        
        # Definir datas padrão
        hoje = timezone.now().date()
        inicio_mes = hoje.replace(day=1)
        
        if not data_inicio:
            data_inicio = inicio_mes
        else:
            try:
                data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            except ValueError:
                data_inicio = inicio_mes
        
        if not data_fim:
            data_fim = hoje
        else:
            try:
                data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
            except ValueError:
                data_fim = hoje
        
        # Buscar registros
        registros = RegistroPonto.objects.filter(
            profissional=profissional,
            data__range=[data_inicio, data_fim]
        ).order_by('data', 'horario')
        
        # Calcular horas trabalhadas
        horas_trabalhadas = calcular_horas_trabalhadas_periodo(data_inicio, data_fim, profissional)
        horas_trabalhadas_decimal = horas_trabalhadas.total_seconds() / 3600
        
        # Calcular dias úteis e horas previstas
        dias_uteis = calcular_dias_uteis(data_inicio, data_fim)
        if profissional.carga_horaria_diaria:
            horas_previstas_segundos = profissional.carga_horaria_diaria.total_seconds() * dias_uteis
            horas_previstas = timedelta(seconds=horas_previstas_segundos)
        else:
            horas_previstas = timedelta()
        
        diferenca_horas = horas_trabalhadas - horas_previstas
        diferenca_horas_decimal = horas_trabalhadas_decimal - (horas_previstas.total_seconds() / 3600)
        
        # Preparar dados para PDF
        def formatar_horas(td):
            if not td:
                return "00:00"
            total_segundos = int(td.total_seconds())
            horas = total_segundos // 3600
            minutos = (total_segundos % 3600) // 60
            return f"{horas:02d}:{minutos:02d}"
        
        context = {
            'profissional': profissional,
            'registros': registros,
            'horas_trabalhadas': formatar_horas(horas_trabalhadas),
            'horas_trabalhadas_decimal': round(horas_trabalhadas_decimal, 2),
            'carga_horaria_diaria': formatar_horas(profissional.carga_horaria_diaria),
            'carga_horaria_semanal': formatar_horas(profissional.carga_horaria_semanal),
            'carga_horaria_esperada': formatar_horas(horas_previstas),
            'diferenca_horas_decimal': round(diferenca_horas_decimal, 2),
            'total_registros': registros.count(),
            'entradas': registros.filter(tipo='ENTRADA').count(),
            'saidas': registros.filter(tipo='SAIDA').count(),
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'gerado_em': timezone.now(),
            'vinculo': {'estabelecimento': profissional.estabelecimento} if profissional.estabelecimento else None,
        }
        
        # Gerar HTML para PDF
        html_string = render_to_string('core/relatorio_profissional_pdf.html', context)
        
        # Configurar resposta PDF
        response = HttpResponse(content_type='application/pdf')
        filename = f"relatorio_{profissional.cpf}_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Gerar PDF
        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
        
        return response
        
    except Exception as e:
        print(f"Erro ao gerar PDF: {str(e)}")
        messages.error(request, f"Erro ao gerar PDF: {str(e)}")
        return redirect('core:relatorio_profissional', profissional_id=profissional_id)