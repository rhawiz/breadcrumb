import os
import urlparse
import requests
from django.contrib.sessions.backends.db import SessionStore
import tweepy
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import MultipleObjectsReturned
from oauth2_provider.models import Application, AccessToken
from rest_framework import serializers
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from api.exceptions import *
from rest_framework.exceptions import *
from api.models import *
from rest_framework.utils import model_meta

from api.utils import generate_access_token, get_user_profile_from_token, is_valid_base64, supermakedirs
from rest_framework.fields import empty
import time
import requests as r
from requests_oauthlib import OAuth2, OAuth1


class TestSerizalizer(serializers.ModelSerializer):
    class Meta:
        model = TestModel
        fields = ('field1', 'field2')


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


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(read_only=True, source='user.username')
    email = serializers.CharField(read_only=True, source='user.email')
    first_name = serializers.CharField(read_only=True, source='user.first_name')
    last_name = serializers.CharField(read_only=True, source='user.last_name')

    class Meta:
        model = UserProfile
        fields = ('id', 'gender', 'username', 'email', 'first_name', 'last_name', 'aliases')


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(required=True, write_only=True)
    email = serializers.CharField(required=True, write_only=True)
    password = serializers.CharField(required=True, write_only=True)
    first_name = serializers.CharField(required=False, write_only=True)
    last_name = serializers.CharField(required=False, write_only=True)
    fullname = serializers.CharField(required=False, write_only=True)
    gender = serializers.IntegerField(required=False, write_only=True)
    aliases = serializers.JSONField(required=False)

    class Meta:
        model = UserProfile
        fields = ('id', 'gender', 'username', 'email', 'password', 'first_name', 'last_name', 'aliases')

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
        return user_profile


class FacebookLoginSerializer(serializers.Serializer):
    code = serializers.CharField(required=True)

    class Meta:
        fields = ('code')

    def create(self, validated_data):
        access_token = validated_data.get('access_token', None)

        user_info_url = "https://graph.facebook.com/v2.5/me?access_token={}&fields=id,name,email,gender".format(
            access_token)

        user_info_response = r.get(user_info_url).json()
        fb_id = user_info_response.get('id')
        fullname = user_info_response.get('name')
        email = user_info_response.get('email')
        gender = user_info_response.get('gender')

        gender_id = 0
        if gender == 'male':
            gender_id = 1
        elif gender == 'female':
            gender_id = 2

        social_account = None
        try:
            social_account = SocialAccount.objects.get(provider='facebook', social_id=fb_id)
            social_account.social_token = access_token
            social_account.save()
        except SocialAccount.DoesNotExist:
            user_profile_data = {
                'username': email,
                'email': email,
                'password': uuid.uuid4(),
                'fullname': fullname,
                'gender': gender_id
            }
            user_profile_serializer = SignupSerializer(data=user_profile_data)
            user_profile_serializer.is_valid(raise_exception=True)
            user_profile = user_profile_serializer.save()
            social_account = SocialAccount.objects.create(user_profile=user_profile, social_id=fb_id,
                                                          social_token=access_token,
                                                          provider='facebook')

        user_profile = social_account.user_profile
        access_token = generate_access_token(user_profile.user)

        access_token_data = AccessTokenSerializer(access_token).data
        self._data = access_token_data
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

        return {'access_token': fb_access_token}


