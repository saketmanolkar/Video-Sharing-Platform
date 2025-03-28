from django.forms import ModelForm
from django import forms
from .models import Video, Tag, Review, Playlist, PlaylistItem
from django.utils.html import strip_tags
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
import os
import mimetypes  # Built-in library, no extra dependencies

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Video
        fields = ['title', 'description', 'file', 'thumbnail', 'tags', 'privacy_status']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Enter video title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'input',
                'placeholder': 'Enter video description',
                'rows': 4
            }),
            'file': forms.FileInput(attrs={
                'class': 'file-input',
                'accept': 'video/mp4,video/mov'
                
            }),
            'thumbnail': forms.FileInput(attrs={
                'class': 'file-input',
                'accept': 'image/*'
                
            }),
            'tags': forms.CheckboxSelectMultiple(attrs={
                'class': 'tag-checkbox'
            }),
            'privacy_status': forms.Select(attrs={
                'class': 'input',
            })
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tags'].help_text = "Please select at least one tag"
        
        # Add help text for privacy
        self.fields['privacy_status'].help_text = "Choose who can view this video"
        
        # Set base requirements
        self.fields['title'].required = True
        self.fields['description'].required = True
        self.fields['tags'].required = True
        self.fields['privacy_status'].required = True
        
        # Handle file requirements based on whether this is an update
        if self.instance and self.instance.pk:
            self.fields['file'].required = False
            self.fields['thumbnail'].required = False
            self.fields['file'].widget.attrs['required'] = False
            self.fields['thumbnail'].widget.attrs['required'] = False
        else:
            self.fields['file'].required = True
            self.fields['thumbnail'].required = True
            self.fields['file'].widget.attrs['required'] = True
            self.fields['thumbnail'].widget.attrs['required'] = True
        
        # Add input class to non-file fields
        for name, field in self.fields.items():
            if name not in ['file', 'thumbnail']:
                field.widget.attrs.update({'class': 'input'})
    
    def clean_title(self):
        title = self.cleaned_data.get('title')
        if not title:
            raise forms.ValidationError("Title is required")
        
        # Sanitize title - remove HTML tags
        sanitized_title = strip_tags(title.strip())
        
        # Enforce length limits
        if len(sanitized_title) < 3:
            raise forms.ValidationError("Title must be at least 3 characters long")
        if len(sanitized_title) > 100:
            raise forms.ValidationError("Title must be less than 100 characters")
            
        return sanitized_title
    
    def clean_description(self):
        description = self.cleaned_data.get('description')
        if not description:
            raise forms.ValidationError("Description is required")
        
        # Sanitize description - remove HTML tags
        sanitized_description = strip_tags(description.strip())
        
        # Count words instead of characters
        word_count = len(sanitized_description.split())
        
        # Enforce word limits
        if word_count < 5:
            raise forms.ValidationError("Description must be at least 5 words long")
        if word_count > 100:
            raise forms.ValidationError("Description must be no more than 100 words")
            
        return sanitized_description
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        # If we're updating and no new file was provided, return None
        if not file and self.instance and self.instance.pk:
            return self.instance.file
            
        if file:
            # Check file size (limit to 2GB)
            if file.size > 2147483648:  # 2GB in bytes
                raise forms.ValidationError("File size must be less than 2GB")
                
            # Check file extension
            ext = os.path.splitext(file.name)[1].lower()
            valid_extensions = ['.mp4', '.mov', '.qt', '.quicktime']
            if ext not in valid_extensions:
                raise forms.ValidationError(f"Only {', '.join(valid_extensions)} files are allowed")
                
            # Check MIME type using built-in mimetypes library
            mime_type, encoding = mimetypes.guess_type(file.name)
            if mime_type:
                valid_types = ['video/mp4', 'video/mov', 'video/quicktime']
                if mime_type not in valid_types:
                    raise forms.ValidationError(f"File type {mime_type} is not supported")
                
        return file
        
    def clean_thumbnail(self):
        thumbnail = self.cleaned_data.get('thumbnail')
        # If we're updating and no new thumbnail was provided, return None
        if not thumbnail and self.instance and self.instance.pk:
            return self.instance.thumbnail
            
        if thumbnail:
            # Check file size (limit to 25MB)
            if thumbnail.size > 26214400:  # 25MB in bytes
                raise forms.ValidationError("Thumbnail size must be less than 5MB")
                
            # Check file extension
            ext = os.path.splitext(thumbnail.name)[1].lower()
            valid_extensions = ['.jpg', '.jpeg', '.png']
            if ext not in valid_extensions:
                raise forms.ValidationError(f"Only {', '.join(valid_extensions)} files are allowed for thumbnails")
                
            # Check MIME type using built-in mimetypes library
            mime_type, encoding = mimetypes.guess_type(thumbnail.name)
            if mime_type:
                valid_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
                if mime_type not in valid_types:
                    raise forms.ValidationError(f"Thumbnail type {mime_type} is not supported")
                
        return thumbnail
    
    def clean_tags(self):
        tags = self.cleaned_data.get('tags')
        if not tags or len(tags) == 0:
            raise forms.ValidationError("Please select at least one tag")
        return tags
    
    
    def clean_privacy_status(self):
        status = self.cleaned_data.get('privacy_status')
        valid_statuses = [choice[0] for choice in Video.PRIVACY_CHOICES]
        
        if not status:
            raise forms.ValidationError("Please select a privacy status")
        
        if status not in valid_statuses:
            raise forms.ValidationError("Invalid privacy status selected")
            
        return status
        
        
