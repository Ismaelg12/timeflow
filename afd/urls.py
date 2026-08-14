# afd/urls.py
from django.urls import path
from . import views

app_name = 'afd'

urlpatterns = [
    path('gerar/', views.download_afd, name='download_afd'),
]

# No urls.py principal do projeto, adicione:
#   path('afd/', include('afd.urls')),
