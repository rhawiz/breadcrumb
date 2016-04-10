import pickle
from importlib import import_module

import sys
import tweepy
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpResponseRedirect
from oauth2_provider.ext.rest_framework import OAuth2Authentication, TokenHasReadWriteScope
from django.contrib.sessions.models import Session
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from breadcrumbcore.ai.sentimentanalyser import analyse_text as sa
from api.serializers import *
from breadcrumbcore.searchengines.googlesearch import GoogleWebSearch

# Create your views here.
from api.utils import get_user_profile_from_token
from api.tasks import scan_user_content


class UserProfileDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


class UserProfileList(generics.ListAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class Scan(APIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def post(self, request, *args, **kwargs):
        token = request.META.get('HTTP_AUTHORIZATION', None)
        user_profile = get_user_profile_from_token(token)
        scan_user_content.delay(str(user_profile.pk))
        return Response(status=status.HTTP_200_OK)


class Signup(generics.CreateAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = SignupSerializer

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        headers = self.get_success_headers(serializer.data)
        response = UserProfileSerializer(instance).data
        return Response(response, status=status.HTTP_201_CREATED, headers=headers)


class Login(APIView):
    queryset = AccessToken.objects.all()

    def post(self, request, *args, **kwargs):
        login_serializer = LoginSerializer(data=request.data)
        login_serializer.is_valid(raise_exception=True)
        login_serializer.save()
        return Response(data=login_serializer.data)


class UploadImage(APIView):
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def post(self, request, *args, **kwargs):
        data = request.data
        data["access_token"] = request.META.get('HTTP_AUTHORIZATION', None)
        serializer = UploadImageSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(data=serializer.data)


class FacebookLogin(APIView):
    def get(self, request, *args, **kwargs):
        base_url = "https://www.facebook.com/dialog/oauth?scope=email,public_profile,user_friends,user_likes,user_photos,user_posts&client_id={client_id}&redirect_uri={callback_url}"
        redirect_url = base_url.format(client_id=settings.FACEBOOK_CLIENT_ID,
                                       callback_url=settings.FACEBOOK_CALLBACK_URL)
        try:
            return HttpResponseRedirect(redirect_url)
        except Exception:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FacebookCallback(APIView):
    def get(self, request, *args, **kwargs):
        code = request.GET.get('code', None)
        data = {'code': code}
        serializer = FacebookLoginSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(data=serializer.data)


class TwitterLogin(APIView):
    def get(self, request, *args, **kwargs):
        auth = tweepy.OAuthHandler(
            settings.TWITTER_CONSUMER_KEY,
            settings.TWITTER_CONSUMER_SECRET,
            settings.TWITTER_CALLBACK_URL
        )
        try:
            redirect_url = auth.get_authorization_url()
            s = SessionStore()
            s['request_token'] = auth.request_token
            s.save(must_create=True)
            settings.TWITTER_LOGIN_SESSION_KEY = s.session_key
            return HttpResponseRedirect(redirect_url)
        except tweepy.TweepError:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TwitterCallback(APIView):
    def get(self, request, *args, **kwargs):

        s = SessionStore(session_key=settings.TWITTER_LOGIN_SESSION_KEY)
        # data = {}
        # data['session_key'] = settings.TWITTER_LOGIN_SESSION_KEY
        # data['s'] = s
        # data['s.session_key'] = s.session_key
        # return Response(data=data)
        request_token = s.get('request_token')
        data = {
            'oauth_verifier': request.GET['oauth_verifier'],
            'request_token': request_token,
        }
        return Response(data={"s":s.get("request_token"),
                              "check":s.has_key("request_token")})
        s.delete('request_token')
        s.save()
        return Response(data=data)
        serializer = TwitterLoginSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(data=serializer.data)
