from django.forms import ModelForm
from django import forms
from .models import Video, Tag, Review, Playlist, PlaylistItem

class ProjectForm(ModelForm):
    class Meta:
        model = Video
        fields = ['title', 'description', 'file', 'thumbnail', 'tags']
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
            })
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tags'].help_text = "Please select at least one tag"
        
        # Set base requirements
        self.fields['title'].required = True
        self.fields['description'].required = True
        self.fields['tags'].required = True
        
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
    
    def clean_tags(self):
        tags = self.cleaned_data.get('tags')
        if not tags:
            raise forms.ValidationError("Please select at least one tag")
        return tags
        
        
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