from django.db import models

# Create your models here.
class Project(models.Model):
    name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

class File(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    path = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    is_directory = models.BooleanField(default=False)