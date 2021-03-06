import datetime
import json
import os
from dateutil.parser import parse
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
from breadcrumbcore.ai.sentimentanalyser import analyse_text as analyse_text
from breadcrumbcore.utils.utils import get_hash8, random_hash8
from breadcrumbcore.searchengines.googlesearch import GoogleImageSearch

# from api import facial_recognition
from requests_oauthlib import OAuth1

from breadcrumb import settings

User._meta.get_field('email')._unique = True


def get_upload_avatar_path(instance, filename):
    timestamp = int(round(time() * 1000))

    path = "avatar/%s/%s_%s" % (instance.id, timestamp, filename)

    return path


class UserProfile(models.Model):
    """
    Model to store a user profile
    """
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
    phone = models.CharField(max_length=64, null=True, blank=True)

    def get_avatar_url(self):
        """
        Get the avatar url
        :return: The avatar URL or None if not set
        """
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        return None

    def generate_report(self):
        """
        Scan for user content and generate a report
        :return: None
        """
        formatted_date = str(datetime.date.today().strftime('%A %d %b %Y, %I:%M%p'))
        report = Report.objects.create(name=formatted_date, user_profile=self)
        self._scan_twitter_content(report)
        self._scan_facebook_content(report)
        self._scan_web_content(report)
        self._scan_images(report)

    def _scan_facebook_content(self, report=None):
        """
        Scan users facebook account and analyse content
        :param report: Associated Report object
        :return: None
        """
        if not report:
            formatted_date = str(datetime.date.today().strftime('%A %d %b %Y, %I:%M%p'))
            report = Report.objects.create(name=formatted_date, user_profile=self)
        try:
            fb_account = SocialAccount.objects.get(user_profile=self, provider='facebook')
        except SocialAccount.DoesNotExist:
            return None

        access_token = fb_account.social_token
        fc = FacebookCollector(access_token=access_token, sentiment_analyser=analyse_text)

        attempts = 0
        facebook_content = []
        while attempts <= 4:
            try:
                facebook_content = fc.run()
                break
            except Exception, e:
                print e
            attempts += 1

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
            created_at_timestamp = user_content.get('created_time')
            created_at_datetime = parse(created_at_timestamp)

            if sentiment_analysis:
                neg_sentiment_rating = sentiment_analysis.get('probability').get('neg')
                pos_sentiment_rating = sentiment_analysis.get('probability').get('pos')
                neut_sentiment_rating = sentiment_analysis.get('probability').get('neutral')
                sentiment_label = sentiment_analysis.get('label')

            extra_data = {
                'id': user_content.get('id'),
                'created_time': created_at_timestamp

            }
            old_content = UserContent.objects.filter(user=self, hashed_url=hashed_url).order_by("created_at")

            try:
                for c in old_content:
                    c.soft_delete()
                if not report or not isinstance(report, Report):
                    formatted_date = str(datetime.date.today().strftime('%A %d %b %Y, %I:%M%p'))
                    report = Report.objects.create(name=formatted_date, user_profile=user)
                UserContent.objects.create(
                    user=user, type=content_type, source=source, content=content, url=url, hashed_url=hashed_url,
                    neg_sentiment_rating=neg_sentiment_rating, pos_sentiment_rating=pos_sentiment_rating,
                    neut_sentiment_rating=neut_sentiment_rating, sentiment_label=sentiment_label,
                    extra_data=extra_data, hidden=False, report=report, post_created_at=created_at_datetime,
                )
            except Exception, e:
                print e
                if len(old_content):
                    old_content[0].hidden = False
                    old_content[0].save()
            print "Twitter scan complete."

    def _scan_twitter_content(self, report=None):
        """
        Scan users twitter account and analyse content
        :param report: Associated Report object
        :return: None
        """
        if not report:
            formatted_date = str(datetime.date.today().strftime('%A %d %b %Y, %I:%M%p'))
            report = Report.objects.create(name=formatted_date, user_profile=self)
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
        attempts = 0
        twitter_content = []
        while attempts <= 4:
            try:
                twitter_content = tc.run()
                break
            except Exception, e:
                print e
            attempts += 1
        for item in twitter_content:
            content_type = 'text'
            user = self
            source = 'twitter'
            content = item['text']
            url = item['url']
            post_id = item['id']
            created_at_timestamp = item['created_at_timestamp']
            created_at_datetime = datetime.datetime.fromtimestamp(created_at_timestamp)
            hashed_url = get_hash8(url)
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

            old_content = UserContent.objects.filter(user=self, hashed_url=hashed_url).order_by("created_at")
            try:
                for c in old_content:
                    c.soft_delete()
                if not report or not isinstance(report, Report):
                    formatted_date = str(datetime.date.today().strftime('%A %d %b %Y, %I:%M%p'))
                    report = Report.objects.create(name=formatted_date, user_profile=user)
                UserContent.objects.create(
                    user=self, type=content_type, source=source, content=content, url=url, hashed_url=hashed_url,
                    neg_sentiment_rating=neg_sentiment_rating, pos_sentiment_rating=pos_sentiment_rating,
                    neut_sentiment_rating=neut_sentiment_rating, sentiment_label=sentiment_label,
                    extra_data=extra_data, hidden=False, report=report, post_created_at=created_at_datetime,
                )

            except Exception, e:
                print e
                if len(old_content):
                    old_content[0].hidden = False
                    old_content[0].save()
            print "Twitter scan complete."

    def _scan_images(self, report=None):
        """
        Scan user images and analyse content
        :param report: Associated Report object
        :return: None
        """
        pass
        if not report:
            formatted_date = str(datetime.date.today().strftime('%A %d %b %Y, %I:%M%p'))
            report = Report.objects.create(name=formatted_date, user_profile=self)
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
                        extra_data=extra_data, hidden=False, report=report
                    )
                except Exception, e:
                    print e
        print "Image scan complete"

    def _scan_web_content(self, report=None):
        """
        Scan web for content and analyse content
        :param report: Associated Report object
        :return: None
        """

        search_content = []

        fullname = "%s %s" % (self.user.first_name, self.user.last_name)
        aliases = self.aliases or []
        long_search = fullname
        for alias in aliases:
            search_query = "{} {}".format(fullname, alias)
            long_search = "%s %s" % (long_search, alias)
            search_content.append(search_query)

        search_content.append(long_search)

        print search_content

        wc = WebCollector(sentiment_analyer=analyse_text, aliases=search_content, results=15)
        attempts = 0
        user_web_content = []
        while attempts <= 4:
            try:
                user_web_content = wc.run()
                break
            except Exception, e:
                print e
            attempts += 1

        for user_content in user_web_content:
            user = self
            type = 'text'
            source = 'web'
            relevant_content = user_content.get('relevant_content')
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
            old_content = UserContent.objects.filter(user=self, hashed_url=hashed_url).order_by("created_at")
            try:
                for c in old_content:
                    c.soft_delete()
                if not report or not isinstance(report, Report):
                    formatted_date = str(datetime.date.today().strftime('%A %d %b %Y, %I:%M%p'))
                    report = Report.objects.create(name=formatted_date, user_profile=user)
                UserContent.objects.create(
                    user=user, type=type, source=source, content=content, url=url, hashed_url=hashed_url,
                    neg_sentiment_rating=neg_sentiment_rating, pos_sentiment_rating=pos_sentiment_rating,
                    neut_sentiment_rating=neut_sentiment_rating, sentiment_label=sentiment_label,
                    extra_data=extra_data, hidden=False, report=report, post_created_at=datetime.datetime.now()
                )

            except Exception, e:
                print e
                if len(old_content):
                    old_content[0].hidden = False
                    old_content[0].save()
        print "Web scan complete"

    def __unicode__(self):
        return self.user.username


class SocialAccount(models.Model):
    """
    Model for storing a users social account (facebook/twitter)
    """
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
    """
    Model to store image data
    """
    name = models.CharField(max_length=255)
    url = models.URLField()
    user_profile = models.ForeignKey(UserProfile)
    local_path = models.CharField(max_length=500)

    def __unicode__(self):
        return self.name


class Report(models.Model):
    """
    Model to store a report
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(null=True, blank=True, max_length=255)
    user_profile = models.ForeignKey(UserProfile, null=True, default=None)

    def _get_content(self):
        return UserContent.objects.filter(report=self)

    def get_content_count(self):
        return len(UserContent.objects.filter(report=self))

    def formatted_date(self, format='%A %d %b %Y, %I:%M%p'):
        return str(self.created_at.strftime(format))

    def __unicode__(self):
        return self.name


class UserContent(models.Model):
    """
    Model to store a user information
    """
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
    post_created_at = models.DateTimeField(null=True, default=None, blank=True)
    report = models.ForeignKey(Report, null=True, default=None)

    def take_down(self):
        """
        Attempt to take down the content
        :return:
        """
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

    def __unicode__(self):
        return "{} - {}".format(self.user.user.username, self.source)
