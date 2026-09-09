from django.urls import path

from .views import *

app_name = 'pos_lightspeed'

urlpatterns = [
    path('status/', LightspeedStatusView.as_view(), name='status'),
    path('authorize/', LightspeedAuthorizeView.as_view(), name='authorize'),
    path('callback/', LightspeedCallbackView.as_view(), name='callback'),
    path('disconnect/', LightspeedDisconnectView.as_view(), name='disconnect'),
    path('sync/', LightspeedManualSyncView.as_view(), name='sync'),
    path('webhook/', LightspeedWebhookView.as_view(), name='webhook'),
]
