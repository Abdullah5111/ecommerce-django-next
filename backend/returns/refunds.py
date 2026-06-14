from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def refund_for(return_request) -> Decimal:
    """Proportional refund: line value minus its share of the order discount.

    Shipping is never refunded.
    """
    order = return_request.order
    subtotal = order.subtotal
    total = Decimal("0")
    for line in return_request.lines.all():
        line_value = line.order_item.unit_price * line.quantity
        if subtotal and order.discount_total:
            discount_share = order.discount_total * (line_value / subtotal)
        else:
            discount_share = Decimal("0")
        total += line_value - discount_share
    return money(total)
