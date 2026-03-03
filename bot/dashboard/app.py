"""Flask web dashboard with Discord OAuth2."""
from __future__ import annotations

import secrets
from functools import wraps
from urllib.parse import urlencode

import requests
from flask import (
    Flask,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from bot.logger import get_logger
from bot.settings import settings

logger = get_logger(__name__)

DISCORD_API = 'https://discord.com/api/v10'
DISCORD_AUTH_URL = 'https://discord.com/api/oauth2/authorize'
DISCORD_TOKEN_URL = 'https://discord.com/api/oauth2/token'
DISCORD_SCOPES = 'identify guilds'
MANAGE_GUILD = 0x20

app = Flask(__name__)
app.secret_key = settings.session_secret


# ------------------------------------------------------------------ helpers

def _csrf_token() -> str:
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(32)
    return session['_csrf']


def _validate_csrf() -> bool:
    token = session.get('_csrf')
    submitted = request.form.get('_csrf')
    return bool(token and submitted and secrets.compare_digest(token, submitted))


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


def _callback_url() -> str:
    return settings.callback_url


# ------------------------------------------------------------------ routes

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html', user=None)


@app.route('/auth/discord')
def auth_discord():
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state
    params = {
        'client_id': settings.client_id,
        'redirect_uri': _callback_url(),
        'response_type': 'code',
        'scope': DISCORD_SCOPES,
        'state': state,
    }
    return redirect(f'{DISCORD_AUTH_URL}?{urlencode(params)}')


@app.route('/auth/discord/callback')
def auth_discord_callback():
    state = request.args.get('state')
    stored_state = session.pop('oauth_state', None)
    if not state or state != stored_state:
        return redirect(url_for('index'))

    code = request.args.get('code')
    if not code:
        return redirect(url_for('index'))

    token_resp = requests.post(
        DISCORD_TOKEN_URL,
        data={
            'client_id': settings.client_id,
            'client_secret': settings.client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': _callback_url(),
        },
        timeout=10,
    )
    if not token_resp.ok:
        return redirect(url_for('index'))

    token_data = token_resp.json()
    access_token = token_data.get('access_token')
    if not access_token:
        return redirect(url_for('index'))

    headers = {'Authorization': f'Bearer {access_token}'}
    user = requests.get(f'{DISCORD_API}/users/@me', headers=headers, timeout=10).json()
    guilds_resp = requests.get(f'{DISCORD_API}/users/@me/guilds', headers=headers, timeout=10)
    user['guilds'] = guilds_resp.json() if guilds_resp.ok else []

    session['user'] = user
    return redirect(url_for('dashboard'))


@app.route('/auth/logout')
def auth_logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    user = session['user']
    manageable = [
        g for g in (user.get('guilds') or [])
        if (int(g.get('permissions', '0')) & MANAGE_GUILD) == MANAGE_GUILD
    ]

    bot_guild_ids: set[str] = set()
    try:
        from bot.main import bot as discord_bot
        if discord_bot.is_ready():
            bot_guild_ids = {str(g.id) for g in discord_bot.guilds}
    except Exception:
        pass

    guilds_with_presence = [
        {**g, 'botPresent': g['id'] in bot_guild_ids}
        for g in manageable
    ]

    return render_template(
        'dashboard.html',
        user=user,
        guilds=guilds_with_presence,
        discord_client_id=settings.client_id,
    )


@app.route('/dashboard/<guild_id>/settings', methods=['GET'])
@login_required
def guild_settings_get(guild_id: str):
    user = session['user']
    if not _has_access(user, guild_id):
        return 'Forbidden', 403

    import asyncio
    guild_settings = asyncio.run(_get_settings(guild_id))
    csrf = _csrf_token()
    return render_template('settings.html', user=user, guild_id=guild_id, settings=guild_settings, saved=False, csrf_token=csrf)


@app.route('/dashboard/<guild_id>/settings', methods=['POST'])
@login_required
def guild_settings_post(guild_id: str):
    if not _validate_csrf():
        return 'Invalid CSRF token', 403

    user = session['user']
    if not _has_access(user, guild_id):
        return 'Forbidden', 403

    prefix = (request.form.get('prefix') or '!')[:5]
    language = request.form.get('language', 'en')
    if language not in ('en', 'es'):
        language = 'en'
    default_volume = max(1, min(100, int(request.form.get('defaultVolume') or 80)))
    dj_role_id = request.form.get('djRoleId') or None
    announce = request.form.get('announceNowPlaying') == 'on'

    import asyncio
    asyncio.run(_update_settings(guild_id, {
        'prefix': prefix,
        'language': language,
        'defaultVolume': default_volume,
        'djRoleId': dj_role_id,
        'announceNowPlaying': int(announce),
    }))

    guild_settings = asyncio.run(_get_settings(guild_id))
    csrf = _csrf_token()
    return render_template('settings.html', user=user, guild_id=guild_id, settings=guild_settings, saved=True, csrf_token=csrf)


# ------------------------------------------------------------------ db helpers (sync wrappers)

def _has_access(user: dict, guild_id: str) -> bool:
    return any(
        g['id'] == guild_id and (int(g.get('permissions', '0')) & MANAGE_GUILD) == MANAGE_GUILD
        for g in (user.get('guilds') or [])
    )


async def _get_settings(guild_id: str) -> dict:
    from bot.db import get_guild_settings, init_db
    await init_db()
    return await get_guild_settings(guild_id)


async def _update_settings(guild_id: str, data: dict) -> dict:
    from bot.db import update_guild_settings, init_db
    await init_db()
    return await update_guild_settings(guild_id, data)


# ------------------------------------------------------------------ entry point

if __name__ == '__main__':
    if not settings.session_secret:
        raise RuntimeError('session_secret is not set in settings.json. Refusing to start.')
    port = settings.dashboard_port
    logger.info('Dashboard running at http://localhost:%d', port)
    app.run(host='0.0.0.0', port=port)
