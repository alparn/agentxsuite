import json
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

User = get_user_model()

class ClaudeAgentAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="password123",
            first_name="Test",
            last_name="User"
        )
        self.manifest_url = reverse("claude_agent:manifest")
        self.wellknown_url = reverse("wellknown_agent_manifest")
        self.tools_url = reverse("claude_agent:tools")
        self.execute_url = reverse("claude_agent:execute")
        self.health_url = reverse("claude_agent:health")

    def test_wellknown_manifest(self):
        """Test the well-known discovery endpoint."""
        response = self.client.get(self.wellknown_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("manifest_url", response.data)
        self.assertEqual(response.data["name"], "AgentxSuite")

    def test_agent_manifest(self):
        """Test the full agent manifest endpoint."""
        response = self.client.get(self.manifest_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "AgentxSuite")
        self.assertIn("tools", response.data)
        self.assertIn("api", response.data)
        self.assertIn("authentication", response.data)

    def test_list_tools_unauthenticated(self):
        """Test listing tools without authentication fails."""
        response = self.client.get(self.tools_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_tools_authenticated(self):
        """Test listing tools with authentication."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.tools_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tools", response.data)
        self.assertIsInstance(response.data["tools"], list)

    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get(self.health_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("status", response.data)

    @patch("apps.claude_agent.sdk_agent.Anthropic")
    def test_execute_agent(self, MockAnthropic):
        """Test agent execution endpoint with real Agent class."""
        # Create a token for the user
        from rest_framework.authtoken.models import Token
        token, _ = Token.objects.get_or_create(user=self.user)
        
        # Setup mock Anthropic client
        mock_client = MockAnthropic.return_value
        mock_message = MagicMock()
        mock_message.stop_reason = "end_turn"
        mock_message.content = [MagicMock(text="Hello!", type="text")]
        # Mock text attribute for content block
        mock_message.content[0].text = "Hello!"
        mock_message.usage.input_tokens = 10
        mock_message.usage.output_tokens = 5
        mock_client.messages.create.return_value = mock_message
        
        mcp_servers = [
            {
                "type": "url",
                "url": "https://example.com/sse",
                "name": "example",
                "authorization_token": "secret"
            }
        ]
        
        payload = {
            "message": "Hello agent",
            "organization_id": "00000000-0000-0000-0000-000000000000",
            "environment_id": "00000000-0000-0000-0000-000000000000",
            "system_prompt": "You are helpful.",
            "mcp_servers": mcp_servers
        }
        
        # Pass Authorization header explicitly
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self.execute_url, 
            payload, 
            format="json",
            HTTP_AUTHORIZATION='Bearer ' + token.key
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["response"], "Hello!")
        self.assertTrue(response.data["success"])
        
        # Verify Anthropic was initialized (proving AgentxSuiteClaudeAgent was instantiated)
        MockAnthropic.assert_called()
        
        # Verify messages.create was called with correct model, messages, and MCP params
        mock_client.messages.create.assert_called()
        call_kwargs = mock_client.messages.create.call_args[1]
        self.assertEqual(call_kwargs["messages"][0]["content"], "Hello agent")
        self.assertEqual(call_kwargs["system"], "You are helpful.")
        self.assertEqual(call_kwargs["mcp_servers"], mcp_servers)
        self.assertEqual(call_kwargs["extra_headers"]["anthropic-beta"], "mcp-client-2025-04-04")