class LinkFacebookAccountSerializer(serializers.Serializer):
    code = serializers.CharField(required=True)
    access_token = serializers.CharField(required=True)

    class Meta:
        fields = ('code', 'access_token')

    def create(self, validated_data):
        fb_access_token = validated_data.get('fb_access_token', None)
        access_token = validated_data.get('access_token', None)

        user_info_url = "https://graph.facebook.com/v2.5/me?access_token={}&fields=id,name,email,gender".format(
            fb_access_token)

        user_info_response = r.get(user_info_url).json()
        fb_id = user_info_response.get('id')

        user_profile = get_user_profile_from_token("Bearer %s" % access_token)

        social_account = SocialAccount.objects.create(
            user_profile=user_profile,
            social_id=fb_id,
            social_token=fb_access_token,
            provider='facebook'
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

        return {'fb_access_token': fb_access_token,
                'access_token': access_token}


class LinkTwitterAccountSerializer(serializers.Serializer):
    oauth_verifier = serializers.CharField(write_only=True)
    request_token = serializers.DictField(write_only=True)
    access_token = serializers.CharField(write_only=True)

    def create(self, validated_data):
        key = validated_data.get('key')
        secret = validated_data.get('secret')
        access_token = validated_data.get('access_token')
        consumer_secret = validated_data.get('consumer_secret')
        consumer_key = validated_data.get('consumer_key')
        url = "https://api.twitter.com/1.1/account/verify_credentials.json?&include_email=true"
        auth = OAuth1(consumer_key, consumer_secret, key, secret)
        r = requests.get(url=url, auth=auth)
        twitter_data = r.json()
        twitter_id = twitter_data.get('id')

        user_profile = get_user_profile_from_token("Bearer %s" % access_token)
        social_account = SocialAccount.objects.create(
            user_profile=user_profile,
            social_id=twitter_id,
            social_token=key,
            social_secret=secret,
            provider='twitter'
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

        if len(SocialAccount.objects.filter(provider='twitter', social_token=key)) >= 1:
            raise ValidationError(detail={"social_token": "Social token in use."})

        if len(SocialAccount.objects.filter(provider='twitter', social_secret=secret)) >= 1:
            raise ValidationError(detail={"social_secret": "Secret key in use."})

        try:
            AccessToken.objects.get(token=access_token)
        except AccessToken.DoesNotExist:
            raise NotAuthenticated()

        return {
            'key': key,
            'secret': secret,
            'consumer_key': consumer_key,
            'consumer_secret': consumer_secret,
            'access_token': access_token
        }

    class Meta:
        fields = ('oauth_verifier', 'request_token', 'access_token')


class TwitterLoginSerializer(serializers.Serializer):
    oauth_verifier = serializers.CharField(write_only=True)
    request_token = serializers.DictField(write_only=True)

    def create(self, validated_data):
        key = validated_data.get('key')
        secret = validated_data.get('secret')
        consumer_secret = validated_data.get('consumer_secret')
        consumer_key = validated_data.get('consumer_key')

        url = "https://api.twitter.com/1.1/account/verify_credentials.json?&include_email=true"
        auth = OAuth1(consumer_key, consumer_secret, key, secret)
        r = requests.get(url=url, auth=auth)
        twitter_data = r.json()
        twitter_id = twitter_data.get('id')
        fullname = twitter_data.get('name')
        email = twitter_data.get('email')
        username = twitter_data.get('screen_name') or email
        social_account = None

        try:
            social_account = SocialAccount.objects.get(provider='twitter', social_id=twitter_id)
        except SocialAccount.DoesNotExist:
            user_profile_data = {
                'username': username,
                'email': email,
                'password': uuid.uuid4(),
                'fullname': fullname,
            }
            user_profile_serializer = SignupSerializer(data=user_profile_data)
            user_profile_serializer.is_valid(raise_exception=True)
            user_profile = user_profile_serializer.save()
            social_account = SocialAccount.objects.create(
                user_profile=user_profile,
                social_id=twitter_id,
                social_token=key,
                social_secret=secret,
                provider='twitter'
            )

        user_profile = social_account.user_profile
        access_token = generate_access_token(user_profile.user)

        access_token_data = AccessTokenSerializer(access_token).data
        self._data = access_token_data

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

        return {
            'key': key,
            'secret': secret,
            'consumer_key': consumer_key,
            'consumer_secret': consumer_secret
        }

    class Meta:
        fields = ('oauth_verifier', 'request_token')


class AccessTokenSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    expires = serializers.SerializerMethodField('_get_expires_timestamp')

    class Meta:
        model = AccessToken
        fields = ('user', 'token', 'expires', 'scope')

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
        access_token_data = AccessTokenSerializer(access_token).data
        self._data = {
            "access_token": access_token_data,
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
        fh = open("{}/{}".format(file_path, file_name), "wb")
        fh.write(image_base64.decode('base64'))
        fh.close()
        url = "{}users/{}/{}".format(settings.MEDIA_URL, user_profile.id, file_name)
        image = Image.objects.create(user_profile=user_profile, url=url, name=name)
        self._data = {
            "url": url
        }

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
