from django.forms import ModelForm
from django import forms
from .models import Video, Tag, Review

class ProjectForm(ModelForm):
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=True,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'placeholder': 'Select tags (required)'
        }),
        help_text="Please select at least one tag"
    )
    
    class Meta:
        model = Video
        fields = ['title', 'description', 'file', 'thumbnail', 'tags']
        
        
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
        
        