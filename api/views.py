import pickle
from importlib import import_module

import sys
from random import randint, randrange, uniform

import tweepy
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpResponseRedirect, JsonResponse
from oauth2_provider.ext.rest_framework import OAuth2Authentication, TokenHasReadWriteScope
from django.contrib.sessions.models import Session
from rest_framework import generics
from rest_framework.decorators import permission_classes, authentication_classes, api_view
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


class CurrentUserDetail(APIView):
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        token = request.META.get('HTTP_AUTHORIZATION', None)
        instance = get_user_profile_from_token(token)
        serializer = UserProfileSerializer(instance)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        token = request.META.get('HTTP_AUTHORIZATION', None)
        instance = get_user_profile_from_token(token)

        serializer = UpdateUserProfileSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AccountList(generics.ListAPIView):
    queryset = SocialAccount.objects.all()
    serializer_class = AccountSerializer
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        token = request.META.get('HTTP_AUTHORIZATION', None)
        user_profile = get_user_profile_from_token(token)
        social_account_list = SocialAccount.objects.filter(user_profile=user_profile)

        queryset = [
            {
                'account': "web",
                'name': "%s %s" % (user_profile.user.first_name, user_profile.user.last_name)
            }
        ]

        for social_account in social_account_list:
            data = {
                'account': social_account.provider,
                'name': social_account.social_username or "%s %s" % (
                    user_profile.user.first_name, user_profile.user.last_name)
            }
            queryset.append(data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


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
        try:
            scan_user_content.delay(str(user_profile.pk))
        except Exception, e:
            print e
            scan_user_content(str(user_profile.pk))

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
        return Response(data=serializer.data, status=status.HTTP_201_CREATED)


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
        scope = "email,public_profile,user_friends,user_likes,user_photos,user_posts,publish_actions,publish_pages,manage_pages"
        base_url = "https://www.facebook.com/dialog/oauth?scope={scope}&client_id={client_id}&redirect_uri={callback_url}"
        redirect_url = base_url.format(client_id=settings.FACEBOOK_CLIENT_ID,
                                       callback_url=settings.FACEBOOK_CALLBACK_URL,
                                       scope=scope)
        s = SessionStore()
        s['is_login'] = True
        s.save(must_create=True)
        try:
            return HttpResponseRedirect(redirect_url)
        except Exception:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LinkFacebookAccount(APIView):
    authentication_classes = (OAuth2Authentication,)

    # permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        base_url = "https://www.facebook.com/dialog/oauth?scope=email,public_profile,user_friends,user_likes,user_photos,user_posts&client_id={client_id}&redirect_uri={callback_url}"
        redirect_url = base_url.format(client_id=settings.FACEBOOK_CLIENT_ID,
                                       callback_url=settings.FACEBOOK_CALLBACK_URL)
        s = SessionStore()
        s['is_login'] = False
        s['access_token'] = kwargs.get("access_token")
        s.save(must_create=True)
        try:
            return HttpResponseRedirect(redirect_url)
        except Exception:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FacebookCallback(APIView):
    def get(self, request, *args, **kwargs):
        code = request.GET.get('code', None)
        data = {'code': code}
        session_key = Session.objects.latest('expire_date').session_key
        s = SessionStore(session_key=session_key)
        is_login = s.get('is_login')
        access_token = s.get('access_token')
        s.delete('is_login')
        s.delete('access_token')
        s.delete()
        if is_login:
            serializer = FacebookLoginSerializer(data=data)
        else:
            data["access_token"] = access_token
            serializer = LinkFacebookAccountSerializer(data=data)

        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(data=serializer.data)


class LinkTwitterAccount(APIView):
    authentication_classes = (OAuth2Authentication,)

    # permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def post(self, request, *args, **kwargs):
        auth = tweepy.OAuthHandler(
            settings.TWITTER_CONSUMER_KEY,
            settings.TWITTER_CONSUMER_SECRET,
            settings.TWITTER_CALLBACK_URL
        )
        try:
            redirect_url = auth.get_authorization_url()
            s = SessionStore()
            s['request_token'] = auth.request_token
            s['is_login'] = False
            s['access_token'] = request.META.get('HTTP_AUTHORIZATION', None)
            s.save(must_create=True)
            return HttpResponseRedirect(redirect_url)
        except tweepy.TweepError:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            s['is_login'] = False
            s['access_token'] = kwargs.get("access_token")
            s.save(must_create=True)
            return HttpResponseRedirect(redirect_url)
        except tweepy.TweepError:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            s['is_login'] = True
            s['access_token'] = None
            s.save(must_create=True)
            return HttpResponseRedirect(redirect_url)
        except tweepy.TweepError:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TwitterCallback(APIView):
    def get(self, request, *args, **kwargs):
        if 'denied' in request.GET:
            return Response()
        session_key = Session.objects.latest('expire_date').session_key
        s = SessionStore(session_key=session_key)
        is_login = s.get('is_login')
        access_token = s.get('access_token')

        data = {
            'oauth_verifier': request.GET['oauth_verifier'],
            'request_token': s.get("request_token"),
        }
        s.delete('request_token')
        s.delete('is_login')
        s.delete('access_token')
        s.save()
        if is_login:
            serializer = TwitterLoginSerializer(data=data)
        else:
            data["access_token"] = access_token
            serializer = LinkTwitterAccountSerializer(data=data)

        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_data = serializer.data
        return Response(data=response_data)


class AccountDetail(APIView):
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        account_type = kwargs.get("account_type")
        token = request.META.get('HTTP_AUTHORIZATION', None)
        if account_type not in ('facebook', 'twitter', 'web'):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        user_profile = get_user_profile_from_token(token)

        content_list = UserContent.objects.filter(user=user_profile, type=account_type)

        positive = 0
        negative = 0
        neutral = 0

        for content in content_list:
            if content.pos_sentiment_rating:
                positive += content.pos_sentiment_rating
            if content.neg_sentiment_rating:
                negative += content.neg_sentiment_rating
            if content.neut_sentiment_rating:
                neutral += content.neut_sentiment_rating

        rating = positive + negative + neutral

        data = {
            'positive': positive,
            'negative': negative,
            'neutral': neutral,
            'rating': rating,
        }

        serializer = AccountDetailSerializer(data)

        return Response(serializer.data)


class ContentList(generics.ListAPIView):
    queryset = UserContent.objects.all()
    serializers_class = ContentSerializer
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        content_type = kwargs.get("content_type") or None
        if content_type not in ('facebook', 'twitter', 'web'):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        token = request.META.get('HTTP_AUTHORIZATION', None)
        user_profile = get_user_profile_from_token(token)

        queryset = UserContent.objects.filter(user=user_profile, source=content_type, hidden=False)

        serializer = self.get_serializer(queryset, many=True)

        return Response(data=serializer.data)


class TakedownPost(APIView):
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        pk = kwargs.get("pk")

        try:
            user_content = UserContent.objects.get(pk=pk)
        except UserContent.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)

        user_content.take_down()

        return Response(status=status.HTTP_200_OK)


