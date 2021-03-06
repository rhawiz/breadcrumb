from random import randint, randrange, uniform
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpResponseRedirect, JsonResponse
from oauth2_provider.ext.rest_framework import OAuth2Authentication, TokenHasReadWriteScope
from django.contrib.sessions.models import Session
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from api.serializers import *
from api.utils import get_user_profile_from_token
from api.tasks import scan_user_content


class UserProfileDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a UserProfile
    HTTP GET, PUT and DELETE
    """
    queryset = UserProfile.objects.all()


    serializer_class = UserProfileSerializer

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


class CurrentUserDetail(APIView):
    """
    Get or update current user details
    HTTP GET and PUT
    """
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


class ProfileDetail(APIView):
    """
    Get content for the profiles page
    HTTP GET
    """
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        token = request.META.get('HTTP_AUTHORIZATION', None)

        user_profile = get_user_profile_from_token(token)

        # Get all user contents
        content_list = UserContent.objects.filter(user=user_profile)

        pos = 0.0
        neg = 0.0

        # Sum up total positive and negative scores
        for content in content_list:
            if content.pos_sentiment_rating is not None:
                pos = pos + float(content.pos_sentiment_rating)
            if content.neg_sentiment_rating is not None:
                neg = neg + float(content.neg_sentiment_rating)

        # Total scores and normalise
        total = pos + neg
        ppos = 0.0
        pneg = 0.0

        if total:
            ppos = (pos / total)
            pneg = (neg / total)

        pos_norm = ppos
        neg_norm = pneg

        data = {
            "positive": float("%.3f" % pos_norm),
            "negative": float("%.3f" % neg_norm)
        }

        return Response(data=data, status=status.HTTP_200_OK)


class AccountList(generics.ListAPIView):
    """
    List all accounts associated with the user
    HTTP GET
    """

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


class ReportList(generics.ListAPIView):
    """
    List all reports
    HTTP GET
    """
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        data = {
            "count": len(serializer.data),
            "reports": serializer.data
        }
        return Response(data)

    def get_queryset(self):
        token = self.request.META.get('HTTP_AUTHORIZATION', None)
        user_profile = get_user_profile_from_token(token)
        return Report.objects.filter(user_profile=user_profile)


class ReportDetail(generics.RetrieveDestroyAPIView):
    """
    Get details of a report or delete a report
    HTTP GET and DELETE
    """
    queryset = Report.objects.all()
    serializer_class = ReportDetailSerializer
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


class UserProfileList(generics.ListAPIView):
    """
    List all users
    HTTP GET
    """
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class Scan(APIView):
    """
    Start a scan and gather user content
    HTTP POST
    """
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def post(self, request, *args, **kwargs):
        token = request.META.get('HTTP_AUTHORIZATION', None)
        user_profile = get_user_profile_from_token(token)

        source = kwargs.get("source") or None

        print source

        try:
            scan_user_content.delay(str(user_profile.pk), source)
        except Exception, e:
            print e
            scan_user_content(str(user_profile.pk), source)

        return Response(status=status.HTTP_200_OK)


class Signup(generics.CreateAPIView):
    """
    Username/email signup
    HTTP POST
    """
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
    """
    Username/email Login. Generate access token for a session.
    HTTP POST
    """
    queryset = AccessToken.objects.all()

    def post(self, request, *args, **kwargs):
        login_serializer = LoginSerializer(data=request.data)
        login_serializer.is_valid(raise_exception=True)
        login_serializer.save()
        return Response(data=login_serializer.data)


class Logout(APIView):
    """
    Revoke an access token
    HTTP POST
    """
    queryset = AccessToken.objects.all()
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def post(self, request, *args, **kwargs):
        access_token = request.META.get('HTTP_AUTHORIZATION', None).split(' ')[1]
        access_token_obj = AccessToken.objects.get(token=access_token)
        access_token_obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UploadImage(APIView):
    """
    Upload an image
    HTTP POST
    """
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
    """
    Redirect to facebook's authentication system
    HTTP GET
    """

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
    """
    Link a Facebook account with the current user
    HTTP GET
    """
    authentication_classes = (OAuth2Authentication,)

    # permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        base_url = "https://www.facebook.com/dialog/oauth?scope=email,public_profile,user_friends,user_likes,user_photos,user_posts&client_id={client_id}&redirect_uri={callback_url}"
        redirect_url = base_url.format(client_id=settings.FACEBOOK_CLIENT_ID,
                                       callback_url=settings.FACEBOOK_CALLBACK_URL)
        s = SessionStore()
        s['is_login'] = False
        access_token = kwargs.get("access_token") or None
        if not access_token:
            access_token = request.META.get('HTTP_AUTHORIZATION', None)
        s['access_token'] = access_token
        s.save(must_create=True)
        try:
            return HttpResponseRedirect(redirect_url)
        except Exception:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FacebookCallback(APIView):
    """
    Facebook api will call this endpoint after authenticating a user.
    Handles creation/retrieval of the user profile and generate an access token
    HTTP GET
    """

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
    """
    Link a twitter account with the current user
    HTTP GET
    """
    authentication_classes = (OAuth2Authentication,)

    # permission_classes = [IsAuthenticated, TokenHasReadWriteScope]


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
            access_token = kwargs.get("access_token") or None
            if not access_token:
                access_token = request.META.get('HTTP_AUTHORIZATION', None)
            s['access_token'] = access_token
            s.save(must_create=True)
            return HttpResponseRedirect(redirect_url)
        except tweepy.TweepError:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TwitterLogin(APIView):
    """
    Redirect to Twitter's authentication screen
    HTTP GET
    """

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
        except tweepy.TweepError as e:
            print e
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TwitterCallback(APIView):
    """
    Twitter api will call this endpoint after authenticating a user.
    Handles creation/retrieval of the user profile and generate an access token
    HTTP GET
    """

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
    """
    Get details of a user's account
    HTTP GET
    """
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        account_type = kwargs.get("account_type")
        token = request.META.get('HTTP_AUTHORIZATION', None)
        if account_type not in ('facebook', 'twitter', 'web'):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        user_profile = get_user_profile_from_token(token)

        content_list = UserContent.objects.filter(user=user_profile, source=account_type)

        pos = 0.0
        neg = 0.0
        neut = 0.0

        for content in content_list:
            if content.pos_sentiment_rating:
                pos += float(content.pos_sentiment_rating)
            if content.neg_sentiment_rating:
                neg += float(content.neg_sentiment_rating)
            if content.neut_sentiment_rating:
                neut += float(content.neut_sentiment_rating)

        total = pos + neg + neut

        ppos = 0.0
        pneg = 0.0
        pneut = 0.0

        if total:
            ppos = (pos / total)
            pneg = (neg / total)
            pneut = (neut / total)

        pos_norm = ppos * 100
        neg_norm = pneg * 100
        neut_norm = pneut * 100

        if pos_norm >= 90:
            rating = "A*"
        elif pos_norm >= 80:
            rating = "B"
        elif pos_norm >= 70:
            rating = "C"
        elif pos_norm >= 60:
            rating = "D"
        elif pos_norm >= 50:
            rating = "E"
        else:
            rating = "F"

        data = {
            'positive': pos_norm,
            'negative': neg_norm,
            'neutral': neut_norm,
            'rating': rating,
        }

        serializer = AccountDetailSerializer(data)

        return Response(serializer.data)


class ContentList(generics.ListAPIView):
    """
    Get the list user content
    HTTP GET
    """
    queryset = UserContent.objects.all()
    serializer_class = ContentSerializer
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def get(self, request, *args, **kwargs):
        content_type = kwargs.get("content_type") or None

        if content_type not in ('facebook', 'twitter', 'web'):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        sentiment = request.GET.get("sentiment") or None
        page = request.GET.get("page") or 0
        count = request.GET.get("count") or 10
        sort = request.GET.get("sort") or None

        if sort == "neutral":
            sort_field = '-neut_sentiment_rating'
        elif sort == "pos":
            sort_field = '-pos_sentiment_rating'
        else:
            sort_field = '-neg_sentiment_rating'

        page = int(page)

        if not isinstance(page, int):
            page = 0

        try:
            count = int(count)
        except ValueError:
            count = 10

        start = page * int(count)

        end = start + int(count)

        if sentiment not in ("pos", "neg", "neutral"):
            sentiment = None

        token = request.META.get('HTTP_AUTHORIZATION', None)
        user_profile = get_user_profile_from_token(token)

        if sentiment:
            queryset = UserContent.objects.filter(user=user_profile, source=content_type, hidden=False,
                                                  sentiment_label=sentiment).order_by(sort_field)[start:end]
        else:
            queryset = UserContent.objects.filter(user=user_profile, source=content_type, hidden=False).order_by(
                sort_field)[start:end]

        serializer = self.get_serializer(queryset, many=True)

        return Response(data=serializer.data)


class TakedownPost(APIView):
    """
    Attempt to take down a post that breadcrumb has found
    HTTP DELETE
    """
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def delete(self, request, *args, **kwargs):
        pk = kwargs.get("pk")

        try:
            user_content = UserContent.objects.get(pk=pk)
        except UserContent.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)

        user_content.take_down()

        return Response(status=status.HTTP_200_OK)


class Insights(APIView):
    """
    Generate custom user insights using trending topics
    HTTP GET
    """
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

        trend_list = api.trends_place(23424975)[0].get("trends")[0:5] or []

        insight_list = []
        for trend in trend_list:
            tweets = []
            tag = trend["name"]
            tweet_volume = trend["tweet_volume"]
            recommendation = "Create a new post relating to %s" % tag
            insight = {
                "tag": tag,
                "tweets": tweets,
                "recommendation": recommendation,
                "tweet_volume": tweet_volume,
                "score": randint(1, 20),
            }

            results = api.search(q=tag, count=3)
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
                    "tweet_id": str(tweet_id),
                    "favourites_count": favourites_count,
                    "retweets_count": retweets_count,
                    "user_photo_url": user_photo_url,
                    "user_followers": user_followers
                }

                tweets.append(tweet_data)
            insight_list.append(insight)

        return Response(data=insight_list, status=status.HTTP_200_OK)


class ContentDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Get details about a content
    HTTP GET
    """
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


class PublishPost(APIView):
    """
    Post a twitter or facebook post
    HTTP POST
    """
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def post(self, request, *args, **kwargs):
        data = request.data
        data["access_token"] = request.META.get('HTTP_AUTHORIZATION', None)
        serializer = PublishPostSerializer(data=data)

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(data=serializer.data)

class Retweet(APIView):
    """
    Retweet a twitter status
    HTTP POST
    """
    authentication_classes = (OAuth2Authentication,)
    permission_classes = [IsAuthenticated, TokenHasReadWriteScope]

    def post(self, request, *args, **kwargs):
        data = request.data
        data["access_token"] = request.META.get('HTTP_AUTHORIZATION', None)
        data['tweet_id'] = kwargs.get("tweet_id")
        serializer = RetweetSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(data=serializer.data)
