import os
import urllib2
import urlparse
from base64 import b64decode
from tempfile import NamedTemporaryFile

import requests
from django.contrib.sessions.backends.db import SessionStore
import tweepy
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import MultipleObjectsReturned
from django.core.files import File
from io import BytesIO

from django.core.files.base import ContentFile
from oauth2_provider.models import Application, AccessToken
from rest_framework import serializers
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from api.exceptions import *
from rest_framework.exceptions import *

# from api.facial_recognition import update_face_rec_model
from api.models import *
from rest_framework.utils import model_meta

from api.utils import generate_access_token, get_user_profile_from_token, is_valid_base64, supermakedirs
from rest_framework.fields import empty
import time
import requests as r
from requests_oauthlib import OAuth2, OAuth1


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            'username', 'first_name', 'last_name', 'password', 'email',
        )
        write_only_fields = ('password')

    def create(self, validated_data):
        user = User.objects.create(**validated_data)
        user.set_password(validated_data.pop('password'))
        user.save()
        return user

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            if attr == 'password':
                instance.set_password(value)
            else:
                setattr(instance, attr, value)

        instance.save()
        return instance


class AccountSerializer(serializers.Serializer):
    account = serializers.CharField(required=True)
    name = serializers.CharField(required=True)

    class Meta:
        fields = (
            'account', 'name'
        )


class AccountDetailSerializer(serializers.Serializer):
    positive = serializers.IntegerField()
    negative = serializers.IntegerField()
    neutral = serializers.IntegerField()
    rating = serializers.CharField()

    class Meta:
        fields = (
            'positive', 'negative', 'neutral', 'rating'
        )


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(read_only=True, source='user.username')
    email = serializers.CharField(read_only=True, source='user.email')
    first_name = serializers.CharField(read_only=True, source='user.first_name')
    last_name = serializers.CharField(read_only=True, source='user.last_name')
    avatar = serializers.CharField(read_only=True, source='get_avatar_url')

    class Meta:
        model = UserProfile
        fields = ('id', 'gender', 'username', 'email', 'first_name', 'last_name', 'aliases', 'avatar')


class ContentSerializer(serializers.ModelSerializer):
    created_at_timestamp = serializers.SerializerMethodField('_get_post_created_timestamp')
    sentiment = serializers.SerializerMethodField('_get_sentiment')

    class Meta:
        model = UserContent
        fields = ('id', 'content', 'created_at_timestamp', 'type', 'source', 'url', 'sentiment',
                  'neg_sentiment_rating', 'pos_sentiment_rating', 'neut_sentiment_rating', 'sentiment_label')

        extra_kwargs = {
            'neg_sentiment_rating': {'write_only': True},
            'pos_sentiment_rating': {'write_only': True},
            'neut_sentiment_rating': {'write_only': True},
            'sentiment_label': {'write_only': True},
        }

    def _get_post_created_timestamp(self, obj):
        if obj.post_created_at:
            return int(time.mktime(obj.post_created_at.timetuple()))
        return int(time.mktime(obj.created_at.timetuple()))

    def _get_sentiment(self, obj):
        return {
            "neg": obj.neg_sentiment_rating,
            "pos": obj.pos_sentiment_rating,
            "neut": obj.neut_sentiment_rating,
            "label": obj.sentiment_label,
        }


class ReportSerializer(serializers.ModelSerializer):
    content_count = serializers.IntegerField(source='get_content_count', read_only=True)

    class Meta:
        model = Report
        fields = (
            'id', 'name', 'created_at',
        )


class ReportDetailSerializer(serializers.ModelSerializer):
    content = ContentSerializer(source='_get_content', many=True)

    class Meta:
        model = Report
        fields = (
            'id', 'name', 'created_at', 'content'
        )


class UpdateUserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=False, write_only=True)
    email = serializers.CharField(required=False, write_only=True)
    first_name = serializers.CharField(required=False, write_only=True)
    last_name = serializers.CharField(required=False, write_only=True)
    aliases = serializers.ListField(required=False, write_only=True)
    avatar_base64 = serializers.CharField(required=False, write_only=True)
    avatar_url = serializers.CharField(required=False, write_only=True)

    class Meta:
        model = UserProfile
        fields = ('username', 'email', 'first_name', 'last_name', 'aliases', 'avatar_base64', 'avatar_url')

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            if attr == 'avatar_base64':
                avatar_base64 = b64decode(validated_data.get('avatar_base64'))
                img_filename = "%s.%s" % (str(uuid.uuid4()), "jpg")
                instance.avatar = ContentFile(avatar_base64, img_filename)
                instance.save()
            elif attr == 'avatar_url':
                avatar_url = validated_data.get('avatar_url')
                response = urllib2.urlopen(avatar_url)
                content_type = response.info().getheader('Content-Type')
                extension = "jpg"
                if 'image' in content_type:
                    parts = content_type.split('/')
                    extension = parts[1] or 'jpg'
                img_filename = "%s.%s" % (str(uuid.uuid4()), extension)

                img_temp = NamedTemporaryFile(delete=True)
                img_temp.write(response.read())
                img_temp.flush()
                instance.avatar.save(img_filename, File(img_temp))
            if hasattr(instance, attr):
                setattr(instance, attr, value)
            elif hasattr(instance.user, attr):
                setattr(instance.user, attr, value)
        instance.save()
        instance.user.save()
        self._data = UserProfileSerializer(instance).data
        return instance


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(required=True, write_only=True)
    email = serializers.CharField(required=True, write_only=True)
    password = serializers.CharField(required=True, write_only=True)
    first_name = serializers.CharField(required=False, write_only=True)
    last_name = serializers.CharField(required=False, write_only=True)
    fullname = serializers.CharField(required=False, write_only=True)
    gender = serializers.IntegerField(required=False, write_only=True)
    avatar_url = serializers.CharField(required=False, write_only=True)
    avatar_base64 = serializers.CharField(required=False, write_only=True)
    aliases = serializers.JSONField(required=False)

    class Meta:
        model = UserProfile
        fields = ('id', 'gender', 'username', 'email', 'password', 'first_name', 'last_name', 'aliases', 'avatar_url',
                  'avatar_base64')

    def create(self, validated_data):

        if 'fullname' in validated_data:
            if validated_data['fullname'].find(' ') != -1:
                first_name, last_name = validated_data['fullname'].split(' ')
                validated_data['first_name'] = first_name
                validated_data['last_name'] = last_name

        user_serializer = UserSerializer(data=validated_data)

        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()

        user_profile_data = {}
        user_profile_fields = ['gender', 'aliases']
        for field in user_profile_fields:
            if field in validated_data:
                user_profile_data[field] = validated_data[field]

        user_profile_data['user'] = user

        user_profile = UserProfile.objects.create(**user_profile_data)
        user_profile.save()

        if 'avatar_base64' in validated_data:
            avatar_base64 = b64decode(validated_data.get('avatar_base64'))
            img_filename = "%s.%s" % (str(uuid.uuid4()), "jpg")
            user_profile.avatar = ContentFile(avatar_base64, img_filename)
            user_profile.save()
        elif 'avatar_url' in validated_data:
            avatar_url = validated_data.get('avatar_url')
            response = urllib2.urlopen(avatar_url)
            content_type = response.info().getheader('Content-Type')
            extension = "jpg"
            if 'image' in content_type:
                parts = content_type.split('/')
                extension = parts[1] or 'jpg'
            img_filename = "%s.%s" % (str(uuid.uuid4()), extension)

            img_temp = NamedTemporaryFile(delete=True)
            img_temp.write(response.read())
            img_temp.flush()

            user_profile.avatar.save(img_filename, File(img_temp))

        access_token = generate_access_token(user)

        user_data = UserSerializer(user_profile.user).data
        self._data = {
            "access_token": str(access_token),
            'user': user_data,
        }

        return user_profile


