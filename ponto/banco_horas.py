# ponto/banco_horas.py
"""
Serviço de cálculo do Banco de Horas.

Regra adotada (padrão de mercado / CLT art. 59):
- O saldo é calculado por MARCAÇÃO (entrada pareada com a PRÓXIMA saída,
  em ordem cronológica) — não por "mesma data de calendário". Isso é
  importante pra plantões de 24h: a entrada pode ser dia 10 às 07:00 e a
  saída dia 11 às 07:00, e isso é UM plantão completo, não dois dias
  incompletos.
- saldo_dia = horas_trabalhadas_do_plantao - carga_horaria_diaria_esperada,
  atribuído ao dia em que a entrada aconteceu (é assim que plantão costuma
  ser reportado: "o plantão de segunda", mesmo terminando terça de manhã).
- Uma entrada sem saída correspondente em nenhum lugar (nem depois, no
  buffer de +1 dia consultado) fica marcada como "incompleto" — não entra
  no saldo até o RH resolver com ajuste manual.
- O saldo total do período é a soma dos saldos diários válidos.

⚠️ CORRIGIDO (bug anterior): a primeira versão deste arquivo agrupava
registros por data igual, o que fazia todo plantão de 24h aparecer como
DOIS dias pendentes (a entrada num dia, a saída sem par no outro) mesmo
quando o plantão estava completo. Testado com o cenário entrada
10/08 07:00 -> saída 11/08 07:00 antes de publicar esta versão.
"""
from datetime import timedelta, datetime

from .models import RegistroPonto


def _formatar_timedelta(td):
    """Formata um timedelta (pode ser negativo) como '+HH:MM' ou '-HH:MM'."""
    total_seconds = int(td.total_seconds())
    sinal = '-' if total_seconds < 0 else '+'
    total_seconds = abs(total_seconds)
    horas = total_seconds // 3600
    minutos = (total_seconds % 3600) // 60
    return f"{sinal}{horas:02d}:{minutos:02d}"


def calcular_extrato_banco_horas(profissional, data_inicio, data_fim):
    """
    Monta o extrato diário do banco de horas de um profissional num período.
    Retorna dict com 'dias' (lista ordenada), 'saldo_total',
    'saldo_total_formatado' e 'dias_incompletos'.
    """
    carga_diaria = profissional.carga_horaria_diaria or timedelta()

    # Busca com 1 dia de folga antes/depois do período — necessário pra
    # conseguir casar um plantão que começou um pouco antes ou termina um
    # pouco depois das bordas do período pedido.
    registros = list(
        RegistroPonto.objects.filter(
            profissional=profissional,
            data__gte=data_inicio - timedelta(days=1),
            data__lte=data_fim + timedelta(days=1),
        ).order_by('data', 'horario')
    )

    dias_extrato = {}
    dias_incompletos = []
    saldo_total = timedelta()

    def _marcar_incompleto(entrada):
        if data_inicio <= entrada.data <= data_fim:
            dias_incompletos.append(entrada.data)
            dias_extrato[entrada.data] = {
                'data': entrada.data,
                'horas_trabalhadas': timedelta(),
                'horas_esperadas': carga_diaria,
                'saldo': None,
                'saldo_formatado': 'Pendente',
                'completo': False,
            }

    entrada_pendente = None
    for registro in registros:
        if registro.tipo == 'ENTRADA':
            # Uma entrada nova apareceu antes da anterior ter sido fechada
            # com uma saída — a anterior fica marcada como incompleta.
            if entrada_pendente is not None:
                _marcar_incompleto(entrada_pendente)
            entrada_pendente = registro

        elif registro.tipo == 'SAIDA' and entrada_pendente is not None:
            dia_referencia = entrada_pendente.data
            entrada_dt = datetime.combine(entrada_pendente.data, entrada_pendente.horario)
            saida_dt = datetime.combine(registro.data, registro.horario)
            if saida_dt < entrada_dt:
                saida_dt += timedelta(days=1)

            horas_trabalhadas = saida_dt - entrada_dt

            if data_inicio <= dia_referencia <= data_fim:
                saldo_dia = horas_trabalhadas - carga_diaria
                saldo_total += saldo_dia
                dias_extrato[dia_referencia] = {
                    'data': dia_referencia,
                    'horas_trabalhadas': horas_trabalhadas,
                    'horas_esperadas': carga_diaria,
                    'saldo': saldo_dia,
                    'saldo_formatado': _formatar_timedelta(saldo_dia),
                    'completo': True,
                }
            entrada_pendente = None

    # Entrada que ficou pendurada até o fim da consulta, sem saída em lugar nenhum.
    if entrada_pendente is not None:
        _marcar_incompleto(entrada_pendente)

    dias_ordenados = sorted(dias_extrato.values(), key=lambda d: d['data'])

    return {
        'dias': dias_ordenados,
        'saldo_total': saldo_total,
        'saldo_total_formatado': _formatar_timedelta(saldo_total),
        'dias_incompletos': dias_incompletos,
    }