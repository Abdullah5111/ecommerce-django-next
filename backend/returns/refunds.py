from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def refund_for(return_request) -> Decimal:
    """Proportional refund: each returned line's value minus its share of the
    order discount, plus the tax charged on that amount. Shipping never refunded.
    """
    order = return_request.order
    subtotal = order.subtotal
    # Tax per net dollar, to redistribute it proportionally to each returned line.
    discounted_subtotal = subtotal - order.discount_total
    tax_ratio = (
        order.tax_total / discounted_subtotal
        if discounted_subtotal > 0 and order.tax_total
        else Decimal("0")
    )
    total = Decimal("0")
    for line in return_request.lines.all():
        line_value = line.order_item.unit_price * line.quantity
        if subtotal and order.discount_total:
            discount_share = order.discount_total * (line_value / subtotal)
        else:
            discount_share = Decimal("0")
        net = line_value - discount_share
        total += net + net * tax_ratio
    return money(total)
