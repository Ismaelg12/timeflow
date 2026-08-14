from django.contrib import admin
from .models import RegistroPonto

@admin.register(RegistroPonto)
class RegistroPontoSimpleAdmin(admin.ModelAdmin):
    list_display = [
        'profissional',
        'estabelecimento',
        'data',
        'horario',
        'tipo',
        'dentro_tolerancia',
        'created_at'
    ]
    
    list_filter = [
        'tipo',
        'dentro_tolerancia', 
        'data',
        'estabelecimento'
    ]
    
    # ⚠️ CORRIGIDO: Profissional não tem campo 'user' (não é ligado a auth.User),
    # a busca anterior ('profissional__user__first_name'/'last_name') quebrava o admin.
    search_fields = [
        'profissional__nome',
        'profissional__cpf',
        'estabelecimento__nome'
    ]
    
    readonly_fields = ['created_at']
    
    fieldsets = (
        (None, {
            'fields': (
                'profissional',
                'estabelecimento', 
                'data',
                'horario',
                'tipo',
                'latitude',
                'longitude',
                'dentro_tolerancia'
            )
        }),
        ('Informações de Tolerância', {
            'fields': (
                'atraso_minutos',
                'saida_antecipada_minutos',
            )
        }),
        ('Metadados', {
            'fields': ('created_at',)
        })
    )