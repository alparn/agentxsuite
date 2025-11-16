"""
Serializers for accounts app.
"""
from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.accounts.models import ServiceAccount, User


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    organization_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    organization_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = User
        fields = ["email", "password", "password_confirm", "first_name", "last_name", "organization_name", "organization_id"]
        extra_kwargs = {
            "email": {"required": True},
            "password": {"required": True},
            "password_confirm": {"required": True},
        }

    def validate(self, attrs):
        """Validate that passwords match."""
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match"})
        
        # Validate organization: either name (create new) or id (join existing), but not both
        org_name = attrs.get("organization_name", "").strip()
        org_id = attrs.get("organization_id")
        
        if org_name and org_id:
            raise serializers.ValidationError({
                "organization": "Provide either organization_name (to create new) or organization_id (to join existing), not both"
            })
        
        return attrs

    def create(self, validated_data):
        """Create user with hashed password and optionally create/join organization."""
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        organization_name = validated_data.pop("organization_name", "").strip()
        organization_id = validated_data.pop("organization_id", None)
        
        user = User.objects.create_user(password=password, **validated_data)
        
        # Handle organization
        if organization_name:
            # Create new organization and add user as owner
            from apps.tenants.models import Organization, OrganizationMembership
            org = Organization.objects.create(name=organization_name)
            OrganizationMembership.objects.create(
                user=user,
                organization=org,
                role="owner",
                is_active=True,
            )
        elif organization_id:
            # Join existing organization as member
            from apps.tenants.models import Organization, OrganizationMembership
            try:
                org = Organization.objects.get(id=organization_id)
                OrganizationMembership.objects.get_or_create(
                    user=user,
                    organization=org,
                    defaults={"role": "member", "is_active": True},
                )
            except Organization.DoesNotExist:
                raise serializers.ValidationError({"organization_id": "Organization not found"})
        
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for login."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "is_staff", "is_superuser", "date_joined"]
        read_only_fields = ["id", "is_staff", "is_superuser", "date_joined"]


class ServiceAccountSerializer(serializers.ModelSerializer):
    """Serializer for ServiceAccount."""

    organization_name = serializers.CharField(source="organization.name", read_only=True)
    environment_name = serializers.CharField(source="environment.name", read_only=True, allow_null=True)
    agent_id = serializers.UUIDField(source="agent.id", read_only=True, allow_null=True)
    agent_name = serializers.CharField(source="agent.name", read_only=True, allow_null=True)

    class Meta:
        model = ServiceAccount
        fields = [
            "id",
            "name",
            "organization",
            "organization_name",
            "environment",
            "environment_name",
            "subject",
            "issuer",
            "audience",
            "scope_allowlist",
            "credential_ref",
            "expires_at",
            "rotated_at",
            "enabled",
            "agent_id",
            "agent_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_at", "updated_at", "rotated_at"]

    def validate(self, attrs):
        """Validate ServiceAccount constraints."""
        # Validate unique (subject, issuer) if both are provided
        subject = attrs.get("subject")
        issuer = attrs.get("issuer")
        
        if subject and issuer:
            # Get organization from attrs, instance, or context (set by perform_create)
            org = attrs.get("organization")
            if not org and self.instance:
                org = self.instance.organization
            # For create: organization will be set in perform_create, so we can't validate uniqueness here
            # We'll rely on database constraint for create, but validate for update
            if org and self.instance:
                existing = ServiceAccount.objects.filter(
                    subject=subject,
                    issuer=issuer,
                ).exclude(pk=self.instance.pk)
                if existing.exists():
                    raise serializers.ValidationError(
                        {"subject": "ServiceAccount with this (subject, issuer) already exists"}
                    )
        
        return attrs
