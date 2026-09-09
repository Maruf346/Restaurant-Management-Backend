from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import DailySalesRecord, SoldDishRecord
from .serializers import DailySalesRecordSerializer, SoldDishRecordSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['sales'],
        summary='List daily sales records',
        description='Return the sales totals for each date and location.',
        responses={200: DailySalesRecordSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['sales'],
        summary='Get daily sales record',
        description='Return a single daily sales summary, including profitability metrics.',
        responses={200: DailySalesRecordSerializer},
    ),
    create=extend_schema(
        tags=['sales'],
        summary='Create daily sales record',
        description='Create a daily sales summary record and assign it to a location.',
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


@extend_schema_view(
    list=extend_schema(
        tags=['sales'],
        summary='List sold dish items',
        description='Return individual dish sales rows for each daily sales record.',
        responses={200: SoldDishRecordSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['sales'],
        summary='Get sold dish item',
        description='Return a single sold dish record with revenue and cost calculations.',
        responses={200: SoldDishRecordSerializer},
    ),
    create=extend_schema(
        tags=['sales'],
        summary='Create sold dish item',
        description='Record a sold menu item for a daily sales period.',
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
