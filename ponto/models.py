from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from usuarios.models import Profissional
from estabelecimentos.models import Estabelecimento
from datetime import timedelta, datetime, time
import pytz
from django.utils import timezone
import uuid
import hashlib


class RegistroManual(models.Model):
    """
    Model para registrar ajustes manuais de ponto (esquecimento)
    """
    TIPO_REGISTRO = [
        ('ENTRADA', 'Entrada'),
        ('SAIDA', 'Saída'),
    ]

    MOTIVOS = [
        ('ESQUECIMENTO', 'Esquecimento do profissional'),
        ('PROBLEMA_SISTEMA', 'Problema no sistema de ponto'),
        ('EMERGENCIA', 'Emergência/urgência médica'),
        ('REUNIAO', 'Reunião prolongada'),
        ('ATIVIDADE_EXTERNA', 'Atividade externa'),
        ('FALHA_EQUIPAMENTO', 'Falha no equipamento'),
        ('CAPACITACAO', 'Capacitação/treinamento'),
        ('OUTRO', 'Outro motivo'),
    ]

    profissional = models.ForeignKey(Profissional, on_delete=models.CASCADE)
    data = models.DateField(verbose_name='Data do registro')
    horario = models.TimeField(verbose_name='Horário real')
    tipo = models.CharField(max_length=10, choices=TIPO_REGISTRO, verbose_name='Tipo de registro')
    motivo = models.CharField(max_length=50, choices=MOTIVOS, verbose_name='Motivo do ajuste')
    descricao = models.TextField(blank=True, verbose_name='Descrição adicional')
    ajustado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Ajustado por'
    )
    latitude = models.FloatField(default=0, verbose_name='Latitude (aprox.)')
    longitude = models.FloatField(default=0, verbose_name='Longitude (aprox.)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Data do ajuste')
    confirmado = models.BooleanField(default=False, verbose_name='Confirmado pelo RH')
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ajustes_confirmados',
        verbose_name='Confirmado por'
    )
    confirmado_em = models.DateTimeField(null=True, blank=True, verbose_name='Data da confirmação')

    # Mantido aqui — pode servir pra um "comprovante do ajuste manual" no
    # futuro (diferente do comprovante do registro de ponto em si).
    codigo_validacao = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name='Código de validação do ajuste manual',
    )

    class Meta:
        verbose_name = "Registro Manual"
        verbose_name_plural = "Registros Manuais"
        ordering = ['-data', '-horario']

    def __str__(self):
        return f"{self.profissional.nome} - {self.data} {self.tipo} ({self.motivo})"

    def save(self, *args, **kwargs):
        # Garantir que está no timezone correto
        if not self.pk and self.horario:
            tz_brasilia = pytz.timezone('America/Sao_Paulo')
            agora_brasilia = timezone.now().astimezone(tz_brasilia)

            if not self.data:
                self.data = agora_brasilia.date()

        super().save(*args, **kwargs)

    @property
    def justificativa_formatada(self):
        """Retorna a justificativa formatada"""
        if self.motivo == 'OUTRO':
            return f"OUTRO: {self.descricao[:50]}..." if self.descricao else "OUTRO"
        return self.get_motivo_display()


