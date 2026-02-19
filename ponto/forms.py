# ponto/forms.py
from django import forms
from django.utils import timezone
from .models import RegistroManual
from usuarios.models import Profissional


class RegistroManualForm(forms.ModelForm):
    data = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Data do registro'
    )
    horario = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        label='Horário real'
    )
    descricao = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Descreva o motivo do ajuste...'}),
        required=False,
        label='Descrição detalhada'
    )
    
    class Meta:
        model = RegistroManual
        fields = ['profissional', 'data', 'horario', 'tipo', 'motivo', 'descricao']
        widgets = {
            'profissional': forms.Select(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'motivo': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Limitar profissionais aos ativos
        self.fields['profissional'].queryset = Profissional.objects.filter(ativo=True).order_by('nome')
        
        # Configurar valores padrão
        if not self.instance.pk:
            hoje = timezone.now().date()
            self.fields['data'].initial = hoje
            self.fields['horario'].initial = timezone.now().time().strftime('%H:%M')
    
    def clean(self):
        cleaned_data = super().clean()
        profissional = cleaned_data.get('profissional')
        data = cleaned_data.get('data')
        horario = cleaned_data.get('horario')
        tipo = cleaned_data.get('tipo')
        
        # Validação: data não pode ser futura (exceto para hoje)
        hoje = timezone.now().date()
        if data and data > hoje:
            raise forms.ValidationError("Não é possível registrar ponto para datas futuras.")
        
        # Validação: data muito antiga (limite de 30 dias)
        if data and (hoje - data).days > 30:
            raise forms.ValidationError("Não é possível ajustar registros com mais de 30 dias.")
        
        # Validação: horário razoável (entre 05:00 e 23:00)
        if horario:
            hora = horario.hour
            if hora < 5 or hora > 23:
                raise forms.ValidationError("Horário fora do período permitido (05:00 - 23:00).")
        
        return cleaned_data