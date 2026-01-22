# -*- coding: utf-8 -*-
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from usuarios.models import Profissional
from usuarios.forms import ProfissionalForm, ProfissionalEdicaoForm
from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth.views import LoginView


'''
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
+                           CADASTRO PÚBLICO (SEM USER, SEM LOGIN)
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
'''

# usuarios/views.py - Adicione no início do arquivo
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect

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
                # Salva como INATIVO (aguarda aprovação)
                profissional = form.save(commit=False)
                profissional.ativo = False
                profissional.save()
                
                # ✅ REDIRECIONA PARA PÁGINA DE CONFIRMAÇÃO COM ID
                return redirect('usuarios:cadastro_sucesso', id=profissional.id)
                
            except IntegrityError:
                messages.error(request, "CPF já cadastrado.")
    else:
        form = ProfissionalForm()
    
    return render(request, 'profissionais/add.html', {'form': form})

# ✅ ADICIONE ESTA NOVA VIEW
@staff_member_required
@login_required
def cadastro_sucesso(request, id):
    """
    Página de confirmação após cadastro
    """
    profissional = get_object_or_404(Profissional, id=id)
    
    context = {
        'profissional': profissional,
        'nome_profissional': f"{profissional.nome} {profissional.sobrenome}",
        'cpf': profissional.cpf,
        'profissao': profissional.profissao.profissao if profissional.profissao else '',
        'estabelecimento': profissional.estabelecimento.nome if profissional.estabelecimento else '',
    }
    
    return render(request, 'login/cadastro_sucesso.html', context)


'''
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
+                           GERENCIAMENTO (APENAS ADMIN)
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
'''

@staff_member_required
@login_required
def listar_profissionais(request):
    """
    Lista SIMPLES de profissionais
    """
    # Filtro básico
    status = request.GET.get('status', 'ativos')  # ativos, inativos
    busca = request.GET.get('busca', '')
    
    # Query base
    profissionais = Profissional.objects.all()
    
    # Status
    if status == 'ativos':
        profissionais = profissionais.filter(ativo=True)
    elif status == 'inativos':
        profissionais = profissionais.filter(ativo=False)
    
    # Busca
    if busca:
        profissionais = profissionais.filter(
            Q(nome__icontains=busca) |
            Q(sobrenome__icontains=busca) |
            Q(cpf__icontains=busca)
        )
    
    profissionais = profissionais.order_by('-ativo', 'nome', 'sobrenome')
    
    # Paginação
    paginator = Paginator(profissionais, 20)
    page = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)
    
    # ✅ ADICIONAR ESTES CONTADORES:
    total_ativos = Profissional.objects.filter(ativo=True).count()
    total_inativos = Profissional.objects.filter(ativo=False).count()
    
    return render(request, 'profissionais/listar.html', {
        'page_obj': page_obj,
        'status': status,
        'busca': busca,
        'total_ativos': total_ativos,      # ✅ ADICIONADO
        'total_inativos': total_inativos   # ✅ ADICIONADO
    })

@staff_member_required
@login_required
def detalhar_profissional(request, id):
    """
    Mostra detalhes de um profissional
    """
    profissional = get_object_or_404(Profissional, id=id)
    
    # Busca registros de ponto se existir o app 'ponto'
    registros = []
    try:
        from ponto.models import RegistroPonto
        registros = RegistroPonto.objects.filter(
            profissional=profissional
        ).order_by('-data', '-horario')[:10]
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
        # ✅ USA O FORMULÁRIO DE EDIÇÃO (sem termo_uso)
        form = ProfissionalEdicaoForm(request.POST, instance=profissional)
        if form.is_valid():
            form.save()
            messages.success(request, f'Dados de {profissional.nome} atualizados com sucesso!')
            return redirect('usuarios:listar_profissionais')
    else:
        # ✅ USA O FORMULÁRIO DE EDIÇÃO (sem termo_uso)
        form = ProfissionalEdicaoForm(instance=profissional)
    
    return render(request, 'profissionais/edit.html', {
        'form': form,
        'profissional': profissional
    })