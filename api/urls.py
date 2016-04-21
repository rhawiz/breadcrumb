from django.conf.urls import include, url, patterns
from rest_framework.urlpatterns import format_suffix_patterns
from api import views

urlpatterns = [
    url(r'^users/$', views.UserProfileList.as_view()),
    url(r'^users/(?P<pk>[^/]+)/$', views.UserProfileDetail.as_view()),

    # Session
    url(r'^signup/$', views.Signup.as_view(), name="signup"),
    url(r'^login/$', views.Login.as_view(), name="login"),
    url(r'^facebook_callback/', views.FacebookCallback.as_view(), name="facebook_callback"),
    url(r'^twitter_callback/', views.TwitterCallback.as_view(), name="twitter_callback"),
    url(r'^twitter_login/', views.TwitterLogin.as_view(), name="twitter_login"),
    url(r'^facebook_login/', views.FacebookLogin.as_view(), name="facebook_login"),
    url(r'^link_twitter/(?P<access_token>[^/]+)/$', views.LinkTwitterAccount.as_view(), name="link_twitter_get"),
    url(r'^link_twitter/$', views.LinkTwitterAccount.as_view(), name="link_twitter_post"),
    url(r'^link_facebook/(?P<access_token>[^/]+)/$', views.LinkFacebookAccount.as_view(), name="link_facebook"),
    url(r'^scan/', views.Scan.as_view(), name="scan"),
    url(r'^upload_image/$', views.UploadImage.as_view(), name="upload_image"),

    url(r'^accounts/(?P<account_type>[^/]+)/', views.AccountDetail.as_view(), name="account_detail"),

    url(r'^accounts/', views.AccountList.as_view(), name="account_list"),

    url(r'^content/facebook/', views.ContentList.as_view(), name="facebook_content_list", kwargs={'content_type':"facebook"}),
    url(r'^content/twitter/', views.ContentList.as_view(), name="twitter_content_list", kwargs={'content_type':"twitter"}),
    url(r'^content/web/', views.ContentList.as_view(), name="web_content_list", kwargs={'content_type':"web"}),

    url(r'^content/(?P<pk>[^/]+)/$', views.ContentDetail.as_view(), name="content_detail"),

    url(r'^takedown/(?P<pk>[^/]+)/$', views.TakedownPost.as_view(), name="takedown_post"),

    url(r'^insights/$', views.Insights.as_view(), name="insights"),

    url(r'^me/', views.CurrentUserDetail.as_view(), name="current_user_detail"),





    # url(r"^logout/$", views.Logout.as_view(), name="logout"),

]

urlpatterns = format_suffix_patterns(urlpatterns)
