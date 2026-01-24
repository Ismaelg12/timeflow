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
from .serializers import RegistroPontoSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
def comprovante_completo(request, registro_id):
    """Retorna comprovante completo com QR Code incluído"""
    registro = get_object_or_404(RegistroPonto, id=registro_id)
    
    # Dados do comprovante conforme Portaria 671
    comprovante = {
        "codigo_registro": f"TF-{registro.id:08d}",
        "empresa_cnpj": registro.estabelecimento.cnpj if hasattr(registro.estabelecimento, 'cnpj') else "",
        "empresa_nome": registro.estabelecimento.nome,
        "funcionario_cpf": registro.profissional.cpf,
        "funcionario_nome": registro.profissional.get_full_name(),
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
        "url_validacao": request.build_absolute_uri(f'/api/comprovante/{registro.id}/validar/')
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
        'hora': comprovante['hora'],
        'tipo': comprovante['tipo'],
        'latitude': comprovante['latitude'],
        'longitude': comprovante['longitude']
    }))
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
        'url_validacao': request.build_absolute_uri(f'/api/comprovante/{registro.id}/validar/')
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def gerar_comprovante_pdf(request, registro_id):
    """Gera JSON do comprovante (pode ser convertido para PDF depois)"""
    registro = get_object_or_404(RegistroPonto, id=registro_id)
    
    comprovante = {
        "codigo_registro": f"TF-{registro.id:08d}",
        "empresa_cnpj": registro.estabelecimento.cnpj if hasattr(registro.estabelecimento, 'cnpj') else "",
        "empresa_nome": registro.estabelecimento.nome,
        "funcionario_cpf": registro.profissional.cpf,
        "funcionario_nome": registro.profissional.get_full_name(),
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
        "url_validacao": request.build_absolute_uri(f'/api/comprovante/{registro.id}/validar/')
    }
    
    return JsonResponse({
        'sucesso': True,
        'mensagem': 'Comprovante gerado com sucesso',
        'comprovante': comprovante,
        'formato': 'JSON - Para conversão em PDF'
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def gerar_qr_code(request, registro_id):
    """Gera QR Code com dados do registro"""
    registro = get_object_or_404(RegistroPonto, id=registro_id)
    
    # Dados que vão no QR Code
    qr_data = {
        'id': registro.id,
        'empresa': registro.estabelecimento.nome,
        'cnpj': registro.estabelecimento.cnpj if hasattr(registro.estabelecimento, 'cnpj') else "",
        'funcionario': registro.profissional.get_full_name(),
        'cpf': registro.profissional.cpf,
        'data': registro.data.strftime('%d/%m/%Y'),
        'hora': registro.horario.strftime('%H:%M'),
        'tipo': registro.tipo,
        'status': 'VALIDO' if registro.dentro_tolerancia else 'ATRASO',
        'url': request.build_absolute_uri(f'/api/comprovante/{registro.id}/')
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


@api_view(['GET'])
@permission_classes([AllowAny])
def validar_registro(request, registro_id):
    """API para validar um registro via QR Code"""
    registro = get_object_or_404(RegistroPonto, id=registro_id)
    
    # Passe o contexto com request para o serializer
    serializer = RegistroPontoSerializer(registro, context={'request': request})
    
    return JsonResponse({
        'sucesso': True,
        'valido': True,
        'registro': serializer.data,
        'data_validacao': timezone.now().isoformat(),
        'empresa_cnpj': registro.estabelecimento.cnpj if hasattr(registro.estabelecimento, 'cnpj') else ""
    })