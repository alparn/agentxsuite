"""
Views for accounts app.
"""
from __future__ import annotations

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.accounts.models import ServiceAccount, User
from apps.accounts.serializers import (
    LoginSerializer,
    ServiceAccountSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request) -> Response:
    """
    Register a new user.

    POST /api/v1/auth/register/
    {
        "email": "user@example.com",
        "password": "securepass123",
        "password_confirm": "securepass123",
        "first_name": "John",
        "last_name": "Doe"
    }
    """
    serializer = UserRegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()

    # Create token for the new user
    token, created = Token.objects.get_or_create(user=user)

    return Response(
        {
            "user": UserSerializer(user).data,
            "token": token.key,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request) -> Response:
    """
    Login user and return token.

    POST /api/v1/auth/login/
    {
        "email": "user@example.com",
        "password": "securepass123"
    }
    """
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]

    user = authenticate(username=email, password=password)

    if not user:
        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        return Response(
            {"error": "User account is disabled"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Get or create token
    token, created = Token.objects.get_or_create(user=user)

    return Response(
        {
            "user": UserSerializer(user).data,
            "token": token.key,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request) -> Response:
    """
    Logout user by deleting token.

    POST /api/v1/auth/logout/
    Requires: Authorization: Token <token>
    """
    try:
        request.user.auth_token.delete()
    except Exception:  # noqa: BLE001
        pass

    return Response({"message": "Successfully logged out"}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request) -> Response:
    """
    Get current user details.

    GET /api/v1/auth/me/
    Requires: Authorization: Token <token>
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_organizations(request) -> Response:
    """
    Get organizations for the current user.

    GET /api/v1/auth/me/orgs/
    Requires: Authorization: Token <token>
    
    Returns list of organizations the user has access to.
    Filters by OrganizationMembership to only return organizations the user belongs to.
    """
    try:
        from apps.tenants.models import Organization, OrganizationMembership
        from apps.tenants.serializers import OrganizationSerializer
        
        # Get organizations where user has active membership
        memberships = OrganizationMembership.objects.filter(
            user=request.user,
            is_active=True,
        ).select_related("organization")
        
        organization_ids = [m.organization_id for m in memberships]
        organizations = Organization.objects.filter(id__in=organization_ids).order_by("name")
        
        serializer = OrganizationSerializer(organizations, many=True)
        return Response(
            {
                "organizations": serializer.data,
                "count": len(serializer.data),
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ServiceAccountViewSet(ModelViewSet):
    """ViewSet for ServiceAccount management."""

    queryset = ServiceAccount.objects.all()
    serializer_class = ServiceAccountSerializer

    def get_queryset(self):
        """Filter by organization if org_id is provided."""
        queryset = super().get_queryset()
        org_id = self.kwargs.get("org_id")
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        return queryset

    def perform_create(self, serializer):
        """Set organization from URL parameter."""
        org_id = self.kwargs.get("org_id")
        if org_id:
            serializer.save(organization_id=org_id)
