import asyncio

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
from datetime import datetime
import logging
from handlers.registration_handler import start_survey
from services.database.models import User

logger = logging.getLogger(__name__)


async def log_current_state(state):
    current_state = await state.get_state()
    logger.info(f"Current state after job execution: {current_state}")


from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR


def job_listener(event, state):
    if event.exception:
        logger.error(f"Job {event.job_id} failed")
    else:
        logger.info(f"Job {event.job_id} executed successfully")
        # Логирование текущего состояния после завершения задания
        loop = asyncio.get_event_loop()
        loop.create_task(log_current_state(state))


class ReminderManager:
    def __init__(self, database, bot: Bot, state: FSMContext):
        self.database = database
        self.bot = bot
        self.scheduler = AsyncIOScheduler(
            timezone=pytz.timezone("Asia/Almaty")
        )
        self.scheduler.add_listener(
            lambda event: job_listener(event, state),
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR,
        )
        self.scheduler.start()
        self.state = state

    async def schedule_reminder(self, user_id, reminder_time):
        job_id = f"reminder_{user_id}"
        # Удаление существующего задания, если оно есть
        existing_job = self.scheduler.get_job(job_id)
        if existing_job:
            self.scheduler.remove_job(job_id)
            logger.info(
                f"Scheduled reminder for user {user_id} at {reminder_time} is deleted"
            )

        self.scheduler.add_job(
            self.send_reminder,
            "cron",
            hour=reminder_time.hour,
            minute=reminder_time.minute,
            id=job_id,
            args=[user_id],
        )
        logger.info(
            f"Scheduled reminder for user {user_id} at {reminder_time}"
        )

    async def send_reminder(self, user_id):
        try:
            user = await self.database.get_entity_parameter(
                model_class=User, filters={"userid": user_id}
            )
            if user:
                now = datetime.now(pytz.timezone("Asia/Almaty"))
                reminder_time = await self.database.get_entity_parameter(
                    model_class=User,
                    filters={"userid": user_id},
                    parameter="reminder_time",
                )
                if (
                    reminder_time
                    and now.time() >= reminder_time
                    and (
                        now.time().hour == reminder_time.hour
                        and now.time().minute == reminder_time.minute
                    )
                ):
                    await self.bot.send_message(
                        user_id,
                        "Пора пройти ежедневный опрос.\n Одну секундочку...",
                    )
                    # Запускаем процесс опроса
                    await start_survey(
                        state=self.state,
                        database=self.database,
                        bot=self.bot,
                        user_id=user_id,
                    )
                    # Обновляем состояние после отправки сообщения
                    # from states.states import Form
                    #
                    # await self.state.set_state(Form.waiting_for_voice)
                    # logger.info("State updated to Form.waiting_for_voice")
                    # current_state = await self.state.get_state()
                    # logger.info(
                    #     f"Current state in Send reminder: {current_state}"
                    # )
        except Exception as e:
            logger.error(f"Error sending reminder: {e}")

    async def cancel_reminder(self, user_id):
        job_id = f"reminder_{user_id}"
        self.scheduler.remove_job(job_id)
        logger.info(f"Cancelled reminder for user {user_id}")
