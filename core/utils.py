# core/utils.py (se não existir, crie)
from datetime import datetime, timedelta
from collections import defaultdict

def verificar_dia_incompleto(registros_dia):
    """Verifica se um dia tem apenas entrada sem saída"""
    tipos = [r.tipo for r in registros_dia]
    return 'ENTRADA' in tipos and 'SAIDA' not in tipos

def preparar_dados_grafico(registros_por_data):
    """Prepara dados para o gráfico de horas por dia da semana"""
    horas_por_dia_semana = defaultdict(timedelta)
    dias_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
    
    for data_dia, registros_dia in registros_por_data.items():
        horas_dia = calcular_horas_trabalhadas_dia(registros_dia)
        dia_semana = data_dia.weekday()
        horas_por_dia_semana[dia_semana] += horas_dia
    
    resultado = []
    for i in range(7):
        horas_total = horas_por_dia_semana[i]
        horas_decimal = horas_total.total_seconds() / 3600
        
        resultado.append({
            'dia': dias_semana[i],
            'horas': formatar_horas(horas_total),
            'horas_decimal': round(horas_decimal, 2)
        })
    
    return resultado

def get_justificativas_registro_manual():
    """Retorna lista de justificativas predefinidas"""
    return [
        ('ESQUECIMENTO', 'Esquecimento do profissional'),
        ('PROBLEMA_SISTEMA', 'Problema no sistema de ponto'),
        ('EMERGENCIA', 'Emergência/urgência médica'),
        ('REUNIAO', 'Reunião prolongada'),
        ('ATIVIDADE_EXTERNA', 'Atividade externa'),
        ('FALHA_EQUIPAMENTO', 'Falha no equipamento'),
        ('CAPACITACAO', 'Capacitação/treinamento'),
        ('OUTRO', 'Outro (especificar)'),
    ]