class Insights(APIView):
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        token = request.META.get('HTTP_AUTHORIZATION', None)
        user_profile = get_user_profile_from_token(token)

        try:
            twitter_account = SocialAccount.objects.get(user_profile=user_profile, provider='twitter')
        except SocialAccount.DoesNotExist:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        auth = tweepy.OAuthHandler(settings.TWITTER_CONSUMER_KEY, settings.TWITTER_CONSUMER_SECRET)
        auth.set_access_token(twitter_account.social_token, twitter_account.social_secret)

        api = tweepy.API(auth)

        trend_list = api.trends_place(1)[0].get("trends")[0:10] or []

        insight_list = []
        print len(trend_list)
        for trend in trend_list:
            sleep(uniform(0.5, 0.9))
            tweets = []
            tag = trend["name"]
            tweet_volume = trend["tweet_volume"]
            recommendation = "Create a new Twitter post relating to %s" % tag
            insight = {
                "tag": tag,
                "tweets": tweets,
                "recommendation":recommendation,
                "tweet_volume": tweet_volume,
                "score":randint(1,20),
            }

            results = api.search(q=tag, count=10)
            for result in results:

                screen_name = result.user.screen_name
                text = result.text
                tweet_id = result.id
                favourites_count = result.favorite_count
                retweets_count = result.retweet_count
                user_photo_url = result.user.profile_image_url
                user_followers = result.user.followers_count
                tweet_data = {
                    "screen_name": screen_name,
                    "text": text,
                    "tweet_id": tweet_id,
                    "favourites_count": favourites_count,
                    "retweets_count": retweets_count,
                    "user_photo_url": user_photo_url,
                    "user_followers": user_followers
                }

                tweets.append(tweet_data)
            insight_list.append(insight)

        return Response(data=insight_list, status=status.HTTP_200_OK)


class ContentDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = UserContent.objects.all()
    serializer_class = ContentSerializer
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
