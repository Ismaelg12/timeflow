from django.contrib import admin
from .models import Municipio

@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ['nome', 'uf', 'codigo_ibge']
    search_fields = ['nome']
    list_filter = ['nome', 'uf']
 
    
    fieldsets = (
        (None, {
            'fields': ('nome', 'uf', 'codigo_ibge')
        }),
    )