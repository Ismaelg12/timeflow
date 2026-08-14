# afd/management/commands/backfill_eventos_funcionario.py
"""
Cria retroativamente o registro tipo "5" (inclusão) do AFD pra cada
Profissional que já existia no banco ANTES do app afd/signals.py entrar em
funcionamento. Sem isso, gente cadastrada antes de hoje nunca aparece no
AFD até editar o cadastro de novo.

Uso:
    python manage.py backfill_eventos_funcionario
    python manage.py backfill_eventos_funcionario --somente-ativos
    python manage.py backfill_eventos_funcionario --dry-run
"""
from django.core.management.base import BaseCommand

from usuarios.models import Profissional
from afd.models import EventoFuncionarioAFD


def _cpf_digitos(cpf):
    return ''.join(filter(str.isdigit, cpf or ''))


class Command(BaseCommand):
    help = 'Cria eventos tipo 5 (inclusão) retroativos pros profissionais já cadastrados.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--somente-ativos',
            action='store_true',
            help='Gera evento só pra profissionais com ativo=True (padrão: todos).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria criado, sem gravar nada no banco.',
        )

    def handle(self, *args, **options):
        profissionais = Profissional.objects.all()
        if options['somente_ativos']:
            profissionais = profissionais.filter(ativo=True)

        # Não duplica quem já tem algum evento tipo 5 (ex: quem foi editado
        # depois que o signal já estava ativo, e por isso já gerou o próprio
        # registro de inclusão/alteração sozinho).
        ja_tem_evento = set(
            EventoFuncionarioAFD.objects
            .exclude(profissional=None)
            .values_list('profissional_id', flat=True)
        )

        pendentes = [p for p in profissionais if p.id not in ja_tem_evento]

        self.stdout.write(f'{len(pendentes)} profissional(is) sem evento tipo 5 no AFD.')

        if options['dry_run']:
            for p in pendentes:
                self.stdout.write(f'  [dry-run] criaria evento para: {p.nome} (CPF {p.cpf})')
            self.stdout.write(self.style.WARNING('Nenhuma gravação feita (--dry-run).'))
            return

        criados = 0
        for p in pendentes:
            EventoFuncionarioAFD.objects.create(
                tipo_operacao='I',
                profissional=p,
                cpf_funcionario=_cpf_digitos(p.cpf),
                nome_funcionario=p.nome[:52],
            )
            criados += 1

        self.stdout.write(self.style.SUCCESS(f'{criados} evento(s) tipo 5 criado(s) com sucesso.'))
