# botconfig/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('update-config/', views.update_config_view, name='update_config'),
    path('get-config/', views.get_config_view, name='get_config'),
    path('config/', views.display_config_view, name='display-config')
]