from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserRole(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
    RESTAURANT_ADMIN = 'RESTAURANT_ADMIN', 'Restaurant Admin'


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        extra_fields.setdefault('username', email.split('@')[0])
        extra_fields.setdefault('role', UserRole.RESTAURANT_ADMIN)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.SUPER_ADMIN)
        extra_fields.setdefault('password_change_required', False)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True, default='')

    # Application-level role (separate from Django's is_staff / is_superuser)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.RESTAURANT_ADMIN,
    )

    # Set to True when a Super Admin creates a Restaurant Admin with a
    # temporary password. The frontend must redirect to the change-password
    # screen while this flag is True.
    password_change_required = models.BooleanField(default=False)

    # Optional profile picture — stored in MEDIA_ROOT/profile_pictures/
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        null=True,
        blank=True,
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def save(self, *args, **kwargs):
        if not self.full_name:
            names = [self.first_name, self.last_name]
            self.full_name = ' '.join(part for part in names if part).strip()
        if not self.username:
            self.username = self.email.split('@')[0]
        super().save(*args, **kwargs)

    # ── Convenience properties ─────────────────────────────────────────────

    @property
    def is_super_admin(self) -> bool:
        return self.role == UserRole.SUPER_ADMIN

    @property
    def is_restaurant_admin(self) -> bool:
        return self.role == UserRole.RESTAURANT_ADMIN

    @property
    def assigned_restaurants(self):
        from apps.restaurants.models import Restaurant
        return Restaurant.objects.filter(user_restaurants__user=self)

    def get_assigned_restaurant_ids(self):
        """Return a queryset of Restaurant PKs this user can access."""
        from apps.restaurants.models import UserRestaurant
        return UserRestaurant.objects.filter(user=self).values_list('restaurant_id', flat=True)

    # Backward-compatible aliases
    @property
    def assigned_locations(self):
        return self.assigned_restaurants

    def get_assigned_location_ids(self):
        return self.get_assigned_restaurant_ids()

    def __str__(self):
        return self.full_name or self.email
