from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.locations.models import Location
from .services import DashboardAnalyticsService


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
