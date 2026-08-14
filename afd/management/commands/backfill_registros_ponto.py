# afd/management/commands/backfill_registros_ponto.py
"""
Atribui nsr + hash_registro retroativamente aos RegistroPonto que já
existiam ANTES da migration do AFD (e por isso nunca passaram pelo save()
com a lógica de NSR/hash ativa — self._state.adding só é True na criação
original, não numa atualização posterior).

Processa em ordem de created_at (quando o registro realmente entrou no
banco) — não por data/horário da marcação — porque é essa a ordem que o
hash encadeado precisa respeitar: cada registro referencia o hash do que
foi gravado imediatamente antes dele no sistema.

Uso:
    python manage.py backfill_registros_ponto --dry-run
    python manage.py backfill_registros_ponto
"""
import hashlib

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone as tz

from ponto.models import RegistroPonto
from afd.models import SequenciaNSR


class Command(BaseCommand):
    help = 'Atribui nsr + hash_registro retroativos aos RegistroPonto anteriores à migration do AFD.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra quantos registros seriam processados, sem gravar nada.',
        )

    def handle(self, *args, **options):
        candidatos = (
            RegistroPonto.objects
            .filter(nsr__isnull=True, ajuste_manual=False)
            .order_by('created_at')
        )

        total = candidatos.count()
        self.stdout.write(f'{total} registro(s) de ponto sem nsr (excluindo ajustes manuais).')

        if total == 0:
            return

        if options['dry_run']:
            primeiro = candidatos.first()
            ultimo = candidatos.last()
            self.stdout.write(f'  [dry-run] processaria de {primeiro.created_at} até {ultimo.created_at}')
            self.stdout.write(self.style.WARNING('Nenhuma gravação feita (--dry-run).'))
            return

        processados = 0

        # Uma transação só: se algo der errado no meio, ninguém fica com
        # hash quebrado pela metade.
        with transaction.atomic():
            hash_anterior = (
                RegistroPonto.objects
                .exclude(hash_registro='')
                .order_by('-nsr')
                .values_list('hash_registro', flat=True)
                .first()
            ) or ''

            for registro in candidatos.iterator():
                nsr = SequenciaNSR.proximo()

                data_hora_marcacao = tz.datetime.combine(registro.data, registro.horario)
                data_hora_gravacao = registro.created_at  # gravação de verdade, não "agora"

                base = (
                    f"{nsr}"
                    f"7"
                    f"{data_hora_marcacao.strftime('%Y-%m-%dT%H:%M:00')}"
                    f"{registro.profissional.cpf}"
                    f"{data_hora_gravacao.strftime('%Y-%m-%dT%H:%M:00')}"
                    f"{registro.identificador_coletor}"
                    f"{'1' if registro.offline else '0'}"
                    f"{hash_anterior}"
                )
                hash_novo = hashlib.sha256(base.encode('utf-8')).hexdigest()

                registro.nsr = nsr
                registro.hash_registro = hash_novo
                registro.save(update_fields=['nsr', 'hash_registro'])

                hash_anterior = hash_novo
                processados += 1

                if processados % 100 == 0:
                    self.stdout.write(f'  ... {processados}/{total}')

        self.stdout.write(self.style.SUCCESS(f'{processados} registro(s) de ponto atualizado(s) com sucesso.'))
