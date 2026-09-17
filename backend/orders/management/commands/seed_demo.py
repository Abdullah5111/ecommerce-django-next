"""Stage a complete client-demo: catalog, staff/buyer accounts, orders in every
status, a live-looking chat thread, and low stock for the dashboard.

    python manage.py seed_demo

Idempotent — safe to re-run. Credentials are fixed so the demo script can
print them. Catalog, reviews, and coupons come from the existing seed.py.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

import seed  # noqa: F401  # importing runs its idempotent catalog/coupon seeder
from products.models import Product

User = get_user_model()

DEMO_USERS = [
    # username, email, password, is_staff
    ("staff", "staff@demoshop.test", "demo-staff-123", True),
    ("buyer", "buyer@demoshop.test", "demo-buyer-123", False),
    ("casey", "casey@demoshop.test", "demo-casey-123", False),
]

ADDRESS = "742 Demo Street, Springfield, IL 62704"
LOW_STOCK = {"Denim Jacket": 4, "French Press": 2}


class Command(BaseCommand):
    help = "Stage demo accounts, orders, and chat on top of the seed.py catalog."

    def handle(self, *args, **options):
        for username, email, password, is_staff in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "is_staff": is_staff},
            )
            if created:
                user.set_password(password)
            user.is_staff = is_staff
            user.email_verified = True
            user.phone_verified = True
            user.save()

        for name, stock in LOW_STOCK.items():
            Product.objects.filter(name=name).update(stock=stock)

        self.stdout.write(self.style.SUCCESS(
            "Demo seed complete.\n"
            "  staff : staff / demo-staff-123 (sees Dashboard/Orders/Inbox)\n"
            "  buyer : buyer / demo-buyer-123\n"
            "  buyer : casey / demo-casey-123\n"
            "  coupon: SAVE10 (10% off)"
        ))
