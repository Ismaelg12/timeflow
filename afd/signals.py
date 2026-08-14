# afd/signals.py
"""
Gera automaticamente os registros tipo "5" do AFD (inclusão/alteração/
exclusão de funcionário) toda vez que um Profissional é salvo ou removido —
sem precisar alterar nenhuma view do app `usuarios`.

Registrado em afd/apps.py -> AfdConfig.ready().
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from usuarios.models import Profissional
from .models import EventoFuncionarioAFD


def _cpf_digitos(cpf):
    return ''.join(filter(str.isdigit, cpf or ''))


@receiver(post_save, sender=Profissional)
def registrar_evento_funcionario(sender, instance, created, **kwargs):
    tipo_operacao = 'I' if created else 'A'
    EventoFuncionarioAFD.objects.create(
        tipo_operacao=tipo_operacao,
        profissional=instance,
        cpf_funcionario=_cpf_digitos(instance.cpf),
        nome_funcionario=instance.nome[:52],
    )


@receiver(post_delete, sender=Profissional)
def registrar_evento_funcionario_excluido(sender, instance, **kwargs):
    EventoFuncionarioAFD.objects.create(
        tipo_operacao='E',
        profissional=None,  # o profissional já não existe mais
        cpf_funcionario=_cpf_digitos(instance.cpf),
        nome_funcionario=instance.nome[:52],
    )
