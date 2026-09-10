from django.urls import path

from .views import DashboardAnalyticsView, DishPerformanceAnalyticsView

urlpatterns = [
    path('dashboard/', DashboardAnalyticsView.as_view(), name='dashboard-analytics'),
    path('dish-performance/', DishPerformanceAnalyticsView.as_view(), name='dish-performance-analytics'),
]
