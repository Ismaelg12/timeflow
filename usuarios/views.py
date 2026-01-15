# -*- coding: utf-8 -*-
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import PasswordChangeForm
from usuarios.models import Profissional, AreaAtuacao
from django.contrib import messages
from usuarios.forms import ProfissionalForm, SignUpForm, AreaAtuacaoForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.db import IntegrityError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth import authenticate, login



'''
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
+                           Views de Usuarios
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
'''

def custom_login(request):
    """
    View personalizada de login com verificação de profissional ativo
    """
    # Se o usuário já está autenticado, redireciona
    if request.user.is_authenticated:
        next_url = request.GET.get('next', 'core:dashboard')
        return redirect(next_url)
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Verifica se é um profissional (tem perfil Profissional)
            try:
                profissional = Profissional.objects.get(usuario=user)
                if not profissional.ativo:
                    messages.error(request, "Seu cadastro está aguardando aprovação. Entre em contato com o administrador.")
                    return render(request, 'login/login.html')
            except Profissional.DoesNotExist:
                # Se não tem perfil profissional, pode ser superuser - permite login
                if not user.is_superuser and not user.is_staff:
                    messages.error(request, "Perfil de profissional não encontrado.")
                    return render(request, 'login/login.html')
            
            # Se passou nas verificações, faz login
            login(request, user)
            
            # ✅ CORREÇÃO CRÍTICA: Use o nome correto da URL que existe
            next_url = request.POST.get('next') or request.GET.get('next')
            
            if next_url:
                return redirect(next_url)
            
            # ✅ REDIRECIONAMENTO INTELIGENTE: Use 'core:relatorio_profissional' (sem 's')
            if user.is_superuser or user.is_staff:
                return redirect('core:dashboard')
            else:
                try:
                    profissional = Profissional.objects.get(usuario=user)
                    # ✅ CORREÇÃO: Use 'relatorio_profissional' (singular)
                    return redirect('core:relatorio_profissional', profissional_id=profissional.id)
                except Profissional.DoesNotExist:
                    return redirect('core:dashboard')
        else:
            messages.error(request, "Usuário ou senha inválidos.")
    
    # GET request - mostra o formulário de login
    context = {}
    if 'next' in request.GET:
        context['next'] = request.GET['next']
    
    return render(request, 'login/login.html', context)

def redirect_user_by_type(user):
    """
    Função auxiliar para redirecionar usuários baseado no tipo
    """
    if user.is_superuser or user.is_staff:
        # Admin vai para o dashboard administrativo
        return redirect('core:dashboard')
    else:
        # Usuário comum (profissional) vai para sua página de relatórios
        try:
            profissional = Profissional.objects.get(usuario=user)
            return redirect('core:relatorios_profissional', pk=profissional.id)
        except Profissional.DoesNotExist:
            # Fallback se não encontrar o profissional
            return redirect('core:dashboard')


'''
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
+                           Crud de Profissional/Usuarios
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
'''

@staff_member_required
@login_required
def profissionais(request):
    """Lista de profissionais ativos com paginação"""
    lista_profissionais = Profissional.objects.filter(ativo=True).exclude(usuario__username='admin').order_by('nome', 'sobrenome')
    
    # Paginação
    page = request.GET.get('page', 1)
    paginator = Paginator(lista_profissionais, 15)
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    context = {
        'page_obj': page_obj,  # ✅ APENAS A VARIÁVEL NECESSÁRIA
        'titulo': 'Profissionais Cadastrados'
    }
    return render(request, 'profissionais/profissionais.html', context)

@staff_member_required
@login_required 
def profissionais_inativos(request):
    """Lista de profissionais inativos com paginação"""
    lista_profissionais = Profissional.objects.filter(ativo=False).order_by('nome', 'sobrenome')
    
    # Paginação
    page = request.GET.get('page', 1)
    paginator = Paginator(lista_profissionais, 15)
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    context = {
        'page_obj': page_obj,  # ✅ APENAS A VARIÁVEL NECESSÁRIA
        'titulo': 'Profissionais Inativos'
    }
    return render(request, 'profissionais/profissionais.html', context)