class RegistroPonto(models.Model):
    TIPO_REGISTRO = [
        ('ENTRADA', 'Entrada'),
        ('SAIDA', 'Saída'),
    ]

    # Identificador do que capturou a marcação — exigido pelo registro tipo
    # "7" do AFD (Anexo I / Portaria 671, REP-P).
    IDENTIFICADOR_COLETOR_CHOICES = [
        ('01', 'Aplicativo mobile'),
        ('02', 'Browser (navegador internet)'),
        ('03', 'Aplicativo desktop'),
        ('04', 'Dispositivo eletrônico'),
        ('05', 'Outro dispositivo eletrônico'),
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

    # ✅ CAMPOS PARA REGISTRO MANUAL
    ajuste_manual = models.BooleanField(default=False, verbose_name='Ajuste Manual')
    registro_manual_referencia = models.ForeignKey(
        RegistroManual,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Referência do Registro Manual'
    )

    justificativa_ajuste = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Justificativa do Ajuste',
        help_text='Justificativa para o ajuste manual do registro'
    )

    observacoes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observações',
        help_text='Observações adicionais sobre o registro'
    )

    ajustado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registros_ajustados',
        verbose_name='Ajustado por'
    )

    # ⚠️ CORRIGIDO: este campo estava (por engano) só em RegistroManual.
    # É usado pelos 4 endpoints de comprovante em api/views_comprovantes.py
    # (get_object_or_404(RegistroPonto, codigo_validacao=codigo)) — sem ele
    # aqui, esses endpoints quebravam com FieldError.
    codigo_validacao = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name='Código de validação do comprovante',
        help_text='Usado nas URLs públicas de comprovante/QR Code em vez do ID sequencial.'
    )

    # ---- Campos exigidos pelo AFD (registro tipo "7", Portaria 671/2021) ----
    # NSR nunca é reaproveitado, mesmo que o registro seja corrigido depois —
    # por isso vem de uma sequência global (afd.models.SequenciaNSR), não de
    # um contador local. hash_registro é a cadeia SHA-256 (cada marcação
    # inclui o hash da anterior), o que torna impossível inserir ou remover
    # uma marcação no meio do histórico sem quebrar a cadeia.
    #
    # Ajustes manuais (ajuste_manual=True) NÃO entram nessa cadeia — eles não
    # foram capturados por um coletor de verdade, então não fazem sentido
    # como registro tipo "7" do AFD. Ficam de fora de propósito; o lugar
    # certo pra eles aparecer nos relatórios fiscais é o Espelho de Ponto
    # (ainda não implementado).
    nsr = models.PositiveBigIntegerField(unique=True, editable=False, null=True, blank=True)
    hash_registro = models.CharField(max_length=64, editable=False, blank=True)
    identificador_coletor = models.CharField(
        max_length=2, choices=IDENTIFICADOR_COLETOR_CHOICES, default='02'
    )
    offline = models.BooleanField(
        default=False,
        verbose_name='Marcação offline',
        help_text='Marcação feita sem conexão no momento e sincronizada depois.'
    )

    class Meta:
        verbose_name = "Registro de Ponto"
        verbose_name_plural = "Registros de Ponto"
        unique_together = ['profissional', 'estabelecimento', 'data', 'tipo']
        ordering = ['-data', '-horario']
        indexes = [
            models.Index(fields=['profissional', 'data']),
            models.Index(fields=['ajuste_manual']),
            models.Index(fields=['data', 'tipo']),
        ]

    def __str__(self):
        return f"{self.profissional.get_full_name()} - {self.data} {self.tipo}"

    def clean(self):
        """Validação para garantir apenas uma entrada e uma saída por dia"""
        if not self.ajuste_manual:
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
        """Sobrescreve o save para validar, calcular tolerância e (se for
        marcação de verdade, não ajuste manual) atribuir NSR + hash do AFD"""
        eh_novo = self.pk is None

        # Valida antes de salvar
        self.clean()

        # ✅ CONVERTE PARA HORÁRIO DE BRASÍLIA ANTES DE SALVAR
        if not self.pk:  # Apenas para novos registros
            self._converter_para_brasilia()

        # Calcula atraso/saída antecipada antes de salvar
        self._calcular_tolerancia()

        # Se for ajuste manual, marca campos específicos
        if self.ajuste_manual and not self.ajustado_por:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            # ⚠️ NOTA: connection.user não existe no Django — este bloco nunca
            # de fato atribui ajustado_por (é um no-op silencioso). Se
            # precisar disso, passe ajustado_por explicitamente na view que
            # cria o registro (ex: RegistroPonto.objects.create(..., ajustado_por=request.user)).
            from django.db import connection
            if hasattr(connection, 'user') and connection.user:
                self.ajustado_por = connection.user

        # ---- AFD: atribui NSR + hash encadeado só para marcações reais ----
        if eh_novo and not self.ajuste_manual and not self.nsr:
            from afd.models import SequenciaNSR  # import local: evita import circular com afd
            self.nsr = SequenciaNSR.proximo()

            data_hora_marcacao = datetime.combine(self.data, self.horario)
            data_hora_gravacao = timezone.now()

            hash_anterior = (
                RegistroPonto.objects
                .exclude(hash_registro='')
                .order_by('-nsr')
                .values_list('hash_registro', flat=True)
                .first()
            ) or ''

            base = (
                f"{self.nsr}"
                f"7"
                f"{data_hora_marcacao.strftime('%Y-%m-%dT%H:%M:00')}"
                f"{self.profissional.cpf}"
                f"{data_hora_gravacao.strftime('%Y-%m-%dT%H:%M:00')}"
                f"{self.identificador_coletor}"
                f"{'1' if self.offline else '0'}"
                f"{hash_anterior}"
            )
            self.hash_registro = hashlib.sha256(base.encode('utf-8')).hexdigest()

        super().save(*args, **kwargs)

    def _converter_para_brasilia(self):
        """Converte o horário para o fuso horário de Brasília"""
        try:
            tz_brasilia = pytz.timezone('America/Sao_Paulo')
            agora_brasilia = timezone.now().astimezone(tz_brasilia)

            if not self.ajuste_manual:
                self.data = agora_brasilia.date()
                self.horario = agora_brasilia.time()

            if self.ajuste_manual:
                self.latitude = 0
                self.longitude = 0

        except Exception as e:
            print(f"Erro na conversão de timezone: {e}")

    def _calcular_tolerancia(self):
        """Calcula atraso e saída antecipada baseado no horário esperado"""
        try:
            horario_entrada_esperado = self.profissional.horario_entrada
            horario_saida_esperado = self.profissional.horario_saida
            tolerancia_minutos = self.profissional.tolerancia_minutos or 0

            if not horario_entrada_esperado or not horario_saida_esperado:
                self.dentro_tolerancia = True
                self.atraso_minutos = 0
                self.saida_antecipada_minutos = 0
                return

            if self.tipo == 'ENTRADA':
                horario_registro = datetime.combine(self.data, self.horario)
                horario_limite = datetime.combine(self.data, horario_entrada_esperado)
                horario_com_tolerancia = horario_limite + timedelta(minutes=tolerancia_minutos)

                if horario_registro > horario_com_tolerancia:
                    diferenca = horario_registro - horario_com_tolerancia
                    self.atraso_minutos = int(diferenca.total_seconds() / 60)
                    self.dentro_tolerancia = False
                else:
                    self.atraso_minutos = 0
                    self.dentro_tolerancia = True

                self.saida_antecipada_minutos = 0

            elif self.tipo == 'SAIDA':
                horario_registro = datetime.combine(self.data, self.horario)
                horario_limite = datetime.combine(self.data, horario_saida_esperado)
                horario_com_tolerancia = horario_limite - timedelta(minutes=tolerancia_minutos)

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
            self.atraso_minutos = 0
            self.saida_antecipada_minutos = 0
            self.dentro_tolerancia = True

    @property
    def horario_brasilia(self):
        return self.horario.strftime('%H:%M')

    @property
    def status_tolerancia(self):
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
        if self.dentro_tolerancia:
            return "success"
        else:
            return "warning"

    @property
    def proximo_tipo(self):
        if self.tipo == 'ENTRADA':
            return 'SAIDA'
        return 'ENTRADA'

    @property
    def e_ajuste_manual(self):
        return self.ajuste_manual or self.registro_manual_referencia is not None

    @property
    def justificativa_completa(self):
        if self.justificativa_ajuste:
            return self.justificativa_ajuste
        elif self.registro_manual_referencia:
            return self.registro_manual_referencia.justificativa_formatada
        return "Não informada"

    @property
    def pode_ser_editado(self):
        if not self.e_ajuste_manual:
            return False
        limite_edicao = self.created_at + timedelta(hours=24)
        return timezone.now() <= limite_edicao

    @property
    def info_ajuste(self):
        if self.ajuste_manual:
            if self.ajustado_por:
                return f"Ajustado por: {self.ajustado_por.get_full_name() or self.ajustado_por.username}"
            return "Ajuste manual"
        return "Registro normal"


