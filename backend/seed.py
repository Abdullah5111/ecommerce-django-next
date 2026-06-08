"""Seed the database with sample hierarchical categories and products.

Usage:
    python manage.py shell < seed.py
"""
import hashlib
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Count

from products.models import Category, Product, ProductImage, Review

# Hierarchy: top-level -> {child: [products]}
# Product tuple: (name, description, price, stock, [image_urls], on_sale)
# Featured: roughly half the catalog, picking one product per top-level
# parent category for variety. Deterministic + idempotent.
FEATURED_NAMES = {
    "Wireless Headphones",   # Electronics
    "Cotton T-Shirt",        # Apparel
    "French Press",          # Home & Kitchen
    "Designing Data-Intensive Applications",  # Books
}

HIERARCHY = {
    "Electronics": {
        "Audio": [
            ("Wireless Headphones", "Bluetooth 5.3, 30hr battery, ANC.", 89.99, 50,
             [
                 "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600",
                 "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=600",
                 "https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=600",
             ], True),
        ],
        "Computers & Accessories": [
            ("Mechanical Keyboard", "75% layout, hot-swappable, RGB.", 129.00, 30,
             [
                 "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600",
                 "https://images.unsplash.com/photo-1561112078-7d24e04c3407?w=600",
                 "https://images.unsplash.com/photo-1595225476474-87563907a212?w=600",
             ], False),
            ("4K Webcam", "Auto-focus, dual mic, USB-C.", 79.50, 40,
             [
                 "https://images.unsplash.com/photo-1587825140708-dfaf72ae4b04?w=600",
                 "https://images.unsplash.com/photo-1622979135225-d2ba269cf1ac?w=600",
             ], True),
        ],
    },
    "Apparel": {
        "Tops": [
            ("Cotton T-Shirt", "100% organic cotton, unisex fit.", 24.00, 100,
             [
                 "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600",
                 "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?w=600",
                 "https://images.unsplash.com/photo-1622445275576-721325763afe?w=600",
             ], False),
        ],
        "Outerwear": [
            ("Denim Jacket", "Classic blue, mid-weight.", 89.00, 25,
             [
                 "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=600",
                 "https://images.unsplash.com/photo-1543076447-215ad9ba6923?w=600",
                 "https://images.unsplash.com/photo-1604644401890-0bd678c83788?w=600",
             ], True),
        ],
    },
    "Home & Kitchen": {
        "Drinkware": [
            ("Ceramic Mug Set", "Set of 4, microwave safe.", 32.00, 60,
             [
                 "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?w=600",
                 "https://images.unsplash.com/photo-1493857671505-72967e2e2760?w=600",
             ], False),
        ],
        "Coffee & Tea": [
            ("French Press", "1L glass carafe, stainless filter.", 45.00, 35,
             [
                 "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600",
                 "https://images.unsplash.com/photo-1521017432531-fbd92d768814?w=600",
                 "https://images.unsplash.com/photo-1542317854-cd8d8e4f4eaa?w=600",
             ], True),
        ],
    },
    "Books": {
        "Programming": [
            ("The Pragmatic Programmer", "20th anniversary edition.", 38.00, 80,
             [
                 "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=600",
                 "https://images.unsplash.com/photo-1512820790803-83ca734da794?w=600",
             ], False),
            ("Designing Data-Intensive Applications", "Martin Kleppmann.", 52.00, 45,
             [
                 "https://images.unsplash.com/photo-1532012197267-da84d127e765?w=600",
                 "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?w=600",
                 "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?w=600",
             ], True),
        ],
    },
}


def _digest_byte(name: str, index: int) -> int:
    return hashlib.md5(name.encode()).digest()[index]


def deterministic_rating(name: str):
    """rating_avg in [3.5, 4.9], rating_count in [20, 800], deterministic by name."""
    b0 = _digest_byte(name, 0)
    b1 = _digest_byte(name, 1)
    # rating_avg: 3.5 + (b0 % 141) / 100  -> 3.50 .. 4.90
    avg = Decimal("3.50") + (Decimal(b0 % 141) / Decimal(100))
    avg = avg.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    # rating_count: 20 + (b1 * b0) % 781 -> 20 .. 800
    count = 20 + ((b0 * b1) % 781)
    return avg, count


SPECS_BY_NAME = {
    "Wireless Headphones": {
        "Battery": "30h",
        "Bluetooth": "5.3",
        "Noise Cancellation": "Active",
        "Weight": "240 g",
        "Driver": "40 mm dynamic",
    },
    "Mechanical Keyboard": {
        "Layout": "75%",
        "Switches": "Hot-swappable",
        "Backlight": "RGB",
        "Connection": "USB-C / Bluetooth",
        "Keycaps": "PBT double-shot",
    },
    "4K Webcam": {
        "Resolution": "4K @ 30fps",
        "Focus": "Auto",
        "Microphone": "Dual stereo",
        "Connection": "USB-C",
        "Field of View": "90 deg",
    },
    "Cotton T-Shirt": {
        "Material": "100% organic cotton",
        "Fit": "Unisex regular",
        "Weight": "180 gsm",
        "Care": "Machine wash cold",
        "Origin": "Portugal",
    },
    "Denim Jacket": {
        "Material": "100% cotton denim",
        "Weight": "Mid-weight",
        "Closure": "Button front",
        "Pockets": "4",
        "Care": "Machine wash cold",
    },
    "Ceramic Mug Set": {
        "Material": "Stoneware ceramic",
        "Capacity": "350 ml",
        "Set Size": "4 pieces",
        "Microwave Safe": "Yes",
        "Dishwasher Safe": "Yes",
    },
    "French Press": {
        "Capacity": "1 L",
        "Carafe": "Borosilicate glass",
        "Filter": "Stainless steel",
        "Frame": "Brushed steel",
        "Dishwasher Safe": "Yes",
    },
    "The Pragmatic Programmer": {
        "Edition": "20th Anniversary",
        "Pages": "352",
        "Format": "Hardcover",
        "Publisher": "Addison-Wesley",
        "Language": "English",
    },
    "Designing Data-Intensive Applications": {
        "Author": "Martin Kleppmann",
        "Pages": "616",
        "Format": "Paperback",
        "Publisher": "O'Reilly",
        "Language": "English",
    },
}

