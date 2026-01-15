from django.db import models
from municipio.models import Municipio

class Estabelecimento(models.Model):
    nome = models.CharField(max_length=200)
    endereco = models.TextField()
    cnpj = models.CharField(max_length=18, unique=True)
    municipio = models.ForeignKey(Municipio, on_delete=models.CASCADE)
    latitude = models.FloatField()
    longitude = models.FloatField()
    raio_permitido = models.FloatField(default=100, help_text="Raio em metros")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name = "Estabelecimento"
        verbose_name_plural = "Estabelecimentos"