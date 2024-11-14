from django.forms import ModelForm
from django import forms
from .models import Video, Tag

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
        
        