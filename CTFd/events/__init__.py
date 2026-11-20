from flask import Blueprint, Response, current_app, stream_with_context

from CTFd.models import db
from CTFd.utils import get_app_config
from CTFd.utils.decorators import authed_only, ratelimit
from CTFd.utils.decorators.visibility import (
    check_account_visibility,
    check_score_visibility,
)

events = Blueprint("events", __name__)


@events.route("/events")
@authed_only
@ratelimit(method="GET", limit=150, interval=60)
def subscribe():
    @stream_with_context
    def gen():
        for event in current_app.events_manager.subscribe():
            yield str(event)

    enabled = get_app_config("SERVER_SENT_EVENTS")
    if enabled is False:
        return ("", 204)

    # Close the db session to avoid OperationalError with MySQL connection errors
    db.session.close()

    return Response(gen(), mimetype="text/event-stream")


@events.route("/scoreboard/events")
@check_account_visibility
@check_score_visibility
@ratelimit(method="GET", limit=150, interval=60)
def subscribe_scoreboard():
    if get_app_config("SERVER_SENT_EVENTS") is False:
        return ("", 204)

    @stream_with_context
    def gen():
        for event in current_app.events_manager.subscribe(channel="scoreboard"):
            yield str(event)

    db.session.close()
    return Response(gen(), mimetype="text/event-stream")
