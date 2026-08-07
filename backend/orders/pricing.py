from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

from coupons.models import Coupon

TWO_PLACES = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass
class Line:
    """One priced cart/order line; a set `variant` supplies the unit price."""

    product: object
    quantity: int
    variant: object = None

    @property
    def unit_price(self) -> Decimal:
        return self.variant.effective_price if self.variant is not None else self.product.price


def _to_lines(items) -> list:
    """Accept Line objects, 3-tuples (product, qty, variant) or 2-tuples (product, qty)."""
    lines = []
    for it in items:
        if isinstance(it, Line):
            lines.append(it)
        elif len(it) == 3:
            lines.append(Line(it[0], it[1], it[2]))
        else:
            lines.append(Line(it[0], it[1]))
    return lines


@dataclass
class PriceQuote:
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    shipping_total: Decimal
    grand_total: Decimal
    coupon_code: str | None
    coupon_error: str | None


def _subtotal(lines) -> Decimal:
    total = Decimal("0")
    for line in lines:
        total += line.unit_price * Decimal(line.quantity)
    return money(total)


def _bogo_discount(coupon, eligible) -> Decimal:
    units = []
    for line in eligible:
        units.extend([line.unit_price] * line.quantity)
    units.sort()  # cheapest first receive the discount
    buy = coupon.buy_quantity or 1
    get = coupon.get_quantity or 1
    group = buy + get
    free_count = (len(units) // group) * get
    discounted = units[:free_count]
    total = sum((p * coupon.value / Decimal("100") for p in discounted), Decimal("0"))
    return money(total)


def _discount(coupon, lines) -> Decimal:
    # Eligibility is by product/category; pricing uses each line's own unit price.
    eligible = [line for line in lines if coupon.is_product_eligible(line.product)]
    elig_subtotal = sum((l.unit_price * l.quantity for l in eligible), Decimal("0"))
    if coupon.kind == Coupon.Kind.PERCENT:
        return money(elig_subtotal * coupon.value / Decimal("100"))
    if coupon.kind == Coupon.Kind.FIXED:
        # Cap at the eligible subtotal so a scoped fixed coupon can't discount
        # more than the items it applies to (an unscoped one caps at the whole cart).
        return money(min(coupon.value, elig_subtotal))
    if coupon.kind == Coupon.Kind.BOGO:
        return _bogo_discount(coupon, eligible)
    # FREE_SHIPPING: no line discount; shipping is waived separately
    return Decimal("0.00")


def _shipping(subtotal, free_shipping) -> Decimal:
    if free_shipping or subtotal >= settings.FREE_SHIPPING_THRESHOLD:
        return Decimal("0.00")
    return money(settings.SHIPPING_FLAT_FEE)


def _tax(taxable) -> Decimal:
    """Tax on the taxable base (TAX_RATE is a percent: 8.25 → 8.25%).
    Applied to merchandise after discount, not shipping.
    """
    rate = settings.TAX_RATE
    if rate <= 0 or taxable <= 0:
        return Decimal("0.00")
    return money(taxable * rate / Decimal("100"))


def quote(items, coupon=None, user=None) -> PriceQuote:
    """Compute the authoritative price breakdown. Pure — no DB writes.
    items: Line / (product, qty, variant) / (product, qty); variant sets unit price.
    """
    lines = _to_lines(items)
    subtotal = _subtotal(lines)
    discount = Decimal("0.00")
    code = None
    error = None
    free_shipping = False

    if coupon is not None:
        # validate_for only needs product identity + quantity for its checks.
        pairs = [(l.product, l.quantity) for l in lines]
        error = coupon.validate_for(user, pairs, subtotal)
        if error is None:
            code = coupon.code
            discount = _discount(coupon, lines)
            free_shipping = coupon.kind == Coupon.Kind.FREE_SHIPPING

    shipping = _shipping(subtotal, free_shipping)
    # Floor the taxable base at 0 so an over-large discount can't make tax negative.
    taxable = subtotal - discount
    if taxable < 0:
        taxable = Decimal("0.00")
    tax = _tax(taxable)
    grand = subtotal - discount + tax + shipping
    # Defensive floor: a misconfigured coupon must never bill a negative total.
    if grand < 0:
        grand = Decimal("0.00")

    return PriceQuote(
        subtotal=subtotal,
        discount_total=money(discount),
        tax_total=tax,
        shipping_total=shipping,
        grand_total=money(grand),
        coupon_code=code,
        coupon_error=error,
    )
