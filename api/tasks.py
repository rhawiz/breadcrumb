from __future__ import absolute_import
from celery.utils.log import get_task_logger
from celery import task, shared_task
from api.models import UserProfile
logger = get_task_logger(__name__)
from celery.result import AsyncResult


@shared_task(name="scan_user_content")
def scan_user_content(user_profile):
    print user_profile
    logger.info("Scanning User Contents")
    if isinstance(user_profile, UserProfile):
        logger.info("Scanning User Contents")
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