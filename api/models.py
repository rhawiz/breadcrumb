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



class SocialAccount(models.Model):
    PROVIDER_CHOICE_FACEBOOK = 'facebook'
    PROVIDER_CHOICE_TWITTER = 'twitter'
    PROVIDER_CHOICES = (
        (PROVIDER_CHOICE_FACEBOOK, 'facebook'),
        (PROVIDER_CHOICE_TWITTER, 'twitter'),
    )

    user = models.ForeignKey(UserProfile)
    social_id = models.CharField(max_length=255)
    social_token = models.CharField(max_length=255)
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)


class UserContent(models.Model):
    SOURCE_FACEBOOK = 'facebook'
    SOURCE_TWITTER = 'twitter'
    SOURCE_WEB = 'web'
    SOURCE_CHOICES = (
        (SOURCE_FACEBOOK, 'facebook'),
        (SOURCE_TWITTER, 'twitter'),
        (SOURCE_WEB, 'web'),
    )

    user = models.ForeignKey(UserProfile)
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    content = models.TextField(null=True)
    url = models.CharField(max_length=255)
    neg_sentiment_rating = models.DecimalField(decimal_places=3, default=0.0, max_digits=3)
    pos_sentiment_rating = models.DecimalField(decimal_places=3, default=0.0, max_digits=3)
    neut_sentiment_rating = models.DecimalField(decimal_places=3, default=0.0, max_digits=3)
    sentiment_label = models.CharField(max_length=10, null=True)
    extra_data = JSONField(null=True, blank=True)