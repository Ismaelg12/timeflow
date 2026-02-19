# from datetime import datetime, time, timedelta
# from django.utils import timezone

# def calcular_tolerancia(profissional, horario_atual, tipo):
#     """
#     Calcula tolerância para entrada e saída
#     Retorna: (minutos_atraso/antecipacao, dentro_tolerancia)
#     """
#     if tipo == 'ENTRADA':
#         horario_previsto = profissional.horario_entrada
#         tolerancia = profissional.tolerancia_minutos or 10
#     else:
#         horario_previsto = profissional.horario_saida
#         tolerancia = profissional.tolerancia_minutos or 10
    
#     if not horario_previsto:
#         return 0, True
    
#     # Converter para datetime para cálculo
#     hoje = timezone.now().date()
#     horario_previsto_dt = datetime.combine(hoje, horario_previsto)
#     horario_atual_dt = datetime.combine(hoje, horario_atual)
    
#     if tipo == 'ENTRADA':
#         # Para entrada: atraso se chegar depois do horário + tolerância
#         horario_limite = horario_previsto_dt + timedelta(minutes=tolerancia)
        
#         if horario_atual_dt > horario_limite:
#             diferenca = horario_atual_dt - horario_limite
#             minutos_atraso = int(diferenca.total_seconds() / 60)
#             return minutos_atraso, False
#         else:
#             return 0, True
    
#     else:  # SAIDA
#         # Para saída: antecipação se sair antes do horário - tolerância
#         horario_limite = horario_previsto_dt - timedelta(minutes=tolerancia)
        
#         if horario_atual_dt < horario_limite:
#             diferenca = horario_limite - horario_atual_dt
#             minutos_antecipacao = int(diferenca.total_seconds() / 60)
#             return minutos_antecipacao, False
#         else:
#             return 0, True

# def calcular_horas_trabalhadas_dia(profissional, estabelecimento, data):
#     """
#     Calcula horas trabalhadas no dia baseado nos registros de entrada e saída
#     """
#     from .models import RegistroPonto
    
#     registros_dia = RegistroPonto.objects.filter(
#         profissional=profissional,
#         estabelecimento=estabelecimento,
#         data=data
#     ).order_by('horario')
    
#     # Verifica se tem par completo (entrada e saída)
#     entradas = [r for r in registros_dia if r.tipo == 'ENTRADA']
#     saidas = [r for r in registros_dia if r.tipo == 'SAIDA']
    
#     if not entradas or not saidas:
#         return time(0, 0)  # Retorna 00:00 se não tiver par completo
    
#     # Pega a primeira entrada e última saída
#     entrada = entradas[0]
#     saida = saidas[-1]
    
#     # Calcula diferença
#     entrada_dt = datetime.combine(data, entrada.horario)
#     saida_dt = datetime.combine(data, saida.horario)
    
#     diferenca = saida_dt - entrada_dt
#     horas = int(diferenca.total_seconds() // 3600)
#     minutos = int((diferenca.total_seconds() % 3600) // 60)
    
#     return time(horas, minutos)

# def determinar_proximo_tipo(profissional, estabelecimento, data):
#     """
#     Determina o próximo tipo de registro baseado nos registros existentes
#     CORREÇÃO: Lógica simplificada e mais robusta
#     """
#     from .models import RegistroPonto
    
#     # Buscar todos os registros do dia
#     registros_hoje = RegistroPonto.objects.filter(
#         profissional=profissional,
#         estabelecimento=estabelecimento,
#         data=data
#     )
    
#     # Contar quantas entradas e saídas já existem
#     entradas_count = registros_hoje.filter(tipo='ENTRADA').count()
#     saidas_count = registros_hoje.filter(tipo='SAIDA').count()
    
#     if entradas_count == 0 and saidas_count == 0:
#         return 'ENTRADA'
#     elif entradas_count > saidas_count:
#         return 'SAIDA'
#     else:
#         return 'ENTRADA'

# def verificar_registro_duplicado(profissional, estabelecimento, data, tipo):
#     """
#     Verifica se já existe registro do mesmo tipo no dia
#     """
#     from .models import RegistroPonto
    
#     return RegistroPonto.objects.filter(
#         profissional=profissional,
#         estabelecimento=estabelecimento,
#         data=data,
#         tipo=tipo
#     ).exists()
# ponto/utils.py (corrigido)
from datetime import datetime, time, timedelta
from django.utils import timezone