def criar_registro_manual_saida(profissional, data, horario, justificativa, observacoes, usuario_admin):
    """
    Função para criar registro manual de saída
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        entrada_existente = RegistroPonto.objects.filter(
            profissional=profissional,
            data=data,
            tipo='ENTRADA'
        ).first()

        if not entrada_existente:
            raise ValueError("Não existe entrada registrada para este dia.")

        saida_existente = RegistroPonto.objects.filter(
            profissional=profissional,
            data=data,
            tipo='SAIDA'
        ).exists()

        if saida_existente:
            raise ValueError("Já existe uma saída registrada para este dia.")

        registro_manual = RegistroManual.objects.create(
            profissional=profissional,
            data=data,
            horario=horario,
            tipo='SAIDA',
            motivo=justificativa[:50],
            descricao=observacoes or f"Justificativa: {justificativa}",
            ajustado_por=usuario_admin,
            latitude=0,
            longitude=0,
            confirmado=True,
            confirmado_por=usuario_admin,
            confirmado_em=timezone.now()
        )

        saida_antecipada_minutos = 0
        dentro_tolerancia = True

        if profissional.horario_saida:
            horario_saida_dt = datetime.combine(data, horario)
            horario_previsto_dt = datetime.combine(data, profissional.horario_saida)

            if horario_saida_dt < horario_previsto_dt:
                diferenca = horario_previsto_dt - horario_saida_dt
                saida_antecipada_minutos = int(diferenca.total_seconds() / 60)
                dentro_tolerancia = saida_antecipada_minutos <= (profissional.tolerancia_minutos or 10)

        registro_ponto = RegistroPonto.objects.create(
            profissional=profissional,
            estabelecimento=entrada_existente.estabelecimento,
            data=data,
            horario=horario,
            tipo='SAIDA',
            latitude=0,
            longitude=0,
            atraso_minutos=0,
            saida_antecipada_minutos=saida_antecipada_minutos,
            dentro_tolerancia=dentro_tolerancia,
            ajuste_manual=True,
            registro_manual_referencia=registro_manual,
            justificativa_ajuste=justificativa,
            observacoes=observacoes,
            ajustado_por=usuario_admin
        )

        return {
            'sucesso': True,
            'registro': registro_ponto,
            'registro_manual': registro_manual,
            'mensagem': f"Saída registrada manualmente para {data.strftime('%d/%m/%Y')} às {horario.strftime('%H:%M')}"
        }

    except Exception as e:
        return {
            'sucesso': False,
            'erro': str(e)
        }