from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'full_name', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Extra Info', {'fields': ('full_name',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Extra Info', {'fields': ('email', 'full_name')}),
    )
