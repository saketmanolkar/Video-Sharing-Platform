from django.forms import ModelForm
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from .models import Profile , Message
import re
from django.utils.html import strip_tags

class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'input input--text',
            'placeholder': 'Enter your first name...'
        })
    )
    
    last_name = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'input input--text',
            'placeholder': 'Enter your last name...(optional)'
        })
    )
    
    username = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'input input--text',
            'placeholder': 'Letters, digits and @/./+/-/_ only.'
        })
    )
    
    email = forms.EmailField(
        max_length=254,
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'input input--email',
            'placeholder': 'Enter your valid email address...'
        })
    )
    
    password1 = forms.CharField(
        required=True,
        label='Password',
        help_text='''
        • Your password must contain at least 8 characters<br>
        • Your password can't be entirely numeric<br>
        • Your password can't be too common
        ''',
        widget=forms.PasswordInput(attrs={
            'class': 'input input--password',
            'placeholder': 'Enter your password...'
        })
    )
    
    password2 = forms.CharField(
        required=True,
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'input input--password',
            'placeholder': 'Enter your password again...'
        })
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean_first_name(self):
        return self.cleaned_data.get('first_name', '').strip()
        
    def clean_last_name(self):
        return self.cleaned_data.get('last_name', '').strip()

    # validation for email already in use (USE IN PRODUCTION)
    # def clean_email(self):
    #     email = self.cleaned_data.get('email', '').strip().lower()
    #     if User.objects.filter(email=email).exists():
    #         raise forms.ValidationError('Email address is already in use')
    #     return email

