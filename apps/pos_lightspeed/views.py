from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import LightspeedConfig
from .serializers import LightspeedConfigSerializer


class LightspeedConfigViewSet(viewsets.ModelViewSet):
    queryset = LightspeedConfig.objects.select_related('location').all()
    serializer_class = LightspeedConfigSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        location_id = self.request.query_params.get('location')
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        return queryset
