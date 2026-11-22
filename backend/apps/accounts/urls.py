from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ChangePasswordView,
    EmailVerifyView,
    LoginView,
    LogoutView,
    MeView,
    MFAViewSet,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PermissionViewSet,
    ProfileViewSet,
    RegisterView,
    RekaTokenRefreshView,
    RoleViewSet,
    SocialAuthView,
    UserRoleViewSet,
)

router = DefaultRouter()
router.register("profiles", ProfileViewSet, basename="profile")
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", PermissionViewSet, basename="permission")
router.register("user-roles", UserRoleViewSet, basename="user-role")
router.register("mfa", MFAViewSet, basename="mfa")

urlpatterns = [
    path("users/", RegisterView.as_view(), name="register"),
    path("users/me/", MeView.as_view(), name="me"),
    path("users/change_password/", ChangePasswordView.as_view(), name="change-password"),
    path("token/", LoginView.as_view(), name="token"),
    path("token/refresh/", RekaTokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("email/verify/", EmailVerifyView.as_view(), name="email-verify"),
    path("social/<str:provider>/", SocialAuthView.as_view(), name="social-auth"),
    path("", include(router.urls)),
]
