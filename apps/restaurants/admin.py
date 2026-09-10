from django.contrib import admin

from .models import Restaurant, UserRestaurant


class UserRestaurantInline(admin.TabularInline):
    model = UserRestaurant
    extra = 1
    fields = ('user', 'assigned_by', 'assigned_at')
    readonly_fields = ('assigned_at',)


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'city', 'country', 'is_active', 'created_at')
    search_fields = ('name', 'code', 'city', 'country', 'address')
    list_filter = ('is_active', 'country')
    inlines = [UserRestaurantInline]


@admin.register(UserRestaurant)
class UserRestaurantAdmin(admin.ModelAdmin):
    list_display = ('user', 'restaurant', 'assigned_by', 'assigned_at')
    list_filter = ('restaurant', 'assigned_at')
    search_fields = ('user__email', 'user__full_name', 'restaurant__name')
