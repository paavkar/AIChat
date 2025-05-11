# botconfig/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('update_config/', views.update_config_view, name='update_config'),
    path('get_config/', views.get_config_view, name='get_config'),
]