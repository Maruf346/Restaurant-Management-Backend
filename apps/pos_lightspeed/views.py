"""
apps/pos_lightspeed/views.py
────────────────────────────
Business-specific API views for Lightspeed POS OAuth, status, disconnect,
manual sync, and webhook processing.

Access Control Rules:
  - SUPER_ADMIN: Can view, authorize, disconnect, and sync any restaurant.
  - RESTAURANT_ADMIN: Strictly restricted to their assigned restaurant(s).
  - Zero sensitive token exposure in any response serializer.
"""

from datetime import datetime, timedelta
import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.restaurants.models import Restaurant
from apps.users.permissions import IsSuperAdmin

from .models import LightspeedConfig, LightspeedConnectionStatus
from .oauth import LightspeedOAuthError, LightspeedOAuthService
from .serializers import *
from .state import OAuthStateManager

logger = logging.getLogger(__name__)


def _check_user_restaurant_access(user, restaurant: Restaurant) -> bool:
    """Helper to verify if user has access to a restaurant."""
    if user.is_super_admin:
        return True
    return user.assigned_restaurants.filter(pk=restaurant.pk).exists()


_check_user_location_access = _check_user_restaurant_access


class LightspeedStatusView(APIView):
    """
    Get Lightspeed connection status.
    - If `restaurant_id` (or `location_id`) is supplied: returns status for that restaurant.
    - If omitted: returns a list of statuses for all restaurants accessible to the user.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['pos_lightspeed'],
        summary='Get Lightspeed connection status',
        description=(
            'Returns safe connection status information without exposing sensitive tokens. '
            'Filter by `restaurant_id` (or legacy `location_id`) to get status for a single restaurant.'
        ),
        parameters=[
            OpenApiParameter(
                name='restaurant_id',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description='UUID of the restaurant to check status for.',
            ),
            OpenApiParameter(
                name='location_id',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Legacy UUID parameter for backward compatibility.',
            ),
        ],
        responses={200: LightspeedStatusSerializer(many=True)},
    )
    def get(self, request):
        restaurant_id = (
            request.query_params.get('restaurant_id')
            or request.query_params.get('location_id')
            or request.query_params.get('restaurant')
            or request.query_params.get('location')
        )

        if restaurant_id:
            restaurant = get_object_or_404(Restaurant, pk=restaurant_id)
            if not _check_user_restaurant_access(request.user, restaurant):
                return Response(
                    {'detail': 'You do not have permission to view this restaurant.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            config, _ = LightspeedConfig.objects.get_or_create(restaurant=restaurant)
            serializer = LightspeedStatusSerializer(config)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # List all accessible configs
        if request.user.is_super_admin:
            restaurants = Restaurant.objects.all()
        else:
            restaurants = request.user.assigned_restaurants.all()

        configs = []
        for rest in restaurants:
            cfg, _ = LightspeedConfig.objects.get_or_create(restaurant=rest)
            configs.append(cfg)

        serializer = LightspeedStatusSerializer(configs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LightspeedAuthorizeView(APIView):
    """
    Initiates OAuth 2.0 flow by generating a secure state token and returning
    the Lightspeed authorization URL.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['pos_lightspeed'],
        summary='Generate Lightspeed OAuth authorization URL',
        description='Returns the authorization URL to redirect the user to Lightspeed for login/consent.',
        parameters=[
            OpenApiParameter(
                name='restaurant_id',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description='UUID of the restaurant to connect.',
            ),
            OpenApiParameter(
                name='location_id',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Legacy UUID of the location to connect.',
            ),
        ],
        responses={200: LightspeedAuthorizeUrlSerializer},
    )
    def get(self, request):
        restaurant_id = request.query_params.get('restaurant_id') or request.query_params.get('location_id')
        if not restaurant_id:
            return Response(
                {'detail': 'restaurant_id query parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        restaurant = get_object_or_404(Restaurant, pk=restaurant_id)
        if not _check_user_restaurant_access(request.user, restaurant):
            return Response(
                {'detail': 'You do not have permission to configure this restaurant.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        state = OAuthStateManager.create_state(request.user.id, restaurant_id=restaurant.id)
        try:
            auth_url = LightspeedOAuthService.build_authorization_url(state)
        except LightspeedOAuthError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'authorization_url': auth_url, 'state': state}, status=status.HTTP_200_OK)


class LightspeedCallbackView(APIView):
    """
    Handles redirect callback from Lightspeed OAuth server.
    Validates the state token and exchanges authorization code for access/refresh tokens.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['pos_lightspeed'],
        summary='OAuth callback from Lightspeed',
        description='Validates OAuth state, exchanges code for tokens, and marks restaurant as connected.',
        parameters=[
            OpenApiParameter(name='code', type=str, location=OpenApiParameter.QUERY, required=True),
            OpenApiParameter(name='state', type=str, location=OpenApiParameter.QUERY, required=True),
        ],
        responses={200: LightspeedStatusSerializer},
    )
    def get(self, request):
        code = request.query_params.get('code')
        state = request.query_params.get('state')

        if not code or not state:
            return Response(
                {'detail': 'Both code and state query parameters are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = OAuthStateManager.validate_and_consume_state(state)
        if not payload:
            return Response(
                {'detail': 'Invalid, expired, or previously consumed OAuth state.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        restaurant_id = payload.get('restaurant_id') or payload.get('location_id')
        try:
            restaurant = Restaurant.objects.get(pk=restaurant_id)
        except Restaurant.DoesNotExist:
            return Response({'detail': 'Restaurant not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            token_data = LightspeedOAuthService.exchange_code_for_tokens(code)
        except LightspeedOAuthError as exc:
            logger.error("Token exchange failed in callback: %s", exc)
            return Response(
                {'detail': f'OAuth token exchange failed: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        access_token = token_data.get('access_token', '')
        refresh_token = token_data.get('refresh_token', '')
        expires_in = int(token_data.get('expires_in', 3600))
        account_id = str(token_data.get('account_id', ''))
        expires_at = timezone.now() + timedelta(seconds=expires_in)

        config, _ = LightspeedConfig.objects.get_or_create(restaurant=restaurant)
        config.mark_connected(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            account_id=account_id,
        )

        return Response(
            {
                'detail': 'Lightspeed account connected successfully.',
                'config': LightspeedStatusSerializer(config).data,
            },
            status=status.HTTP_200_OK,
        )


class LightspeedDisconnectView(APIView):
    """
    Disconnects a restaurant from Lightspeed by clearing stored tokens.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['pos_lightspeed'],
        summary='Disconnect Lightspeed integration',
        description='Clears stored OAuth tokens and resets connection status to DISCONNECTED.',
        request={'application/json': {'type': 'object', 'properties': {'restaurant_id': {'type': 'string'}, 'location_id': {'type': 'string'}}}},
        responses={200: LightspeedStatusSerializer},
    )
    def post(self, request):
        restaurant_id = request.data.get('restaurant_id') or request.data.get('location_id')
        if not restaurant_id:
            return Response(
                {'detail': 'restaurant_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        restaurant = get_object_or_404(Restaurant, pk=restaurant_id)
        if not _check_user_restaurant_access(request.user, restaurant):
            return Response(
                {'detail': 'You do not have permission to disconnect this restaurant.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        config, _ = LightspeedConfig.objects.get_or_create(restaurant=restaurant)
        config.mark_disconnected()

        return Response(
            {
                'detail': 'Lightspeed disconnected successfully.',
                'config': LightspeedStatusSerializer(config).data,
            },
            status=status.HTTP_200_OK,
        )


class LightspeedManualSyncView(APIView):
    """
    Trigger a manual sales synchronization for a specific restaurant.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['pos_lightspeed'],
        summary='Trigger manual Lightspeed sales sync',
        description='Queues an asynchronous Celery task to fetch sales and recalculate food costs.',
        request=LightspeedManualSyncSerializer,
        responses={202: {'type': 'object', 'properties': {'detail': {'type': 'string'}, 'task_id': {'type': 'string'}}}},
    )
    def post(self, request):
        serializer = LightspeedManualSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        restaurant_id = request.data.get('restaurant_id') or request.data.get('location_id')
        if not restaurant_id:
            return Response(
                {'detail': 'restaurant_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        restaurant = get_object_or_404(Restaurant, pk=restaurant_id)
        if not _check_user_restaurant_access(request.user, restaurant):
            return Response(
                {'detail': 'You do not have permission to sync this restaurant.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        config = getattr(restaurant, 'lightspeed_config', None)
        if not config or not config.is_connected:
            return Response(
                {'detail': 'Lightspeed is not connected for this restaurant.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sync_date = serializer.validated_data.get('date') or (timezone.now().date() - timedelta(days=1))
        date_str = sync_date.isoformat()

        # Import task lazily to avoid circular dependency
        from .tasks import sync_lightspeed_sales
        task_result = sync_lightspeed_sales.delay(str(config.id), date_str)

        return Response(
            {
                'detail': 'Sales sync task queued successfully.',
                'task_id': str(task_result.id) if hasattr(task_result, 'id') else None,
                'restaurant_id': str(restaurant.id),
                'location_id': str(restaurant.id),
                'date': date_str,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class LightspeedWebhookView(APIView):
    """
    Receives incoming webhook notifications from Lightspeed.
    Processes payload asynchronously via Celery.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['pos_lightspeed'],
        summary='Lightspeed webhook endpoint',
        description='Accepts webhook events from Lightspeed and dispatches them for async processing.',
        request={'application/json': {'type': 'object'}},
        responses={200: {'type': 'object', 'properties': {'status': {'type': 'string'}}}},
    )
    def post(self, request):
        payload = request.data
        logger.info("Received Lightspeed webhook payload")

        from .tasks import process_lightspeed_webhook
        process_lightspeed_webhook.delay(payload)

        return Response({'status': 'received'}, status=status.HTTP_200_OK)
