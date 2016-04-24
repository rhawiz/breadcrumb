from __future__ import absolute_import
import datetime

import uuid
from time import sleep

from celery.utils.log import get_task_logger
from celery import task, shared_task
from api.models import UserProfile, Report

logger = get_task_logger(__name__)
from celery.result import AsyncResult


@task(name="scan_user_content")
def scan_user_content(user_profile_id, source):
    try:
        user_profile_uuid = uuid.UUID(user_profile_id).hex
        user_profile = UserProfile.objects.get(pk=user_profile_uuid)
    except UserProfile.DoesNotExist:
        print "Invalid UserProfile id"
        return None
    if isinstance(user_profile, UserProfile):
        formatted_date = str(datetime.date.today().strftime('%A %d %b %Y, %I:%M%p'))
        report = Report.objects.create(name=formatted_date, user_profile=user_profile)
        if source == 'web':
            print "Scanning web content..."
            user_profile._scan_web_content(report)
        elif source == 'facebook':
            print "Scanning facebook content..."
            user_profile._scan_facebook_content(report)
        elif source == 'twitter':
            print "Scanning twitter content..."
            user_profile._scan_twitter_content(report)
        else:
            user_profile.generate_report()


def get_result(my_work):
    work = AsyncResult(my_work.id)
    if work.ready():  # check task state: true/false
        try:
            result = work.get(timeout=1)
            return result
        except:
            pass

    return "Please waiting result."
