# afd/views.py
from datetime import datetime

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render

from .gerador import gerar_afd


@staff_member_required
def download_afd(request):
    """
    Tela simples pra escolher o período e baixar o AFD (.txt).
    Restrita a staff — é um arquivo fiscal, não deve ficar público.
    """
    if request.method == 'POST' or request.GET.get('data_inicio'):
        data_inicio = datetime.strptime(request.GET['data_inicio'], '%Y-%m-%d').date()
        data_fim = datetime.strptime(request.GET['data_fim'], '%Y-%m-%d').date()

        nome_arquivo, conteudo = gerar_afd(data_inicio, data_fim)

        response = HttpResponse(
            conteudo.encode('iso-8859-1', errors='replace'),
            content_type='text/plain; charset=iso-8859-1'
        )
        response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
        return response

    return render(request, 'afd/download_afd.html')
