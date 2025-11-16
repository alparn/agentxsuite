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
from apps.audit.mixins import AuditLoggingMixin


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


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def me(request) -> Response:
    """
    Get or update current user details and current organization.

    GET /api/v1/auth/me/
    Requires: Authorization: Token <token>
    Returns user info and current organization (first active membership).

    PUT/PATCH /api/v1/auth/me/
    Requires: Authorization: Token <token>
    Update user profile:
    {
        "first_name": "John",
        "last_name": "Doe",
        "email": "newemail@example.com"
    }
    """
    if request.method == "GET":
        serializer = UserSerializer(request.user)
        user_data = serializer.data
        
        # Get current organization (first active membership)
        try:
            from apps.tenants.models import OrganizationMembership
            
            membership = OrganizationMembership.objects.filter(
                user=request.user,
                is_active=True,
            ).select_related("organization").order_by("-created_at").first()
            
            if membership:
                user_data["organization_id"] = str(membership.organization.id)
                user_data["organization"] = {
                    "id": str(membership.organization.id),
                    "name": membership.organization.name,
                }
        except Exception:
            # If organization lookup fails, continue without it
            pass
        
        return Response(user_data, status=status.HTTP_200_OK)
    
    else:
        # PUT/PATCH: Update user profile
        serializer = UserSerializer(request.user, data=request.data, partial=request.method == "PATCH")
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return updated user data with organization
        user_data = serializer.data
        try:
            from apps.tenants.models import OrganizationMembership
            
            membership = OrganizationMembership.objects.filter(
                user=request.user,
                is_active=True,
            ).select_related("organization").order_by("-created_at").first()
            
            if membership:
                user_data["organization_id"] = str(membership.organization.id)
                user_data["organization"] = {
                    "id": str(membership.organization.id),
                    "name": membership.organization.name,
                }
        except Exception:
            pass
        
        return Response(user_data, status=status.HTTP_200_OK)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def my_organizations(request) -> Response:
    """
    Get or add organizations for the current user.

    GET /api/v1/auth/me/orgs/
    Requires: Authorization: Token <token>
    Returns list of organizations the user has access to.

    POST /api/v1/auth/me/orgs/
    Requires: Authorization: Token <token>
    Add user to an organization:
    {
        "organization_id": "uuid"  // Join existing organization
        OR
        "organization_name": "New Org"  // Create new organization and join as owner
    }
    """
    if request.method == "GET":
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
    else:
        # POST: Add user to organization
        try:
            from apps.tenants.models import Organization, OrganizationMembership
            from apps.tenants.serializers import OrganizationSerializer
            
            organization_id = request.data.get("organization_id")
            organization_name = request.data.get("organization_name", "").strip()
            
            if organization_name and organization_id:
                return Response(
                    {"error": "Provide either organization_id or organization_name, not both"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            if organization_name:
                # Create new organization and add user as owner
                org = Organization.objects.create(name=organization_name)
                membership, created = OrganizationMembership.objects.get_or_create(
                    user=request.user,
                    organization=org,
                    defaults={"role": "owner", "is_active": True},
                )
                if not created:
                    membership.role = "owner"
                    membership.is_active = True
                    membership.save()
            elif organization_id:
                # Join existing organization as member
                try:
                    org = Organization.objects.get(id=organization_id)
                    membership, created = OrganizationMembership.objects.get_or_create(
                        user=request.user,
                        organization=org,
                        defaults={"role": "member", "is_active": True},
                    )
                    if not created and not membership.is_active:
                        membership.is_active = True
                        membership.save()
                except Organization.DoesNotExist:
                    return Response(
                        {"error": "Organization not found"},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            else:
                return Response(
                    {"error": "Provide either organization_id or organization_name"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            serializer = OrganizationSerializer(org)
            return Response(
                {
                    "organization": serializer.data,
                    "membership": {
                        "role": membership.role,
                        "is_active": membership.is_active,
                    },
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ServiceAccountViewSet(AuditLoggingMixin, ModelViewSet):
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
