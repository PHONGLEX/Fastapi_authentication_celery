import os
import time
import asyncio
import concurrent.futures

from celery import Celery
from helper.email_helper import send_mail


celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")


@celery.task(name="send_mail_task")
def send_mail_task(data):
    asyncio.get_event_loop().run_until_complete(send_mail(data))
    # executor = concurrent.futures.ThreadPoolExecutor(
    #     max_workers=3,
    # )

    # event_loop = asyncio.get_event_loop()
    # try:
    #     event_loop.run_until_complete(
    #         send_mail(data)
    #     )
    # finally:
    #     event_loop.close()