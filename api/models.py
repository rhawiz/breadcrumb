import datetime
import json
import os

import thread
import urllib
from multiprocessing import Process
from time import sleep, time

# from breadcrumbcore.ai.facialrecognition import detect_face
import requests
import tweepy
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
from utils import analyse_text
from breadcrumbcore.utils.utils import get_hash8, random_hash8
from breadcrumbcore.searchengines.googlesearch import GoogleImageSearch

# from api import facial_recognition
from requests_oauthlib import OAuth1

from breadcrumb import settings

User._meta.get_field('email')._unique = True


class TestModel(models.Model):
    field1 = models.CharField(max_length=100, blank=True)
    field2 = models.IntegerField(blank=True)


def get_upload_avatar_path(instance, filename):
    timestamp = int(round(time() * 1000))

    path = "avatar/%s/%s_%s" % (instance.id, timestamp, filename)

    return path


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

    avatar = models.ImageField(upload_to=get_upload_avatar_path, blank=True, null=True, default=None, max_length=255)

    web_last_scanned = models.DateTimeField(blank=True, null=True, default=None)
    facebook_last_scanned = models.DateTimeField(blank=True, null=True, default=None)
    twitter_last_scanned = models.DateTimeField(blank=True, null=True, default=None)

    def get_avatar_url(self):
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        return None

    def scan_all_content(self):
        self._scan_twitter_content()
        self._scan_facebook_content()
        self._scan_web_content()
        self._scan_images()

    def _scan_facebook_content(self):
        try:
            fb_account = SocialAccount.objects.get(user_profile=self, provider='facebook')
        except SocialAccount.DoesNotExist:
            return None

        access_token = fb_account.social_token
        fc = FacebookCollector(access_token=access_token, sentiment_analyser=analyse_text)
        facebook_content = fc.run()
        for user_content in facebook_content:
            user = self
            content_type = 'text'
            source = 'facebook'
            content = user_content.get('message', None)
            url = user_content.get('permalink_url', None)
            hashed_url = get_hash8(url)
            if len(UserContent.objects.filter(hashed_url=hashed_url, user=self)) == 0:
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
                    UserContent.objects.create(
                        user=user, type=content_type, source=source, content=content, url=url, hashed_url=hashed_url,
                        neg_sentiment_rating=neg_sentiment_rating, pos_sentiment_rating=pos_sentiment_rating,
                        neut_sentiment_rating=neut_sentiment_rating, sentiment_label=sentiment_label,
                        extra_data=extra_data
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
            post_id = item['id']
            hashed_url = get_hash8(url)
            if len(UserContent.objects.filter(hashed_url=hashed_url, user=self)) == 0:
                sentiment_analysis = item.get('analysis', None)
                neg_sentiment_rating = None
                pos_sentiment_rating = None
                neut_sentiment_rating = None
                sentiment_label = None

                if not sentiment_analysis:
                    try:
                        sentiment_analysis = analyse_text(content)
                        print sentiment_analysis
                    except Exception as e:
                        print e
                        pass

                if sentiment_analysis:
                    neg_sentiment_rating = sentiment_analysis.get('probability').get('neg')
                    pos_sentiment_rating = sentiment_analysis.get('probability').get('pos')
                    neut_sentiment_rating = sentiment_analysis.get('probability').get('neutral')
                    sentiment_label = sentiment_analysis.get('label')

                extra_data = {'id': post_id}

                try:
                    print "creating content..."
                    content = UserContent.objects.create(
                        user=self, type=content_type, source=source, content=content, url=url, hashed_url=hashed_url,
                        neg_sentiment_rating=neg_sentiment_rating, pos_sentiment_rating=pos_sentiment_rating,
                        neut_sentiment_rating=neut_sentiment_rating, sentiment_label=sentiment_label,
                        extra_data=extra_data,
                    )
                except Exception, e:
                    print e

    def _scan_images(self):
        pass
        # model = facial_recognition.get_model()
        model = None
        if not model:
            print "Could not find face recognition model"
            return

        fullname = "%s %s" % (self.user.first_name, self.user.last_name)

        image_search = GoogleImageSearch(fullname, start=0, num=50, search_type="face")

        attempts = 0

        content_list = image_search.search()

        while not len(content_list) and attempts <= 5:
            content_list = image_search.search()
            attempts += 1

        for content in content_list:
            print content
            img_url = content.get("img_url") or None
            if not img_url:
                continue
            temp_file = os.path.abspath("media\\temp\\%s.jpg" % str(uuid.uuid4()))
            print temp_file
            try:
                urllib.urlretrieve(img_url, temp_file)
                # img = detect_face(temp_file)
                img = img.convert("L")
                os.remove(temp_file)
            except Exception as e:
                try:
                    os.remove(temp_file)
                except Exception as e:
                    print e
                continue
            img = img.convert("L")
            # p = model.predict(img)
            p = None
            if p == str(self.pk):
                user = self
                type = 'photo'
                source = 'web'
                source_content = content.get('text') or None
                url = content.get('img_url', None)
                extra_data = {"page_url": content.get('page_url')}
                hashed_url = get_hash8(url)

                try:
                    UserContent.objects.get(hashed_url=hashed_url, hidden=False, user=user).soft_delete()
                except UserContent.DoesNotExist:
                    pass

                try:
                    UserContent.objects.create(
                        user=user, type=type, source=source, content=source_content, url=url, hashed_url=hashed_url,
                        extra_data=extra_data, hidden=False
                    )
                except Exception, e:
                    print e
        print "Image scan complete"

    def _scan_web_content(self):
        search_content = []

        fullname = "%s %s" % (self.user.first_name, self.user.last_name)
        aliases = self.aliases or []
        long_search = fullname
        for alias in aliases:
            search_query = "{} {}".format(fullname, alias)
            long_search = "%s %s" % (long_search, alias)
            search_content.append(search_query)

        search_content.append(long_search)

        print long_search

        wc = WebCollector(aliases=search_content, results=15)
        user_web_content = wc.run()
        for user_content in user_web_content:
            user = self
            type = 'text'
            source = 'web'
            relevant_content = user_content.get('relevant_content')
            content = user_content.get('short_text', None)
            url = user_content.get('url', None)
            hashed_url = get_hash8(url)
            if len(UserContent.objects.filter(hashed_url=hashed_url, user=self)) == 0:
                sentiment_analysis = user_content.get('analysis', None)
                neg_sentiment_rating = None
                pos_sentiment_rating = None
                neut_sentiment_rating = None
                sentiment_label = None
                if not sentiment_analysis:
                    try:
                        if relevant_content:
                            sentiment_analysis = analyse_text(relevant_content)
                        else:
                            sentiment_analysis = analyse_text(content)

                        print sentiment_analysis
                    except Exception as e:
                        print e
                        pass
                if sentiment_analysis:
                    neg_sentiment_rating = sentiment_analysis.get('probability').get('neg')
                    pos_sentiment_rating = sentiment_analysis.get('probability').get('pos')
                    neut_sentiment_rating = sentiment_analysis.get('probability').get('neutral')
                    sentiment_label = sentiment_analysis.get('label')
                extra_data = json.dumps(user_content.get('relevant_content'))

                try:
                    UserContent.objects.create(
                        user=user, type=type, source=source, content=content, url=url, hashed_url=hashed_url,
                        neg_sentiment_rating=neg_sentiment_rating, pos_sentiment_rating=pos_sentiment_rating,
                        neut_sentiment_rating=neut_sentiment_rating, sentiment_label=sentiment_label,
                        extra_data=extra_data,
                        hidden=False,
                    )
                except Exception, e:
                    print e
        print "Web scan complete"

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
    social_username = models.CharField(max_length=255, blank=True, null=True, default=None)
    social_secret = models.CharField(max_length=255, blank=True, null=True, default=None)
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    authenticator = models.BooleanField(default=False)

    class Meta:
        unique_together = (("social_id", "user_profile", "provider"),)

    def __unicode__(self):
        return "{} ({})".format(self.user_profile.user.username, self.provider)


class Image(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField()
    user_profile = models.ForeignKey(UserProfile)
    local_path = models.CharField(max_length=500)

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
    type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_OTHER)
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, null=True, default=None)
    content = models.TextField(null=True)
    url = models.CharField(max_length=255, null=True, default=None)
    hashed_url = models.CharField(max_length=32, default=None)
    neg_sentiment_rating = models.DecimalField(null=True, blank=True, decimal_places=3, default=None, max_digits=3)
    pos_sentiment_rating = models.DecimalField(null=True, blank=True, decimal_places=3, default=None, max_digits=3)
    neut_sentiment_rating = models.DecimalField(null=True, blank=True, decimal_places=3, default=None, max_digits=3)
    sentiment_label = models.CharField(max_length=10, null=True, default=None)
    hidden = models.BooleanField(default=False)
    extra_data = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def take_down(self):
        if self.source == 'facebook':
            pass
        elif self.source == 'twitter':
            if self.extra_data:
                post_id = self.extra_data.get('id') or None
                try:
                    twitter_account = SocialAccount.objects.get(user_profile=self.user, provider='twitter')
                except SocialAccount.DoesNotExist:
                    return None
                if post_id:
                    auth = tweepy.OAuthHandler(settings.TWITTER_CONSUMER_KEY, settings.TWITTER_CONSUMER_SECRET)
                    auth.set_access_token(twitter_account.social_token, twitter_account.social_secret)

                    try:
                        api = tweepy.API(auth)
                        api.destroy_status(post_id)
                        self.soft_delete()
                    except Exception as e:
                        print e
        else:
            pass

    def soft_delete(self):
        self.hidden = True
        self.save()

    class Meta:
        unique_together = (("hashed_url", "user"),)

    def __unicode__(self):
        return "{} - {}".format(self.user.user.username, self.source)
