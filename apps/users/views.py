"""
apps/users/views.py
───────────────────
Business-specific authentication and user management views.

Auth endpoints:
  POST /auth/login/           — obtain access + refresh tokens
  POST /auth/logout/          — blacklist refresh token
  POST /auth/refresh/         — obtain new access token from refresh token

User endpoints:
  GET  /users/me/             — current user profile
  POST /users/change-password/ — change password (clears password_change_required)
  POST /users/restaurant-admins/ — Super Admin creates a Restaurant Admin
  GET  /users/restaurant-admins/ — Super Admin lists Restaurant Admins
"""

import logging

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.models import UserRole
from apps.users.permissions import IsSuperAdmin
from .serializers import *

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Login ──────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['auth'],
    summary='Login',
    description=(
        'Authenticate with email and password. Returns JWT access and refresh tokens, '
        'user role, and password_change_required flag.'
    ),
    request=LoginSerializer,
    responses={
        200: inline_serializer(
            name='LoginResponse',
            fields={
                'access': serializers.CharField(),
                'refresh': serializers.CharField(),
                'user': UserPublicSerializer(),
                'password_change_required': serializers.BooleanField(),
            },
        ),
        400: OpenApiResponse(description='Invalid credentials or account disabled'),
    },
)
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_authenticate_header(self, request):
        return 'Bearer'

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserPublicSerializer(user).data,
            'password_change_required': user.password_change_required,
        }, status=status.HTTP_200_OK)


# ── Logout ─────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['auth'],
    summary='Logout',
    description=(
        'Blacklist the provided refresh token. After this call, the token cannot '
        'be used to obtain new access tokens. The short-lived access token will '
        'expire naturally.'
    ),
    request=LogoutSerializer,
    responses={
        204: OpenApiResponse(description='Successfully logged out'),
        400: OpenApiResponse(description='Invalid or already-blacklisted token'),
    },
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = RefreshToken(serializer.validated_data['refresh'])
            token.blacklist()
        except TokenError as exc:
            raise InvalidToken({'detail': str(exc)})

        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Token Refresh ──────────────────────────────────────────────────────────

@extend_schema(
    tags=['auth'],
    summary='Refresh access token',
    description='Exchange a valid refresh token for a new access token.',
)
class CustomTokenRefreshView(TokenRefreshView):
    pass


# ── Current User ────────────────────────────────────────────────────────────

@extend_schema(
    tags=['users'],
    summary='Get current user',
    description='Return the profile of the currently authenticated user.',
    responses={200: UserPublicSerializer},
)
class MeView(generics.RetrieveAPIView):
    serializer_class = UserPublicSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


# ── Change Password ────────────────────────────────────────────────────────

@extend_schema(
    tags=['users'],
    summary='Change password',
    description=(
        'Change the authenticated user\'s password. '
        'If password_change_required was True, it will be cleared after a '
        'successful change. Requires the current password for verification.'
    ),
    request=ChangePasswordSerializer,
    responses={
        200: OpenApiResponse(description='Password changed successfully'),
        400: OpenApiResponse(description='Validation error or wrong current password'),
    },
)
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        current_password = serializer.validated_data['current_password']
        new_password = serializer.validated_data['new_password']

        if not user.check_password(current_password):
            return Response(
                {'current_password': ['Incorrect current password.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        if user.password_change_required:
            user.password_change_required = False
        user.save(update_fields=['password', 'password_change_required'])

        logger.info('Password changed for user %s', user.email)
        return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)


# ── Restaurant Admin management (Super Admin only) ──────────────────────────

@extend_schema(
    tags=['users'],
    summary='Create Restaurant Admin',
    description=(
        'Super Admin only. Create a new Restaurant Admin user with a temporary '
        'password and assign them to one or more restaurants. '
        'The user will be required to change their password on first login '
        '(password_change_required=true).'
    ),
    request=CreateRestaurantAdminSerializer,
    responses={
        201: RestaurantAdminSerializer,
        400: OpenApiResponse(description='Validation error'),
        403: OpenApiResponse(description='Super Admin required'),
    },
)
class CreateRestaurantAdminView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateRestaurantAdminSerializer
        return RestaurantAdminSerializer

    def get_queryset(self):
        return User.objects.filter(role=UserRole.RESTAURANT_ADMIN).order_by('full_name')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            RestaurantAdminSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=['users'],
    summary='List Restaurant Admins',
    description='Super Admin only. Return all Restaurant Admin users.',
    responses={200: RestaurantAdminSerializer(many=True)},
)
class ListRestaurantAdminsView(generics.ListAPIView):
    serializer_class = RestaurantAdminSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get_queryset(self):
        return User.objects.filter(role=UserRole.RESTAURANT_ADMIN).order_by('full_name')
