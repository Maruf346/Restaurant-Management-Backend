"""
apps/sales/views.py
────────────────────
Sales viewsets with location-level access control.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.locations.mixins import LocationAccessMixin
from .models import DailySalesRecord, SoldDishRecord
from .serializers import DailySalesRecordSerializer, SoldDishRecordSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['sales'],
        summary='List daily sales records',
        description='Return sales totals for each date and accessible location.',
        responses={200: DailySalesRecordSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['sales'],
        summary='Get daily sales record',
        responses={200: DailySalesRecordSerializer},
    ),
    create=extend_schema(
        tags=['sales'],
        summary='Create daily sales record',
        request=DailySalesRecordSerializer,
        responses={201: DailySalesRecordSerializer},
    ),
    update=extend_schema(
        tags=['sales'],
        summary='Update daily sales record',
        request=DailySalesRecordSerializer,
        responses={200: DailySalesRecordSerializer},
    ),
    partial_update=extend_schema(
        tags=['sales'],
        summary='Partially update daily sales record',
        request=DailySalesRecordSerializer,
        responses={200: DailySalesRecordSerializer},
    ),
    destroy=extend_schema(
        tags=['sales'],
        summary='Delete daily sales record',
        responses={204: None},
    ),
)
class DailySalesRecordViewSet(LocationAccessMixin, viewsets.ModelViewSet):
    queryset = DailySalesRecord.objects.select_related('location').prefetch_related('sold_dishes').all()
    serializer_class = DailySalesRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.filter_queryset_by_location(queryset)
        location_id = self.request.query_params.get('location')
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        return queryset

    def perform_create(self, serializer):
        location = serializer.validated_data.get('location')
        if location:
            self.assert_location_access(location.id)
        serializer.save()


@extend_schema_view(
    list=extend_schema(
        tags=['sales'],
        summary='List sold dish items',
        description='Return individual dish sales rows for accessible locations.',
        responses={200: SoldDishRecordSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['sales'],
        summary='Get sold dish item',
        responses={200: SoldDishRecordSerializer},
    ),
    create=extend_schema(
        tags=['sales'],
        summary='Create sold dish item',
        request=SoldDishRecordSerializer,
        responses={201: SoldDishRecordSerializer},
    ),
    update=extend_schema(
        tags=['sales'],
        summary='Update sold dish item',
        request=SoldDishRecordSerializer,
        responses={200: SoldDishRecordSerializer},
    ),
    partial_update=extend_schema(
        tags=['sales'],
        summary='Partially update sold dish item',
        request=SoldDishRecordSerializer,
        responses={200: SoldDishRecordSerializer},
    ),
    destroy=extend_schema(
        tags=['sales'],
        summary='Delete sold dish item',
        responses={204: None},
    ),
)
class SoldDishRecordViewSet(LocationAccessMixin, viewsets.ModelViewSet):
    queryset = SoldDishRecord.objects.select_related('daily_sales__location', 'product').all()
    serializer_class = SoldDishRecordSerializer
    # Filter via daily_sales → location
    location_filter_field = 'daily_sales__location_id'
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.filter_queryset_by_location(queryset)
        location_id = self.request.query_params.get('location')
        if location_id:
            queryset = queryset.filter(daily_sales__location_id=location_id)
        return queryset
