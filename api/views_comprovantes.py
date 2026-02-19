# api/views_comprovantes.py
import qrcode
import json
import base64
from io import BytesIO
from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.utils import timezone

from ponto.models import RegistroPonto
from usuarios.models import Profissional

@api_view(['GET'])
@permission_classes([AllowAny])
def comprovante_completo(request, registro_id):
    """Retorna comprovante completo com QR Code incluído"""
    
    try:
        registro = get_object_or_404(RegistroPonto, id=registro_id)
        profissional = registro.profissional
        
        # Obter horários cadastrados do profissional
        hora_entrada_cadastrada = None
        hora_saida_cadastrada = None
        
        if profissional.horario_entrada:
            hora_entrada_cadastrada = profissional.horario_entrada.strftime('%H:%M')
        
        if profissional.horario_saida:
            hora_saida_cadastrada = profissional.horario_saida.strftime('%H:%M')
        
        # Dados do comprovante conforme Portaria 671
        comprovante = {
            "codigo_registro": f"TF-{registro.id:08d}",
            "empresa_cnpj": registro.estabelecimento.cnpj if hasattr(registro.estabelecimento, 'cnpj') else "",
            "empresa_nome": registro.estabelecimento.nome,
            "funcionario_cpf": profissional.cpf,
            "funcionario_nome": profissional.get_full_name(),
            "data": registro.data.strftime('%d/%m/%Y'),
            "hora": registro.horario.strftime('%H:%M:%S'),
            "tipo": "ENTRADA" if registro.tipo == 'ENTRADA' else "SAÍDA",
            "latitude": str(registro.latitude),
            "longitude": str(registro.longitude),
            "raio_permitido": f"{registro.estabelecimento.raio_permitido}m",
            "dentro_raio": "SIM" if registro.dentro_tolerancia else "NÃO",
            "timestamp_servidor": registro.created_at.isoformat() if registro.created_at else timezone.now().isoformat(),
            "atraso_minutos": registro.atraso_minutos,
            "saida_antecipada_minutos": registro.saida_antecipada_minutos,
            "status": "DENTRO DA TOLERÂNCIA" if registro.dentro_tolerancia else "FORA DA TOLERÂNCIA",
            "data_geracao": datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            
            # NOVOS CAMPOS ADICIONADOS
            "hora_entrada_cadastrada": hora_entrada_cadastrada,
            "hora_saida_cadastrada": hora_saida_cadastrada,
            "tolerancia_minutos": profissional.tolerancia_minutos if hasattr(profissional, 'tolerancia_minutos') else 10,
            "profissao": str(profissional.profissao) if profissional.profissao else "Não informada",
            
            # Adicionar também as horas formatadas (sem segundos) para exibição
            "hora_formatada": registro.horario.strftime('%H:%M'),
            "url_validacao": f"{request.build_absolute_uri('/')}api/validar/{registro.id}/",
        }
        
        # Gerar QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(json.dumps({
            'id': registro.id,
            'codigo': f"TF-{registro.id:08d}",
            'empresa_cnpj': comprovante['empresa_cnpj'],
            'empresa_nome': comprovante['empresa_nome'],
            'funcionario_cpf': comprovante['funcionario_cpf'],
            'funcionario_nome': comprovante['funcionario_nome'],
            'data': comprovante['data'],
            'hora': comprovante['hora_formatada'],  # Usar hora formatada sem segundos
            'tipo': comprovante['tipo'],
            'horario_cadastrado': hora_entrada_cadastrada if registro.tipo == 'ENTRADA' else hora_saida_cadastrada,
            'latitude': comprovante['latitude'],
            'longitude': comprovante['longitude'],
            'url_validacao': comprovante['url_validacao']
        }, ensure_ascii=False))
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        return JsonResponse({
            'sucesso': True,
            'comprovante': comprovante,
            'qr_code': f"data:image/png;base64,{qr_base64}",
            'qr_code_base64': qr_base64,
        })
        
    except Exception as e:
        return JsonResponse({
            'sucesso': False,
            'erro': f'Erro ao gerar comprovante: {str(e)}'
        }, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def gerar_comprovante_pdf(request, registro_id):
    """Gera JSON do comprovante (pode ser convertido para PDF depois)"""
    try:
        registro = get_object_or_404(RegistroPonto, id=registro_id)
        profissional = registro.profissional
        
        # Obter horários cadastrados
        hora_entrada_cadastrada = None
        hora_saida_cadastrada = None
        
        if profissional.horario_entrada:
            hora_entrada_cadastrada = profissional.horario_entrada.strftime('%H:%M')
        
        if profissional.horario_saida:
            hora_saida_cadastrada = profissional.horario_saida.strftime('%H:%M')
        
        comprovante = {
            "codigo_registro": f"TF-{registro.id:08d}",
            "empresa_cnpj": registro.estabelecimento.cnpj if hasattr(registro.estabelecimento, 'cnpj') else "",
            "empresa_nome": registro.estabelecimento.nome,
            "funcionario_cpf": profissional.cpf,
            "funcionario_nome": profissional.get_full_name(),
            "data": registro.data.strftime('%d/%m/%Y'),
            "hora": registro.horario.strftime('%H:%M:%S'),
            "hora_formatada": registro.horario.strftime('%H:%M'),
            "tipo": "ENTRADA" if registro.tipo == 'ENTRADA' else "SAÍDA",
            "latitude": str(registro.latitude),
            "longitude": str(registro.longitude),
            "raio_permitido": f"{registro.estabelecimento.raio_permitido}m",
            "dentro_raio": "SIM" if registro.dentro_tolerancia else "NÃO",
            "timestamp_servidor": registro.created_at.isoformat() if registro.created_at else timezone.now().isoformat(),
            "atraso_minutos": registro.atraso_minutos,
            "saida_antecipada_minutos": registro.saida_antecipada_minutos,
            "status": "DENTRO DA TOLERÂNCIA" if registro.dentro_tolerancia else "FORA DA TOLERÂNCIA",
            "data_geracao": datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            
            # NOVOS CAMPOS
            "hora_entrada_cadastrada": hora_entrada_cadastrada,
            "hora_saida_cadastrada": hora_saida_cadastrada,
            "tolerancia_minutos": profissional.tolerancia_minutos if hasattr(profissional, 'tolerancia_minutos') else 10,
            "profissao": str(profissional.profissao) if profissional.profissao else "Não informada",
            "url_validacao": f"{request.build_absolute_uri('/')}api/validar/{registro.id}/",
        }
        
        return JsonResponse({
            'sucesso': True,
            'mensagem': 'Comprovante gerado com sucesso',
            'comprovante': comprovante,
            'formato': 'JSON - Para conversão em PDF'
        })
        
    except Exception as e:
        return JsonResponse({
            'sucesso': False,
            'erro': f'Erro ao gerar PDF: {str(e)}'
        }, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def gerar_qr_code(request, registro_id):
    """Gera QR Code com dados do registro"""
    try:
        registro = get_object_or_404(RegistroPonto, id=registro_id)
        profissional = registro.profissional
        
        # Obter horários cadastrados
        hora_entrada_cadastrada = None
        hora_saida_cadastrada = None
        
        if profissional.horario_entrada:
            hora_entrada_cadastrada = profissional.horario_entrada.strftime('%H:%M')
        
        if profissional.horario_saida:
            hora_saida_cadastrada = profissional.horario_saida.strftime('%H:%M')
        
        # Dados que vão no QR Code
        qr_data = {
            'id': registro.id,
            'codigo': f"TF-{registro.id:08d}",
            'empresa': registro.estabelecimento.nome,
            'cnpj': registro.estabelecimento.cnpj if hasattr(registro.estabelecimento, 'cnpj') else "",
            'funcionario': profissional.get_full_name(),
            'cpf': profissional.cpf,
            'data': registro.data.strftime('%d/%m/%Y'),
            'hora': registro.horario.strftime('%H:%M'),
            'tipo': registro.tipo,
            
            # Adicionar horários cadastrados
            'horario_entrada_cadastrado': hora_entrada_cadastrada,
            'horario_saida_cadastrado': hora_saida_cadastrada,
            
            'status': 'VALIDO' if registro.dentro_tolerancia else 'ATRASO',
            'url_validacao': f"{request.build_absolute_uri('/')}api/validar/{registro.id}/",
        }
        
        # Converter para string JSON
        qr_text = json.dumps(qr_data, ensure_ascii=False)
        
        # Gerar QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_text)
        qr.make(fit=True)
        
        # Criar imagem
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Converter para base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return JsonResponse({
            'sucesso': True,
            'qr_code_base64': img_str,
            'qr_data': qr_data,
            'mime_type': 'image/png',
            'qr_code_completo': f"data:image/png;base64,{img_str}"
        })
        
    except Exception as e:
        return JsonResponse({
            'sucesso': False,
            'erro': f'Erro ao gerar QR Code: {str(e)}'
        }, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def validar_registro(request, registro_id):
    """API para validar um registro via QR Code"""
    try:
        registro = get_object_or_404(RegistroPonto, id=registro_id)
        profissional = registro.profissional
        
        # Obter horários cadastrados
        hora_entrada_cadastrada = None
        hora_saida_cadastrada = None
        
        if profissional.horario_entrada:
            hora_entrada_cadastrada = profissional.horario_entrada.strftime('%H:%M')
        
        if profissional.horario_saida:
            hora_saida_cadastrada = profissional.horario_saida.strftime('%H:%M')
        
        return JsonResponse({
            'sucesso': True,
            'valido': True,
            'registro_id': registro.id,
            'codigo_registro': f"TF-{registro.id:08d}",
            'funcionario_nome': profissional.get_full_name(),
            'funcionario_cpf': profissional.cpf,
            'empresa_nome': registro.estabelecimento.nome,
            'empresa_cnpj': registro.estabelecimento.cnpj if hasattr(registro.estabelecimento, 'cnpj') else "",
            'data': registro.data.strftime('%d/%m/%Y'),
            'hora': registro.horario.strftime('%H:%M'),
            'hora_completa': registro.horario.strftime('%H:%M:%S'),
            'tipo': registro.tipo,
            
            # Adicionar horários cadastrados na validação
            'horario_entrada_cadastrado': hora_entrada_cadastrada,
            'horario_saida_cadastrado': hora_saida_cadastrada,
            
            'dentro_tolerancia': registro.dentro_tolerancia,
            'atraso_minutos': registro.atraso_minutos,
            'saida_antecipada_minutos': registro.saida_antecipada_minutos,
            'data_validacao': timezone.now().isoformat(),
            'data_validacao_formatada': timezone.now().strftime('%d/%m/%Y %H:%M:%S'),
        })
        
    except Exception as e:
        return JsonResponse({
            'sucesso': False,
            'erro': f'Erro ao validar registro: {str(e)}'
        }, status=500)