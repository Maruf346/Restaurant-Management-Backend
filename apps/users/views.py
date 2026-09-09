from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import User
from .serializers import RegisterUserSerializer, UserSerializer


@extend_schema(
    tags=['users'],
    summary='Register a new user',
    description='Create a new account for a user with email, username, and password.',
    request=RegisterUserSerializer,
    responses={201: UserSerializer},
)
class RegisterUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterUserSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        response_serializer = UserSerializer(user)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['users'],
    summary='Get current authenticated user',
    description='Return the profile details for the currently authenticated user.',
    responses={200: UserSerializer},
)
class CurrentUserView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