class FacebookLoginSerializer(serializers.Serializer):
    code = serializers.CharField(required=True)

    class Meta:
        fields = ('code')

    def create(self, validated_data):

        fb_id = validated_data.get('fb_id')
        fullname = validated_data.get('name')
        email = validated_data.get('email')
        gender = validated_data.get('gender')
        avatar_url = validated_data.get('avatar_url')
        fb_access_token = validated_data.get('fb_access_token')

        gender_id = 0
        if gender == 'male':
            gender_id = 1
        elif gender == 'female':
            gender_id = 2

        social_account = None
        try:
            social_account = SocialAccount.objects.get(provider='facebook', social_id=fb_id, authenticator=True)
            social_account.social_token = fb_access_token
            social_account.social_username = fullname
            social_account.save()
        except SocialAccount.DoesNotExist:
            user_profile_data = {
                'username': email,
                'email': email,
                'password': uuid.uuid4(),
                'fullname': fullname,
                'gender': gender_id,
                'avatar_url': avatar_url,
            }
            user_profile_serializer = SignupSerializer(data=user_profile_data)
            user_profile_serializer.is_valid(raise_exception=True)
            user_profile = user_profile_serializer.save()
            social_account = SocialAccount.objects.create(user_profile=user_profile,
                                                          social_username=fullname,
                                                          social_id=fb_id,
                                                          social_token=fb_access_token,
                                                          provider='facebook',
                                                          authenticator=True)

        user_profile = social_account.user_profile
        access_token = generate_access_token(user_profile.user)

        user_data = UserSerializer(user_profile.user).data

        self._data = {
            "access_token": str(access_token),
            'user': user_data,
        }

        return user_profile

    def validate(self, data):
        code = data.get('code', None)
        client_id = getattr(settings, "FACEBOOK_CLIENT_ID", None)
        client_secret = getattr(settings, "FACEBOOK_CLIENT_SECRET", None)
        callback_url = getattr(settings, "FACEBOOK_CALLBACK_URL", None)

        if not client_id:
            raise ValidationError(detail={'client_id': 'Cannot find FACEBOOK_CLIENT_ID in django settings'})

        if not client_secret:
            raise ValidationError(detail={'client_secret': 'Cannot find FACEBOOK_CLIENT_SECRET in django settings'})

        if not callback_url:
            raise ValidationError(detail={'callback_url': 'Cannot find FACEBOOK_CALLBACK_URL in django settings'})

        if not code:
            raise ValidationError(detail={'code': 'This field is required.'})

        fb_token_url = "https://graph.facebook.com/oauth/access_token?code={}&client_id={}&client_secret={}&redirect_uri={}".format(
            code, client_id, client_secret, callback_url)

        fb_access_token_response = r.get(fb_token_url)

        fb_access_token_response_parts = urlparse.parse_qsl(fb_access_token_response.content)

        fb_access_token = None

        for part in fb_access_token_response_parts:
            if part[0] == 'access_token':
                fb_access_token = part[1]

        if not fb_access_token:
            raise ValidationError(detail={'access_token': 'Could not retrieve Facebook access token'})

        user_info_url = "https://graph.facebook.com/v2.5/me?access_token={}&fields=id,name,email,gender".format(
            fb_access_token)

        user_info_response = r.get(user_info_url).json()

        fb_id = user_info_response.get('id')
        fullname = user_info_response.get('name')
        gender = user_info_response.get('gender')
        avatar_url = "https://graph.facebook.com/%s/picture?width=1000" % fb_id
        email = user_info_response.get('email')
        try:
            User.objects.get(email=email)
            email = "%s%s@bc.com" % (fullname.replace(" ", "").lower(), str(uuid.uuid4())[:8])
        except User.DoesNotExist:
            pass

        return {
            'fb_id': fb_id,
            'name': fullname,
            'email': email,
            'gender': gender,
            'avatar_url': avatar_url,
            'fb_access_token': fb_access_token
        }


