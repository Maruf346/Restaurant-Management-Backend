from django.contrib import admin

from .models import LightspeedAppCredential, LightspeedConfig


@admin.register(LightspeedAppCredential)
class LightspeedAppCredentialAdmin(admin.ModelAdmin):
    list_display = (
        'series',
        'client_id',
        'redirect_uri',
        'api_base_url',
        'is_active',
        'updated_at',
    )
    list_filter = ('series', 'is_active')
    search_fields = ('client_id', 'redirect_uri', 'api_base_url')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Series Configuration', {
            'fields': (
                'series',
                'is_active',
            ),
        }),
        ('OAuth Credentials', {
            'fields': (
                'client_id',
                'client_secret',
                'redirect_uri',
                'scope',
            ),
        }),
        ('Endpoints', {
            'fields': (
                'auth_url',
                'token_url',
                'api_base_url',
            ),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(LightspeedConfig)
class LightspeedConfigAdmin(admin.ModelAdmin):
    list_display = (
        'restaurant',
        'series',
        'status',
        'requires_reauthorization',
        'auto_sync_enabled',
        'account_id',
        'business_location_id',
        'last_synced_at',
        'updated_at',
    )
    list_filter = ('series', 'status', 'requires_reauthorization', 'auto_sync_enabled')
    search_fields = ('restaurant__name', 'account_id', 'business_location_id')
    readonly_fields = (
        'created_at',
        'updated_at',
        'last_synced_at',
        'last_error_at',
        'token_expires_at',
    )
    # Group configurations cleanly
    fieldsets = (
        ('Restaurant & Series', {
            'fields': (
                'restaurant',
                'series',
                'status',
                'requires_reauthorization',
                'auto_sync_enabled',
            ),
        }),
        ('Lightspeed Account Info', {
            'fields': (
                'account_id',
                'business_location_id',
                'token_expires_at',
            ),
        }),
        ('Error Tracking', {
            'fields': (
                'last_error',
                'last_error_at',
                'last_synced_at',
            ),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
