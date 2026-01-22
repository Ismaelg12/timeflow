# usuarios/forms.py
from django import forms
from .models import Profissional, AreaAtuacao
from estabelecimentos.models import Estabelecimento
from datetime import timedelta, datetime
import re

class ProfissionalForm(forms.ModelForm):
    # ✅ CAMPOS DO TEMPLATE QUE NÃO ESTÃO NO MODELO
    termo_uso = forms.BooleanField(
        required=True,
        label='Termos de Uso',
        error_messages={'required': 'Você deve aceitar os termos de uso.'},
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
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
        widget=forms.Select(attrs={'class': 'form-control form-select'})
    )
    
    carga_horaria_semanal = forms.ChoiceField(
        choices=CARGA_HORARIA_SEMANAL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control form-select'})
    )
    
    # ✅ CAMPOS PARA HORÁRIOS E TOLERÂNCIA
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
        ('', 'Selecione a tolerância'),
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
        widget=forms.Select(attrs={'class': 'form-control form-select'}),
        help_text="Tolerância para atrasos e saídas antecipadas"
    )

    class Meta:
        model = Profissional
        fields = [
            'nome', 'sobrenome', 'cpf', 'telefone',
            'profissao', 'estabelecimento', 'carga_horaria_diaria',
            'carga_horaria_semanal', 'horario_entrada', 'horario_saida',
            'tolerancia_minutos'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Nome completo',
                'id': 'id_nome'
            }),
            'sobrenome': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Nome social',
                'id': 'id_sobrenome'
            }),
            'cpf': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '000.000.000-00',
                'id': 'id_cpf'
            }),
            'telefone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(11) 99999-9999',
                'id': 'id_telefone'
            }),
            'profissao': forms.Select(attrs={
                'class': 'form-control form-select',
                'id': 'id_profissao'
            }),
            'estabelecimento': forms.Select(attrs={
                'class': 'form-control form-select',
                'id': 'id_estabelecimento'
            }),
        }
        help_texts = {
            'horario_entrada': 'Horário padrão de entrada',
            'horario_saida': 'Horário padrão de saída',
            'tolerancia_minutos': 'Tolerância permitida para atrasos/saídas antecipadas',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Tornar campos obrigatórios conforme template
        self.fields['telefone'].required = True
        
        # Melhorar os labels
        self.fields['nome'].label = 'Nome Completo'
        self.fields['sobrenome'].label = 'Nome Social'
        self.fields['cpf'].label = 'CPF'
        self.fields['telefone'].label = 'Telefone'
        self.fields['profissao'].label = 'Profissão'
        self.fields['estabelecimento'].label = 'Estabelecimento'
        self.fields['carga_horaria_diaria'].label = 'Carga Horária Diária'
        self.fields['carga_horaria_semanal'].label = 'Carga Horária Semanal'
        self.fields['horario_entrada'].label = 'Horário de Entrada'
        self.fields['horario_saida'].label = 'Horário de Saída'
        self.fields['tolerancia_minutos'].label = 'Tolerância (minutos)'
        
        # Definir valores iniciais para campos existentes
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
            
            # Definir valores iniciais para horários e tolerância
            if self.instance.horario_entrada:
                self.initial['horario_entrada'] = self.instance.horario_entrada.strftime('%H:%M')
            
            if self.instance.horario_saida:
                self.initial['horario_saida'] = self.instance.horario_saida.strftime('%H:%M')
            
            if self.instance.tolerancia_minutos is not None:
                self.initial['tolerancia_minutos'] = str(self.instance.tolerancia_minutos)
    
    def clean_telefone(self):
        telefone = self.cleaned_data.get('telefone')
        if telefone:
            # Remove caracteres não numéricos
            telefone_limpo = re.sub(r'\D', '', telefone)
            
            # Verifica se tem DDD + número (mínimo 10 dígitos)
            if len(telefone_limpo) < 10:
                raise forms.ValidationError('Número de telefone inválido. Digite DDD + número.')
            
            # Formata para (XX) XXXXX-XXXX
            if len(telefone_limpo) == 11:
                return f'({telefone_limpo[0:2]}) {telefone_limpo[2:7]}-{telefone_limpo[7:]}'
            elif len(telefone_limpo) == 10:
                return f'({telefone_limpo[0:2]}) {telefone_limpo[2:6]}-{telefone_limpo[6:]}'
        
        return telefone
    
    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        if cpf:
            # Remove caracteres não numéricos
            cpf_limpo = re.sub(r'\D', '', cpf)
            
            # Verifica se tem 11 dígitos
            if len(cpf_limpo) != 11:
                raise forms.ValidationError('CPF deve conter 11 dígitos.')
            
            # Formata para XXX.XXX.XXX-XX
            return f'{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}'
        
        return cpf
    
    def clean(self):
        cleaned_data = super().clean()
        
        # VALIDAÇÃO: Verificar se horário de saída é depois do horário de entrada
        horario_entrada = cleaned_data.get('horario_entrada')
        horario_saida = cleaned_data.get('horario_saida')
        
        if horario_entrada and horario_saida:
            if horario_saida <= horario_entrada:
                raise forms.ValidationError({
                    'horario_saida': 'O horário de saída deve ser após o horário de entrada.'
                })
        
        # VALIDAÇÃO: Verificar consistência entre carga horária e horários
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
                    self.add_error(
                        'carga_horaria_diaria',
                        f'Atenção: A carga horária selecionada ({carga_horas}h) é diferente '
                        f'do período entre entrada e saída ({diferenca_horas:.1f}h).'
                    )
                    
            except (ValueError, AttributeError):
                pass  # Ignora erros de conversão
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Converter strings para timedelta antes de salvar
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
        
        # Converter tolerância para inteiro
        tolerancia_str = self.cleaned_data.get('tolerancia_minutos')
        if tolerancia_str and tolerancia_str != '':
            try:
                instance.tolerancia_minutos = int(tolerancia_str)
            except (ValueError, TypeError):
                instance.tolerancia_minutos = 10  # Valor padrão
        else:
            instance.tolerancia_minutos = 10  # Valor padrão
        
        # Os campos horario_entrada e horario_saida já são TimeField no modelo
        
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
            profissao = profissao.strip().title()
        return profissao

# usuarios/forms.py
from django import forms
from .models import Profissional, AreaAtuacao
from estabelecimentos.models import Estabelecimento
from datetime import timedelta, datetime
import re

class ProfissionalEdicaoForm(forms.ModelForm):
    """Formulário para EDITAR profissional (sem termo_uso)"""
    
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
        widget=forms.Select(attrs={'class': 'form-control form-select'})
    )
    
    carga_horaria_semanal = forms.ChoiceField(
        choices=CARGA_HORARIA_SEMANAL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control form-select'})
    )
    
    # ✅ CAMPOS PARA HORÁRIOS E TOLERÂNCIA
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
        ('', 'Selecione a tolerância'),
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
        widget=forms.Select(attrs={'class': 'form-control form-select'}),
        help_text="Tolerância para atrasos e saídas antecipadas"
    )

    class Meta:
        model = Profissional
        fields = [
            'nome', 'sobrenome', 'cpf', 'telefone',
            'profissao', 'estabelecimento', 'carga_horaria_diaria',
            'carga_horaria_semanal', 'horario_entrada', 'horario_saida',
            'tolerancia_minutos'
            # ✅ NÃO inclui 'termo_uso' nem 'ativo'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Nome completo',
                'id': 'id_nome'
            }),
            'sobrenome': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Nome social',
                'id': 'id_sobrenome'
            }),
            'cpf': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '000.000.000-00',
                'id': 'id_cpf'
            }),
            'telefone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(11) 99999-9999',
                'id': 'id_telefone'
            }),
            'profissao': forms.Select(attrs={
                'class': 'form-control form-select',
                'id': 'id_profissao'
            }),
            'estabelecimento': forms.Select(attrs={
                'class': 'form-control form-select',
                'id': 'id_estabelecimento'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Tornar campos obrigatórios conforme template
        self.fields['telefone'].required = True
        
        # Definir valores iniciais para campos existentes
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
            
            # Definir valores iniciais para horários e tolerância
            if self.instance.horario_entrada:
                self.initial['horario_entrada'] = self.instance.horario_entrada.strftime('%H:%M')
            
            if self.instance.horario_saida:
                self.initial['horario_saida'] = self.instance.horario_saida.strftime('%H:%M')
            
            if self.instance.tolerancia_minutos is not None:
                self.initial['tolerancia_minutos'] = str(self.instance.tolerancia_minutos)
    
    def clean_telefone(self):
        telefone = self.cleaned_data.get('telefone')
        if telefone:
            # Remove caracteres não numéricos
            telefone_limpo = re.sub(r'\D', '', telefone)
            
            # Verifica se tem DDD + número (mínimo 10 dígitos)
            if len(telefone_limpo) < 10:
                raise forms.ValidationError('Número de telefone inválido. Digite DDD + número.')
            
            # Formata para (XX) XXXXX-XXXX
            if len(telefone_limpo) == 11:
                return f'({telefone_limpo[0:2]}) {telefone_limpo[2:7]}-{telefone_limpo[7:]}'
            elif len(telefone_limpo) == 10:
                return f'({telefone_limpo[0:2]}) {telefone_limpo[2:6]}-{telefone_limpo[6:]}'
        
        return telefone
    
    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        if cpf:
            # Remove caracteres não numéricos
            cpf_limpo = re.sub(r'\D', '', cpf)
            
            # Verifica se tem 11 dígitos
            if len(cpf_limpo) != 11:
                raise forms.ValidationError('CPF deve conter 11 dígitos.')
            
            # Formata para XXX.XXX.XXX-XX
            return f'{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}'
        
        return cpf
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Converter strings para timedelta antes de salvar
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
        
        # Converter tolerância para inteiro
        tolerancia_str = self.cleaned_data.get('tolerancia_minutos')
        if tolerancia_str and tolerancia_str != '':
            try:
                instance.tolerancia_minutos = int(tolerancia_str)
            except (ValueError, TypeError):
                instance.tolerancia_minutos = 10  # Valor padrão
        else:
            instance.tolerancia_minutos = 10  # Valor padrão
        
        if commit:
            instance.save()
        return instance