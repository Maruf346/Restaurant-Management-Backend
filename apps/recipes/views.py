from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Category, Product, RecipeItem
from .serializers import CategorySerializer, ProductSerializer, RecipeItemSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.select_related('location').all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]


class RecipeItemViewSet(viewsets.ModelViewSet):
    queryset = RecipeItem.objects.select_related('product', 'ingredient').all()
    serializer_class = RecipeItemSerializer
    permission_classes = [IsAuthenticated]


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
