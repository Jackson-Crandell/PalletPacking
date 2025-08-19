from django.urls import path
from . import views

app_name = 'packing'

urlpatterns = [
    # Main pages
    path('', views.index, name='index'),
    path('configure/<int:session_id>/', views.configure, name='configure'),
    path('start/<int:session_id>/', views.start_packing, name='start_packing'),
    path('progress/<int:session_id>/', views.progress, name='progress'),
    path('results/<int:session_id>/', views.results, name='results'),
    
    # Session management
    path('sessions/', views.session_list, name='session_list'),
    path('delete/<int:session_id>/', views.delete_session, name='delete_session'),
    
    # API endpoints
    path('api/progress/<int:session_id>/', views.progress_api, name='progress_api'),
]