"""
apps/analytics/views.py
────────────────────────
Analytics views with restaurant-level access enforcement.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.restaurants.models import Restaurant
from apps.restaurants.mixins import RestaurantAccessMixin
from .serializers import (
    DashboardAnalyticsResponseSerializer,
    DishPerformanceAnalyticsResponseSerializer,
)
from .services import DashboardAnalyticsService


class DashboardAnalyticsView(RestaurantAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

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
                description='Start date for the analytics period (YYYY-MM-DD).',
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                required=True,
                description='End date for the analytics period (YYYY-MM-DD).',
            ),
        ],
        responses={
            200: DashboardAnalyticsResponseSerializer,
            400: OpenApiResponse(
                description='Bad Request — missing or invalid parameters',
                response=inline_serializer(
                    name='DashboardAnalyticsError400',
                    fields={'detail': serializers.CharField()}
                ),
            ),
            403: OpenApiResponse(
                description='Forbidden — user does not have access to this restaurant',
                response=inline_serializer(
                    name='DashboardAnalyticsError403',
                    fields={'detail': serializers.CharField()}
                ),
            ),
        },
    )
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

        data = {
            'summary': summary,
            'dish_performance': dish_performance,
        }
        serializer = DashboardAnalyticsResponseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DishPerformanceAnalyticsView(RestaurantAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['analytics'],
        summary='Get dish performance analytics',
        description=(
            'Return dish-performance metrics for a specific restaurant and date range. '
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
                description='Start date for the analytics period (YYYY-MM-DD).',
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                required=True,
                description='End date for the analytics period (YYYY-MM-DD).',
            ),
        ],
        responses={
            200: DishPerformanceAnalyticsResponseSerializer,
            400: OpenApiResponse(
                description='Bad Request — missing or invalid parameters',
                response=inline_serializer(
                    name='DishPerformanceAnalyticsError400',
                    fields={'detail': serializers.CharField()}
                ),
            ),
            403: OpenApiResponse(
                description='Forbidden — user does not have access to this restaurant',
                response=inline_serializer(
                    name='DishPerformanceAnalyticsError403',
                    fields={'detail': serializers.CharField()}
                ),
            ),
        },
    )
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

        dish_performance = DashboardAnalyticsService.get_dish_performance(restaurant, start_date, end_date)

        data = {
            'restaurant_id': restaurant.id,
            'restaurant_name': restaurant.name,
            'start_date': start_date,
            'end_date': end_date,
            'dish_performance': dish_performance,
        }
        serializer = DishPerformanceAnalyticsResponseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
