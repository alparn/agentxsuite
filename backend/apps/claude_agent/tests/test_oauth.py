from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from apps.claude_agent.oauth import OAuthManager

User = get_user_model()

class OAuthManagerTests(TestCase):
    def setUp(self):
        self.manager = OAuthManager()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="password123",
            first_name="Test",
            last_name="User"
        )
        self.org_id = "org-123"
        self.env_id = "env-456"

    def tearDown(self):
        cache.clear()

    def test_generate_authorization_url(self):
        """Test generating authorization URL and state."""
        result = self.manager.generate_authorization_url(self.org_id, self.env_id)
        
        self.assertIn("authorization_url", result)
        self.assertIn("state", result)
        
        # Verify state is cached
        state = result["state"]
        state_data = self.manager.validate_state(state)
        self.assertIsNotNone(state_data)
        self.assertEqual(state_data["organization_id"], self.org_id)
        self.assertEqual(state_data["environment_id"], self.env_id)

    def test_validate_state_invalid(self):
        """Test validating invalid state."""
        result = self.manager.validate_state("invalid-state")
        self.assertIsNone(result)

    def test_generate_authorization_code(self):
        """Test generating authorization code."""
        code = self.manager.generate_authorization_code(self.user, self.org_id, self.env_id)
        self.assertIsNotNone(code)
        
        # Verify code is cached (internal implementation detail, but good to check)
        code_key = f"oauth_code:{code}"
        code_data = cache.get(code_key)
        self.assertIsNotNone(code_data)
        self.assertEqual(code_data["user_id"], self.user.id)

    def test_exchange_code_for_token(self):
        """Test exchanging code for token."""
        # 1. Generate code
        code = self.manager.generate_authorization_code(self.user, self.org_id, self.env_id)
        
        # 2. Exchange for token
        token_data = self.manager.exchange_code_for_token(code)
        
        self.assertIsNotNone(token_data)
        self.assertIn("access_token", token_data)
        self.assertEqual(token_data["organization_id"], self.org_id)
        self.assertEqual(token_data["environment_id"], self.env_id)
        
        # 3. Verify code is consumed (cannot be used twice)
        second_attempt = self.manager.exchange_code_for_token(code)
        self.assertIsNone(second_attempt)

    def test_revoke_token(self):
        """Test token revocation."""
        # 1. Get a token
        code = self.manager.generate_authorization_code(self.user, self.org_id, self.env_id)
        token_data = self.manager.exchange_code_for_token(code)
        access_token = token_data["access_token"]
        
        # 2. Revoke it
        success = self.manager.revoke_token(access_token)
        self.assertTrue(success)
        
        # 3. Try to revoke again (should fail or return False depending on impl, here False)
        success_again = self.manager.revoke_token(access_token)
        self.assertFalse(success_again)
