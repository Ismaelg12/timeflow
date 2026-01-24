# api/serializers.py
from rest_framework import serializers
from usuarios.models import Profissional
from ponto.models import RegistroPonto
from estabelecimentos.models import Estabelecimento


class ProfissionalSerializer(serializers.ModelSerializer):
    estabelecimento_nome = serializers.CharField(source='estabelecimento.nome', read_only=True)
    estabelecimento_cnpj = serializers.CharField(source='estabelecimento.cnpj', read_only=True)
    profissao_nome = serializers.CharField(source='profissao.profissao', read_only=True)
    nome_completo = serializers.SerializerMethodField()
    
    class Meta:
        model = Profissional
        fields = [
            'id', 'nome', 'nome_completo', 'email', 'cpf', 
            'profissao', 'profissao_nome', 'estabelecimento', 
            'estabelecimento_nome', 'estabelecimento_cnpj',
            'horario_entrada', 'horario_saida',
            'tolerancia_minutos', 'ativo'
        ]
    
    def get_nome_completo(self, obj):
        return f"{obj.nome}"


class EstabelecimentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estabelecimento
        fields = ['id', 'nome', 'cnpj', 'endereco', 'latitude', 'longitude', 'raio_permitido'] 


class RegistroPontoSerializer(serializers.ModelSerializer):
    profissional_nome = serializers.CharField(source='profissional.get_full_name', read_only=True)
    estabelecimento_nome = serializers.CharField(source='estabelecimento.nome', read_only=True)
    estabelecimento_cnpj = serializers.CharField(source='estabelecimento.cnpj', read_only=True) 
    data_formatada = serializers.SerializerMethodField()
    horario_formatado = serializers.SerializerMethodField()
    status_tolerancia = serializers.SerializerMethodField()
    qr_code_url = serializers.SerializerMethodField()  
    
    class Meta:
        model = RegistroPonto
        fields = [
            'id', 'profissional', 'profissional_nome', 'estabelecimento', 
            'estabelecimento_nome', 'estabelecimento_cnpj', 'data',  
            'data_formatada', 'horario', 'horario_formatado', 'tipo', 
            'latitude', 'longitude', 'created_at', 'atraso_minutos', 
            'saida_antecipada_minutos', 'dentro_tolerancia', 'status_tolerancia',
            'qr_code_url'  
        ]
        read_only_fields = fields
    
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
    
    def get_qr_code_url(self, obj):
        request = self.context.get('request')
        if request:
            base_url = request.build_absolute_uri('/')
            return f"{base_url}api/comprovante/{obj.id}/qr-code/"
        return None


class RegistroPontoCreateSerializer(serializers.Serializer):
    cpf = serializers.CharField(max_length=11, min_length=11)
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    biom_hash = serializers.CharField(required=False, allow_blank=True, max_length=255)
    
    def validate_cpf(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("CPF deve conter apenas números")
        return value