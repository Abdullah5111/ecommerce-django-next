"""Stage a complete client-demo: catalog, staff/buyer accounts, orders in every
status, a live-looking chat thread, and low stock for the dashboard.

    python manage.py seed_demo

Idempotent — safe to re-run. Credentials are fixed so the demo script can
print them. Catalog, reviews, and coupons come from the existing seed.py.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

import seed  # noqa: F401  # importing runs its idempotent catalog/coupon seeder
from chat.models import ChatMessage, ChatThread
from orders import transitions
from orders.models import Order, OrderItem
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

        buyer = User.objects.get(username="buyer")
        casey = User.objects.get(username="casey")
        staff = User.objects.get(username="staff")
        self._stage_orders(buyer)
        self._stage_orders(casey, light=True)
        self._stage_chat(buyer, staff)

        self.stdout.write(self.style.SUCCESS(
            "Demo seed complete.\n"
            "  staff : staff / demo-staff-123 (sees Dashboard/Orders/Inbox)\n"
            "  buyer : buyer / demo-buyer-123\n"
            "  buyer : casey / demo-casey-123\n"
            "  coupon: SAVE10 (10% off)"
        ))

    def _stage_orders(self, buyer, light=False):
        """One order per interesting status, built through the real transitions
        so audit events and notifications exist. Skipped once the user has any
        orders (keeps re-runs idempotent)."""
        if Order.objects.filter(user=buyer).exists():
            return
        headphones = Product.objects.get(name="Wireless Headphones")
        press = Product.objects.get(name="French Press")
        mug = Product.objects.get(name="Ceramic Mug Set")

        def new_order(product, qty=1):
            order = Order.objects.create(
                user=buyer, shipping_address=ADDRESS,
                ship_recipient=buyer.username,
                subtotal=product.price * qty, total=product.price * qty,
            )
            OrderItem.objects.create(
                order=order, product=product, quantity=qty, unit_price=product.price,
            )
            return order

        # The full happy path — the demo's "delivered" order.
        delivered = new_order(headphones)
        transitions.mark_paid(delivered)
        transitions.ship(delivered, tracking_number="1Z999AA10123456784", tracking_carrier="UPS")
        transitions.deliver(delivered)

        shipped = new_order(press, qty=2)
        transitions.mark_paid(shipped)
        transitions.ship(shipped, tracking_number="9400111899223197428490", tracking_carrier="USPS")

        paid = new_order(mug, qty=4)
        transitions.mark_paid(paid)

        transitions.cancel(new_order(mug))  # cancelled while pending

        if not light:
            pending = new_order(press)
            pending.status = Order.Status.PENDING  # already the default; explicit for clarity
            pending.save(update_fields=["status"])

    def _stage_chat(self, buyer, staff):
        thread, _ = ChatThread.objects.get_or_create(user=buyer)
        if thread.messages.exists():
            return
        ChatMessage.objects.create(
            thread=thread, sender=buyer,
            body="Hi! Is the Wireless Headphones in stock for immediate shipping?",
        )
        ChatMessage.objects.create(
            thread=thread, sender=staff,
            body="Hey! Yes — it ships same-day with free tracking. Any color preference?",
        )
        # left unread on both sides on purpose: lights up the buyer widget badge
        # AND the staff inbox badge for the demo.