def add_profissional(request):
    if request.method == 'POST':
        user_form = SignUpForm(request.POST)
        profissional_form = ProfissionalForm(request.POST)
        
        if user_form.is_valid() and profissional_form.is_valid():
            try:
                # Cria o usuário (desativa signal temporariamente)
                user = user_form.save(commit=False)
                user._disable_signal = True
                user.save()
                
                # Cria o profissional como INATIVO (aguardando aprovação)
                profissional = profissional_form.save(commit=False)
                profissional.usuario = user
                profissional.ativo = False
                
                # Verifica e salva os dados do termo de uso
                if profissional_form.cleaned_data.get('termo_uso', False):
                    profissional.termo_uso = True
                    profissional.termo_uso_versao = "1.0"
                    profissional.termo_uso_data = timezone.now()  # ✅ AGORA É USADO
                    profissional.termo_uso_ip = request.META.get('REMOTE_ADDR', '')
                
                profissional.save()
                
                # Mostra a página de confirmação
                nome_completo = f"{profissional.nome} {profissional.sobrenome}"
                return render(request, 'login/cadastro_aguardando_aprovacao.html', {
                    'nome_profissional': nome_completo
                })
                
            except IntegrityError as e:
                # Rollback manual do usuário se houver erro
                if 'user' in locals() and user.pk:
                    user.delete()
                
                # Tratamento específico de erros
                if 'usuario_id_key' in str(e):
                    messages.error(request, "Erro: Já existe um cadastro para este usuário")
                elif 'cpf_key' in str(e):
                    messages.error(request, "Erro: CPF já está cadastrado")
                else:
                    messages.error(request, f"Erro inesperado: {str(e)}")
    
    else:
        user_form = SignUpForm()
        profissional_form = ProfissionalForm()

    return render(request, 'profissionais/add_profissional.html', {
        'user_form': user_form,
        'profissional_form': profissional_form
    })

@login_required
def profissional_detalhe(request, pk):
    # ✅ USANDO get_object_or_404 (agora é usado)
    profissional = get_object_or_404(Profissional, pk=pk)
    context = {
        'prof': profissional,
    }
    return render(request, 'profissionais/profissional_detalhe.html', context)


@login_required
def update_profissional(request, pk):
    # Verifica se o usuário logado tem um Profissional associado
    if not hasattr(request.user, 'profissional'):
        messages.error(request, "Seu perfil não está completo. Por favor, entre em contato com o administrador.")
        return redirect('core:dashboard')

    # ✅ USANDO get_object_or_404 (agora é usado)
    profissional = get_object_or_404(Profissional, pk=pk)

    # Verifica se o usuário autenticado é o proprietário do perfil ou um superusuário
    if not request.user.is_superuser and profissional.usuario != request.user:
        messages.error(request, "Você não tem permissão para editar este perfil.")
        return redirect('core:dashboard')

    profissional_form = ProfissionalForm(request.POST or None, instance=profissional)

    if profissional_form.is_valid():
        profissional_form.save()
        messages.success(request, 'Dados atualizados com sucesso!')
        return redirect('core:dashboard')

    return render(request, 'profissionais/add_profissional.html', {
        'profissional_form': profissional_form,
        'profissional': profissional,
    })


@staff_member_required
@login_required 
def desativar_profissional(request, pk):
    """Desativa um profissional em vez de excluir"""
    # ✅ USANDO get_object_or_404 (agora é usado)
    profissional = get_object_or_404(Profissional, pk=pk)
    profissional.ativo = False
    profissional.save()
    
    messages.success(request, 'Profissional desativado com sucesso!')
    return redirect('profissionais')


@staff_member_required
@login_required 
def ativar_profissional(request, pk):
    """Reativa um profissional desativado"""
    # ✅ USANDO get_object_or_404 (agora é usado)
    profissional = get_object_or_404(Profissional, pk=pk)
    profissional.ativo = True
    profissional.save()
    
    messages.success(request, 'Profissional ativado com sucesso!')
    return redirect('profissionais_inativos')




'''
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
+                         Reset de senha de Profissional/Usuarios Logados
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
'''

def change_password_user(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Sua Senha foi Atualizada com Sucesso!')
            return redirect('change_password')
        else:
            messages.error(request, 'Por Favor Verifique o Erro!.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'login/change_password.html', {
        'form': form
    })


'''
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
+                         Gestão de Profissões
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
'''

@staff_member_required
@login_required
def areatuacao(request):
    # ✅ REMOVIDA verificação redundante (já tem @staff_member_required)
    atuacao = AreaAtuacao.objects.all()    
    return render(request, 'areaatuacao/atuacoes.html', {'atuacao': atuacao})


@staff_member_required
@login_required
def adicionar_areatuacao(request):
    # ✅ REMOVIDA verificação redundante
    if request.method == 'POST':
        form = AreaAtuacaoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('atuacoes')
    else:
        form = AreaAtuacaoForm()
    return render(request, 'areaatuacao/add_atuacao.html', {
        'form': form,            
        'titulo_pagina': 'Adicionar Função',
        'botao_submit': 'Salvar',
    })


@staff_member_required
@login_required
def update_atuacao(request, atuacao_id):
    # ✅ USANDO get_object_or_404 (agora é usado)
    atuacao = get_object_or_404(AreaAtuacao, pk=atuacao_id)
    form = AreaAtuacaoForm(request.POST or None, instance=atuacao)
    
    if form.is_valid():
        form.save()
        messages.success(request, 'Função atualizada com sucesso!')
        return redirect('atuacoes')
    
    return render(request, 'areaatuacao/add_atuacao.html', {
        'form': form,
        'titulo_pagina': 'Editar Função',
        'botao_submit': 'Salvar atualização',
    })