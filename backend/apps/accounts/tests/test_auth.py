"""Mandatory auth tests — docs/05-test-strategy.md §4.3."""
from __future__ import annotations

import json

from django.test import Client, TestCase

from apps.accounts.models import MFADevice, Role, User, UserRole
from apps.accounts.tokens import issue_token_pair


class AuthAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(
            email="cust@test.local",
            username="cust",
            password="correct-horse-42",
            email_verified=True,
        )
        self.admin = User.objects.create_user(
            email="admin@test.local",
            username="adminu",
            password="correct-horse-42",
            email_verified=True,
            is_staff=True,
        )
        admin_role, _ = Role.objects.get_or_create(name="Administrator")
        UserRole.objects.get_or_create(user=self.admin, role=admin_role)

    def _auth(self, user, mfa=False):
        tokens = issue_token_pair(user, mfa_verified=mfa)
        return {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}"}

    def test_customer_cannot_list_roles(self):
        r = self.client.get("/api/v1/auth/roles/", **self._auth(self.customer))
        self.assertIn(r.status_code, (403, 401))

    def test_customer_cannot_create_permission(self):
        role = Role.objects.create(name="Evil")
        r = self.client.post(
            "/api/v1/auth/permissions/",
            data=json.dumps(
                {
                    "role": role.id,
                    "module": "admin",
                    "can_create": True,
                    "can_read": True,
                    "can_update": True,
                    "can_delete": True,
                }
            ),
            content_type="application/json",
            **self._auth(self.customer),
        )
        self.assertIn(r.status_code, (403, 401))

    def test_customer_cannot_modify_role(self):
        role = Role.objects.create(name="Staffish")
        r = self.client.patch(
            f"/api/v1/auth/roles/{role.id}/",
            data=json.dumps({"name": "Hacked"}),
            content_type="application/json",
            **self._auth(self.customer),
        )
        self.assertIn(r.status_code, (403, 401))

    def test_password_only_token_is_pre_auth(self):
        import pyotp

        secret = "JBSWY3DPEHPK3PXP"
        MFADevice.objects.create(
            user=self.customer,
            device_type=MFADevice.DeviceType.AUTHENTICATOR,
            secret=secret,
            is_active=True,
        )
        r = self.client.post(
            "/api/v1/auth/token/",
            data=json.dumps(
                {"email": "cust@test.local", "password": "correct-horse-42"}
            ),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body.get("mfa_required"))
        self.assertIn("pre_auth_token", body)

        pre = body["pre_auth_token"]
        denied = self.client.get(
            "/api/v1/auth/profiles/",
            HTTP_AUTHORIZATION=f"Bearer {pre}",
        )
        self.assertIn(denied.status_code, (401, 403))

        code = pyotp.TOTP(secret).now()
        ok = self.client.post(
            "/api/v1/auth/mfa/verify/",
            data=json.dumps(
                {
                    "code": code,
                    "device_type": "authenticator",
                    "pre_auth_token": pre,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {pre}",
        )
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertTrue(ok.json().get("mfa_verified"))

    def test_register_and_verify_email(self):
        from apps.accounts.models import EmailVerificationToken

        r = self.client.post(
            "/api/v1/auth/users/",
            data=json.dumps(
                {
                    "email": "new@test.local",
                    "username": "newuser",
                    "password": "correct-horse-42",
                    "password2": "correct-horse-42",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertFalse(body["email_verified"])
        token = EmailVerificationToken.objects.get(user__email="new@test.local").token

        v = self.client.post(
            "/api/v1/auth/email/verify/",
            data=json.dumps({"token": token}),
            content_type="application/json",
        )
        self.assertEqual(v.status_code, 200)
        user = User.objects.get(email="new@test.local")
        self.assertTrue(user.email_verified)

    def test_password_reset_flow(self):
        from apps.accounts.models import PasswordResetToken

        r = self.client.post(
            "/api/v1/auth/password-reset/",
            data=json.dumps({"email": "cust@test.local"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        token = PasswordResetToken.objects.filter(
            user=self.customer, used_at__isnull=True
        ).latest("created_at").token
        r2 = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            data=json.dumps({"token": token, "new_password": "new-correct-horse-99"}),
            content_type="application/json",
        )
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(
            User.objects.get(email="cust@test.local").check_password(
                "new-correct-horse-99"
            )
        )

    def test_admin_can_list_roles(self):
        r = self.client.get("/api/v1/auth/roles/", **self._auth(self.admin, mfa=True))
        self.assertEqual(r.status_code, 200)
