# ponto/utils.py
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

    hoje = timezone.now().date()
    horario_previsto_dt = datetime.combine(hoje, horario_previsto)
    horario_atual_dt = datetime.combine(hoje, horario_atual)

    if tipo == 'ENTRADA':
        horario_limite = horario_previsto_dt + timedelta(minutes=tolerancia)
        if horario_atual_dt > horario_limite:
            diferenca = horario_atual_dt - horario_limite
            minutos_atraso = int(diferenca.total_seconds() / 60)
            return minutos_atraso, False
        else:
            return 0, True
    else:  # SAIDA
        horario_limite = horario_previsto_dt - timedelta(minutes=tolerancia)
        if horario_atual_dt < horario_limite:
            diferenca = horario_limite - horario_atual_dt
            minutos_antecipacao = int(diferenca.total_seconds() / 60)
            return minutos_antecipacao, False
        else:
            return 0, True


def determinar_proximo_tipo(profissional, estabelecimento, data):
    """
    Determina próximo tipo considerando plantões de 24h
    """
    from .models import RegistroPonto

    is_plantao_24h = False
    if profissional.carga_horaria_diaria:
        is_plantao_24h = profissional.carga_horaria_diaria.total_seconds() == 86400

    registros_hoje = RegistroPonto.objects.filter(
        profissional=profissional,
        estabelecimento=estabelecimento,
        data=data
    )

    entradas_count = registros_hoje.filter(tipo='ENTRADA').count()
    saidas_count = registros_hoje.filter(tipo='SAIDA').count()

    if not is_plantao_24h:
        if entradas_count == 0:
            return 'ENTRADA'
        elif entradas_count > saidas_count:
            return 'SAIDA'
        else:
            return 'ENTRADA'
    else:
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

        if entrada_ontem and not saida_ontem:
            return 'SAIDA'
        else:
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

    carga_horaria_24h = False
    if profissional.carga_horaria_diaria:
        carga_horaria_24h = profissional.carga_horaria_diaria.total_seconds() == 86400

    if carga_horaria_24h and tipo == 'SAIDA':
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
    registros_ordenados = sorted(registros_dia, key=lambda x: (x.data, x.horario))

    entrada_atual = None
    data_entrada_atual = None

    for registro in registros_ordenados:
        if registro.tipo == 'ENTRADA':
            if entrada_atual is not None:
                pass
            entrada_atual = registro.horario
            data_entrada_atual = registro.data

        elif registro.tipo == 'SAIDA' and entrada_atual is not None:
            entrada_dt = datetime.combine(data_entrada_atual, entrada_atual)
            saida_dt = datetime.combine(registro.data, registro.horario)

            if saida_dt.date() != entrada_dt.date():
                if saida_dt < entrada_dt:
                    saida_dt = saida_dt + timedelta(days=1)

            horas_trabalhadas = saida_dt - entrada_dt
            horas_dia += horas_trabalhadas

            entrada_atual = None
            data_entrada_atual = None

    return horas_dia