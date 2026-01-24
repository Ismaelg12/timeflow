# usuarios/views.py
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProfissionalForm, ProfissionalEdicaoForm
from .models import Profissional


def custom_login(request):
    """View de login que redireciona para o template correto"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    return LoginView.as_view(
        template_name='login/login.html',
        redirect_authenticated_user=True,
        next_page='dashboard'
    )(request)


@staff_member_required
@login_required
def solicitar_cadastro(request):
    """
    View ADMINISTRATIVA para cadastrar profissional
    """
    if request.method == 'POST':
        form = ProfissionalForm(request.POST)
        if form.is_valid():
            try:
                profissional = form.save(commit=False)
                profissional.ativo = False
                profissional.save()
                return redirect('usuarios:cadastro_sucesso', id=profissional.id)
            except IntegrityError:
                messages.error(request, "CPF já cadastrado.")
    else:
        form = ProfissionalForm()
    
    return render(request, 'profissionais/add.html', {'form': form})


@staff_member_required
@login_required
def cadastro_sucesso(request, id):
    """
    Página de confirmação após cadastro
    """
    profissional = get_object_or_404(Profissional, id=id)
    
    context = {
        'profissional': profissional,
        'nome_profissional': f"{profissional.nome}",
        'cpf': profissional.cpf,
        'profissao': profissional.profissao.profissao if profissional.profissao else '',
        'estabelecimento': profissional.estabelecimento.nome if profissional.estabelecimento else '',
    }
    
    return render(request, 'login/cadastro_sucesso.html', context)


@staff_member_required
@login_required
def listar_profissionais(request):
    """
    Lista SIMPLES de profissionais
    """
    status = request.GET.get('status', 'ativos')
    busca = request.GET.get('busca', '')
    
    profissionais = Profissional.objects.all()
    
    if status == 'ativos':
        profissionais = profissionais.filter(ativo=True)
    elif status == 'inativos':
        profissionais = profissionais.filter(ativo=False)
    
    if busca:
        profissionais = profissionais.filter(
            Q(nome__icontains=busca) |
            Q(cpf__icontains=busca)
        )
    
    profissionais = profissionais.order_by('-ativo', 'nome')
    
    paginator = Paginator(profissionais, 20)
    page = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)
    
    total_ativos = Profissional.objects.filter(ativo=True).count()
    total_inativos = Profissional.objects.filter(ativo=False).count()
    
    return render(request, 'profissionais/listar.html', {
        'page_obj': page_obj,
        'status': status,
        'busca': busca,
        'total_ativos': total_ativos,
        'total_inativos': total_inativos
    })


@staff_member_required
@login_required
def detalhar_profissional(request, id):
    """
    Mostra detalhes de um profissional
    """
    profissional = get_object_or_404(Profissional, id=id)
    
    registros = []
    try:
        from ponto.models import RegistroPonto
        registros = RegistroPonto.objects.filter(
            profissional=profissional
        ).order_by('-data', '-hororia')[:10]
    except:
        pass
    
    return render(request, 'profissionais/detalhar_profissional.html', {
        'profissional': profissional,
        'registros': registros
    })


@staff_member_required
@login_required
def aprovar_profissional(request, id):
    """
    Aprova um profissional (ativa)
    """
    profissional = get_object_or_404(Profissional, id=id, ativo=False)
    
    if request.method == 'POST':
        profissional.ativo = True
        profissional.save()
        messages.success(request, f'{profissional.nome} aprovado!')
        return redirect('usuarios:detalhar_profissional', id=profissional.id)
    
    return render(request, 'profissionais/confirmar_aprovacao.html', {
        'profissional': profissional
    })


@staff_member_required
@login_required
def desativar_profissional(request, id):
    """
    Desativa um profissional (não exclui)
    """
    profissional = get_object_or_404(Profissional, id=id, ativo=True)
    
    if request.method == 'POST':
        profissional.ativo = False
        profissional.save()
        messages.success(request, f'{profissional.nome} desativado.')
        return redirect('usuarios:listar_profissionais')
    
    return render(request, 'profissionais/confirmar_desativacao.html', {
        'profissional': profissional
    })


@staff_member_required
@login_required
def editar_profissional(request, id):
    """
    Edita dados de um profissional
    """
    profissional = get_object_or_404(Profissional, id=id)
    
    if request.method == 'POST':
        form = ProfissionalEdicaoForm(request.POST, instance=profissional)
        if form.is_valid():
            form.save()
            messages.success(request, f'Dados de {profissional.nome} atualizados com sucesso!')
            return redirect('usuarios:listar_profissionais')
    else:
        form = ProfissionalEdicaoForm(instance=profissional)
    
    return render(request, 'profissionais/edit.html', {
        'form': form,
        'profissional': profissional
    })