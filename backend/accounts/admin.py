from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Address, User

admin.site.register(User, UserAdmin)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "recipient", "city", "country", "is_default_shipping")
