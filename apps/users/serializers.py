"""
apps/users/serializers.py
─────────────────────────
Serializers for the ProfitPlate user and authentication system.

Security rules:
  - Passwords are always write-only.
  - Role is exposed read-only on outgoing responses.
  - password_change_required is exposed in login responses only.
  - No internal Django flags (is_staff, is_superuser) are returned to the API.
"""

import logging

from django.contrib.auth import get_user_model, authenticate
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.restaurants.models import Restaurant, UserRestaurant

logger = logging.getLogger(__name__)

User = get_user_model()


# ── Safe public representation ─────────────────────────────────────────────

class UserPublicSerializer(serializers.ModelSerializer):
    """
    Safe read-only representation of a user for API responses.
    Never exposes passwords, is_staff, or is_superuser.
    """

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'role', 'is_active']
        read_only_fields = fields


# ── Authentication serializers ──────────────────────────────────────────────

from rest_framework.exceptions import AuthenticationFailed


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        email = attrs.get('email', '').strip().lower()
        password = attrs.get('password', '')

        user = authenticate(request=self.context.get('request'), username=email, password=password)

        if user is None:
            raise AuthenticationFailed('Invalid email or password.')

        if not user.is_active:
            raise AuthenticationFailed('This account has been deactivated.')

        attrs['user'] = user
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        write_only=True,
        help_text='The JWT refresh token to blacklist.',
    )


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
    )

    def validate_new_password(self, value):
        from django.contrib.auth.password_validation import validate_password
        validate_password(value)
        return value


# ── Super Admin → Restaurant Admin creation ─────────────────────────────────

class CreateRestaurantAdminSerializer(serializers.Serializer):
    """
    Used by Super Admin to create a new Restaurant Admin user.
    The backend automatically sets password_change_required = True.
    """

    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=150)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text='Initial temporary password. User will be required to change it on first login.',
    )
    restaurant_ids = serializers.ListField(
        child=serializers.UUIDField(),
        help_text='List of Restaurant UUIDs to assign this admin to.',
        required=False,
    )
    location_ids = serializers.ListField(
        child=serializers.UUIDField(),
        help_text='Backward-compatible alias for restaurant_ids.',
        required=False,
    )

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate(self, attrs):
        ids = attrs.get('restaurant_ids') or attrs.get('location_ids')
        if not ids:
            raise serializers.ValidationError({
                'restaurant_ids': ['This field is required.']
            })
        existing = set(Restaurant.objects.filter(id__in=ids).values_list('id', flat=True))
        missing = [str(i) for i in ids if i not in existing]
        if missing:
            raise serializers.ValidationError({
                'restaurant_ids': [f'The following restaurant IDs do not exist: {", ".join(missing)}']
            })
        attrs['resolved_restaurant_ids'] = ids
        return attrs

    def create(self, validated_data):
        restaurant_ids = validated_data.pop('resolved_restaurant_ids')
        validated_data.pop('restaurant_ids', None)
        validated_data.pop('location_ids', None)
        password = validated_data.pop('password')
        requesting_user = self.context['request'].user

        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['email'],
            full_name=validated_data['full_name'],
            password=password,
            role='RESTAURANT_ADMIN',
            password_change_required=True,
            is_active=True,
        )

        # Assign to restaurants
        restaurants = Restaurant.objects.filter(id__in=restaurant_ids)
        for rest in restaurants:
            UserRestaurant.objects.create(
                user=user,
                restaurant=rest,
                assigned_by=requesting_user,
            )

        return user


class RestaurantAdminSerializer(serializers.ModelSerializer):
    """Read serializer for listing Restaurant Admin users."""
    assigned_restaurants = serializers.SerializerMethodField()
    assigned_locations = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'role', 'is_active',
                  'password_change_required', 'assigned_restaurants',
                  'assigned_locations', 'date_joined']
        read_only_fields = fields

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_assigned_restaurants(self, obj):
        from apps.restaurants.serializers import RestaurantSerializer
        restaurants = Restaurant.objects.filter(user_restaurants__user=obj)
        return RestaurantSerializer(restaurants, many=True).data

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_assigned_locations(self, obj):
        return self.get_assigned_restaurants(obj)
