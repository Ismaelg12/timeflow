from django.contrib import admin
from .models import Profissional, AreaAtuacao

@admin.register(Profissional)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display = [
        'nome_completo', 
        'profissao', 
        'estabelecimento',
        'carga_horaria_diaria_display',
        'tolerancia_minutos',
        'ativo',
        'criado_em'
    ]
    list_filter = ['ativo', 'profissao', 'estabelecimento']
    search_fields = ['nome', 'cpf']
    list_editable = ['ativo', 'estabelecimento', 'tolerancia_minutos']
    
    fieldsets = [
        ('Dados Pessoais', {
            'fields': [
                'nome', 
                'cpf',
                'profissao'
            ]
        }),
        ('Vínculo Profissional', {
            'fields': [
                'estabelecimento',
                'carga_horaria_diaria',
                'carga_horaria_semanal',
                'ativo'
            ]
        }),
        ('Horários e Tolerância', {
            'fields': [
                'horario_entrada',
                'horario_saida',
                'tolerancia_minutos'
            ]
        }),
        ('Datas', {
            'fields': [
                'criado_em',
                'atualizado_em'
            ],
            'classes': ('collapse',)
        }),
    ]
    
    readonly_fields = ['criado_em', 'atualizado_em']
    
    def nome_completo(self, obj):
        return f"{obj.nome}"
    nome_completo.short_description = 'Nome Completo'
    
    def carga_horaria_diaria_display(self, obj):
        return obj.get_carga_horaria_diaria_display()
    carga_horaria_diaria_display.short_description = 'Carga Diária'


@admin.register(AreaAtuacao)
class AreaAtuacaoAdmin(admin.ModelAdmin):
    list_display = ['profissao']
    search_fields = ['profissao']