GENERIC_SPECS = {
    "Material": "Mixed",
    "Origin": "Imported",
    "Warranty": "1 year",
}


def specs_for(product_name: str) -> dict:
    return SPECS_BY_NAME.get(product_name, dict(GENERIC_SPECS))


SAMPLE_REVIEW_USERS = [
    "Alex P.", "Jordan M.", "Sam K.", "Taylor R.", "Casey L.",
    "Morgan S.", "Riley J.", "Avery N.", "Quinn D.", "Hayden B.",
    "Reese T.", "Sky W.", "Drew H.", "Parker V.",
]

REVIEW_TEMPLATES = [
    ("Excellent value", "Exactly as described. Very happy with this purchase."),
    ("Great quality", "Solid build and works perfectly out of the box."),
    ("Highly recommend", "I would buy this again. No regrets."),
    ("Pretty good", "Mostly meets expectations, minor nitpicks aside."),
    ("Love it", "Use it every day. Quality is noticeably better than what I had before."),
    ("Solid pick", "Good price for the quality you get."),
    ("Worth it", "Took a chance and glad I did. Recommended."),
    ("Decent", "Does the job. Nothing fancy but reliable."),
]


def seed_reviews_for(product):
    """Create deterministic, idempotent reviews for a product."""
    name = product.name
    n = (_digest_byte(name, 3) % 4) + 3  # 3..6 reviews
    for i in range(n):
        idx_user = _digest_byte(name, 4 + i) % len(SAMPLE_REVIEW_USERS)
        idx_tmpl = _digest_byte(name, 10 + i) % len(REVIEW_TEMPLATES)
        # Bias rating high: 3..5, weighted toward 5.
        r_byte = _digest_byte(name, 6 + i) % 10
        if r_byte < 6:
            rating = 5
        elif r_byte < 9:
            rating = 4
        else:
            rating = 3
        author = SAMPLE_REVIEW_USERS[idx_user]
        title, body = REVIEW_TEMPLATES[idx_tmpl]
        Review.objects.get_or_create(
            product=product,
            author_name=author,
            title=title,
            defaults={
                "user": None,
                "rating": rating,
                "body": body,
            },
        )


def deterministic_compare_at(name: str, price: float):
    """compare_at_price ~20-35% above price, deterministic."""
    b = _digest_byte(name, 2)
    # 1.20 .. 1.35
    multiplier = Decimal("1.20") + (Decimal(b % 16) / Decimal(100))
    cap = (Decimal(str(price)) * multiplier).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return cap


def run():
    created = 0
    for parent_name, children in HIERARCHY.items():
        parent, _ = Category.objects.get_or_create(name=parent_name)
        parent.save()
        for child_name, products in children.items():
            child, _ = Category.objects.get_or_create(
                name=child_name,
                defaults={"parent": parent},
            )
            if child.parent_id != parent.id:
                child.parent = parent
                child.save()
            for name, desc, price, stock, images, on_sale in products:
                rating_avg, rating_count = deterministic_rating(name)
                compare_at = deterministic_compare_at(name, price) if on_sale else None
                is_featured = name in FEATURED_NAMES
                specs = specs_for(name)
                product, p_created = Product.objects.get_or_create(
                    name=name,
                    defaults={
                        "category": child,
                        "description": desc,
                        "price": price,
                        "compare_at_price": compare_at,
                        "rating_avg": rating_avg,
                        "rating_count": rating_count,
                        "stock": stock,
                        "image_url": images[0],
                        "is_featured": is_featured,
                        "specifications": specs,
                    },
                )
                if not p_created:
                    if product.category_id != child.id:
                        product.category = child
                    product.compare_at_price = compare_at
                    product.rating_avg = rating_avg
                    product.rating_count = rating_count
                    product.is_featured = is_featured
                    product.specifications = specs
                    product.save()

                # Image rows: only create if product has zero existing images.
                if not product.images.exists():
                    for idx, url in enumerate(images):
                        ProductImage.objects.create(
                            product=product,
                            url=url,
                            alt=f"{name} image {idx + 1}",
                            sort_order=idx,
                        )

                # Seed reviews and recompute aggregate explicitly.
                seed_reviews_for(product)
                agg = product.reviews.aggregate(avg=Avg("rating"), n=Count("id"))
                product.rating_avg = round(agg["avg"] or 0, 2)
                product.rating_count = agg["n"] or 0
                product.save(update_fields=["rating_avg", "rating_count"])

                if p_created:
                    created += 1
    print(f"Seed complete. {created} new product(s) created.")


run()
