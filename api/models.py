import datetime
import json

import thread
from multiprocessing import Process

from breadcrumbcore.contentcollectors.twittercollector import TwitterCollector
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

from breadcrumb import settings

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
        fc = FacebookCollector(access_token=access_token, sentiment_analyser=sentimentanalyser.analyse_text)
        facebook_content = fc.run()
        for user_content in facebook_content:
            user = self
            content_type = 'text'
            source = 'facebook'
            content = user_content.get('message', None)
            url = user_content.get('permalink_url', None)
            hashed_url = get_hash8(url)
            sentiment_analysis = user_content.get('analysis', None)
            neg_sentiment_rating = None
            pos_sentiment_rating = None
            neut_sentiment_rating = None
            sentiment_label = None
            if sentiment_analysis:
                neg_sentiment_rating = sentiment_analysis.get('probability').get('neg')
                pos_sentiment_rating = sentiment_analysis.get('probability').get('pos')
                neut_sentiment_rating = sentiment_analysis.get('probability').get('neutral')
                sentiment_label = sentiment_analysis.get('label')

            extra_data = {
                'id': user_content.get('id'),
                'created_time': user_content.get('created_time')

            }
            try:
                UserContent.objects.get(hashed_url=hashed_url).delete()
            except UserContent.DoesNotExist:
                pass

            try:
                UserContent.objects.create(
                    user=user, type=content_type, source=source, content=content, url=url, hashed_url=hashed_url,
                    neg_sentiment_rating=neg_sentiment_rating, pos_sentiment_rating=pos_sentiment_rating,
                    neut_sentiment_rating=neut_sentiment_rating, sentiment_label=sentiment_label, extra_data=extra_data
                )
            except Exception, e:
                print e

    def _scan_twitter_content(self):
        try:
            twitter_account = SocialAccount.objects.get(user_profile=self, provider='twitter')
        except SocialAccount.DoesNotExist:
            return None

        key = twitter_account.social_token
        secret = twitter_account.social_secret

        consumer_secret = settings.TWITTER_CONSUMER_SECRET
        consumer_key = settings.TWITTER_CONSUMER_KEY

        tc = TwitterCollector(
            key=key,
            secret=secret,
            consumer_secret=consumer_secret,
            consumer_key=consumer_key,
        )
        twitter_content = tc.run()
        for item in twitter_content:
            content_type = 'text'
            source = 'twitter'
            content = item['text']
            url = item['url']
            hashed_url = get_hash8(url)
            if UserContent.objects.filter(hashed_url=hashed_url) == 0:
                sentiment_analysis = item.get('analysis', None)
                neg_sentiment_rating = None
                pos_sentiment_rating = None
                neut_sentiment_rating = None
                sentiment_label = None

                if not sentiment_analysis:
                    try:
                        sentiment_analysis = sentimentanalyser.analyse_text(content)
                    except Exception:
                        pass

                if sentiment_analysis:
                    neg_sentiment_rating = sentiment_analysis.get('probability').get('neg')
                    pos_sentiment_rating = sentiment_analysis.get('probability').get('pos')
                    neut_sentiment_rating = sentiment_analysis.get('probability').get('neutral')
                    sentiment_label = sentiment_analysis.get('label')

                try:
                    content = UserContent.objects.create(
                        user=self, type=content_type, source=source, content=content, url=url, hashed_url=hashed_url,
                        neg_sentiment_rating=neg_sentiment_rating, pos_sentiment_rating=pos_sentiment_rating,
                        neut_sentiment_rating=neut_sentiment_rating, sentiment_label=sentiment_label
                    )
                    print content
                except Exception, e:
                    print e

    def _scan_web_content(self):
        search_content = []

        fullname = "{} {}".format(self.user.first_name, self.user.last_name)
        aliases = self.aliases or []
        for alias in aliases:
            search_query = "{} {}".format(fullname, alias)
            search_content.append(search_query)

        print search_content

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
            neg_sentiment_rating = None
            pos_sentiment_rating = None
            neut_sentiment_rating = None
            sentiment_label = None
            if sentiment_analysis:
                neg_sentiment_rating = sentiment_analysis.get('probability').get('neg')
                pos_sentiment_rating = sentiment_analysis.get('probability').get('pos')
                neut_sentiment_rating = sentiment_analysis.get('probability').get('neutral')
                sentiment_label = sentiment_analysis.get('label')
            extra_data = json.dumps(user_content.get('relevant_content'))

            try:
                UserContent.objects.get(hashed_url=hashed_url).delete()
            except UserContent.DoesNotExist:
                pass

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
    social_secret = models.CharField(max_length=255, null=True, default=None)
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)

    def __unicode__(self):
        return "{} ({})".format(self.user_profile.user.username, self.provider)


class Image(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField()
    user_profile = models.ForeignKey(UserProfile)

    def __unicode__(self):
        return self.name


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
    hashed_url = models.CharField(unique=True, max_length=32, default=None)
    neg_sentiment_rating = models.DecimalField(null=True, blank=True, decimal_places=3, default=None, max_digits=3)
    pos_sentiment_rating = models.DecimalField(null=True, blank=True, decimal_places=3, default=None, max_digits=3)
    neut_sentiment_rating = models.DecimalField(null=True, blank=True, decimal_places=3, default=None, max_digits=3)
    sentiment_label = models.CharField(max_length=10, null=True, default=None)
    extra_data = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
