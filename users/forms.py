from django.forms import ModelForm
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.core.exceptions import ValidationError
from .models import Profile , Message

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

class MessageForm(ModelForm):
    class Meta:
        model = Message
        fields = ['name', 'email', 'subject', 'body']

    def __init__(self, *args, **kwargs):
        super(MessageForm, self).__init__(*args, **kwargs)

        for name, field in self.fields.items():
            field.widget.attrs.update({'class': 'input input--text'})