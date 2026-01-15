# usuarios/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Usuario, Profissional, AreaAtuacao
from estabelecimentos.models import Estabelecimento
from datetime import timedelta, datetime, time  
import pytz

class SignUpForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ['username', 'password1', 'password2']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Nome de usuário'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Senha'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control', 
            'placeholder': 'Confirmação de senha'
        })

class ProfissionalForm(forms.ModelForm):
    # ✅ CAMPOS DE CARGA HORÁRIA
    CARGA_HORARIA_DIARIA_CHOICES = [
        ('', 'Selecione a carga horária diária'),
        ('06:00:00', '6 horas/dia'),
        ('07:00:00', '7 horas/dia'), 
        ('08:00:00', '8 horas/dia'),
        ('09:00:00', '9 horas/dia'),
        ('10:00:00', '10 horas/dia'),
        ('12:00:00', '12 horas/dia'),
    ]
    
    CARGA_HORARIA_SEMANAL_CHOICES = [
        ('', 'Selecione a carga horária semanal'),
        ('30:00:00', '30 horas/semana'),
        ('35:00:00', '35 horas/semana'),
        ('36:00:00', '36 horas/semana'),
        ('40:00:00', '40 horas/semana'),
        ('44:00:00', '44 horas/semana'),
        ('45:00:00', '45 horas/semana'),
        ('50:00:00', '50 horas/semana'),
        ('60:00:00', '60 horas/semana'),
    ]
    
    carga_horaria_diaria = forms.ChoiceField(
        choices=CARGA_HORARIA_DIARIA_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    carga_horaria_semanal = forms.ChoiceField(
        choices=CARGA_HORARIA_SEMANAL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # ✅ NOVOS CAMPOS PARA HORÁRIOS E TOLERÂNCIA
    horario_entrada = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={
            'class': 'form-control',
            'type': 'time',
            'placeholder': 'HH:MM'
        }),
        help_text="Horário de entrada esperado"
    )
    
    horario_saida = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={
            'class': 'form-control',
            'type': 'time', 
            'placeholder': 'HH:MM'
        }),
        help_text="Horário de saída esperado"
    )
    
    TOLERANCIA_CHOICES = [
        (0, 'Sem tolerância'),
        (5, '5 minutos'),
        (10, '10 minutos'),
        (15, '15 minutos'),
        (20, '20 minutos'),
        (30, '30 minutos'),
    ]
    
    tolerancia_minutos = forms.ChoiceField(
        choices=TOLERANCIA_CHOICES,
        initial=10,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Tolerância para atrasos e saídas antecipadas"
    )

    class Meta:
        model = Profissional
        fields = [
            'nome', 'sobrenome', 'email', 'telefone', 'cpf', 
            'profissao', 'estabelecimento', 'carga_horaria_diaria',
            'carga_horaria_semanal', 'horario_entrada', 'horario_saida',
            'tolerancia_minutos', 'termo_uso'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Nome completo'
            }),
            'sobrenome': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Sobrenome'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control', 
                'placeholder': 'E-mail'
            }),
            'telefone': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '(00) 00000-0000'
            }),
            'cpf': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '000.000.000-00'
            }),
            'profissao': forms.Select(attrs={
                'class': 'form-control'
            }),
            'estabelecimento': forms.Select(attrs={
                'class': 'form-control'
            }),
            'termo_uso': forms.CheckboxInput(attrs={
                'class': 'form-check-input', 
                'required': 'required'
            }),
        }
        help_texts = {
            'horario_entrada': 'Horário padrão de entrada',
            'horario_saida': 'Horário padrão de saída',
            'tolerancia_minutos': 'Tolerância permitida para atrasos/saídas antecipadas',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # ✅ CORREÇÃO: Definir valores iniciais para campos existentes
        if self.instance and self.instance.pk:
            # Para carga horária diária
            if self.instance.carga_horaria_diaria:
                total_seconds = int(self.instance.carga_horaria_diaria.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                self.initial['carga_horaria_diaria'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            # Para carga horária semanal
            if self.instance.carga_horaria_semanal:
                total_seconds = int(self.instance.carga_horaria_semanal.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                self.initial['carga_horaria_semanal'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            # ✅ NOVO: Definir valores iniciais para horários e tolerância
            if self.instance.horario_entrada:
                self.initial['horario_entrada'] = self.instance.horario_entrada.strftime('%H:%M')
            
            if self.instance.horario_saida:
                self.initial['horario_saida'] = self.instance.horario_saida.strftime('%H:%M')
            
            if self.instance.tolerancia_minutos:
                self.initial['tolerancia_minutos'] = str(self.instance.tolerancia_minutos)
    
    def clean(self):
        cleaned_data = super().clean()
        
        # ✅ VALIDAÇÃO: Verificar se horário de saída é depois do horário de entrada
        horario_entrada = cleaned_data.get('horario_entrada')
        horario_saida = cleaned_data.get('horario_saida')
        
        if horario_entrada and horario_saida:
            if horario_saida <= horario_entrada:
                raise forms.ValidationError({
                    'horario_saida': 'O horário de saída deve ser após o horário de entrada.'
                })
        
        # ✅ VALIDAÇÃO: Verificar consistência entre carga horária e horários
        carga_diaria_str = cleaned_data.get('carga_horaria_diaria')
        if carga_diaria_str and horario_entrada and horario_saida:
            try:
                # Calcular diferença entre horários
                entrada_dt = datetime.combine(datetime.min, horario_entrada)
                saida_dt = datetime.combine(datetime.min, horario_saida)
                
                # Se saída for antes da entrada, assumir que é no dia seguinte
                if saida_dt < entrada_dt:
                    saida_dt += timedelta(days=1)
                
                diferenca_horas = (saida_dt - entrada_dt).total_seconds() / 3600
                
                # Converter carga horária selecionada para horas
                horas_carga, minutos_carga, _ = map(int, carga_diaria_str.split(':'))
                carga_horas = horas_carga + (minutos_carga / 60)
                
                # Verificar se há grande discrepância
                if abs(diferenca_horas - carga_horas) > 2:  # 2 horas de tolerância
                    self.add_warning(
                        'carga_horaria_diaria',
                        f'Atenção: A carga horária selecionada ({carga_horas}h) é diferente '
                        f'do período entre entrada e saída ({diferenca_horas:.1f}h).'
                    )
                    
            except (ValueError, AttributeError):
                pass  # Ignora erros de conversão
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # ✅ CORREÇÃO: Converter strings para timedelta antes de salvar
        carga_diaria_str = self.cleaned_data.get('carga_horaria_diaria')
        if carga_diaria_str and carga_diaria_str != '':
            try:
                hours, minutes, seconds = map(int, carga_diaria_str.split(':'))
                instance.carga_horaria_diaria = timedelta(hours=hours, minutes=minutes, seconds=seconds)
            except (ValueError, AttributeError):
                instance.carga_horaria_diaria = None
        else:
            instance.carga_horaria_diaria = None
        
        # Converter carga horária semanal
        carga_semanal_str = self.cleaned_data.get('carga_horaria_semanal')
        if carga_semanal_str and carga_semanal_str != '':
            try:
                hours, minutes, seconds = map(int, carga_semanal_str.split(':'))
                instance.carga_horaria_semanal = timedelta(hours=hours, minutes=minutes, seconds=seconds)
            except (ValueError, AttributeError):
                instance.carga_horaria_semanal = None
        else:
            instance.carga_horaria_semanal = None
        
        # ✅ NOVO: Converter tolerância para inteiro
        tolerancia_str = self.cleaned_data.get('tolerancia_minutos')
        if tolerancia_str and tolerancia_str != '':
            try:
                instance.tolerancia_minutos = int(tolerancia_str)
            except (ValueError, TypeError):
                instance.tolerancia_minutos = 10  # Valor padrão
        else:
            instance.tolerancia_minutos = 10  # Valor padrão
        
        # ✅ Os campos horario_entrada e horario_saida já são TimeField no modelo
        # e serão salvos automaticamente
        
        if commit:
            instance.save()
        return instance

class AreaAtuacaoForm(forms.ModelForm):
    class Meta:
        model = AreaAtuacao
        fields = ['profissao']
        widgets = {
            'profissao': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome da profissão'
            })
        }
    
    def clean_profissao(self):
        profissao = self.cleaned_data.get('profissao')
        if profissao:
            # Normalizar: primeira letra maiúscula, resto minúscula
            profissao = profissao.strip().title()
        return clean_profissao  