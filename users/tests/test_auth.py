from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

class BasicAuthenticationTest(TestCase):
    def setUp(self):
        # Create a test user
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        
        # Get actual URL names from your application
        self.login_url = reverse('login-page')
        self.logout_url = reverse('logout-user')
        self.home_url = reverse('projects')
        self.register_url = reverse('register-page')
    
    def test_login(self):
        """Test user can login with correct credentials"""
        response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'password123'
        })
        
        # Your login view returns 200, not 302 (no redirect)
        self.assertEqual(response.status_code, 200)
        
        # Test if we can access a protected page or check session
        session = self.client.session
        self.assertTrue(session.get('_auth_user_id'))
    
    def test_failed_login(self):
        """Test login fails with wrong password"""
        response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        
        # Your view returns 400 Bad Request for invalid login
        self.assertEqual(response.status_code, 400)
        
        # Make sure user is not authenticated
        session = self.client.session
        self.assertFalse(session.get('_auth_user_id'))
    
    def test_logout(self):
        """Test user can logout"""
        # First login
        self.client.login(username='testuser', password='password123')
        
        # Then logout
        response = self.client.get(self.logout_url)
        
        # Should redirect after logout
        self.assertEqual(response.status_code, 302)
        
        # User should not be authenticated
        session = self.client.session
        self.assertFalse(session.get('_auth_user_id'))
    
    def test_registration(self):
        """Test user registration with valid data"""
        user_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'securepassword123',
            'password2': 'securepassword123',
        }
        
        response = self.client.post(self.register_url, user_data)
        
        # Your register_user view redirects to update-profile
        self.assertEqual(response.status_code, 302)
        
        # Check if user was created
        new_user = User.objects.filter(username='newuser').first()
        self.assertIsNotNone(new_user)
        
        # Check the proper fields were saved
        self.assertEqual(new_user.first_name, 'New')
        self.assertEqual(new_user.last_name, 'User')
        self.assertEqual(new_user.email, 'newuser@example.com')
        
    def test_registration_password_mismatch(self):
        """Test registration fails when passwords don't match"""
        user_data = {
            'username': 'newuser2',
            'email': 'newuser2@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'securepassword123',
            'password2': 'differentpassword',
        }
        
        response = self.client.post(self.register_url, user_data)
        
        # Your view renders the form again with errors
        self.assertEqual(response.status_code, 200)
        
        # User should not be created
        self.assertFalse(User.objects.filter(username='newuser2').exists())
        
    def test_registration_missing_required_field(self):
        """Test registration fails when required fields are missing"""
        user_data = {
            'username': 'newuser3',
            'email': 'newuser3@example.com',
            # Missing first_name which is required
            'last_name': 'User',
            'password1': 'securepassword123',
            'password2': 'securepassword123',
        }
        
        response = self.client.post(self.register_url, user_data)
        
        # Your view renders the form again with errors
        self.assertEqual(response.status_code, 200)
        
        # User should not be created
        self.assertFalse(User.objects.filter(username='newuser3').exists())
        
    def test_registration_existing_user(self):
        """Test registration fails with existing username"""
        user_data = {
            'username': 'testuser',  # Already exists from setUp
            'email': 'another@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password1': 'securepassword123',
            'password2': 'securepassword123',
        }
        
        response = self.client.post(self.register_url, user_data)
        
        # Your view renders the form again with errors
        self.assertEqual(response.status_code, 200)
        
        # Only one user with this username should exist
        self.assertEqual(User.objects.filter(username='testuser').count(), 1)