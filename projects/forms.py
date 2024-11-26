from django.forms import ModelForm
from django import forms
from .models import Video, Tag, Review

class ProjectForm(ModelForm):
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=True,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'tag-checkbox'
        }),
        help_text="Please select at least one tag"
    )
    
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
                'class': 'input'
            }),
            'thumbnail': forms.FileInput(attrs={
                'class': 'input'
            })
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print("Files in form:", kwargs.get('files'))
        self.label_suffix = ''
        
        
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

