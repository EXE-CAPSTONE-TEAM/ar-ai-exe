from redis import Redis
from rq import Worker

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    worker = Worker([settings.rq_queue_name], connection=Redis.from_url(settings.redis_url))
    worker.work()


if __name__ == "__main__":
    main()
