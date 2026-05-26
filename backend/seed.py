"""Seed the database with sample categories and products.

Usage:
    python manage.py shell < seed.py
"""
from products.models import Category, Product

SAMPLE = {
    "Electronics": [
        ("Wireless Headphones", "Bluetooth 5.3, 30hr battery, ANC.", 89.99, 50,
         "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600"),
        ("Mechanical Keyboard", "75% layout, hot-swappable, RGB.", 129.00, 30,
         "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600"),
        ("4K Webcam", "Auto-focus, dual mic, USB-C.", 79.50, 40,
         "https://images.unsplash.com/photo-1587825140708-dfaf72ae4b04?w=600"),
    ],
    "Apparel": [
        ("Cotton T-Shirt", "100% organic cotton, unisex fit.", 24.00, 100,
         "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600"),
        ("Denim Jacket", "Classic blue, mid-weight.", 89.00, 25,
         "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=600"),
    ],
    "Home & Kitchen": [
        ("Ceramic Mug Set", "Set of 4, microwave safe.", 32.00, 60,
         "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?w=600"),
        ("French Press", "1L glass carafe, stainless filter.", 45.00, 35,
         "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600"),
    ],
    "Books": [
        ("The Pragmatic Programmer", "20th anniversary edition.", 38.00, 80,
         "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=600"),
        ("Designing Data-Intensive Applications", "Martin Kleppmann.", 52.00, 45,
         "https://images.unsplash.com/photo-1532012197267-da84d127e765?w=600"),
    ],
}


def run():
    created = 0
    for cat_name, products in SAMPLE.items():
        category, _ = Category.objects.get_or_create(name=cat_name)
        for name, desc, price, stock, image in products:
            _, was_created = Product.objects.get_or_create(
                name=name,
                defaults={
                    "category": category,
                    "description": desc,
                    "price": price,
                    "stock": stock,
                    "image_url": image,
                },
            )
            if was_created:
                created += 1
    print(f"Seed complete. {created} new product(s) created.")


run()
