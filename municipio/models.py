from django.db import models

class Municipio(models.Model):
    nome = models.CharField(max_length=100)
    uf = models.CharField(max_length=2)
    codigo_ibge = models.CharField(max_length=7, unique=True)
    
    def __str__(self):
        return f"{self.nome}/{self.uf}"
    
    class Meta:
        verbose_name = "Município"
        verbose_name_plural = "Municípios"