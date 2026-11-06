"""Seed a small Afia demo store for local end-to-end testing."""
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models.inventory import InventoryItem
from app.models.products import Product, Store
from app.models.users import Merchant


def main() -> None:
    with Session(get_engine()) as session:
        merchant = session.exec(select(Merchant).where(Merchant.slug == "afia-demo-merchant")).first()
        if merchant is None:
            merchant = Merchant(name="Afia Demo Merchant", slug="afia-demo-merchant", email="merchant@example.com", username="demo-merchant")
            session.add(merchant)
            session.commit()
            session.refresh(merchant)

        store = session.exec(select(Store).where(Store.slug == "demo-store")).first()
        if store is None:
            store = Store(merchant_id=merchant.id, name="Afia Demo Store", slug="demo-store", description="A demo store for Afia's USA₮ shopping flow", category="furniture", template_id="luxury-furniture", sections_config={"home": []}, theme_config={}, settings_config={"currency": "USD"})
            session.add(store)
            session.commit()
            session.refresh(store)

        products = [
            ("Lagos Executive Desk", "lagos-executive-desk", "A solid wood desk for a productive workspace.", 24900, "furniture", "physical", None, 10),
            ("Adire Accent Chair", "adire-accent-chair", "Handmade Nigerian textile accent chair.", 18900, "furniture", "physical", None, 8),
            ("Afia Accessibility Guide", "afia-accessibility-guide", "A downloadable guide to accessible digital commerce.", 500, "digital", "digital", "https://example.com/demo-download", 1000),
        ]
        for name, slug, description, amount, category, product_type, digital_url, stock in products:
            product = session.exec(select(Product).where(Product.store_id == store.id, Product.slug == slug)).first()
            if product is None:
                product = Product(store_id=store.id, name=name, slug=slug, description=description, amount_minor=amount, currency="USD", category=category, product_type=product_type, digital_url=digital_url)
                session.add(product)
                session.commit()
                session.refresh(product)
            inventory = session.exec(select(InventoryItem).where(InventoryItem.product_id == product.id)).first()
            if inventory is None:
                session.add(InventoryItem(product_id=product.id, available_quantity=stock))
        session.commit()
        print(f"seeded store=demo-store merchant={merchant.id}")


if __name__ == "__main__":
    main()
