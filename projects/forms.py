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