import json
import os
import uuid

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "reka.settings")
django.setup()

from django.test import Client  # noqa: E402

c = Client()
sid = str(uuid.uuid4())
h = {"HTTP_X_CART_SESSION": sid, "HTTP_X_APP_VERSION": "1.0.0"}

r = c.get("/api/v1/products/", **h)
data = r.json()
results = data.get("results", data if isinstance(data, list) else [])
print("products", r.status_code, len(results))

r = c.post(
    "/api/v1/auth/token/",
    data=json.dumps(
        {"email": "jordan@northbound.test", "password": "correct-horse-42"}
    ),
    content_type="application/json",
    **h,
)
print("login", r.status_code, r.json())
pre = r.json()["pre_auth_token"]

r = c.post(
    "/api/v1/auth/mfa/verify/",
    data=json.dumps(
        {
            "code": "123456",
            "device_type": "authenticator",
            "pre_auth_token": pre,
        }
    ),
    content_type="application/json",
    HTTP_AUTHORIZATION=f"Bearer {pre}",
    **h,
)
print("mfa", r.status_code, list(r.json().keys()), r.json().get("mfa_verified"))
tokens = r.json()
auth = {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}", **h}

r = c.get("/api/v1/products/1/", **auth)
p = r.json()
v = next(x for x in p["variants"] if int(x["stock"]) > 0)
print("product", p["name"], "variant", v["id"])

r = c.post(
    "/api/v1/cart/cart/add_item/",
    data=json.dumps({"product": 1, "variant": v["id"], "quantity": 1}),
    content_type="application/json",
    **h,
)
print("add guest", r.status_code, r.json().get("total_items"), r.json().get("totals"))

r = c.post(
    "/api/v1/cart/cart/apply_discount/",
    data=json.dumps({"code": "DISCOUNT20"}),
    content_type="application/json",
    **h,
)
print("discount", r.status_code, r.json().get("totals"))

# guest update qty
item_id = r.json()["items"][0]["id"]
r = c.post(
    f"/api/v1/cart/cart/items/{item_id}/update/",
    data=json.dumps({"quantity": 2}),
    content_type="application/json",
    **h,
)
print("guest update", r.status_code, r.json().get("total_items"))

r = c.post(
    "/api/v1/cart/cart/transfer_cart/",
    data=json.dumps({"session_id": sid}),
    content_type="application/json",
    **auth,
)
print("transfer", r.status_code, r.json().get("total_items"), r.json().get("totals"))

r = c.post(
    "/api/v1/orders/",
    data=json.dumps({"payment_method": "card", "address": "14 Harbour Lane"}),
    content_type="application/json",
    HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    **auth,
)
body = r.json()
print(
    "order",
    r.status_code,
    body.get("reference"),
    body.get("status"),
    body.get("grand_total"),
    (body.get("payment") or {}).get("redirect_url", "")[:60],
    body if r.status_code >= 400 else "",
)
ref = body.get("reference")
if ref:
    r = c.post(
        "/api/v1/payments/sandbox/complete/",
        data=json.dumps({"order_reference": ref}),
        content_type="application/json",
        **auth,
    )
    print("pay", r.status_code, r.json())
    r = c.post(
        f"/api/v1/orders/{ref}/advance/",
        data="{}",
        content_type="application/json",
        **auth,
    )
    print("advance", r.status_code, r.json().get("status"), r.json().get("tracking_stage"))
