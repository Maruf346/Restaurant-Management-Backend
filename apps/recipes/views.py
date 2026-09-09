from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Category, Product, RecipeItem
from .serializers import CategorySerializer, ProductSerializer, RecipeItemSerializer


@extend_schema_view(
    list=extend_schema(
        tags=['recipes'],
        summary='List categories',
        description='Return menu categories for one or more restaurant locations.',
        responses={200: CategorySerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['recipes'],
        summary='Get category',
        description='Return the details for a single menu category.',
        responses={200: CategorySerializer},
    ),
    create=extend_schema(
        tags=['recipes'],
        summary='Create category',
        description='Create a new category to organize menu items.',
        request=CategorySerializer,
        responses={201: CategorySerializer},
    ),
    update=extend_schema(
        tags=['recipes'],
        summary='Update category',
        request=CategorySerializer,
        responses={200: CategorySerializer},
    ),
    partial_update=extend_schema(
        tags=['recipes'],
        summary='Partially update category',
        request=CategorySerializer,
        responses={200: CategorySerializer},
    ),
    destroy=extend_schema(
        tags=['recipes'],
        summary='Delete category',
        responses={204: None},
    ),
)
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.select_related('location').all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    list=extend_schema(
        tags=['recipes'],
        summary='List recipe items',
        description='Return recipe ingredient rows for menu items.',
        responses={200: RecipeItemSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['recipes'],
        summary='Get recipe item',
        responses={200: RecipeItemSerializer},
    ),
    create=extend_schema(
        tags=['recipes'],
        summary='Create recipe item',
        description='Add an ingredient requirement to a product recipe.',
        request=RecipeItemSerializer,
        responses={201: RecipeItemSerializer},
    ),
    update=extend_schema(
        tags=['recipes'],
        summary='Update recipe item',
        request=RecipeItemSerializer,
        responses={200: RecipeItemSerializer},
    ),
    partial_update=extend_schema(
        tags=['recipes'],
        summary='Partially update recipe item',
        request=RecipeItemSerializer,
        responses={200: RecipeItemSerializer},
    ),
    destroy=extend_schema(
        tags=['recipes'],
        summary='Delete recipe item',
        responses={204: None},
    ),
)
class RecipeItemViewSet(viewsets.ModelViewSet):
    queryset = RecipeItem.objects.select_related('product', 'ingredient').all()
    serializer_class = RecipeItemSerializer
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    list=extend_schema(
        tags=['recipes'],
        summary='List products',
        description='Return menu products and their recipe cost information.',
        responses={200: ProductSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['recipes'],
        summary='Get product details',
        description='Return a single product and recipe-cost summary.',
        responses={200: ProductSerializer},
    ),
    create=extend_schema(
        tags=['recipes'],
        summary='Create product',
        description='Create a menu product with recipe and pricing details.',
        request=ProductSerializer,
        responses={201: ProductSerializer},
    ),
    update=extend_schema(
        tags=['recipes'],
        summary='Update product',
        request=ProductSerializer,
        responses={200: ProductSerializer},
    ),
    partial_update=extend_schema(
        tags=['recipes'],
        summary='Partially update product',
        request=ProductSerializer,
        responses={200: ProductSerializer},
    ),
    destroy=extend_schema(
        tags=['recipes'],
        summary='Delete product',
        responses={204: None},
    ),
)
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('location', 'category').all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        location_id = self.request.query_params.get('location')
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        return queryset
