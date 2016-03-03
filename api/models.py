from django.db import models
from django.contrib.auth.models import User
import uuid
from django.db.models import signals


# Create your models here.
from jsonfield import JSONField

from django.contrib.auth.models import User
User._meta.get_field('email')._unique = True

class TestModel(models.Model):
    field1 = models.CharField(max_length=100, blank=True)
    field2 = models.IntegerField(blank=True)


class UserProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, blank=False, null=False)

    GENDER_CHOICE_UNSET = 0
    GENDER_CHOICE_MALE = 1
    GENDER_CHOICE_FEMALE = 2
    GENDER_CHOICES = (
        (GENDER_CHOICE_UNSET, 'Unset'),
        (GENDER_CHOICE_MALE, 'Male'),
        (GENDER_CHOICE_FEMALE, 'Female'),
    )
    gender = models.IntegerField(choices=GENDER_CHOICES, default=GENDER_CHOICE_UNSET)

    aliases = JSONField(null=True, blank=True)

    def __unicode__(self):
        return self.user.username


# def delete_user(sender, instance, **kwargs):
#     user = instance.user
#     user.delete()
#
# signals.post_delete()
