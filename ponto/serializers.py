# from rest_framework import serializers
# from .models import RegistroPonto

# class RegistroPontoSerializer(serializers.ModelSerializer):
#     profissional_nome = serializers.CharField(source='profissional.get_full_name', read_only=True)
#     estabelecimento_nome = serializers.CharField(source='estabelecimento.nome', read_only=True)
#     proximo_tipo = serializers.SerializerMethodField()
#     status_tolerancia = serializers.CharField(read_only=True)
#     horario_brasilia = serializers.CharField(read_only=True)
    
#     class Meta:
#         model = RegistroPonto
#         fields = [
#             'id', 'profissional', 'profissional_nome', 'estabelecimento', 'estabelecimento_nome',
#             'data', 'horario', 'horario_brasilia', 'tipo', 'latitude', 'longitude', 
#             'atraso_minutos', 'saida_antecipada_minutos', 'dentro_tolerancia', 
#             'status_tolerancia', 'created_at', 'proximo_tipo'
#         ]
#         read_only_fields = ['created_at']
    
#     def get_proximo_tipo(self, obj):
#         return obj.proximo_tipo

# class RegistroPontoCreateSerializer(serializers.Serializer):
#     cpf = serializers.CharField(max_length=11, min_length=11)
#     estabelecimento_id = serializers.IntegerField()
#     latitude = serializers.FloatField()
#     longitude = serializers.FloatField()
    
#     def validate_cpf(self, value):
#         if not value.isdigit():
#             raise serializers.ValidationError("CPF deve conter apenas números")
#         return value
# ponto/serializers.py
from rest_framework import serializers
from .models import RegistroPonto

class RegistroPontoSerializer(serializers.ModelSerializer):
    profissional_nome = serializers.CharField(source='profissional.get_full_name', read_only=True)
    estabelecimento_nome = serializers.CharField(source='estabelecimento.nome', read_only=True)
    proximo_tipo = serializers.SerializerMethodField()
    status_tolerancia = serializers.CharField(read_only=True)
    horario_brasilia = serializers.CharField(read_only=True)
    
    class Meta:
        model = RegistroPonto
        fields = [
            'id', 'profissional', 'profissional_nome', 'estabelecimento', 'estabelecimento_nome',
            'data', 'horario', 'horario_brasilia', 'tipo', 'latitude', 'longitude', 
            'atraso_minutos', 'saida_antecipada_minutos', 'dentro_tolerancia', 
            'status_tolerancia', 'created_at', 'proximo_tipo'
        ]
        read_only_fields = ['created_at']
    
    def get_proximo_tipo(self, obj):
        return obj.proximo_tipo

class RegistroPontoCreateSerializer(serializers.Serializer):
    """
    Serializer específico para criação via API mobile
    """
    cpf = serializers.CharField(max_length=11, min_length=11)
    estabelecimento_id = serializers.IntegerField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    
    def validate_cpf(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("CPF deve conter apenas números")
        return value