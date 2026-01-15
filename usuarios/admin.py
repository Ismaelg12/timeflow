from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Profissional, AreaAtuacao, LogAtividade

@admin.register(Usuario)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active']
    list_filter = ['is_staff', 'is_superuser', 'is_active']
    search_fields = ['username', 'email', 'first_name', 'last_name']

@admin.register(Profissional)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display = [
        'get_full_name', 
        'profissao', 
        'estabelecimento',
        'carga_horaria_diaria',
        'tolerancia_minutos',
        'ativo'
    ]
    list_filter = ['ativo', 'profissao', 'estabelecimento']
    search_fields = ['nome', 'sobrenome', 'cpf', 'usuario__username', 'email']
    raw_id_fields = ['usuario', 'estabelecimento']
    list_editable = ['ativo', 'estabelecimento', 'carga_horaria_diaria', 'tolerancia_minutos']
    
    fieldsets = [
        ('Dados Pessoais', {
            'fields': [
                'usuario',
                'nome', 
                'sobrenome', 
                'cpf',
                'email',
                'telefone',
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
        ('Termo de Uso', {
            'fields': [
                'termo_uso',
                'termo_uso_versao',
                'termo_uso_data',
                'termo_uso_ip'
            ]
        }),
    ]
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Nome Completo'

@admin.register(AreaAtuacao)
class AreaAtuacaoAdmin(admin.ModelAdmin):
    list_display = ['profissao']
    search_fields = ['profissao']

@admin.register(LogAtividade)
class LogAtividadeAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'acao', 'ip_address', 'data_hora']
    list_filter = ['acao', 'data_hora']
    search_fields = ['usuario__username', 'acao', 'detalhes']
    readonly_fields = ['usuario', 'acao', 'detalhes', 'ip_address', 'data_hora']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False