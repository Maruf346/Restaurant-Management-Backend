from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Ingredient
from .serializers import IngredientSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['inventory'],
        summary='List ingredients',
        description='Return ingredients for the selected location or across all locations.',
        responses={200: IngredientSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['inventory'],
        summary='Get ingredient details',
        description='Return the full ingredient record and stock details.',
        responses={200: IngredientSerializer},
    ),
    create=extend_schema(
        tags=['inventory'],
        summary='Create ingredient',
        description='Add a new ingredient and set its baseline stock and purchasing details.',
        request=IngredientSerializer,
        responses={201: IngredientSerializer},
    ),
    update=extend_schema(
        tags=['inventory'],
        summary='Update ingredient',
        description='Replace ingredient details with a full update.',
        request=IngredientSerializer,
        responses={200: IngredientSerializer},
    ),
    partial_update=extend_schema(
        tags=['inventory'],
        summary='Partially update ingredient',
        description='Update only the supplied ingredient fields.',
        request=IngredientSerializer,
        responses={200: IngredientSerializer},
    ),
    destroy=extend_schema(
        tags=['inventory'],
        summary='Delete ingredient',
        description='Delete an ingredient record permanently.',
        responses={204: None},
    ),
)
class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.select_related('location').all()
    serializer_class = IngredientSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        location_id = self.request.query_params.get('location')
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        return queryset
