from rest_framework import serializers
from api.models import *

class TestSerizalizer(serializers.ModelSerializer):
    class Meta:
        model = TestModel
        fields = ('field1', 'field2')