"""
apps/users/views.py
───────────────────
Authentication and user management views.

Auth:
  POST /auth/login/             — obtain access + refresh tokens
  POST /auth/logout/            — blacklist refresh token
  POST /auth/refresh/           — obtain new access token

User:
  GET  /users/me/               — current user profile
  PATCH /users/me/              — update profile (full_name, profile_picture)
  POST /users/change-password/  — change password (clears password_change_required)

Restaurant Admin management:
  GET  /users/restaurant-admins/         — list admins (scoped by role)
  POST /users/restaurant-admins/         — create admin (super admin OR restaurant admin)
  GET  /users/restaurant-admins/{id}/    — retrieve single admin by UUID
  PATCH /users/restaurant-admins/{id}/toggle-status/ — activate/deactivate (super admin only)
"""

import logging

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    extend_schema, OpenApiResponse, inline_serializer, OpenApiParameter,
)
from rest_framework import filters, generics, serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.models import UserRole
from apps.users.permissions import IsSuperAdmin, IsSuperAdminOrIsRestaurantAdmin
from .serializers import (
    ChangePasswordSerializer,
    CreateRestaurantAdminSerializer,
    LoginSerializer,
    LogoutSerializer,
    RestaurantAdminSerializer,
    UpdateProfileSerializer,
    UserPublicSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Login ──────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['auth'],
    summary='Login',
    description=(
        'Authenticate with email and password. Returns JWT access and refresh tokens, '
        'user role, profile picture URL, and password_change_required flag.'
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
            'user': UserPublicSerializer(user, context={'request': request}).data,
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


# ── Current User — GET + PATCH ─────────────────────────────────────────────

@extend_schema(
    tags=['users'],
    summary='Get current user',
    description='Return the profile of the currently authenticated user, including profile_picture URL.',
    responses={200: UserPublicSerializer},
)
class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UpdateProfileSerializer
        return UserPublicSerializer

    @extend_schema(
        tags=['users'],
        summary='Update profile',
        description=(
            'Update the current user\'s full name and/or profile picture. '
            'Send as multipart/form-data when uploading a profile picture.'
        ),
        request=UpdateProfileSerializer,
        responses={200: UserPublicSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = UpdateProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.update(user, serializer.validated_data)
        return Response(
            UserPublicSerializer(user, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )

    # Disable full PUT (only PATCH makes sense for profile updates)
    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.partial_update(request, *args, **kwargs)


# ── Change Password ────────────────────────────────────────────────────────

@extend_schema(
    tags=['users'],
    summary='Change password',
    description=(
        'Change the authenticated user\'s password. '
        'new_password and confirm_new_password must match. '
        'If password_change_required was True, it will be cleared after a '
        'successful change. Requires the current password for verification.'
    ),
    request=ChangePasswordSerializer,
    responses={
        200: OpenApiResponse(description='Password changed successfully'),
        400: OpenApiResponse(description='Validation error, wrong current password, or passwords do not match'),
    },
)
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['current_password']):
            return Response(
                {'current_password': ['Incorrect current password.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data['new_password'])
        if user.password_change_required:
            user.password_change_required = False
        user.save(update_fields=['password', 'password_change_required'])

        logger.info('Password changed for user %s', user.email)
        return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)


# ── Restaurant Admin list + create ─────────────────────────────────────────

@extend_schema(
    methods=['GET'],
    tags=['users'],
    summary='List Restaurant Admins',
    description=(
        '**Super Admin**: returns all Restaurant Admin users with search support '
        '(`?search=` matches email or full name).\n\n'
        '**Restaurant Admin**: returns only the admins who share at least one '
        'restaurant with the requester (i.e., co-admins of your restaurants).'
    ),
    parameters=[
        OpenApiParameter(
            name='search', type=str, location=OpenApiParameter.QUERY,
            required=False, description='Search by name or email.',
        ),
    ],
    responses={200: RestaurantAdminSerializer(many=True)},
)
@extend_schema(
    methods=['POST'],
    tags=['users'],
    summary='Create Restaurant Admin',
    description=(
        'Create a new Restaurant Admin and send them an invitation email '
        'containing their temporary password and assigned restaurant details.\n\n'
        '**Super Admin**: can assign any valid restaurant.\n\n'
        '**Restaurant Admin**: can only assign restaurants they manage. '
        'Assigning another restaurant raises a 400 error.'
    ),
    request=CreateRestaurantAdminSerializer,
    responses={
        201: RestaurantAdminSerializer,
        400: OpenApiResponse(description='Validation error or unauthorized restaurant assignment'),
        403: OpenApiResponse(description='Insufficient permissions'),
    },
)
class RestaurantAdminListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsSuperAdminOrIsRestaurantAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['email', 'full_name']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateRestaurantAdminSerializer
        return RestaurantAdminSerializer

    def get_queryset(self):
        user = self.request.user
        qs = User.objects.filter(role=UserRole.RESTAURANT_ADMIN)

        if user.is_super_admin:
            return qs.order_by('full_name')

        # Restaurant Admin: only co-admins sharing at least one restaurant
        restaurant_ids = user.get_assigned_restaurant_ids()
        return qs.filter(
            user_restaurants__restaurant_id__in=restaurant_ids
        ).exclude(pk=user.pk).distinct().order_by('full_name')

    def create(self, request, *args, **kwargs):
        serializer = CreateRestaurantAdminSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        new_user = serializer.save()
        return Response(
            RestaurantAdminSerializer(new_user, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


# ── Restaurant Admin retrieve by UUID ─────────────────────────────────────

@extend_schema(
    tags=['users'],
    summary='Retrieve Restaurant Admin',
    description=(
        'Retrieve a single Restaurant Admin by their UUID.\n\n'
        '**Super Admin**: can retrieve any admin.\n\n'
        '**Restaurant Admin**: can only retrieve co-admins of their restaurants.'
    ),
    responses={
        200: RestaurantAdminSerializer,
        403: OpenApiResponse(description='Insufficient permissions'),
        404: OpenApiResponse(description='Admin not found'),
    },
)
class RestaurantAdminDetailView(generics.RetrieveAPIView):
    serializer_class = RestaurantAdminSerializer
    permission_classes = [IsAuthenticated, IsSuperAdminOrIsRestaurantAdmin]

    def get_object(self):
        user = self.request.user
        pk = self.kwargs['pk']
        qs = User.objects.filter(role=UserRole.RESTAURANT_ADMIN)

        if user.is_super_admin:
            return get_object_or_404(qs, pk=pk)

        # Restaurant Admin: only co-admins
        restaurant_ids = user.get_assigned_restaurant_ids()
        return get_object_or_404(
            qs.filter(user_restaurants__restaurant_id__in=restaurant_ids).distinct(),
            pk=pk,
        )


# ── Toggle Restaurant Admin active status (Super Admin only) ──────────────

@extend_schema(
    tags=['users'],
    summary='Toggle Restaurant Admin status',
    description=(
        'Toggle the `is_active` status of a Restaurant Admin. '
        'Deactivated users cannot log in.\n\n'
        '**Super Admin**: can toggle any Restaurant Admin.\n\n'
        '**Restaurant Admin**: can only toggle co-admins who share at least one '
        'of their restaurants. Attempting to toggle an unrelated admin returns 403.'
    ),
    responses={
        200: RestaurantAdminSerializer,
        403: OpenApiResponse(description='Insufficient permissions or admin not in your restaurants'),
        404: OpenApiResponse(description='Admin not found'),
    },
)
class ToggleRestaurantAdminStatusView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdminOrIsRestaurantAdmin]

    def patch(self, request, pk, *args, **kwargs):
        admin = get_object_or_404(User, pk=pk, role=UserRole.RESTAURANT_ADMIN)

        # Restaurant Admins can only toggle co-admins of their own restaurants
        if request.user.is_restaurant_admin:
            restaurant_ids = set(request.user.get_assigned_restaurant_ids())
            is_co_admin = admin.user_restaurants.filter(
                restaurant_id__in=restaurant_ids
            ).exists()
            if not is_co_admin or admin.pk == request.user.pk:
                return Response(
                    {'detail': 'You can only toggle the status of admins who share your restaurants.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        admin.is_active = not admin.is_active
        admin.save(update_fields=['is_active'])
        action = 'activated' if admin.is_active else 'deactivated'
        logger.info('%s %s user %s', request.user.email, action, admin.email)
        return Response(
            RestaurantAdminSerializer(admin, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )
