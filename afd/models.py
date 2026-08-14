# afd/models.py
"""
Modelos de apoio à geração do AFD (Arquivo Fonte de Dados), exigido pela
Portaria MTP 671/2021 para todo REP-P (Registrador Eletrônico de Ponto via
Programa) — que é a categoria em que o TimeFlow se enquadra.

NSR = Número Sequencial de Registro. É GLOBAL (compartilhado entre os tipos
2 a 7 do AFD) e NUNCA pode ser reaproveitado ou reordenado, mesmo que um
registro seja corrigido depois — por isso vive numa sequência própria
(SequenciaNSR), e não em cada tabela separadamente.
"""
from django.db import models, transaction


class SequenciaNSR(models.Model):
    """
    Linha única (singleton) que guarda o próximo NSR a ser emitido.
    Use SequenciaNSR.proximo() para obter o próximo valor de forma atômica
    (select_for_update evita dois registros simultâneos pegarem o mesmo NSR).
    """
    valor_atual = models.PositiveBigIntegerField(default=0)

    class Meta:
        verbose_name = "Sequência de NSR"
        verbose_name_plural = "Sequência de NSR"

    @classmethod
    def proximo(cls):
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(pk=1)
            seq.valor_atual += 1
            seq.save(update_fields=['valor_atual'])
            return seq.valor_atual


class EventoFuncionarioAFD(models.Model):
    """
    Registro tipo "5" do AFD — inclusão, alteração ou exclusão de um
    funcionário no REP. Criado automaticamente por um signal quando um
    Profissional é aprovado, editado ou desativado (ver afd/signals.py).
    """
    TIPO_OPERACAO = [
        ('I', 'Inclusão'),
        ('A', 'Alteração'),
        ('E', 'Exclusão'),
    ]

    nsr = models.PositiveBigIntegerField(unique=True, editable=False)
    data_hora = models.DateTimeField(auto_now_add=True)
    tipo_operacao = models.CharField(max_length=1, choices=TIPO_OPERACAO)
    profissional = models.ForeignKey(
        'usuarios.Profissional', on_delete=models.SET_NULL, null=True, blank=True
    )
    cpf_funcionario = models.CharField(max_length=11)
    nome_funcionario = models.CharField(max_length=52)
    cpf_responsavel = models.CharField(max_length=11, blank=True, default='')

    class Meta:
        verbose_name = "Evento de funcionário (AFD tipo 5)"
        verbose_name_plural = "Eventos de funcionário (AFD tipo 5)"
        ordering = ['nsr']

    def save(self, *args, **kwargs):
        if not self.nsr:
            self.nsr = SequenciaNSR.proximo()
        super().save(*args, **kwargs)


class EventoServicoAFD(models.Model):
    """
    Registro tipo "6" do AFD — eventos sensíveis do REP-P. Para REP-P só
    fazem sentido "02" (retorno de energia/serviço), "07" (disponibilidade)
    e "08" (indisponibilidade).

    ⚠️ Isso só registra o que for chamado explicitamente (ex: no início/fim
    de uma manutenção programada). Não existe hoje um monitor automático de
    uptime — se quiser 100% de cobertura, isso precisa de um serviço externo
    de monitoramento chamando EventoServicoAFD.objects.create(...).
    """
    TIPO_EVENTO = [
        ('02', 'Retorno de energia/serviço'),
        ('07', 'Disponibilidade de serviço'),
        ('08', 'Indisponibilidade de serviço'),
    ]

    nsr = models.PositiveBigIntegerField(unique=True, editable=False)
    data_hora = models.DateTimeField(auto_now_add=True)
    tipo_evento = models.CharField(max_length=2, choices=TIPO_EVENTO)

    class Meta:
        verbose_name = "Evento de serviço (AFD tipo 6)"
        verbose_name_plural = "Eventos de serviço (AFD tipo 6)"
        ordering = ['nsr']

    def save(self, *args, **kwargs):
        if not self.nsr:
            self.nsr = SequenciaNSR.proximo()
        super().save(*args, **kwargs)