class LinkFacebookAccountSerializer(serializers.Serializer):
    code = serializers.CharField(required=True)
    access_token = serializers.CharField(required=True)

    class Meta:
        fields = ('code', 'access_token')

    def create(self, validated_data):
        fb_access_token = validated_data.get('fb_access_token', None)
        user_profile = validated_data.get('user_profile', None)
        fb_id = validated_data.get('fb_id', None)
        fullname = validated_data.get('fullname', None)

        try:
            social_account = SocialAccount.objects.get(
                provider='facebook',
                social_id=fb_id,
                user_profile=user_profile
            )
        except SocialAccount.DoesNotExist:
            social_account = SocialAccount.objects.create(
                user_profile=user_profile,
                social_id=fb_id,
                social_token=fb_access_token,
                provider='facebook',
                authenticator=False,
                social_username=fullname,

            )

        self._data = {
            "social_id": social_account.social_id,
            "provider": "facebook",
            "user": UserSerializer(social_account.user_profile.user).data
        }

        return social_account

    def validate(self, data):
        code = data.get('code', None)
        access_token = data.get('access_token', None)
        client_id = getattr(settings, "FACEBOOK_CLIENT_ID", None)
        client_secret = getattr(settings, "FACEBOOK_CLIENT_SECRET", None)
        callback_url = getattr(settings, "FACEBOOK_CALLBACK_URL", None)

        try:
            AccessToken.objects.get(token=access_token)
        except AccessToken.DoesNotExist:
            raise NotAuthenticated()

        if not client_id:
            raise ValidationError(detail={'client_id': 'Cannot find FACEBOOK_CLIENT_ID in django settings'})

        if not client_secret:
            raise ValidationError(detail={'client_secret': 'Cannot find FACEBOOK_CLIENT_SECRET in django settings'})

        if not callback_url:
            raise ValidationError(detail={'callback_url': 'Cannot find FACEBOOK_CALLBACK_URL in django settings'})

        if not code:
            raise ValidationError(detail={'code': 'This field is required.'})

        fb_token_url = "https://graph.facebook.com/oauth/access_token?code={}&client_id={}&client_secret={}&redirect_uri={}".format(
            code, client_id, client_secret, callback_url)

        fb_access_token_response = r.get(fb_token_url)

        fb_access_token_response_parts = urlparse.parse_qsl(fb_access_token_response.content)

        fb_access_token = None

        for part in fb_access_token_response_parts:
            if part[0] == 'access_token':
                fb_access_token = part[1]

        if not fb_access_token:
            raise ValidationError(detail={'access_token': 'Could not retrieve Facebook access token'})

        user_info_url = "https://graph.facebook.com/v2.5/me?access_token={}&fields=id,name,email,gender".format(
            fb_access_token)

        user_info_response = r.get(user_info_url).json()
        fb_id = user_info_response.get('id')
        fullname = user_info_response.get('name')
        user_profile = get_user_profile_from_token("Bearer %s" % access_token)

        return {'fb_access_token': fb_access_token,
                'user_profile': user_profile,
                'fb_id': fb_id,
                'fullname': fullname,
                }


