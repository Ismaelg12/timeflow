from django.shortcuts import render, redirect
from django.utils import timezone
from django.http import JsonResponse
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from usuarios.models import Profissional
from estabelecimentos.models import Estabelecimento
from .models import RegistroPonto
from .serializers import RegistroPontoSerializer, RegistroPontoCreateSerializer
from .utils import calcular_tolerancia, calcular_horas_trabalhadas_dia, determinar_proximo_tipo, verificar_registro_duplicado

class RegistroPontoViewSet(viewsets.ModelViewSet):
    queryset = RegistroPonto.objects.all()
    serializer_class = RegistroPontoSerializer
    
    @action(detail=False, methods=['post'])
    def registrar(self, request):
        """
        Registra ponto com restrição de apenas uma entrada e uma saída por dia
        CORREÇÃO: Lógica melhorada para determinar saída
        """
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
            
            # Validar localização
            if not self.validar_localizacao(estabelecimento, latitude, longitude):
                return Response(
                    {'erro': 'Fora do raio permitido para registro'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Determinar tipo de registro
            hoje = timezone.now().date()
            horario_atual = timezone.now().time()
            
            # ✅ DETERMINAR PRÓXIMO TIPO (CORREÇÃO APLICADA)
            tipo = determinar_proximo_tipo(profissional, estabelecimento, hoje)
            
            print(f"🔍 DEBUG: Próximo tipo determinado: {tipo}")
            
            # ✅ VERIFICAR SE JÁ EXISTE REGISTRO DO MESMO TIPO
            if verificar_registro_duplicado(profissional, estabelecimento, hoje, tipo):
                tipo_oposto = 'SAIDA' if tipo == 'ENTRADA' else 'ENTRADA'
                return Response(
                    {'erro': f'Já existe um registro de {tipo.lower()} para hoje. Próximo registro deve ser {tipo_oposto.lower()}.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # ✅ CALCULAR TOLERÂNCIAS E ATRASOS
            atraso_minutos, dentro_tolerancia = calcular_tolerancia(
                profissional, horario_atual, tipo
            )
            
            # ✅ CRIAR REGISTRO
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
            
            # ✅ SALVAR (irá validar unique_together)
            registro.save()
            
            # ✅ MENSAGEM PERSONALIZADA
            proximo_tipo = 'saída' if tipo == 'ENTRADA' else 'entrada'
            
            if dentro_tolerancia:
                mensagem = f'{tipo.lower().capitalize()} registrada com sucesso!'
            else:
                if tipo == 'ENTRADA':
                    mensagem = f'Entrada registrada com {atraso_minutos}min de atraso'
                else:
                    mensagem = f'Saída registrada com {atraso_minutos}min de antecipação'
            
            # Adicionar informação do próximo registro
            if tipo == 'ENTRADA':
                mensagem += ' | Próximo registro: Saída'
            else:
                mensagem += ' | Registro do dia concluído'
            
            response_serializer = RegistroPontoSerializer(registro)
            return Response({
                'sucesso': True,
                'mensagem': mensagem,
                'registro': response_serializer.data,
                'proximo_tipo': proximo_tipo,
                'dentro_tolerancia': dentro_tolerancia,
                'dia_concluido': tipo == 'SAIDA'  # Indica se o dia está completo
            })
            
        except Profissional.DoesNotExist:
            return Response(
                {'erro': 'CPF não encontrado ou profissional inativo'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Estabelecimento.DoesNotExist:
            return Response(
                {'erro': 'Estabelecimento não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except ValidationError as e:
            return Response(
                {'erro': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except IntegrityError:
            return Response(
                {'erro': 'Registro duplicado. Já existe um ponto com essas informações.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    def validar_localizacao(self, estabelecimento, lat, lng):
        """Valida se a localização está dentro do raio permitido"""
        try:
            lat_diff = estabelecimento.latitude - float(lat)
            lng_diff = estabelecimento.longitude - float(lng)
            distancia = (lat_diff**2 + lng_diff**2)**0.5 * 111000  # Aproximação em metros
            return distancia <= estabelecimento.raio_permitido
        except (TypeError, ValueError):
            return False
    
    @action(detail=False, methods=['get'])
    def historico(self, request):
        """Retorna histórico de registros do profissional"""
        cpf = request.query_params.get('cpf')
        estabelecimento_id = request.query_params.get('estabelecimento_id')
        
        if not cpf or not estabelecimento_id:
            return Response(
                {'erro': 'CPF e estabelecimento_id são obrigatórios'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            profissional = Profissional.objects.get(cpf=cpf, ativo=True)
            estabelecimento = Estabelecimento.objects.get(id=estabelecimento_id)
            
            registros = RegistroPonto.objects.filter(
                profissional=profissional,
                estabelecimento=estabelecimento
            ).order_by('-data', '-horario')[:100]  # Limita a 100 registros
            
            serializer = self.get_serializer(registros, many=True)
            return Response(serializer.data)
            
        except Profissional.DoesNotExist:
            return Response(
                {'erro': 'CPF não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Estabelecimento.DoesNotExist:
            return Response(
                {'erro': 'Estabelecimento não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def resumo_dia(self, request):
        """Retorna resumo do dia com horas trabalhadas"""
        cpf = request.query_params.get('cpf')
        estabelecimento_id = request.query_params.get('estabelecimento_id')
        data_str = request.query_params.get('data')
        
        if not cpf or not estabelecimento_id:
            return Response(
                {'erro': 'CPF e estabelecimento_id são obrigatórios'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            data = timezone.datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else timezone.now().date()
            profissional = Profissional.objects.get(cpf=cpf, ativo=True)
            estabelecimento = Estabelecimento.objects.get(id=estabelecimento_id)
            
            registros_dia = RegistroPonto.objects.filter(
                profissional=profissional,
                estabelecimento=estabelecimento,
                data=data
            ).order_by('horario')
            
            horas_trabalhadas = calcular_horas_trabalhadas_dia(profissional, estabelecimento, data)
            
            # Calcular totais
            total_atrasos = sum(r.atraso_minutos for r in registros_dia)
            total_saidas_antecipadas = sum(r.saida_antecipada_minutos for r in registros_dia)
            
            # Determinar próximo tipo
            proximo_tipo = determinar_proximo_tipo(profissional, estabelecimento, data)
            
            return Response({
                'data': data,
                'profissional': profissional.get_full_name(),
                'horas_trabalhadas': str(horas_trabalhadas),
                'total_atrasos_minutos': total_atrasos,
                'total_saidas_antecipadas_minutos': total_saidas_antecipadas,
                'proximo_registro': proximo_tipo,
                'registros': RegistroPontoSerializer(registros_dia, many=True).data
            })
            
        except Profissional.DoesNotExist:
            return Response({'erro': 'CPF não encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except Estabelecimento.DoesNotExist:
            return Response({'erro': 'Estabelecimento não encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({'erro': 'Formato de data inválido. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def status_atual(self, request):
        """Retorna o status atual do profissional (qual o próximo registro esperado)"""
        cpf = request.query_params.get('cpf')
        estabelecimento_id = request.query_params.get('estabelecimento_id')
        
        if not cpf or not estabelecimento_id:
            return Response(
                {'erro': 'CPF e estabelecimento_id são obrigatórios'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            profissional = Profissional.objects.get(cpf=cpf, ativo=True)
            estabelecimento = Estabelecimento.objects.get(id=estabelecimento_id)
            hoje = timezone.now().date()
            
            proximo_tipo = determinar_proximo_tipo(profissional, estabelecimento, hoje)
            
            registros_hoje = RegistroPonto.objects.filter(
                profissional=profissional,
                estabelecimento=estabelecimento,
                data=hoje
            ).order_by('horario')
            
            return Response({
                'proximo_registro': proximo_tipo,
                'registros_hoje': RegistroPontoSerializer(registros_hoje, many=True).data,
                'total_registros_hoje': registros_hoje.count(),
                'mensagem': f'Próximo registro: {proximo_tipo.lower()}'
            })
            
        except Profissional.DoesNotExist:
            return Response({'erro': 'CPF não encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except Estabelecimento.DoesNotExist:
            return Response({'erro': 'Estabelecimento não encontrado'}, status=status.HTTP_404_NOT_FOUND)

# Views para interface web
def verificar_cpf(request):
    """View para verificar se CPF existe e está ativo via AJAX"""
    cpf = request.GET.get('cpf', '')
    
    if not cpf or len(cpf) != 11:
        return JsonResponse({
            'valido': False,
            'mensagem': 'CPF inválido'
        })
    
    try:
        profissional = Profissional.objects.get(cpf=cpf)

        if profissional.ativo:
            estabelecimentos_list = []
            
            if profissional.estabelecimento:
                estabelecimento = profissional.estabelecimento
                estabelecimentos_list = [{
                    'id': estabelecimento.id,
                    'nome': estabelecimento.nome,
                    'latitude': estabelecimento.latitude,
                    'longitude': estabelecimento.longitude,
                    'raio_permitido': estabelecimento.raio_permitido
                }]
            
            # Verificar status atual
            hoje = timezone.now().date()
            proximo_tipo = determinar_proximo_tipo(profissional, profissional.estabelecimento, hoje) if profissional.estabelecimento else 'ENTRADA'
            
            return JsonResponse({
                'valido': True,
                'mensagem': f'Profissional: {profissional.nome} {profissional.sobrenome}',
                'profissional': {
                    'id': profissional.id,
                    'nome': profissional.nome,
                    'sobrenome': profissional.sobrenome,
                    'horario_entrada': profissional.horario_entrada.strftime('%H:%M') if profissional.horario_entrada else '08:00',
                    'horario_saida': profissional.horario_saida.strftime('%H:%M') if profissional.horario_saida else '17:00',
                    'tolerancia_minutos': profissional.tolerancia_minutos or 10,
                    'estabelecimento_id': profissional.estabelecimento.id if profissional.estabelecimento else None
                },
                'estabelecimentos': estabelecimentos_list,
                'proximo_registro': proximo_tipo
            })
        else:
            return JsonResponse({
                'valido': False,
                'mensagem': 'Profissional inativo. Contate o administrador.'
            })
            
    except Profissional.DoesNotExist:
        return JsonResponse({
            'valido': False,
            'mensagem': 'CPF não encontrado no sistema'
        })
    except Exception as e:
        return JsonResponse({
            'valido': False,
            'mensagem': f'Erro interno: {str(e)}'
        })

def tela_registro_ponto(request):
    """Tela para registro de ponto por CPF"""
    estabelecimentos = Estabelecimento.objects.all()
    return render(request, 'registro_ponto.html', {
        'estabelecimentos': estabelecimentos
    })

def registrar_ponto_view(request):
    """View para registrar ponto via formulário HTML - CORREÇÃO APLICADA"""
    if request.method == 'POST':
        cpf = request.POST.get('cpf')
        estabelecimento_id = request.POST.get('estabelecimento_id')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        
        try:
            profissional = Profissional.objects.get(cpf=cpf, ativo=True)
            estabelecimento = Estabelecimento.objects.get(id=estabelecimento_id)
            
            # Validar localização
            if latitude and longitude:
                lat_diff = estabelecimento.latitude - float(latitude)
                lng_diff = estabelecimento.longitude - float(longitude)
                distancia = (lat_diff**2 + lng_diff**2)**0.5 * 111000
                
                if distancia > estabelecimento.raio_permitido:
                    return render(request, 'registro_ponto.html', {
                        'erro': f'Fora do raio permitido. Distância: {distancia:.0f}m > Raio: {estabelecimento.raio_permitido}m',
                        'estabelecimentos': Estabelecimento.objects.all()
                    })
            
            # Determinar tipo de registro
            hoje = timezone.now().date()
            horario_atual = timezone.now().time()
            
            tipo = determinar_proximo_tipo(profissional, estabelecimento, hoje)
            
            print(f"🔍 DEBUG WEB: Próximo tipo determinado: {tipo}")
            
            # Verificar se já existe registro do mesmo tipo
            if verificar_registro_duplicado(profissional, estabelecimento, hoje, tipo):
                tipo_oposto = 'SAIDA' if tipo == 'ENTRADA' else 'ENTRADA'
                return render(request, 'registro_ponto.html', {
                    'erro': f'Já existe um registro de {tipo.lower()} para hoje. Próximo registro deve ser {tipo_oposto.lower()}.',
                    'estabelecimentos': Estabelecimento.objects.all()
                })
            
            # Calcular tolerância
            atraso_minutos, dentro_tolerancia = calcular_tolerancia(profissional, horario_atual, tipo)
            
            # Criar registro
            registro = RegistroPonto(
                profissional=profissional,
                estabelecimento=estabelecimento,
                data=hoje,
                horario=horario_atual,
                tipo=tipo,
                latitude=latitude or estabelecimento.latitude,
                longitude=longitude or estabelecimento.longitude,
                atraso_minutos=atraso_minutos if tipo == 'ENTRADA' else 0,
                saida_antecipada_minutos=atraso_minutos if tipo == 'SAIDA' else 0,
                dentro_tolerancia=dentro_tolerancia
            )
            
            registro.save()
            
            # Mensagem de sucesso
            if dentro_tolerancia:
                mensagem = f'✅ {tipo.lower().capitalize()} registrada com sucesso!'
            else:
                if tipo == 'ENTRADA':
                    mensagem = f'⚠️ Entrada registrada com {atraso_minutos}min de atraso'
                else:
                    mensagem = f'⚠️ Saída registrada com {atraso_minutos}min de antecipação'
            
            # Informação do próximo registro
            if tipo == 'ENTRADA':
                mensagem += '<br><strong>Próximo registro: Saída</strong>'
            else:
                mensagem += '<br><strong>✅ Registro do dia concluído!</strong>'
            
            # Buscar registros do dia para exibir
            registros_hoje = RegistroPonto.objects.filter(
                profissional=profissional,
                estabelecimento=estabelecimento,
                data=hoje
            ).order_by('horario')
            
            # Contar registros para debug
            entradas = registros_hoje.filter(tipo='ENTRADA').count()
            saidas = registros_hoje.filter(tipo='SAIDA').count()
            
            print(f"🔍 DEBUG FINAL: Entradas: {entradas}, Saídas: {saidas}")
            
            return render(request, 'registro_ponto.html', {
                'sucesso': True,
                'mensagem': mensagem,
                'profissional': profissional,
                'tipo': tipo,
                'horario': registro.horario,
                'estabelecimento': estabelecimento,
                'registro': registro,
                'registros_hoje': registros_hoje,
                'entradas_count': entradas,
                'saidas_count': saidas,
                'estabelecimentos': Estabelecimento.objects.all()
            })
            
        except Profissional.DoesNotExist:
            return render(request, 'registro_ponto.html', {
                'erro': 'CPF não encontrado ou profissional inativo',
                'estabelecimentos': Estabelecimento.objects.all()
            })
        except Estabelecimento.DoesNotExist:
            return render(request, 'registro_ponto.html', {
                'erro': 'Estabelecimento não encontrado',
                'estabelecimentos': Estabelecimento.objects.all()
            })
        except ValidationError as e:
            return render(request, 'registro_ponto.html', {
                'erro': str(e),
                'estabelecimentos': Estabelecimento.objects.all()
            })
        except IntegrityError:
            return render(request, 'registro_ponto.html', {
                'erro': 'Registro duplicado. Já existe um ponto com essas informações.',
                'estabelecimentos': Estabelecimento.objects.all()
            })
        except Exception as e:
            print(f"❌ Erro inesperado: {str(e)}")
            return render(request, 'registro_ponto.html', {
                'erro': f'Erro inesperado: {str(e)}',
                'estabelecimentos': Estabelecimento.objects.all()
            })
    
    return redirect('tela_registro_ponto')