import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from urllib.parse import urlencode

from flask import Blueprint, abort, redirect, request

from CTFd.utils.config import is_teams_mode
from CTFd.utils.decorators import authed_only
from CTFd.utils.user import get_current_team, get_current_user


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode()


def _issue_token(account_id: int, secret: str) -> str:
    payload = json.dumps(
        {
            'team_id': str(account_id),
            'exp': int(time.time()) + 900,
            'nonce': secrets.token_hex(8),
        },
        separators=(',', ':'),
    ).encode()
    payload_part = _base64url(payload)
    signature = hmac.new(secret.encode(), payload_part.encode(), hashlib.sha256).digest()
    return f'{payload_part}.{_base64url(signature)}'


def load(app):
    bp = Blueprint('tiny_instancer_auth', __name__, url_prefix='/instancer')

    @bp.get('/auth')
    @authed_only
    def authorize():
        callback = os.environ.get(
            'TINY_INSTANCER_CALLBACK_URL',
            'https://instances.cyberctfhub.ie/auth',
        )
        secret = os.environ.get('TINY_INSTANCER_AUTH_SECRET', '')
        redirect_uri = request.args.get('redirect_uri', '')
        state = request.args.get('state', '')

        if redirect_uri != callback or not re.fullmatch(r'[a-z0-9-]+', state):
            abort(400)
        if len(secret) < 32:
            abort(503, 'Tiny-instancer authentication is not configured')

        user = get_current_user()
        if user is None:
            abort(401)

        if is_teams_mode():
            team = get_current_team()
            if team is None:
                abort(403, 'Join a team before starting an instance')
            account_id = team.id
        else:
            account_id = user.id

        query = urlencode({'state': state, 'token': _issue_token(account_id, secret)})
        return redirect(f'{callback}?{query}')

    app.register_blueprint(bp)

