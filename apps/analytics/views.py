from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.locations.models import Location
from .services import DashboardAnalyticsService


@extend_schema(
    tags=['analytics'],
    summary='Get dashboard analytics',
    description='Return summary and dish-performance metrics for a specific location and date range.',
    parameters=[
        OpenApiParameter(
            name='location_id',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Location UUID to analyze.',
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
    responses={200: dict, 400: dict},
)
class DashboardAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        location_id = request.query_params.get('location_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if not location_id:
            return Response({'detail': 'location_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not start_date or not end_date:
            return Response({'detail': 'start_date and end_date are required.'}, status=status.HTTP_400_BAD_REQUEST)

        location = get_object_or_404(Location, id=location_id)

        summary = DashboardAnalyticsService.get_dashboard_summary(location, start_date, end_date)
        dish_performance = DashboardAnalyticsService.get_dish_performance(location, start_date, end_date)

        return Response({
            'summary': summary,
            'dish_performance': dish_performance,
        }, status=status.HTTP_200_OK)
