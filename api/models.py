import datetime
import json

import thread
from multiprocessing import Process

from breadcrumbcore.contentcollectors.webcollector import WebCollector
from breadcrumbcore.contentcollectors.facebookcollector import FacebookCollector
from django.db import models
from django.contrib.auth.models import User
import uuid
from django.db.models import signals

# Create your models here.
from jsonfield import JSONField

from django.contrib.auth.models import User
from breadcrumbcore.ai import sentimentanalyser
from breadcrumbcore.utils.utils import get_hash8, random_hash8

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

    web_last_scanned = models.DateTimeField(blank=True, null=True, default=None)
    facebook_last_scanned = models.DateTimeField(blank=True, null=True, default=None)
    twitter_last_scanned = models.DateTimeField(blank=True, null=True, default=None)

    def scan_all_content(self):
        self._scan_facebook_content()
        self._scan_twitter_content()
        self._scan_web_content()

    def _scan_facebook_content(self):
        try:
            fb_account = SocialAccount.objects.get(user_profile=self, provider='facebook')
        except SocialAccount.DoesNotExist:
            return None

        access_token = fb_account.social_token
        fc = FacebookCollector(access_token=access_token)
        facebook_content = fc.run()
        for content in facebook_content:
            user = self
            type = 'text'
            source = 'facebook'
            content = content.get('short_text', None)
            url = content.get('url', None)
            hashed_url = get_hash8(url)
            sentiment_analysis = user_content.get('analysis', None)
            neg_sentiment_rating = sentiment_analysis.get('probability').get('neg')
            pos_sentiment_rating = sentiment_analysis.get('probability').get('pos')
            neut_sentiment_rating = sentiment_analysis.get('probability').get('neutral')
            sentiment_label = sentiment_analysis.get('label')
            extra_data = json.dumps(user_content.get('relevant_content'))

            try:
                UserContent.objects.create(
                    user=user, type=type, source=source, content=content, url=url, hashed_url=hashed_url,
                    neg_sentiment_rating=neg_sentiment_rating, pos_sentiment_rating=pos_sentiment_rating,
                    neut_sentiment_rating=neut_sentiment_rating, sentiment_label=sentiment_label, extra_data=extra_data
                )
            except Exception, e:
                print e

    def _scan_twitter_content(self):
        print "Twitter scan complete todo: Push notifications"

    def _scan_web_content(self):
        search_content = self.aliases
        if not search_content:
            search_content = []
        first_name = self.user.first_name
        last_name = self.user.last_name

        if first_name and last_name:
            search_content.append("{} {}".format(first_name, last_name))

        wc = WebCollector(sentiment_analyer=sentimentanalyser.analyse_text, aliases=search_content, results=50)
        user_web_content = wc.run()
        for user_content in user_web_content:
            user = self
            type = 'text'
            source = 'web'
            content = user_content.get('short_text', None)
            url = user_content.get('url', None)
            hashed_url = get_hash8(url)
            sentiment_analysis = user_content.get('analysis', None)
            neg_sentiment_rating = sentiment_analysis.get('probability').get('neg')
            pos_sentiment_rating = sentiment_analysis.get('probability').get('pos')
            neut_sentiment_rating = sentiment_analysis.get('probability').get('neutral')
            sentiment_label = sentiment_analysis.get('label')
            extra_data = json.dumps(user_content.get('relevant_content'))

            try:
                UserContent.objects.create(
                    user=user, type=type, source=source, content=content, url=url, hashed_url=hashed_url,
                    neg_sentiment_rating=neg_sentiment_rating, pos_sentiment_rating=pos_sentiment_rating,
                    neut_sentiment_rating=neut_sentiment_rating, sentiment_label=sentiment_label, extra_data=extra_data
                )
            except Exception, e:
                print e
        print "Web scan complete todo: Push notifications"

    def __unicode__(self):
        return self.user.username


class SocialAccount(models.Model):
    PROVIDER_CHOICE_FACEBOOK = 'facebook'
    PROVIDER_CHOICE_TWITTER = 'twitter'
    PROVIDER_CHOICES = (
        (PROVIDER_CHOICE_FACEBOOK, 'facebook'),
        (PROVIDER_CHOICE_TWITTER, 'twitter'),
    )

    user_profile = models.ForeignKey(UserProfile)
    social_id = models.CharField(max_length=255)
    social_token = models.CharField(max_length=255)
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)

    def __unicode__(self):
        return "{} ({})".format(self.user_profile.user.username, self.provider)


class UserContent(models.Model):
    SOURCE_FACEBOOK = 'facebook'
    SOURCE_TWITTER = 'twitter'
    SOURCE_WEB = 'web'
    SOURCE_CHOICES = (
        (SOURCE_FACEBOOK, 'Facebook'),
        (SOURCE_TWITTER, 'Twitter'),
        (SOURCE_WEB, 'web'),
    )

    TYPE_PHOTO = 'photo'
    TYPE_TEXT = 'text'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = (
        (TYPE_PHOTO, 'Photo'),
        (TYPE_TEXT, 'Text'),
        (TYPE_OTHER, 'Other'),
    )

    user = models.ForeignKey(UserProfile)
    type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    content = models.TextField(null=True)
    url = models.CharField(max_length=255)
    hashed_url = models.CharField(unique=True, max_length=32, default=random_hash8())
    neg_sentiment_rating = models.DecimalField(decimal_places=3, default=0.0, max_digits=3)
    pos_sentiment_rating = models.DecimalField(decimal_places=3, default=0.0, max_digits=3)
    neut_sentiment_rating = models.DecimalField(decimal_places=3, default=0.0, max_digits=3)
    sentiment_label = models.CharField(max_length=10, null=True)
    extra_data = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
