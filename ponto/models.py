from django.db import models
from django.core.exceptions import ValidationError
from usuarios.models import Profissional
from estabelecimentos.models import Estabelecimento
from datetime import timedelta, datetime, time
import pytz
from django.utils import timezone

class RegistroPonto(models.Model):
    TIPO_REGISTRO = [
        ('ENTRADA', 'Entrada'),
        ('SAIDA', 'Saída'),
    ]
    
    profissional = models.ForeignKey(Profissional, on_delete=models.CASCADE)
    estabelecimento = models.ForeignKey(Estabelecimento, on_delete=models.CASCADE)
    data = models.DateField()
    horario = models.TimeField()
    tipo = models.CharField(max_length=10, choices=TIPO_REGISTRO)
    latitude = models.FloatField()
    longitude = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # ✅ CAMPOS PARA CONTROLE DE TOLERÂNCIA
    atraso_minutos = models.IntegerField(default=0, verbose_name='Atraso (minutos)')
    saida_antecipada_minutos = models.IntegerField(default=0, verbose_name='Saída Antecipada (minutos)')
    dentro_tolerancia = models.BooleanField(default=True, verbose_name='Dentro da Tolerância')
    
    class Meta:
        verbose_name = "Registro de Ponto"
        verbose_name_plural = "Registros de Ponto"
        unique_together = ['profissional', 'estabelecimento', 'data', 'tipo']
        ordering = ['-data', '-horario']
    
    def __str__(self):
        return f"{self.profissional.get_full_name()} - {self.data} {self.tipo}"
    
    def clean(self):
        """Validação para garantir apenas uma entrada e uma saída por dia"""
        if RegistroPonto.objects.filter(
            profissional=self.profissional,
            estabelecimento=self.estabelecimento,
            data=self.data,
            tipo=self.tipo
        ).exclude(pk=self.pk).exists():
            raise ValidationError(
                f'Já existe um registro de {self.get_tipo_display().lower()} para este profissional nesta data.'
            )
    
    def save(self, *args, **kwargs):
        """Sobrescreve o save para validar e calcular tolerância"""
        # Valida antes de salvar
        self.clean()
        
        # ✅ CONVERTE PARA HORÁRIO DE BRASÍLIA ANTES DE SALVAR
        if not self.pk:  # Apenas para novos registros
            self._converter_para_brasilia()
        
        # Calcula atraso/saída antecipada antes de salvar
        self._calcular_tolerancia()
        
        super().save(*args, **kwargs)
    
    def _converter_para_brasilia(self):
        """Converte o horário para o fuso horário de Brasília"""
        try:
            # Timezone do Brasil (Brasília)
            tz_brasilia = pytz.timezone('America/Sao_Paulo')
            
            # Usa o horário atual convertido para Brasília
            agora_brasilia = timezone.now().astimezone(tz_brasilia)
            self.data = agora_brasilia.date()
            self.horario = agora_brasilia.time()
                
        except Exception as e:
            # Fallback: usa o horário do sistema sem conversão
            print(f"Erro na conversão de timezone: {e}")
    
    def _calcular_tolerancia(self):
        """Calcula atraso e saída antecipada baseado no horário esperado"""
        try:
            # Obter horários esperados do profissional
            horario_entrada_esperado = self.profissional.horario_entrada
            horario_saida_esperado = self.profissional.horario_saida
            tolerancia_minutos = self.profissional.tolerancia_minutos or 0
            
            if not horario_entrada_esperado or not horario_saida_esperado:
                # Se não há horários definidos, considera dentro da tolerância
                self.dentro_tolerancia = True
                self.atraso_minutos = 0
                self.saida_antecipada_minutos = 0
                return
            
            if self.tipo == 'ENTRADA':
                # ✅ CÁLCULO DE ATRASO NA ENTRADA
                horario_registro = datetime.combine(self.data, self.horario)
                horario_limite = datetime.combine(self.data, horario_entrada_esperado)
                
                # Adiciona tolerância ao horário esperado
                horario_com_tolerancia = horario_limite + timedelta(minutes=tolerancia_minutos)
                
                # Calcula atraso em minutos
                if horario_registro > horario_com_tolerancia:
                    diferenca = horario_registro - horario_com_tolerancia
                    self.atraso_minutos = int(diferenca.total_seconds() / 60)
                    self.dentro_tolerancia = False
                else:
                    self.atraso_minutos = 0
                    self.dentro_tolerancia = True
                
                self.saida_antecipada_minutos = 0
            
            elif self.tipo == 'SAIDA':
                # ✅ CÁLCULO DE SAÍDA ANTECIPADA
                horario_registro = datetime.combine(self.data, self.horario)
                horario_limite = datetime.combine(self.data, horario_saida_esperado)
                
                # Subtrai tolerância do horário esperado
                horario_com_tolerancia = horario_limite - timedelta(minutes=tolerancia_minutos)
                
                # Calcula saída antecipada em minutos
                if horario_registro < horario_com_tolerancia:
                    diferenca = horario_com_tolerancia - horario_registro
                    self.saida_antecipada_minutos = int(diferenca.total_seconds() / 60)
                    self.dentro_tolerancia = False
                else:
                    self.saida_antecipada_minutos = 0
                    self.dentro_tolerancia = True
                
                self.atraso_minutos = 0
        
        except Exception as e:
            print(f"Erro no cálculo de tolerância: {e}")
            # Em caso de erro, define valores padrão
            self.atraso_minutos = 0
            self.saida_antecipada_minutos = 0
            self.dentro_tolerancia = True
    
    # ✅ PROPRIEDADES PARA FACILITAR O ACESSO
    @property
    def horario_brasilia(self):
        """Retorna o horário já convertido para string no formato Brasília"""
        return self.horario.strftime('%H:%M')
    
    @property
    def status_tolerancia(self):
        """Retorna o status de tolerância de forma legível"""
        if self.dentro_tolerancia:
            return "No horário"
        elif self.atraso_minutos > 0:
            return f"Atraso: {self.atraso_minutos}min"
        elif self.saida_antecipada_minutos > 0:
            return f"Saída antecipada: {self.saida_antecipada_minutos}min"
        else:
            return "No horário"
    
    @property
    def cor_status(self):
        """Retorna a cor Bootstrap para o status"""
        if self.dentro_tolerancia:
            return "success"
        else:
            return "warning"
    
    @property
    def proximo_tipo(self):
        """Retorna qual será o próximo tipo de registro"""
        if self.tipo == 'ENTRADA':
            return 'SAIDA'
        return 'ENTRADA'