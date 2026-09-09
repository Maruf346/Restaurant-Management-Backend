from django.contrib import admin

from .models import Location, UserLocation


class UserLocationInline(admin.TabularInline):
    model = UserLocation
    extra = 1
    fields = ('user', 'assigned_by', 'assigned_at')
    readonly_fields = ('assigned_at',)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'city', 'country', 'is_active', 'created_at')
    search_fields = ('name', 'code', 'city', 'country', 'address')
    list_filter = ('is_active', 'country')
    inlines = [UserLocationInline]


@admin.register(UserLocation)
class UserLocationAdmin(admin.ModelAdmin):
    list_display = ('user', 'location', 'assigned_by', 'assigned_at')
    list_filter = ('location', 'assigned_at')
    search_fields = ('user__email', 'user__full_name', 'location__name')
