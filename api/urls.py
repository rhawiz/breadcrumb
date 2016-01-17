from django.conf.urls import include, url, patterns
from rest_framework.urlpatterns import format_suffix_patterns
from api import views

urlpatterns = [
    url(r'^detail/(?P<pk>[0-9]+)/$', views.TestDetailView.as_view()),
    url(r'^list/$', views.TestListView.as_view()),
    url(r'^users/$', views.UserProfileList.as_view()),
]

urlpatterns = format_suffix_patterns(urlpatterns)
