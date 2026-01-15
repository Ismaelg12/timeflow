from django.contrib import admin
from .models import Estabelecimento

@admin.register(Estabelecimento)
class EstabelecimentoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'municipio', 'cnpj', 'raio_permitido', 'created_at']
    search_fields = ['nome', 'cnpj', 'endereco', 'municipio__nome']
    list_filter = ['municipio', 'created_at']
    list_editable = ['raio_permitido']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('nome', 'cnpj', 'municipio', 'endereco')
        }),
        ('Coordenadas', {
            'fields': ('latitude', 'longitude', 'raio_permitido')
        }),
    )