def calcular_tolerancia(profissional, horario_atual, tipo):
    """
    Calcula tolerância para entrada e saída
    Retorna: (minutos_atraso/antecipacao, dentro_tolerancia)
    """
    if tipo == 'ENTRADA':
        horario_previsto = profissional.horario_entrada
        tolerancia = profissional.tolerancia_minutos or 10
    else:
        horario_previsto = profissional.horario_saida
        tolerancia = profissional.tolerancia_minutos or 10
    
    if not horario_previsto:
        return 0, True
    
    # Converter para datetime para cálculo
    hoje = timezone.now().date()
    horario_previsto_dt = datetime.combine(hoje, horario_previsto)
    horario_atual_dt = datetime.combine(hoje, horario_atual)
    
    if tipo == 'ENTRADA':
        # Para entrada: atraso se chegar depois do horário + tolerância
        horario_limite = horario_previsto_dt + timedelta(minutes=tolerancia)
        
        if horario_atual_dt > horario_limite:
            diferenca = horario_atual_dt - horario_limite
            minutos_atraso = int(diferenca.total_seconds() / 60)
            return minutos_atraso, False
        else:
            return 0, True
    
    else:  # SAIDA
        # Para saída: antecipação se sair antes do horário - tolerância
        horario_limite = horario_previsto_dt - timedelta(minutes=tolerancia)
        
        if horario_atual_dt < horario_limite:
            diferenca = horario_limite - horario_atual_dt
            minutos_antecipacao = int(diferenca.total_seconds() / 60)
            return minutos_antecipacao, False
        else:
            return 0, True


# ponto/utils.py (nova função melhorada)
def determinar_proximo_tipo(profissional, estabelecimento, data):
    """
    Determina próximo tipo considerando plantões de 24h
    """
    from .models import RegistroPonto
    
    # Verificar se é plantão 24h
    is_plantao_24h = False
    if profissional.carga_horaria_diaria:
        is_plantao_24h = profissional.carga_horaria_diaria.total_seconds() == 86400
    
    # Buscar registros do dia
    registros_hoje = RegistroPonto.objects.filter(
        profissional=profissional,
        estabelecimento=estabelecimento,
        data=data
    )
    
    entradas_count = registros_hoje.filter(tipo='ENTRADA').count()
    saidas_count = registros_hoje.filter(tipo='SAIDA').count()
    
    if not is_plantao_24h:
        # Lógica normal
        if entradas_count == 0:
            return 'ENTRADA'
        elif entradas_count > saidas_count:
            return 'SAIDA'
        else:
            return 'ENTRADA'
    else:
        # Lógica para plantão 24h
        # Verificar se há entrada pendente de ontem
        ontem = data - timedelta(days=1)
        entrada_ontem = RegistroPonto.objects.filter(
            profissional=profissional,
            estabelecimento=estabelecimento,
            data=ontem,
            tipo='ENTRADA'
        ).exists()
        
        saida_ontem = RegistroPonto.objects.filter(
            profissional=profissional,
            estabelecimento=estabelecimento,
            data=ontem,
            tipo='SAIDA'
        ).exists()
        
        # Se teve entrada ontem mas não saída, hoje começa com SAIDA
        if entrada_ontem and not saida_ontem:
            # Já tem entrada ontem, precisa sair hoje
            return 'SAIDA'
        else:
            # Dia normal - verificar se já tem entrada hoje
            if entradas_count == 0:
                return 'ENTRADA'
            elif entradas_count > saidas_count:
                return 'SAIDA'
            else:
                return 'ENTRADA'


def verificar_registro_duplicado(profissional, estabelecimento, data, tipo):
    """
    Verifica se já existe registro do mesmo tipo no dia
    """
    from .models import RegistroPonto
    
    # Para plantão 24h, permitir múltiplos registros?
    carga_horaria_24h = False
    if profissional.carga_horaria_diaria:
        carga_horaria_24h = profissional.carga_horaria_diaria.total_seconds() == 86400
    
    if carga_horaria_24h and tipo == 'SAIDA':
        # Para saída em plantão 24h, não verificar duplicidade
        return False
    
    return RegistroPonto.objects.filter(
        profissional=profissional,
        estabelecimento=estabelecimento,
        data=data,
        tipo=tipo
    ).exists()


def calcular_horas_trabalhadas_dia_com_plantao(registros_dia, data=None):
    """
    Calcula horas trabalhadas em um dia específico - COMPATÍVEL COM PLANTÃO 24h
    """
    if not registros_dia:
        return timedelta()
    
    horas_dia = timedelta()
    
    # Organizar registros por ordem cronológica
    registros_ordenados = sorted(registros_dia, key=lambda x: (x.data, x.horario))
    
    # Para plantão 24h, podemos ter múltiplos pares entrada-saída
    entrada_atual = None
    data_entrada_atual = None
    
    for registro in registros_ordenados:
        if registro.tipo == 'ENTRADA':
            if entrada_atual is not None:
                # Entrada sem saída anterior - ignorar (incompleto)
                pass
            entrada_atual = registro.horario
            data_entrada_atual = registro.data
            
        elif registro.tipo == 'SAIDA' and entrada_atual is not None:
            # Calcular horas entre entrada e saída
            entrada_dt = datetime.combine(data_entrada_atual, entrada_atual)
            saida_dt = datetime.combine(registro.data, registro.horario)
            
            # Se saída for em data diferente (plantão que passa da meia-noite)
            if saida_dt.date() != entrada_dt.date():
                # Para plantão 24h, ajustar data da saída
                if saida_dt < entrada_dt:
                    saida_dt = saida_dt + timedelta(days=1)
            
            horas_trabalhadas = saida_dt - entrada_dt
            horas_dia += horas_trabalhadas
            
            # Resetar para próximo ciclo
            entrada_atual = None
            data_entrada_atual = None
    
    return horas_dia