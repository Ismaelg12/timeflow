# afd/gerador.py
"""
Gera o Arquivo Fonte de Dados (AFD) no leiaute do Anexo I do Portal gov.br,
para REP-P (Registrador Eletrônico de Ponto via Programa — categoria em
que o TimeFlow se enquadra, por ser um sistema em nuvem/software).

Referência oficial (mesmo texto usado pra validar este código):
https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/inspecao-do-trabalho/
fiscalizacao-do-trabalho/leiaute-do-arquivo-fonte-de-dados-afd.pdf

⚠️ O QUE ESTE ARQUIVO NÃO RESOLVE SOZINHO:
- A linha de "assinatura digital" do AFD, para REP-P, deve trazer o texto
  literal "ASSINATURA_DIGITAL_EM_ARQUIVO_P7S" — ou seja, a assinatura real
  fica num arquivo .p7s SEPARADO, assinado com um certificado ICP-Brasil.
  Isso é um processo fora do Django (certificado do empregador ou do
  desenvolvedor do software) — este gerador já deixa a linha no formato
  certo, mas não substitui a assinatura de verdade.
- O REP-P precisa de um NÚMERO DE REGISTRO NO INPI (usado no nome do
  arquivo e no cabeçalho). Isso é um registro formal, não código — use
  settings.AFD_NUMERO_REGISTRO_INPI como placeholder até você ter o número
  real.
"""
import hashlib
from datetime import datetime

from django.conf import settings

from ponto.models import RegistroPonto
from .models import EventoFuncionarioAFD, EventoServicoAFD


# ---------------------------------------------------------------------------
# Helpers de formatação de campo (Anexo I, item 7: campos começam pela
# esquerda; N = numérico zero-preenchido à esquerda; A = alfanumérico
# espaço-preenchido à direita; D/DH = formato fixo de data)
# ---------------------------------------------------------------------------

def _n(valor, largura):
    texto = str(valor)
    if len(texto) > largura:
        raise ValueError(f"Campo numérico '{texto}' maior que a largura {largura}")
    return texto.rjust(largura, '0')


def _a(valor, largura):
    texto = (valor or '')[:largura]
    return texto.ljust(largura, ' ')


def _dh(dt: datetime, tz_offset='-0300'):
    """Data e hora no formato AAAA-MM-ddThh:mm:00ZZZZZ (segundos sempre '00')."""
    return dt.strftime('%Y-%m-%dT%H:%M:00') + tz_offset


def _d(dt):
    """Data no formato AAAA-MM-dd."""
    return dt.strftime('%Y-%m-%d')


# ---------------------------------------------------------------------------
# CRC-16/KERMIT (CCITT-TRUE) — usado nos registros tipo 1 a 5.
# Testado contra o vetor oficial: crc16_kermit(b"123456789") == 0x2189
# ---------------------------------------------------------------------------

def crc16_kermit(data: bytes) -> str:
    crc = 0x0000
    for byte in data:
        cur = int(f'{byte:08b}'[::-1], 2)  # reflete o byte de entrada
        crc ^= cur << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    crc = int(f'{crc:016b}'[::-1], 2)  # reflete o resultado final
    return f'{crc:04X}'


# ---------------------------------------------------------------------------
# Construtores de cada tipo de registro
# ---------------------------------------------------------------------------

def _registro_tipo_1(data_inicial, data_final):
    """Cabeçalho — um único registro no começo do arquivo."""
    cnpj = getattr(settings, 'AFD_CNPJ_EMPREGADOR', '00000000000000')
    razao_social = getattr(settings, 'AFD_RAZAO_SOCIAL', 'RAZAO SOCIAL NAO CONFIGURADA')
    numero_inpi = getattr(settings, 'AFD_NUMERO_REGISTRO_INPI', '99999999999999999')
    cnpj_dev = getattr(settings, 'AFD_CNPJ_DESENVOLVEDOR', cnpj)

    corpo = (
        _n('0', 9) +
        _n('1', 1) +
        _n('1', 1) +               # tipo identificador do empregador: 1=CNPJ
        _a(cnpj, 14) +
        _a('', 14) +                # CNO/CAEPF, quando existir
        _a(razao_social, 150) +
        _a(numero_inpi, 17) +        # nº de registro no INPI (REP-P)
        _d(data_inicial) +
        _d(data_final) +
        _dh(datetime.now()) +
        _n('004', 3) +
        _n('1', 1) +                # identificador do desenvolvedor: 1=CNPJ
        _a(cnpj_dev, 14) +
        _a('', 30)                   # modelo — só para REP-C, vazio aqui
    )
    crc = crc16_kermit(corpo.encode('iso-8859-1'))
    return corpo + crc


