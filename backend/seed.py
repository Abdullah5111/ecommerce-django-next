"""Seed the database with sample hierarchical categories and products.

Usage:
    python manage.py shell < seed.py
"""
from products.models import Category, Product

# Hierarchy: top-level -> [(child, [products])]
# Product tuple: (name, description, price, stock, image_url)
HIERARCHY = {
    "Electronics": {
        "Audio": [
            ("Wireless Headphones", "Bluetooth 5.3, 30hr battery, ANC.", 89.99, 50,
             "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600"),
        ],
        "Computers & Accessories": [
            ("Mechanical Keyboard", "75% layout, hot-swappable, RGB.", 129.00, 30,
             "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600"),
            ("4K Webcam", "Auto-focus, dual mic, USB-C.", 79.50, 40,
             "https://images.unsplash.com/photo-1587825140708-dfaf72ae4b04?w=600"),
        ],
    },
    "Apparel": {
        "Tops": [
            ("Cotton T-Shirt", "100% organic cotton, unisex fit.", 24.00, 100,
             "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600"),
        ],
        "Outerwear": [
            ("Denim Jacket", "Classic blue, mid-weight.", 89.00, 25,
             "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=600"),
        ],
    },
    "Home & Kitchen": {
        "Drinkware": [
            ("Ceramic Mug Set", "Set of 4, microwave safe.", 32.00, 60,
             "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?w=600"),
        ],
        "Coffee & Tea": [
            ("French Press", "1L glass carafe, stainless filter.", 45.00, 35,
             "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600"),
        ],
    },
    "Books": {
        "Programming": [
            ("The Pragmatic Programmer", "20th anniversary edition.", 38.00, 80,
             "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=600"),
            ("Designing Data-Intensive Applications", "Martin Kleppmann.", 52.00, 45,
             "https://images.unsplash.com/photo-1532012197267-da84d127e765?w=600"),
        ],
    },
}


def run():
    created = 0
    for parent_name, children in HIERARCHY.items():
        parent, _ = Category.objects.get_or_create(name=parent_name)
        # Re-save in case it was a pre-existing flat category — ensures full_slug/level are set.
        parent.save()
        for child_name, products in children.items():
            child, was_created = Category.objects.get_or_create(
                name=child_name,
                defaults={"parent": parent},
            )
            # If it existed without a parent, attach it now.
            if child.parent_id != parent.id:
                child.parent = parent
                child.save()
            for name, desc, price, stock, image in products:
                product, p_created = Product.objects.get_or_create(
                    name=name,
                    defaults={
                        "category": child,
                        "description": desc,
                        "price": price,
                        "stock": stock,
                        "image_url": image,
                    },
                )
                # Reassign existing products to the leaf category.
                if not p_created and product.category_id != child.id:
                    product.category = child
                    product.save()
                if p_created:
                    created += 1
    print(f"Seed complete. {created} new product(s) created.")


run()