class ReviewForm(ModelForm):
    class Meta:
        model = Review
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Add your comment here...',
                'rows': 4
            })
        }

class MovieRecommendationForm(forms.Form):
    MEDIA_CHOICES = [
        ('any', 'TV Show or Movie'),
        ('tv', 'TV Show'),
        ('movie', 'Movie'),
    ]

    TIME_PERIOD_CHOICES = [
        ('any', 'Any Period'),
        ('Pre-1970s', 'Pre-1970s'), 
        ('1970s-1980s', 'Early 70s to Mid 80s'),
        ('1980s-1990s', 'Late 80s to Early 90s'),
        ('1990s-2000s', 'Mid 90s to Late 2000s'),
        ('2010s-Present', '2010s to Present'),
        ('Unknown', 'Unknown'),
        ('Upcoming', 'Upcoming'),
    ]

    GENRE_CHOICES = [
        ('any', 'Any'),
        ('Action', 'Action'),
        ('Adventure', 'Adventure'),
        ('Animation', 'Animation'),
        ('Comedy', 'Comedy'),
        ('Crime', 'Crime'),
        ('Documentary', 'Documentary'),
        ('Drama', 'Drama'),
        ('Family', 'Family'),
        ('Fantasy', 'Fantasy'),
        ('History', 'History'),
        ('Horror', 'Horror'),
        ('Music', 'Music'),
        ('Mystery', 'Mystery'),
        ('Romance', 'Romance'),
        ('Science Fiction', 'Science Fiction'),
        ('TV Movie', 'TV Movie'),
        ('Thriller', 'Thriller'),
        ('War', 'War'),
        ('Western', 'Western'),
    ]

    LANGUAGE_CHOICES = [
        ('any', 'Any Language'),
        ('English', 'English'),
        ('French', 'French'),
        ('German', 'German'),
        ('Italian', 'Italian'),
        ('Japanese', 'Japanese'),
        ('Korean', 'Korean'),
        ('Mandarin', 'Mandarin'),
        ('Spanish', 'Spanish'),
        ('Hindi', 'Hindi'),
        ('Russian', 'Russian'),
    ]
    
    media_type = forms.ChoiceField(
        choices=MEDIA_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control inline-select',
            'style': 'display: inline-block; width: auto;'
        })
    )
    
    time_period = forms.ChoiceField(
        choices=TIME_PERIOD_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control inline-select',
            'style': 'display: inline-block; width: auto;'
        })
    )
    
    genres = forms.ChoiceField(
        choices=GENRE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control inline-select',
            'style': 'display: inline-block; width: auto;'
        })
    )
    
    language = forms.ChoiceField(
        choices=LANGUAGE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control inline-select',
            'style': 'display: inline-block; width: auto;'
        })
    )

class CreatePlaylistForm(forms.ModelForm):
    class Meta:
        model = Playlist
        fields = ['name', 'is_private']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'input input--text',
                    'placeholder': 'Enter playlist name...'
                }
            ),
            'is_private': forms.CheckboxInput(
                attrs={
                    'class': 'input input--checkbox',
                    'style': 'appearance: checkbox; -webkit-appearance: checkbox; display: inline-block;'
                }
            )
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name', '')
        
        # Sanitize name - remove HTML tags and trim whitespace
        sanitized_name = strip_tags(name.strip())
        
        # Validate name is not empty
        if not sanitized_name:
            raise forms.ValidationError("Playlist name cannot be empty")
        
        # Validate name length
        if len(sanitized_name) > 100:
            raise forms.ValidationError("Playlist name must be less than 100 characters")
        
        return sanitized_name