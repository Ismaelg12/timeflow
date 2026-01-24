# ponto/views.py
from datetime import datetime

from django.db import IntegrityError
from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from estabelecimentos.models import Estabelecimento
from usuarios.models import Profissional
from .models import RegistroPonto
from .utils import calcular_tolerancia, determinar_proximo_tipo, verificar_registro_duplicado
from api.serializers import RegistroPontoSerializer, RegistroPontoCreateSerializer

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