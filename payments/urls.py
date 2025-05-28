from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment endpoints will be added here
    path('', views.payment_list, name='payment_list'),
    path('paypal/subscribe/', views.paypal_subscribe, name='paypal_subscribe'),
] 