def _registro_tipo_5(evento):
    corpo = (
        _n(evento.nsr, 9) +
        _n('5', 1) +
        _dh(evento.data_hora) +
        _a(evento.tipo_operacao, 1) +
        _n(evento.cpf_funcionario, 12) +
        _a(evento.nome_funcionario, 52) +
        _a('', 4) +                  # demais dados de identificação
        _n(evento.cpf_responsavel or '0', 11)
    )
    crc = crc16_kermit(corpo.encode('iso-8859-1'))
    return corpo + crc


def _registro_tipo_6(evento):
    # ⚠️ Diferente dos tipos 1-5, o tipo "6" NÃO leva CRC-16 — o Anexo I
    # (item 8) restringe o CRC-16 explicitamente aos registros tipo "1" a
    # "5". Testado: tamanho final deve ser 36 chars (9+1+24+2), sem sufixo.
    return (
        _n(evento.nsr, 9) +
        _n('6', 1) +
        _dh(evento.data_hora) +
        _a(evento.tipo_evento, 2)
    )


def _registro_tipo_7(registro):
    """Marcação de ponto — REP-P. Não usa CRC-16; usa o hash SHA-256
    encadeado que já foi calculado e salvo em RegistroPonto.hash_registro."""
    data_hora_marcacao = datetime.combine(registro.data, registro.horario)
    return (
        _n(registro.nsr, 9) +
        _n('7', 1) +
        _dh(data_hora_marcacao) +
        _n(''.join(filter(str.isdigit, registro.profissional.cpf)), 12) +
        _dh(registro.created_at) +
        _a(registro.identificador_coletor, 2) +
        _n('1' if registro.offline else '0', 1) +
        _a(registro.hash_registro, 64)
    )


def _registro_tipo_9(qtd_tipo2, qtd_tipo3, qtd_tipo4, qtd_tipo5, qtd_tipo6, qtd_tipo7):
    return (
        _n('9', 9) +
        _n(qtd_tipo2, 9) +
        _n(qtd_tipo3, 9) +
        _n(qtd_tipo4, 9) +
        _n(qtd_tipo5, 9) +
        _n(qtd_tipo6, 9) +
        _n(qtd_tipo7, 9) +
        _n('9', 1)
    )


def _linha_assinatura():
    # Para REP-A e REP-P: texto literal fixo (a assinatura real é um
    # arquivo .p7s separado, assinado com certificado ICP-Brasil).
    return _a('ASSINATURA_DIGITAL_EM_ARQUIVO_P7S', 100)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def gerar_afd(data_inicial, data_final):
    """
    Retorna (nome_arquivo, conteudo_texto) do AFD do período informado.
    conteudo_texto já vem pronto para ser salvo/baixado como .txt
    (ISO-8859-1, linhas terminadas em CRLF, ordenado por NSR).
    """
    eventos_funcionario = EventoFuncionarioAFD.objects.filter(
        data_hora__date__gte=data_inicial, data_hora__date__lte=data_final
    )
    eventos_servico = EventoServicoAFD.objects.filter(
        data_hora__date__gte=data_inicial, data_hora__date__lte=data_final
    )
    marcacoes = RegistroPonto.objects.filter(
        data__gte=data_inicial, data__lte=data_final, nsr__isnull=False
    ).select_related('profissional')

    linhas = [_registro_tipo_1(data_inicial, data_final)]

    registros_ordenaveis = (
        [(e.nsr, _registro_tipo_5(e)) for e in eventos_funcionario] +
        [(e.nsr, _registro_tipo_6(e)) for e in eventos_servico] +
        [(r.nsr, _registro_tipo_7(r)) for r in marcacoes]
    )
    registros_ordenaveis.sort(key=lambda item: item[0])
    linhas.extend(linha for _, linha in registros_ordenaveis)

    linhas.append(_registro_tipo_9(
        qtd_tipo2=0,
        qtd_tipo3=0,
        qtd_tipo4=0,
        qtd_tipo5=eventos_funcionario.count(),
        qtd_tipo6=eventos_servico.count(),
        qtd_tipo7=marcacoes.count(),
    ))
    linhas.append(_linha_assinatura())

    conteudo = '\r\n'.join(linhas) + '\r\n'

    cnpj = getattr(settings, 'AFD_CNPJ_EMPREGADOR', '00000000000000')
    numero_inpi = getattr(settings, 'AFD_NUMERO_REGISTRO_INPI', '99999999999999999')
    nome_arquivo = f"AFD{numero_inpi}{cnpj}REP_P.txt"

    return nome_arquivo, conteudo
