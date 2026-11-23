"""Tax invoice generation — REKA-FR-ORD-013 / ECTA commercial documentation."""
from __future__ import annotations

from decimal import Decimal
from html import escape

from django.conf import settings
from django.utils import timezone

from apps.pricing.services import money_str

# South Africa standard VAT rate (prices already VAT-inclusive in catalogue)
VAT_RATE = Decimal("0.15")


def split_vat_inclusive(gross: Decimal) -> tuple[Decimal, Decimal]:
    """From VAT-inclusive total, derive net + VAT (ROUND_HALF_UP via money_str path)."""
    from apps.pricing.services import q

    gross = q(gross)
    net = q(gross / (1 + VAT_RATE))
    vat = q(gross - net)
    return net, vat


def invoice_context(order) -> dict:
    brand = getattr(settings, "REKA_SITE_BRAND_NAME", "Northbound")
    merchant = {
        "name": getattr(settings, "MERCHANT_LEGAL_NAME", f"{brand} (Pty) Ltd"),
        "vat_number": getattr(settings, "MERCHANT_VAT_NUMBER", "4XXXXXXXXX"),
        "address": getattr(
            settings,
            "MERCHANT_ADDRESS",
            "1 Dock Road, V&A Waterfront, Cape Town, 8001",
        ),
        "email": getattr(settings, "DEFAULT_FROM_EMAIL", "orders@northbound.test"),
    }
    sub_net, sub_vat = split_vat_inclusive(order.subtotal)
    grand_net, grand_vat = split_vat_inclusive(order.grand_total)
    lines = []
    for item in order.items.all():
        line_net, line_vat = split_vat_inclusive(item.line_total)
        lines.append(
            {
                "name": item.product_name_snapshot,
                "sku": item.sku_snapshot,
                "qty": item.quantity,
                "unit": money_str(item.unit_price),
                "line_total": money_str(item.line_total),
                "line_net": money_str(line_net),
                "line_vat": money_str(line_vat),
            }
        )
    issued = timezone.now()
    return {
        "brand": brand,
        "merchant": merchant,
        "order": order,
        "reference": order.reference,
        "invoice_number": f"INV-{order.reference}",
        "issued_at": issued.strftime("%Y-%m-%d %H:%M UTC"),
        "customer_email": order.user.email,
        "ship_to": order.shipping_address_text
        or ("Collected in store" if getattr(order, "channel", "") == "pos" else "—"),
        "document_label": "Counter sale" if getattr(order, "channel", "") == "pos" else "Tax invoice",
        "lines": lines,
        "currency": order.currency,
        "subtotal": money_str(order.subtotal),
        "discount": money_str(order.discount_total),
        "shipping": money_str(order.shipping_total),
        "grand_total": money_str(order.grand_total),
        "vat_amount": money_str(grand_vat),
        "net_amount": money_str(grand_net),
        "vat_rate_pct": "15",
        "status": order.status,
        "payment_method": order.payment_method,
    }


def invoice_payload(order) -> dict:
    """JSON form of the tax invoice for clients that do not render HTML."""
    ctx = invoice_context(order)
    merchant = ctx["merchant"]
    return {
        "brand": ctx["brand"],
        "invoice_number": ctx["invoice_number"],
        "issued_at": ctx["issued_at"],
        "status": ctx["status"],
        "customer_email": ctx["customer_email"],
        "ship_to": ctx["ship_to"],
        "payment_method": ctx["payment_method"] or "",
        "merchant": {
            "name": merchant["name"],
            "vat_number": merchant["vat_number"],
            "address": merchant["address"],
        },
        "lines": ctx["lines"],
        "currency": ctx["currency"],
        "subtotal": ctx["subtotal"],
        "discount": ctx["discount"],
        "shipping": ctx["shipping"],
        "net_amount": ctx["net_amount"],
        "vat_amount": ctx["vat_amount"],
        "vat_rate_pct": ctx["vat_rate_pct"],
        "grand_total": ctx["grand_total"],
    }


