from django.forms import ModelForm
from django import forms
from .models import Video, Tag, Review

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
                'class': 'input'
            }),
            'thumbnail': forms.FileInput(attrs={
                'class': 'input'
            }),
            'tags': forms.CheckboxSelectMultiple(attrs={
                'class': 'tag-checkbox'
            })
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tags'].help_text = "Please select at least one tag"
        print("Form data:", kwargs.get('data'))  # Debug line
        print("Files:", kwargs.get('files'))  # Debug line
        print("Tags in form:", self.fields['tags'].queryset)
        
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

