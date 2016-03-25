from __future__ import absolute_import

import uuid
from time import sleep

from celery.utils.log import get_task_logger
from celery import task, shared_task
from api.models import UserProfile
logger = get_task_logger(__name__)
from celery.result import AsyncResult


@task(name="scan_user_content")
def scan_user_content(user_profile_id):
    print user_profile_id
    try:
        user_profile_uuid = uuid.UUID(user_profile_id).hex
        print user_profile_uuid
        user_profile = UserProfile.objects.get(pk=user_profile_uuid)
    except UserProfile.DoesNotExist:
        print "Invalid UserProfile id"
        return None
    print user_profile
    if isinstance(user_profile, UserProfile):
        print "Scanning user content..."
        user_profile.scan_all_content()


def get_result(my_work):
    work = AsyncResult(my_work.id)
    if work.ready():                     # check task state: true/false
        try:
            result = work.get(timeout=1)
            return result
        except:
            pass

    return "Please waiting result."