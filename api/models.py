from django.db import models

# Create your models here.

class TestModel(models.Model):
    field1 = models.CharField(max_length=100, blank=True)
    field2 = models.IntegerField(blank=True)