class ProfileForm(ModelForm):
    first_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'input input--text',
            'placeholder': 'Enter your first name'
        })
    )
    
    username = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'input input--text',
            'placeholder': 'Enter your username'
        })
    )

    class Meta:
        model = Profile
        fields = [
            'bio',
            'location',
            'profile_pics',
            'github',
            'twitter',
            'linkedin',
            'youtube',
            'instagram'
        ]
        widgets = {
            'bio': forms.TextInput(attrs={
                'class': 'input input--text',
                'placeholder': 'Write a short bio about yourself'
            }),
            'location': forms.TextInput(attrs={
                'class': 'input input--text',
                'placeholder': 'Enter your location'
            }),
            'profile_pics': forms.FileInput(attrs={
                'class': 'input input--text',
                'accept': 'image/*'
            }),
            'github': forms.TextInput(attrs={
                'class': 'input input--text',
                'placeholder': 'Enter your Github URL'
            }),
            'twitter': forms.TextInput(attrs={
                'class': 'input input--text',
                'placeholder': 'Enter your Twitter URL'
            }),
            'linkedin': forms.TextInput(attrs={
                'class': 'input input--text',
                'placeholder': 'Enter your LinkedIn URL'
            }),
            'youtube': forms.TextInput(attrs={
                'class': 'input input--text',
                'placeholder': 'Enter your YouTube URL'
            }),
            'instagram': forms.TextInput(attrs={
                'class': 'input input--text',
                'placeholder': 'Enter your Instagram URL'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['username'].initial = self.instance.user.username
            
        # Make all social media fields and location optional
        for field in ['location', 'github', 'twitter', 'linkedin', 'youtube', 'instagram']:
            self.fields[field].required = False

    def clean_first_name(self):
        # Sanitize first name
        return self.cleaned_data.get('first_name', '').strip()
        
    def clean_last_name(self):
        # Sanitize last name
        return self.cleaned_data.get('last_name', '').strip()
        
    def clean_username(self):
        # Sanitize username
        username = self.cleaned_data.get('username', '').strip().lower()
        
        # Validate username format
        if not re.match(r'^[a-z0-9_@+.-]+$', username):
            raise ValidationError('Username can only contain letters, numbers, and @/./+/-/_')
            
        return username
        
    def clean_bio(self):
        # Sanitize bio
        bio = self.cleaned_data.get('bio', '').strip()
        if len(bio) > 300:
            raise ValidationError('Bio cannot exceed 300 characters')
        return bio
        
    def clean_location(self):
        location = self.cleaned_data.get('location')
        
        # Handle None, empty strings, or placeholder text
        if not location or location == '#':
            return ''
            
        return location.strip()
    
    def _clean_social_url(self, field_name):
        """Helper method to clean social media URLs"""
        url = self.cleaned_data.get(field_name)
        
        # Handle None, empty strings, or placeholder text
        if not url or 'Enter your' in url:
            return ''
            
        # Add https:// if missing
        if url and url != '#' and not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        return url

    def clean_github(self):
        return self._clean_social_url('github')
        
    def clean_twitter(self):
        return self._clean_social_url('twitter')
        
    def clean_linkedin(self):
        return self._clean_social_url('linkedin')
        
    def clean_youtube(self):
        return self._clean_social_url('youtube')
        
    def clean_instagram(self):
        return self._clean_social_url('instagram')
        
    def clean_profile_pics(self):
        profile_pic = self.cleaned_data.get('profile_pics')
        if profile_pic:
            # Check file size (limit to 25MB)
            if profile_pic.size > 25 * 1024 * 1024:
                raise ValidationError('Image file too large (max 25MB)')
                
            # Check file type
            valid_extensions = ['jpg', 'jpeg', 'png']
            ext = profile_pic.name.split('.')[-1].lower()
            if ext not in valid_extensions:
                raise ValidationError('Unsupported file type. Please use JPG, JPEG, PNG.')
                
        return profile_pic

    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get('first_name')
        username = cleaned_data.get('username')

        if not first_name:
            raise ValidationError('First name is required.')
        
        if not username:
            raise ValidationError('Username is required.')

        # Check if username already exists (excluding current user)
        if User.objects.exclude(pk=self.instance.user.pk).filter(username=username).exists():
            raise ValidationError('This username is already taken.')

        return cleaned_data

    def save(self, commit=True):
        profile = super().save(commit=False)
        
        # Update the related User model fields
        profile.user.first_name = self.cleaned_data['first_name']
        profile.user.username = self.cleaned_data['username']
        
        if commit:
            profile.user.save()
            profile.save()
        
        return profile

class MessageForm(forms.ModelForm):
    name = forms.CharField(
        max_length=100, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'input input--text'})
    )
    
    email = forms.EmailField(
        max_length=200, 
        required=True,
        widget=forms.EmailInput(attrs={'class': 'input input--text'})
    )
    
    subject = forms.CharField(
        max_length=200, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'input input--text'})
    )
    
    body = forms.CharField(
        max_length=5000, 
        required=True,
        widget=forms.Textarea(attrs={'class': 'input input--text'})
    )
    
    class Meta:
        model = Message
        fields = ['name', 'email', 'subject', 'body']
    
    def __init__(self, *args, **kwargs):
        super(MessageForm, self).__init__(*args, **kwargs)
        
        # Already set widget attributes in field definitions
    
    def clean_name(self):
        name = self.cleaned_data.get('name', '')
        
        # Server-side validation
        if not name:
            raise forms.ValidationError("Name is required")
        
        # Sanitize name
        name = strip_tags(name.strip())  # Remove HTML tags and whitespace
        
        # Check for alphanumeric + basic punctuation only (server-side validation)
        if not re.match(r'^[a-zA-Z0-9\s\.\-\_\']+$', name):
            raise forms.ValidationError("Name contains invalid characters")
        
        # Length validation
        if len(name) > 100:
            raise forms.ValidationError("Name is too long (maximum 100 characters)")
        
        return name
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        
        # Server-side validation
        if not email:
            raise forms.ValidationError("Email is required")
        
        # Sanitize email
        email = strip_tags(email.strip())  # Remove HTML tags and whitespace
        
        # Email format validation
        try:
            validator = EmailValidator(message="Enter a valid email address")
            validator(email)
        except forms.ValidationError:
            raise forms.ValidationError("Please enter a valid email address")
        
        return email
    
    def clean_subject(self):
        subject = self.cleaned_data.get('subject', '')
        
        # Server-side validation
        if not subject:
            raise forms.ValidationError("Subject is required")
        
        # Sanitize subject
        subject = strip_tags(subject.strip())  # Remove HTML tags and whitespace
        
        # Length validation
        if len(subject) > 200:
            raise forms.ValidationError("Subject is too long (maximum 200 characters)")
        
        return subject
    
    def clean_body(self):
        body = self.cleaned_data.get('body', '')
        
        # Server-side validation
        if not body:
            raise forms.ValidationError("Message body is required")
        
        # Sanitize body - keep some basic HTML formatting but remove potentially harmful tags
        body = strip_tags(body)  # Remove all HTML tags
        body = body.strip()  # Remove leading/trailing whitespace
        
        # Length validation
        if len(body) > 5000:
            raise forms.ValidationError("Message is too long (maximum 5000 characters)")
        
        return body