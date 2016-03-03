from django.conf.urls import include, url, patterns
from rest_framework.urlpatterns import format_suffix_patterns
from api import views

urlpatterns = [
    url(r'^users/$', views.UserProfileList.as_view()),
    url(r'^users/(?P<pk>[^/]+)/$', views.UserProfileDetail.as_view()),

    # Session
    url(r'^signup/$', views.Signup.as_view(), name="signup"),
    url(r'^login/$', views.Login.as_view(), name="login"),
    url(r'^sent_analyser/$', views.SentAnalyser.as_view(), name="sent_analyser"),
    url(r'^social_login/$', views.SocialLogin.as_view(), name="social_login"),
    url(r'^extract_social/$', views.ExtractSocial.as_view(), name="social_login"),

    #url(r"^logout/$", views.Logout.as_view(), name="logout"),

]

urlpatterns = format_suffix_patterns(urlpatterns)
