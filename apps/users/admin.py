from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'full_name', 'role', 'password_change_required', 'is_staff', 'is_active')
    list_filter = ('role', 'password_change_required', 'is_staff', 'is_active')
    search_fields = ('email', 'full_name', 'username')
    ordering = ('email',)

    fieldsets = UserAdmin.fieldsets + (
        ('ProfitPlate Role & Security', {
            'fields': ('role', 'password_change_required'),
        }),
        ('Extra Info', {
            'fields': ('full_name',),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('ProfitPlate Role & Security', {
            'fields': ('role', 'password_change_required'),
        }),
        ('Extra Info', {
            'fields': ('email', 'full_name'),
        }),
    )
