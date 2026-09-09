from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import DailySalesRecord, SoldDishRecord
from .serializers import DailySalesRecordSerializer, SoldDishRecordSerializer


class DailySalesRecordViewSet(viewsets.ModelViewSet):
    queryset = DailySalesRecord.objects.select_related('location').prefetch_related('sold_dishes').all()
    serializer_class = DailySalesRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        location_id = self.request.query_params.get('location')
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        return queryset


class SoldDishRecordViewSet(viewsets.ModelViewSet):
    queryset = SoldDishRecord.objects.select_related('daily_sales', 'product').all()
    serializer_class = SoldDishRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        location_id = self.request.query_params.get('location')
        if location_id:
            queryset = queryset.filter(daily_sales__location_id=location_id)
        return queryset
