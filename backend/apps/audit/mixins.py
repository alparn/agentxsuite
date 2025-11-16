"""
Audit logging mixins for ViewSets.
"""
from __future__ import annotations

from apps.audit.services import log_api_event


class AuditLoggingMixin:
    """
    Mixin to automatically log CRUD operations in ViewSets.
    
    Usage:
        class MyViewSet(AuditLoggingMixin, ModelViewSet):
            ...
    """

    def perform_create(self, serializer):
        """Log creation - calls ViewSet's perform_create if it exists, then logs."""
        from rest_framework.viewsets import ModelViewSet
        
        # Find ViewSet class in MRO (skip AuditLoggingMixin)
        viewset_class = None
        for cls in self.__class__.__mro__:
            if cls != AuditLoggingMixin:
                viewset_class = cls
                break
        
        # Call ViewSet's perform_create if it exists and is different from ModelViewSet's
        if viewset_class:
            viewset_method = getattr(viewset_class, "perform_create", None)
            if viewset_method and viewset_method != ModelViewSet.perform_create:
                # ViewSet has custom perform_create - call it
                viewset_method(self, serializer)
            else:
                # No custom method, use ModelViewSet's default
                from rest_framework.viewsets import ModelViewSet
                ModelViewSet.perform_create(self, serializer)
        else:
            # Fallback to ModelViewSet's default
            from rest_framework.viewsets import ModelViewSet
            ModelViewSet.perform_create(self, serializer)
        
        # Log after creation (only if instance was created)
        instance = serializer.instance
        if instance:
            self._log_api_event("create", instance, serializer.validated_data)
        return instance

    def perform_update(self, serializer):
        """Log update - calls ViewSet's perform_update if it exists, then logs."""
        from rest_framework.viewsets import ModelViewSet
        
        # Get old data before update
        instance = serializer.instance
        old_data = self._get_serialized_data(instance) if instance else None
        
        # Find ViewSet class in MRO (skip AuditLoggingMixin)
        viewset_class = None
        for cls in self.__class__.__mro__:
            if cls != AuditLoggingMixin:
                viewset_class = cls
                break
        
        # Call ViewSet's perform_update if it exists and is different from ModelViewSet's
        if viewset_class:
            viewset_method = getattr(viewset_class, "perform_update", None)
            if viewset_method and viewset_method != ModelViewSet.perform_update:
                # ViewSet has custom perform_update - call it
                viewset_method(self, serializer)
            else:
                # No custom method, use ModelViewSet's default
                from rest_framework.viewsets import ModelViewSet
                ModelViewSet.perform_update(self, serializer)
        else:
            # Fallback to ModelViewSet's default
            from rest_framework.viewsets import ModelViewSet
            ModelViewSet.perform_update(self, serializer)
        
        # Log after update (only if instance was updated)
        instance = serializer.instance
        if instance:
            new_data = serializer.validated_data
            self._log_api_event("update", instance, new_data, old_data=old_data)
        return instance

    def perform_destroy(self, instance):
        """Log deletion - logs before calling ViewSet's perform_destroy."""
        from rest_framework.viewsets import ModelViewSet
        
        # Get old data before deletion
        old_data = self._get_serialized_data(instance)
        
        # Log before deletion (so we have the data)
        self._log_api_event("delete", instance, old_data)
        
        # Find the actual ViewSet class in MRO (skip AuditLoggingMixin)
        # Check if ViewSet has its own perform_destroy (defined directly in its class, not inherited)
        viewset_class = None
        for cls in self.__class__.__mro__:
            if cls != AuditLoggingMixin and cls != ModelViewSet:
                # Check if this class DEFINES perform_destroy (not just inherits it)
                if "perform_destroy" in cls.__dict__:
                    viewset_class = cls
                    break
        
        # Call ViewSet's perform_destroy if it exists
        if viewset_class:
            viewset_method = viewset_class.perform_destroy
            # Call the ViewSet's perform_destroy
            # IMPORTANT: The ViewSet's perform_destroy should call ModelViewSet.perform_destroy
            # directly, NOT super().perform_destroy(), to avoid recursion
            viewset_method(self, instance)
        else:
            # No custom method, use ModelViewSet's default
            ModelViewSet.perform_destroy(self, instance)

    def _get_serialized_data(self, instance):
        """Get serialized data for an instance."""
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(instance)
        return serializer.data

    def _log_api_event(
        self,
        action: str,
        instance,
        data: dict,
        old_data: dict | None = None,
    ) -> None:
        """Log an API event."""
        # Get organization from instance or request
        organization = None
        if hasattr(instance, "organization"):
            organization = instance.organization
        elif hasattr(instance, "organization_id"):
            from apps.tenants.models import Organization
            try:
                organization = Organization.objects.get(id=instance.organization_id)
            except Organization.DoesNotExist:
                pass

        # Get user from request
        user = None
        if hasattr(self, "request") and hasattr(self.request, "user"):
            if self.request.user.is_authenticated:
                user = self.request.user

        # Determine object type from model
        object_type = instance.__class__.__name__.lower()

        # Build event data
        event_data = {
            "object_id": str(instance.id),
            "object_type": object_type,
            "action": action,
        }

        # Add relevant fields from data (limit size to avoid huge logs)
        if action == "create":
            # Only include key fields, not entire data
            event_data["created_fields"] = list(data.keys())[:20]
        elif action == "update":
            # Only include changed fields
            changed_fields = [k for k in data.keys() if k in (old_data or {}) and data[k] != old_data.get(k)]
            event_data["updated_fields"] = changed_fields[:20]
        elif action == "delete":
            # Include object identifier
            event_data["deleted_object"] = object_type

        # Add organization/environment IDs if available
        if hasattr(instance, "organization_id"):
            event_data["organization_id"] = str(instance.organization_id)
        if hasattr(instance, "environment_id"):
            event_data["environment_id"] = str(instance.environment_id)

        # Log the event
        log_api_event(
            organization=organization,
            event_type=f"api.{object_type}.{action}",
            event_data=event_data,
            user=user,
        )

