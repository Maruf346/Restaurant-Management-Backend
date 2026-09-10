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
from apps.restaurants.serializers import RestaurantSerializer

logger = logging.getLogger(__name__)

User = get_user_model()


# ── Safe public representation ─────────────────────────────────────────────

class UserPublicSerializer(serializers.ModelSerializer):
    """
    Safe read-only representation of a user for API responses.
    Never exposes passwords, is_staff, or is_superuser.
    Includes profile_picture as an absolute URL.
    """
    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'role', 'is_active', 'profile_picture']
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_profile_picture(self, obj):
        if not obj.profile_picture:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.profile_picture.url)
        return obj.profile_picture.url


# ── Profile update ─────────────────────────────────────────────────────────

class UpdateProfileSerializer(serializers.Serializer):
    """
    Used by any authenticated user to update their own profile.
    Supports multipart/form-data for profile picture upload.
    """
    full_name = serializers.CharField(max_length=150, required=False)
    profile_picture = serializers.ImageField(required=False, allow_null=True)

    def update(self, instance, validated_data):
        if 'full_name' in validated_data:
            instance.full_name = validated_data['full_name']
        if 'profile_picture' in validated_data:
            instance.profile_picture = validated_data['profile_picture']
        instance.save(update_fields=[k for k in validated_data if k in ('full_name', 'profile_picture')])
        return instance


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
    confirm_new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text='Must match new_password exactly.',
    )

    def validate_new_password(self, value):
        from django.contrib.auth.password_validation import validate_password
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({
                'confirm_new_password': 'New password and confirmation do not match.'
            })
        return attrs


# ── Super Admin / Restaurant Admin → Restaurant Admin creation ──────────────

class CreateRestaurantAdminSerializer(serializers.Serializer):
    """
    Used by Super Admin or Restaurant Admin to invite a new Restaurant Admin.

    - Super Admin: can assign any valid restaurant.
    - Restaurant Admin: can only assign restaurants they themselves manage.
      Attempting to assign another restaurant returns a 400 validation error.
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
        required=True,
    )

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate(self, attrs):
        ids = attrs.get('restaurant_ids', [])
        if not ids:
            raise serializers.ValidationError({
                'restaurant_ids': ['This field is required.']
            })

        # Validate UUIDs exist
        existing = set(Restaurant.objects.filter(id__in=ids).values_list('id', flat=True))
        missing = [str(i) for i in ids if i not in existing]
        if missing:
            raise serializers.ValidationError({
                'restaurant_ids': [f'The following restaurant IDs do not exist: {", ".join(missing)}']
            })

        # Restaurant Admins can only assign restaurants they manage
        requesting_user = self.context['request'].user
        if requesting_user.is_restaurant_admin:
            allowed_ids = set(requesting_user.get_assigned_restaurant_ids())
            unauthorized = [str(i) for i in ids if i not in allowed_ids]
            if unauthorized:
                raise serializers.ValidationError({
                    'restaurant_ids': [
                        'You can only assign new admins to restaurants you manage. '
                        f'Unauthorized restaurant IDs: {", ".join(unauthorized)}'
                    ]
                })

        attrs['resolved_restaurant_ids'] = ids
        return attrs

    def create(self, validated_data):
        restaurant_ids = validated_data.pop('resolved_restaurant_ids')
        validated_data.pop('restaurant_ids', None)
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

        # Assign to restaurants and collect names for the invitation email
        restaurants = list(Restaurant.objects.filter(id__in=restaurant_ids))
        restaurant_names = []
        for rest in restaurants:
            UserRestaurant.objects.create(
                user=user,
                restaurant=rest,
                assigned_by=requesting_user,
            )
            restaurant_names.append(rest.name)

        # Send invitation email (non-blocking — log failure, never raise)
        try:
            from apps.users.email import send_restaurant_admin_invite
            send_restaurant_admin_invite(user, password, restaurant_names)
        except Exception as exc:
            logger.error('Invitation email failed for %s: %s', user.email, exc)

        return user


# ── Restaurant Admin read serializer ───────────────────────────────────────

class RestaurantAdminSerializer(serializers.ModelSerializer):
    """Read serializer for listing and retrieving Restaurant Admin users."""
    assigned_restaurants = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name', 'role', 'is_active',
            'password_change_required', 'profile_picture',
            'assigned_restaurants', 'date_joined',
        ]
        read_only_fields = fields

    @extend_schema_field(RestaurantSerializer(many=True))
    def get_assigned_restaurants(self, obj):
        restaurants = Restaurant.objects.filter(user_restaurants__user=obj)
        return RestaurantSerializer(restaurants, many=True, context=self.context).data

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_profile_picture(self, obj):
        if not obj.profile_picture:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.profile_picture.url)
        return obj.profile_picture.url
