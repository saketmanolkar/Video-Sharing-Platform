from django.forms import ModelForm
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.core.exceptions import ValidationError
from .models import Profile

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

class ProfileForm(ModelForm):
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