class LinkTwitterAccountSerializer(serializers.Serializer):
    oauth_verifier = serializers.CharField(write_only=True)
    request_token = serializers.DictField(write_only=True)
    access_token = serializers.CharField(write_only=True)

    def create(self, validated_data):
        key = validated_data.get('key')
        secret = validated_data.get('secret')
        twitter_id = validated_data.get('twitter_id')
        user_profile = validated_data.get('user_profile')
        social_username = validated_data.get('social_username')

        social_account = None
        try:
            social_account = SocialAccount.objects.get(
                provider='twitter',
                user_profile=user_profile
            )
        except SocialAccount.DoesNotExist:
            social_account = SocialAccount.objects.create(
                user_profile=user_profile,
                social_id=twitter_id,
                social_token=key,
                social_secret=secret,
                social_username=social_username,
                provider='twitter',
                authenticator=False,
            )

        self._data = {
            "social_id": social_account.social_id,
            "provider": "twitter",
            "user": UserSerializer(social_account.user_profile.user).data
        }

        return social_account

    def validate(self, data):
        verifier = data.get('oauth_verifier', None)
        request_token = data.get('request_token', None)
        access_token = data.get('access_token', None)
        consumer_key = getattr(settings, "TWITTER_CONSUMER_KEY", None)
        consumer_secret = getattr(settings, "TWITTER_CONSUMER_SECRET", None)
        callback_url = getattr(settings, "TWITTER_CALLBACK_URL", None)
        if not consumer_key:
            raise ValidationError(detail={'client_id': 'Cannot find TWITTER_CONSUMER_KEY in django settings'})
        if not consumer_secret:
            raise ValidationError(detail={'client_secret': 'Cannot find TWITTER_CONSUMER_SECRET in django settings'})
        if not callback_url:
            raise ValidationError(detail={'callback_url': 'Cannot find TWITTER_CALLBACK_URL in django settings'})
        if not verifier:
            raise ValidationError(detail={'oauth_verifier': 'This field is required.'})
        if not request_token:
            raise ValidationError(detail={'request_token': 'This field is required.'})

        auth = tweepy.OAuthHandler(
            settings.TWITTER_CONSUMER_KEY,
            settings.TWITTER_CONSUMER_SECRET
        )
        auth.request_token = request_token
        key, secret = auth.get_access_token(verifier)

        try:
            AccessToken.objects.get(token=access_token)
        except AccessToken.DoesNotExist:
            raise NotAuthenticated()

        url = "https://api.twitter.com/1.1/account/verify_credentials.json?&include_email=true"
        auth = OAuth1(consumer_key, consumer_secret, key, secret)
        r = requests.get(url=url, auth=auth)
        twitter_data = r.json()
        twitter_id = twitter_data.get('id')
        user_profile = get_user_profile_from_token("Bearer %s" % access_token)
        social_username = twitter_data.get('screen_name') or None

        return {
            'key': key,
            'secret': secret,
            'twitter_id': twitter_id,
            'user_profile': user_profile,
            'social_username': social_username,
        }

    class Meta:
        fields = ('oauth_verifier', 'request_token', 'access_token')


