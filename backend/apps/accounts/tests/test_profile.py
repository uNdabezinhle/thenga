"""Customer profile fields the settings screen saves."""
from __future__ import annotations

from django.test import Client, TestCase

from apps.accounts.models import User, UserProfile
from apps.accounts.tokens import issue_token_pair


class ProfileSettingsTests(TestCase):
    def setUp(self):
        self.jordan = User.objects.create_user(
            email="jordan@northbound.test",
            username="jordan",
            password="correct-horse-42",
            email_verified=True,
        )
        self.other = User.objects.create_user(
            email="other@test.local",
            username="other",
            password="correct-horse-42",
            email_verified=True,
        )

    def _auth(self, user):
        tokens = issue_token_pair(user)
        return {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}"}

    def test_customer_saves_phone_and_date_of_birth(self):
        profile = UserProfile.objects.get(user=self.jordan)
        client = Client()
        saved = client.patch(
            f"/api/v1/auth/profiles/{profile.id}/",
            data='{"phone_number":"0825550101","date_of_birth":"1992-04-03","first_name":"Jordan"}',
            content_type="application/json",
            **self._auth(self.jordan),
        )
        self.assertEqual(saved.status_code, 200, saved.content)
        self.assertEqual(saved.json()["phone_number"], "0825550101")
        self.assertEqual(saved.json()["date_of_birth"], "1992-04-03")
        self.jordan.refresh_from_db()
        self.assertEqual(self.jordan.phone_number, "0825550101")
        other_profile = UserProfile.objects.get(user=self.other)
        denied = client.patch(
            f"/api/v1/auth/profiles/{other_profile.id}/",
            data='{"phone_number":"000"}',
            content_type="application/json",
            **self._auth(self.jordan),
        )
        self.assertEqual(denied.status_code, 404, denied.content)
