from django.contrib import admin

from .models import LightspeedConfig


@admin.register(LightspeedConfig)
class LightspeedConfigAdmin(admin.ModelAdmin):
    list_display = (
        'location',
        'status',
        'requires_reauthorization',
        'auto_sync_enabled',
        'account_id',
        'business_location_id',
        'last_synced_at',
        'updated_at',
    )
    list_filter = ('status', 'requires_reauthorization', 'auto_sync_enabled')
    search_fields = ('location__name', 'account_id', 'business_location_id')
    readonly_fields = (
        'created_at',
        'updated_at',
        'last_synced_at',
        'last_error_at',
        'token_expires_at',
    )
    # Hide sensitive raw tokens by excluding them or grouping them in a collapsed section
    fieldsets = (
        ('Location & Status', {
            'fields': (
                'location',
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