def render_invoice_html(order) -> str:
    ctx = invoice_context(order)
    rows = "".join(
        f"""<tr>
          <td>{escape(r['name'])}<div class="sku">{escape(r['sku'])}</div></td>
          <td class="num">{r['qty']}</td>
          <td class="num mono">{r['unit']}</td>
          <td class="num mono">{r['line_total']}</td>
        </tr>"""
        for r in ctx["lines"]
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(ctx['document_label'])} {escape(ctx['invoice_number'])}</title>
<style>
  :root {{ --ink:#101512; --mute:#6E7B72; --hair:#D8DCD3; --forest:#0E2A22; --lime:#C8F751; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; color:var(--ink); margin:0; padding:32px; background:#F3F4EF; }}
  .sheet {{ max-width:720px; margin:0 auto; background:#fff; border:1px solid var(--hair); border-radius:12px; padding:36px 40px; }}
  h1 {{ font-size:22px; margin:0 0 4px; letter-spacing:-.02em; }}
  .tag {{ display:inline-block; background:var(--forest); color:var(--lime); font-size:11px; font-weight:600;
    letter-spacing:.08em; text-transform:uppercase; padding:4px 8px; border-radius:4px; margin-bottom:16px; }}
  .meta {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; margin:20px 0 28px; font-size:13px; color:var(--mute); line-height:1.55; }}
  .meta strong {{ display:block; color:var(--ink); margin-bottom:4px; font-size:12px; letter-spacing:.04em; text-transform:uppercase; }}
  table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
  th {{ text-align:left; font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:var(--mute);
    border-bottom:2px solid var(--hair); padding:8px 6px; }}
  td {{ padding:10px 6px; border-bottom:1px solid var(--hair); vertical-align:top; }}
  .sku {{ font-size:11px; color:var(--mute); font-family:ui-monospace,monospace; margin-top:2px; }}
  .num {{ text-align:right; }}
  .mono {{ font-family:ui-monospace,monospace; }}
  .totals {{ margin-top:20px; margin-left:auto; width:280px; font-size:13px; font-family:ui-monospace,monospace; }}
  .totals .ln {{ display:flex; justify-content:space-between; padding:4px 0; color:#3D4A42; }}
  .totals .ln.big {{ font-size:16px; font-weight:700; color:var(--ink); border-top:1px solid var(--hair); margin-top:8px; padding-top:10px; }}
  .foot {{ margin-top:32px; font-size:11.5px; color:var(--mute); line-height:1.5; border-top:1px solid var(--hair); padding-top:14px; }}
  @media print {{ body {{ background:#fff; padding:0; }} .sheet {{ border:none; }} }}
</style>
</head>
<body>
  <div class="sheet">
    <span class="tag">{escape(ctx['document_label'])}</span>
    <h1>{escape(ctx['brand'])}</h1>
    <p style="margin:0;color:var(--mute);font-size:13px">{escape(ctx['merchant']['name'])} · VAT {escape(ctx['merchant']['vat_number'])}</p>
    <p style="margin:4px 0 0;color:var(--mute);font-size:12.5px">{escape(ctx['merchant']['address'])}</p>

    <div class="meta">
      <div>
        <strong>Invoice</strong>
        {escape(ctx['invoice_number'])}<br>
        Issued {escape(ctx['issued_at'])}<br>
        Order status: {escape(ctx['status'])}
      </div>
      <div>
        <strong>Bill / ship to</strong>
        {escape(ctx['customer_email'])}<br>
        {escape(ctx['ship_to'])}<br>
        Payment: {escape(ctx['payment_method'] or '—')}
      </div>
    </div>

    <table>
      <thead>
        <tr><th>Description</th><th class="num">Qty</th><th class="num">Unit</th><th class="num">Amount</th></tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>

    <div class="totals">
      <div class="ln"><span>Subtotal (incl. VAT)</span><span>{ctx['currency']} {ctx['subtotal']}</span></div>
      <div class="ln"><span>Discount</span><span>− {ctx['currency']} {ctx['discount']}</span></div>
      <div class="ln"><span>Delivery</span><span>{ctx['currency']} {ctx['shipping']}</span></div>
      <div class="ln"><span>Net (excl. VAT)</span><span>{ctx['currency']} {ctx['net_amount']}</span></div>
      <div class="ln"><span>VAT @ {ctx['vat_rate_pct']}%</span><span>{ctx['currency']} {ctx['vat_amount']}</span></div>
      <div class="ln big"><span>Total due</span><span>{ctx['currency']} {ctx['grand_total']}</span></div>
    </div>

    <p class="foot">
      Prices include VAT at {ctx['vat_rate_pct']}% where applicable. This document is a tax invoice for
      {escape(ctx['merchant']['name'])}. Retain for your records. ECTA s43 disclosures were presented at checkout.
      Cooling-off rights may apply under ECTA s44 subject to s42(2) exclusions.
    </p>
  </div>
</body>
</html>
"""


def render_invoice_text(order) -> str:
    ctx = invoice_context(order)
    lines = "\n".join(
        f"  {r['qty']}× {r['name']} ({r['sku']})  {ctx['currency']} {r['line_total']}"
        for r in ctx["lines"]
    )
    return (
        f"TAX INVOICE {ctx['invoice_number']}\n"
        f"{ctx['merchant']['name']}  VAT {ctx['merchant']['vat_number']}\n"
        f"Issued {ctx['issued_at']}\n"
        f"Customer {ctx['customer_email']}\n"
        f"Ship to: {ctx['ship_to']}\n\n"
        f"{lines}\n\n"
        f"Subtotal  {ctx['currency']} {ctx['subtotal']}\n"
        f"Discount  {ctx['currency']} {ctx['discount']}\n"
        f"Shipping  {ctx['currency']} {ctx['shipping']}\n"
        f"VAT {ctx['vat_rate_pct']}%  {ctx['currency']} {ctx['vat_amount']}\n"
        f"TOTAL     {ctx['currency']} {ctx['grand_total']}\n"
    )
