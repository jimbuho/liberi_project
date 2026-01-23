from django.urls import path
from . import views

urlpatterns = [
    path('save-player-id/', views.save_player_id, name='save_player_id'),
]
