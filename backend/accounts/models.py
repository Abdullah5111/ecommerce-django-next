from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email_verified = models.BooleanField(default=False)

    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.username


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses"
    )
    label = models.CharField(max_length=50, blank=True)
    recipient = models.CharField(max_length=120)
    phone = models.CharField(max_length=30, blank=True)
    line1 = models.CharField(max_length=200)
    line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=2, default="US")
    is_default_shipping = models.BooleanField(default=False)
    is_default_billing = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default_shipping", "-updated_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default_shipping:
            Address.objects.filter(
                user=self.user, is_default_shipping=True
            ).exclude(pk=self.pk).update(is_default_shipping=False)
        if self.is_default_billing:
            Address.objects.filter(
                user=self.user, is_default_billing=True
            ).exclude(pk=self.pk).update(is_default_billing=False)

    def as_text(self) -> str:
        city_line = f"{self.city}, {self.state} {self.postal_code}".strip(", ")
        bits = [self.recipient, self.line1, self.line2, city_line, self.country]
        return "\n".join(b for b in bits if b)

    def __str__(self):
        return f"{self.label or 'Address'} ({self.user})"
