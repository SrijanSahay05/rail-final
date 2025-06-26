from django.urls import path
from feature_railways.views import index

app_name = 'core_home'

urlpatterns = [
    path('', index, name='index'),
]