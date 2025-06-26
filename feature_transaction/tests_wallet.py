from django.test import TestCase
from django.contrib.auth import get_user_model
from feature_transaction.models import Wallet

User = get_user_model()

class WalletCreationTest(TestCase):
    """Test case for automatic wallet creation when a user registers"""
    
    def test_wallet_auto_creation(self):
        # Create a test user
        test_user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        
        # Check if wallet was automatically created
        self.assertTrue(hasattr(test_user, 'wallet'), "Wallet was not automatically created for new user")
        
        # Verify wallet properties
        wallet = Wallet.objects.get(user=test_user)
        self.assertEqual(wallet.balance, 0, "New wallet should have zero balance")
        self.assertTrue(wallet.is_active, "New wallet should be active")
        
    def test_wallet_exists_after_creation(self):
        # Create multiple users
        for i in range(3):
            user = User.objects.create_user(
                username=f"testuser{i}",
                email=f"test{i}@example.com",
                password="password123"
            )
            # Verify each user has exactly one wallet
            wallet_count = Wallet.objects.filter(user=user).count()
            self.assertEqual(wallet_count, 1, f"User should have exactly one wallet, found {wallet_count}")
