"""
apps/analytics/views.py
────────────────────────
Analytics views with restaurant-level access enforcement.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.restaurants.models import Restaurant
from apps.restaurants.mixins import RestaurantAccessMixin
from .services import DashboardAnalyticsService


@extend_schema(
    tags=['analytics'],
    summary='Get dashboard analytics',
    description=(
        'Return summary and dish-performance metrics for a specific restaurant and date range. '
        'Restaurant Admins can only access analytics for their assigned restaurant.'
    ),
    parameters=[
        OpenApiParameter(
            name='restaurant_id',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Restaurant UUID to analyze.',
        ),
        OpenApiParameter(
            name='location_id',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Legacy location UUID to analyze.',
        ),
        OpenApiParameter(
            name='start_date',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Start date for the analytics period.',
        ),
        OpenApiParameter(
            name='end_date',
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            required=True,
            description='End date for the analytics period.',
        ),
    ],
    responses={200: dict, 400: dict, 403: dict},
)
class DashboardAnalyticsView(RestaurantAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        restaurant_id = (
            request.query_params.get('restaurant_id')
            or request.query_params.get('location_id')
            or request.query_params.get('restaurant')
            or request.query_params.get('location')
        )
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if not restaurant_id:
            return Response({'detail': 'restaurant_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not start_date or not end_date:
            return Response({'detail': 'start_date and end_date are required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce restaurant-level access
        try:
            self.assert_restaurant_access(restaurant_id)
        except Exception:
            return Response(
                {'detail': 'You do not have permission to access this restaurant.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        restaurant = get_object_or_404(Restaurant, id=restaurant_id)

        summary = DashboardAnalyticsService.get_dashboard_summary(restaurant, start_date, end_date)
        dish_performance = DashboardAnalyticsService.get_dish_performance(restaurant, start_date, end_date)

        return Response({
            'summary': summary,
            'dish_performance': dish_performance,
        }, status=status.HTTP_200_OK)
