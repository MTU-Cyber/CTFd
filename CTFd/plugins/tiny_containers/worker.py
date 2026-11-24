"""Single process that stops managed projects after the CTF deadline."""

import logging
import time

from CTFd import create_app
from CTFd.cache import clear_challenges
from CTFd.models import Challenges, db
from CTFd.plugins.tiny_containers import TinyContainer, _deadline, manager


def run():
    app = create_app()
    while True:
        with app.app_context():
            try:
                deadline = _deadline()
                if deadline is not None and time.time() >= deadline:
                    for record in TinyContainer.query.all():
                        try:
                            if manager.containers(record.challenge_id):
                                manager.down(record.challenge_id)
                                challenge = Challenges.query.get(record.challenge_id)
                                if challenge and challenge.connection_info == manager.endpoint(record):
                                    challenge.connection_info = None
                                    db.session.commit()
                                    clear_challenges()
                        except (RuntimeError, OSError):
                            logging.exception("Could not stop challenge %s", record.challenge_id)
            except Exception:
                logging.exception("tiny-containers deadline check failed")
            finally:
                db.session.remove()
        time.sleep(30)


if __name__ == "__main__":
    run()
