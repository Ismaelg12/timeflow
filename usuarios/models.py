from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from estabelecimentos.models import Estabelecimento
from datetime import timedelta

class AreaAtuacao(models.Model):
    profissao = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = 'Profissão'
        verbose_name_plural = 'Profissões'

    def __str__(self):
        return str(self.profissao)

class Usuario(AbstractUser):
    telefone = models.CharField(max_length=15, blank=True, null=True)
    data_nascimento = models.DateField(blank=True, null=True)
    cpf = models.CharField(
        max_length=11,
        unique=True,
        null=True,
        blank=True,
        error_messages={
            'unique': 'Este CPF já está cadastrado.',
        }
    )
    
    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

class ProfissionalManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(ativo=True).exclude(usuario__username="admin")

class Profissional(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE)
    nome = models.CharField(max_length=50)
    sobrenome = models.CharField(max_length=50)
    email = models.EmailField(max_length=50, blank=True, null=True)
    telefone = models.CharField(max_length=15, blank=True)
    cpf = models.CharField(
        'CPF',
        max_length=11,
        unique=True,
        null=False,
        blank=False,
        error_messages={
            'unique': 'Este CPF já está cadastrado.',
            'blank': 'O CPF é obrigatório.'
        }
    )
    profissao = models.ForeignKey(AreaAtuacao, on_delete=models.SET_NULL, null=True, blank=True)
    
    # ✅ ESTABELECIMENTO E CARGA HORÁRIA
    estabelecimento = models.ForeignKey(
        Estabelecimento, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='Estabelecimento'
    )
    carga_horaria_diaria = models.DurationField(null=True, blank=True)
    carga_horaria_semanal = models.DurationField(null=True, blank=True)
    
    # Campos calculados para facilitar acesso
    horas_diarias = models.FloatField(default=0, editable=False)
    horas_semanais = models.FloatField(default=0, editable=False)
    
    ativo = models.BooleanField(default=False)
    
    # Campos do termo de uso
    termo_uso = models.BooleanField(
        default=False,
        verbose_name='Aceitou os termos'
    )
    termo_uso_versao = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Versão dos termos'
    )
    termo_uso_data = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data de aceite'
    )
    termo_uso_ip = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name='IP de aceite'
    )
    horario_entrada = models.TimeField(null=True, blank=True, verbose_name='Horário de Entrada')
    horario_saida = models.TimeField(null=True, blank=True, verbose_name='Horário de Saída')
    tolerancia_minutos = models.PositiveIntegerField(default=10, verbose_name='Tolerância (minutos)')
    
    # Campos de data
    criado_em = models.DateField('Criado em', auto_now_add=True)
    atualizado_em = models.DateField('Atualizado em', auto_now=True)

    objects = models.Manager()
    prof_objects = ProfissionalManager()

    class Meta:
        verbose_name = 'Profissional'
        verbose_name_plural = 'Profissionais'

    def __str__(self):
        return f"{self.nome} {self.sobrenome}"

    def get_full_name(self):
        return f"{self.nome} {self.sobrenome}"

    def save(self, *args, **kwargs):
        # Calcular horas diárias e semanais apenas se os campos não forem None
        if self.carga_horaria_diaria:
            self.horas_diarias = self.carga_horaria_diaria.total_seconds() / 3600
        else:
            self.horas_diarias = 0
        
        if self.carga_horaria_semanal:
            self.horas_semanais = self.carga_horaria_semanal.total_seconds() / 3600
        else:
            self.horas_semanais = 0
        
        super().save(*args, **kwargs)

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

class LogAtividade(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, verbose_name='Usuário')
    acao = models.CharField(max_length=100, verbose_name='Ação')
    detalhes = models.TextField(blank=True, verbose_name='Detalhes')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='Endereço IP')
    data_hora = models.DateTimeField(auto_now_add=True, verbose_name='Data/Hora')
    
    class Meta:
        verbose_name = 'Log de Atividade'
        verbose_name_plural = 'Logs de Atividade'
        ordering = ['-data_hora']
    
    def __str__(self):
        return f'{self.usuario.username} - {self.acao} - {self.data_hora.strftime("%d/%m/%Y %H:%M")}'

# Signals
@receiver(post_save, sender=Usuario)
def create_user_profile(sender, instance, created, **kwargs):
    if created and not hasattr(instance, '_disable_signal'):
        Profissional.objects.create(
            usuario=instance, 
            ativo=False,  # ✅ CORREÇÃO: Inativo por padrão
            nome=instance.username,  # Nome padrão
            sobrenome='',  # Sobrenome vazio
            cpf=''  # CPF vazio
        )

@receiver(post_save, sender=Profissional)
def update_user_email(sender, instance, **kwargs):
    if instance.email and instance.usuario.email != instance.email:
        instance.usuario.email = instance.email
        instance.usuario._disable_signal = True  # Evitar loop infinito
        instance.usuario.save()
        delattr(instance.usuario, '_disable_signal')

@receiver(post_delete, sender=Profissional)
def delete_user(sender, instance, **kwargs):
    instance.usuario.delete()