from django.forms import ModelForm
from .models import Video

class ProjectForm(ModelForm):
    class Meta:
        model = Video
        fields = ['title', 'description', 'file', 'thumbnail', 'tags']
        