# api/serializers.py
from rest_framework import serializers
from usuarios.models import Profissional
from ponto.models import RegistroPonto
from estabelecimentos.models import Estabelecimento
from datetime import datetime

# ✅ ADICIONE ESTA CLASSE QUE ESTAVA FALTANDO
class ProfissionalSerializer(serializers.ModelSerializer):
    estabelecimento_nome = serializers.CharField(source='estabelecimento.nome', read_only=True)
    profissao_nome = serializers.CharField(source='profissao.nome', read_only=True)
    nome_completo = serializers.SerializerMethodField()
    
    class Meta:
        model = Profissional
        fields = [
            'id', 'nome', 'sobrenome', 'nome_completo', 'email', 'cpf', 
            'profissao', 'profissao_nome', 'estabelecimento', 
            'estabelecimento_nome', 'horario_entrada', 'horario_saida',
            'tolerancia_minutos', 'carga_horaria_diaria', 'carga_horaria_semanal'
        ]
        read_only_fields = ['id', 'nome_completo', 'profissao_nome', 'estabelecimento_nome']
    
    def get_nome_completo(self, obj):
        return f"{obj.nome} {obj.sobrenome}"

class EstabelecimentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estabelecimento
        fields = ['id', 'nome', 'endereco', 'latitude', 'longitude']

class RegistroPontoSerializer(serializers.ModelSerializer):
    profissional_nome = serializers.CharField(source='profissional.nome_completo', read_only=True)
    estabelecimento_nome = serializers.CharField(source='estabelecimento.nome', read_only=True)
    data_formatada = serializers.SerializerMethodField()
    horario_formatado = serializers.SerializerMethodField()
    status_tolerancia = serializers.SerializerMethodField()
    
    class Meta:
        model = RegistroPonto
        fields = [
            'id', 'profissional', 'profissional_nome', 'estabelecimento', 
            'estabelecimento_nome', 'data', 'data_formatada', 'horario', 
            'horario_formatado', 'tipo', 'latitude', 'longitude', 
            'created_at', 'atraso_minutos', 'saida_antecipada_minutos', 
            'dentro_tolerancia', 'status_tolerancia'
        ]
        read_only_fields = [
            'created_at', 'atraso_minutos', 'saida_antecipada_minutos', 
            'dentro_tolerancia', 'status_tolerancia', 'data_formatada',
            'horario_formatado', 'profissional_nome', 'estabelecimento_nome'
        ]
    
    def get_data_formatada(self, obj):
        return obj.data.strftime('%d/%m/%Y')
    
    def get_horario_formatado(self, obj):
        return obj.horario.strftime('%H:%M')
    
    def get_status_tolerancia(self, obj):
        if obj.dentro_tolerancia:
            return "No horário"
        elif obj.atraso_minutos > 0:
            return f"Atraso: {obj.atraso_minutos}min"
        elif obj.saida_antecipada_minutos > 0:
            return f"Saída antecipada: {obj.saida_antecipada_minutos}min"
        else:
            return "No horário"

# ✅ CORREÇÃO: APENAS UMA CLASSE RegistroPontoCreateSerializer
class RegistroPontoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroPonto
        fields = ['profissional', 'estabelecimento', 'data', 'horario', 'tipo', 'latitude', 'longitude']
        # ✅ CORREÇÃO: Apenas data e horário são read_only
        read_only_fields = ['data', 'horario']
    
    def validate(self, data):
        # Validações básicas
        if 'tipo' not in data:
            raise serializers.ValidationError("Tipo de registro é obrigatório")
        
        if data['tipo'].upper() not in ['ENTRADA', 'SAIDA']:
            raise serializers.ValidationError("Tipo deve ser ENTRADA ou SAIDA")
        
        return data
    
    def create(self, validated_data):
        import pytz
        from django.utils import timezone
        
        tz_brasilia = pytz.timezone('America/Sao_Paulo')
        agora = timezone.now().astimezone(tz_brasilia)
        
        # ✅ Define data e horário atuais
        validated_data['data'] = agora.date()
        validated_data['horario'] = agora.time()
        
        # ✅ Define profissional automaticamente do usuário logado
        request = self.context.get('request')
        if request and hasattr(request.user, 'profissional'):
            validated_data['profissional'] = request.user.profissional
            
            # ✅ Define estabelecimento automaticamente do profissional
            if 'estabelecimento' not in validated_data:
                validated_data['estabelecimento'] = request.user.profissional.estabelecimento
        
        return super().create(validated_data)