from django.db import models
from estabelecimentos.models import Estabelecimento

class AreaAtuacao(models.Model):
    profissao = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = 'Profissão'
        verbose_name_plural = 'Profissões'

    def __str__(self):
        return str(self.profissao)

class Profissional(models.Model):
    # Dados básicos
    nome = models.CharField(max_length=50)
    sobrenome = models.CharField(max_length=50)
    cpf = models.CharField(
        'CPF',
        max_length=14,
        unique=True,
        null=False,
        blank=False,
        error_messages={
            'unique': 'Este CPF já está cadastrado.',
            'blank': 'O CPF é obrigatório.'
        }
    )
    
    # ✅ ADICIONEI O TELEFONE AQUI
    telefone = models.CharField(
        'Telefone',
        max_length=15,
        null=True,
        blank=True,
        help_text='Formato: (11) 99999-9999'
    )
    
    # Profissão
    profissao = models.ForeignKey(AreaAtuacao, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Estabelecimento e carga horária
    estabelecimento = models.ForeignKey(
        Estabelecimento, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='Estabelecimento'
    )
    carga_horaria_diaria = models.DurationField(null=True, blank=True)
    carga_horaria_semanal = models.DurationField(null=True, blank=True)
    
    # Horários fixos
    horario_entrada = models.TimeField(null=True, blank=True, verbose_name='Horário de Entrada')
    horario_saida = models.TimeField(null=True, blank=True, verbose_name='Horário de Saída')
    tolerancia_minutos = models.PositiveIntegerField(default=10, verbose_name='Tolerância (minutos)')
    
    # Status (False = aguardando aprovação, True = aprovado)
    ativo = models.BooleanField(default=False)
    
    # Datas automáticas
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Profissional'
        verbose_name_plural = 'Profissionais'
        ordering = ['nome', 'sobrenome']

    def __str__(self):
        return f"{self.nome} {self.sobrenome}"

    def get_full_name(self):
        return f"{self.nome} {self.sobrenome}"

    def get_carga_horaria_diaria_display(self):
        """Retorna a carga horária diária formatada como HH:MM"""
        if self.carga_horaria_diaria:
            total_seconds = int(self.carga_horaria_diaria.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"
        return ""

    def get_carga_horaria_semanal_display(self):
        """Retorna a carga horária semanal formatada como HH:MM"""
        if self.carga_horaria_semanal:
            total_seconds = int(self.carga_horaria_semanal.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"
        return ""

    # ✅ MÉTODO PARA FORMATAR TELEFONE
    def get_telefone_formatado(self):
        """Retorna o telefone formatado"""
        if self.telefone:
            # Remove caracteres não numéricos
            import re
            numeros = re.sub(r'\D', '', self.telefone)
            
            if len(numeros) == 11:  # Com DDD + 9 dígitos
                return f'({numeros[:2]}) {numeros[2:7]}-{numeros[7:]}'
            elif len(numeros) == 10:  # Com DDD + 8 dígitos
                return f'({numeros[:2]}) {numeros[2:6]}-{numeros[6:]}'
        
        return self.telefone or ''