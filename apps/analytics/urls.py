from django.urls import path

from .views import DashboardAnalyticsView

urlpatterns = [
    path('dashboard/', DashboardAnalyticsView.as_view(), name='dashboard-analytics'),
    path('dish-performance/', DashboardAnalyticsView.as_view(), name='dish-performance-analytics'),
]