class TwitterLoginSerializer(serializers.Serializer):
    oauth_verifier = serializers.CharField(write_only=True)
    request_token = serializers.DictField(write_only=True)

    def create(self, validated_data):
        key = validated_data.get('key')
        secret = validated_data.get('secret')
        fullname = validated_data.get('fullname')
        email = validated_data.get('email')
        twitter_id = validated_data.get('twitter_id')
        username = validated_data.get('username')
        social_username = validated_data.get('social_username')
        avatar_url = validated_data.get('avatar_url')

        social_account = None

        try:
            social_account = SocialAccount.objects.get(provider='twitter', social_id=twitter_id, authenticator=True)
            social_account.social_secret = secret
            social_account.social_token = key
            social_account.save()
        except SocialAccount.DoesNotExist:
            user_profile_data = {
                'username': username,
                'email': email,
                'password': uuid.uuid4(),
                'fullname': fullname,
                'avatar_url': avatar_url,
            }
            user_profile_serializer = SignupSerializer(data=user_profile_data)
            user_profile_serializer.is_valid(raise_exception=True)
            user_profile = user_profile_serializer.save()
            social_account = SocialAccount.objects.create(
                social_username=social_username,
                user_profile=user_profile,
                social_id=twitter_id,
                social_token=key,
                social_secret=secret,
                provider='twitter'
            )

        user_profile = social_account.user_profile
        access_token = generate_access_token(user_profile.user)

        user_data = UserSerializer(user_profile.user).data
        self._data = {
            "access_token": str(access_token),
            'user': user_data,
        }

        return user_profile

    def validate(self, data):
        verifier = data.get('oauth_verifier', None)
        request_token = data.get('request_token', None)
        consumer_key = getattr(settings, "TWITTER_CONSUMER_KEY", None)
        consumer_secret = getattr(settings, "TWITTER_CONSUMER_SECRET", None)
        callback_url = getattr(settings, "TWITTER_CALLBACK_URL", None)
        if not consumer_key:
            raise ValidationError(detail={'client_id': 'Cannot find TWITTER_CONSUMER_KEY in django settings'})
        if not consumer_secret:
            raise ValidationError(detail={'client_secret': 'Cannot find TWITTER_CONSUMER_SECRET in django settings'})
        if not callback_url:
            raise ValidationError(detail={'callback_url': 'Cannot find TWITTER_CALLBACK_URL in django settings'})
        if not verifier:
            raise ValidationError(detail={'oauth_verifier': 'This field is required.'})
        if not request_token:
            raise ValidationError(detail={'request_token': 'This field is required.'})

        auth = tweepy.OAuthHandler(
            settings.TWITTER_CONSUMER_KEY,
            settings.TWITTER_CONSUMER_SECRET
        )
        auth.request_token = request_token
        key, secret = auth.get_access_token(verifier)

        url = "https://api.twitter.com/1.1/account/verify_credentials.json?&include_email=true"
        auth = OAuth1(consumer_key, consumer_secret, key, secret)
        r = requests.get(url=url, auth=auth)
        twitter_data = r.json()
        twitter_id = twitter_data.get('id')
        fullname = twitter_data.get('name')
        email = twitter_data.get('email')
        avatar_url = twitter_data.get('profile_image_url')
        social_username = twitter_data.get('screen_name') or None

        try:
            User.objects.get(email=email)
            email = "%s%s@bc.com" % (fullname.replace(" ", "").lower(), str(uuid.uuid4())[:8])
        except User.DoesNotExist:
            pass

        username = twitter_data.get('screen_name') or email
        try:
            User.objects.get(username=username)
            username = email
        except User.DoesNotExist:
            pass

        return {
            'key': key,
            'secret': secret,
            'twitter_id': twitter_id,
            'fullname': fullname,
            'email': email,
            'username': username,
            'avatar_url': avatar_url,
            'social_username': social_username,
        }

    class Meta:
        fields = ('oauth_verifier', 'request_token')


class AccessTokenSerializer(serializers.ModelSerializer):
    expires = serializers.SerializerMethodField('_get_expires_timestamp')

    class Meta:
        model = AccessToken
        fields = ('token', 'expires', 'scope')

    def _get_expires_timestamp(self, obj):
        return int(time.mktime(obj.expires.timetuple()))


class LoginSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=False)
    password = serializers.CharField(required=True)
    email = serializers.CharField(required=False)

    def create(self, validated_data):
        user = validated_data.get('user')
        access_token = generate_access_token(user)

        user_data = UserSerializer(user).data
        self._data = {
            "access_token": str(access_token),
            'user': user_data,
        }

        return access_token

    def validate(self, data):

        username = data.get('username', None)
        email = data.get('email', None)
        password = data.get('password', None)

        if not password:
            raise NotAuthenticated()
        if username:
            user = authenticate(username=username, password=password)
        elif email:
            user = authenticate(username=email, password=password)
        else:
            raise NotAuthenticated()
        if not user:
            raise AuthenticationFailed()

        return {'user': user}

    class Meta:
        model = AccessToken
        fields = ('username', 'email', 'password')


class UploadImageSerializer(serializers.ModelSerializer):
    image_base64 = serializers.CharField(required=True)
    access_token = serializers.CharField(required=True)
    name = serializers.CharField(required=False)
    url = serializers.CharField(required=False, read_only=True)

    def create(self, validated_data):
        user_profile = validated_data.get('user')
        image_base64 = validated_data.get('image_base64')
        file_name = "{}.jpg".format(str(uuid.uuid4()))
        file_path = "{}/users/{}".format(settings.MEDIA_ROOT, user_profile.id)
        if not os.path.exists(file_path):
            os.mkdir(file_path)
        name = validated_data.get('name') or file_name.split(".")[0]

        file_path = "%s/%s" % (file_path, file_name)
        fh = open(file_path, "wb")

        fh.write(image_base64.decode('base64'))
        fh.close()
        url = "{}users/{}/{}".format(settings.MEDIA_URL, user_profile.id, file_name)
        local_path = os.path.abspath(file_path)
        image = Image.objects.create(user_profile=user_profile, url=url, name=name, local_path=local_path)
        self._data = {
            'url': url,
            'name': name,
        }

        # try:
        #     update_face_rec_model(local_path, user_profile.id)
        # except Exception as e:
        #     print e

        return image

    def validate(self, data):

        image_base64 = data.get('image_base64', None)
        access_token = data.get('access_token', None)
        name = data.get('name', None)
        user = get_user_profile_from_token(access_token)
        if not user:
            raise NotAuthenticated()
        if not is_valid_base64(image_base64):
            raise InvalidBase64()

        return {
            'user': user,
            'image_base64': image_base64,
            'name': name
        }

    class Meta:
        model = Image
        fields = ('name', 'url', 'access_token', 'image_base64')


class PublishPostSerializer(serializers.Serializer):
    provider = serializers.CharField(required=True)
    message = serializers.CharField(required=True)
    access_token = serializers.CharField(required=True)

    def create(self, validated_data):
        provider = validated_data.get('provider')
        message = validated_data.get('message')
        user = validated_data.get('user')
        social_account = SocialAccount.objects.get(user_profile=user, provider=provider)

        if provider == 'facebook':
            url = "https://graph.facebook.com/v2.5/me/feed?access_token={}".format(social_account.social_token)
            payload = {'message': message}
            response = r.post(url=url, data=payload)
            response_content = response.json()
            msg_url = None
            if 'id' in response_content:
                msg_url = "https://www.facebook.com/%s" % response_content.get("id")
        elif provider == 'twitter':
            url_safe_msg = urllib.quote(message)
            url = "https://api.twitter.com/1.1/statuses/update.json?status=%s" % url_safe_msg
            auth = OAuth1(settings.TWITTER_CONSUMER_KEY, settings.TWITTER_CONSUMER_SECRET, social_account.social_token,
                          social_account.social_secret)
            response = requests.post(url=url, auth=auth)
            response_content = response.json()
            msg_url = None
            if 'id' in response_content:
                msg_url = "https://www.twitter.com/%s/status/%s" % (
                    response_content.get('user').get('screen_name'), response_content.get('id'))

        self._data = {
            'provider_response': response_content,
            'message': message,
            'url': msg_url
        }

        return user

    def validate(self, data):
        provider = data.get('provider', None)
        message = data.get('message', None)
        access_token = data.get('access_token', None)
        user_profile = get_user_profile_from_token(access_token)
        if not provider:
            raise ValidationError(detail={'provider': 'This field is required.'})
        if not message:
            raise ValidationError(detail={'message': 'This field is required.'})
        if provider not in ('facebook', 'twitter'):
            raise ValidationError(detail={'provider': 'Invalid platform, choices are facebook or twitter.'})

        try:
            SocialAccount.objects.get(user_profile=user_profile, provider=provider)
        except SocialAccount.DoesNotExist:
            raise ValidationError(detail={'error': 'User profile does not have a %s account' % provider})

        return {
            'provider': provider,
            'message': message,
            'user': user_profile
        }
