""" Used to host the website using flask """
from typing import TYPE_CHECKING
import os
import time
from datetime import datetime
import logging
from werkzeug.utils import secure_filename

# Flask imports
from flask import (
    Flask,
    session,
    request,
    redirect,
    jsonify,
    render_template,
    send_file
)

# Authlib imports
from authlib.integrations.requests_client import OAuth2Session
from authlib.integrations.base_client import MissingTokenError
from authlib.integrations.base_client.errors import InvalidTokenError

# Unity Socket Server imports
from unity_socket_server import UnitySocketServer, PlayerNotFound

# Database Management System imports
from dbms import DBMS

# Tokens imports
from tokens import OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET

# Used to fix RuntimeError in using async from thread
import nest_asyncio
nest_asyncio.apply()

if TYPE_CHECKING:
    # Imports related to the Discord bot (if any)
    from discord_bot import DiscordBot

OAUTH2_REDIRECT_URI = 'https://modkit.nohumanman.com/callback'
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://discordapp.com/api')
AUTHORIZATION_BASE_URL = API_BASE_URL + '/oauth2/authorize'
TOKEN_URL = API_BASE_URL + '/oauth2/token'


logging = logging.getLogger('DescendersSplitTimer')


class WebserverRoute():
    """ Used to denote a webserver url to view function """
    def __init__(self, route, endpoint, view_func, methods):
        self.route = route
        self.endpoint = endpoint
        self.view_func = view_func
        self.methods = methods

    def is_valid(self):
        """ Function to check if the route is valid """
        return (
            self.route is not None
            and self.endpoint is not None
            and self.view_func is not None
            and self.methods is not None
        )

    def to_dict(self):
        """ Function to convert the route to a dictionary """
        return {
            "route": self.route,
            "endpoint": self.endpoint,
            "view_func": self.view_func,
            "methods": self.methods
        }

class Webserver():
    """ Used to host the website using flask """
    def __init__(self, socket_server: UnitySocketServer, dbms : DBMS):
        self.dbms = dbms
        self.webserver_app = Flask(__name__)
        self.webserver_app.config['SECRET_KEY'] = OAUTH2_CLIENT_SECRET
        self.socket_server: UnitySocketServer = socket_server
        self.discord_bot: DiscordBot | None = None
        self.routes = [
            WebserverRoute(
                "/callback", "callback",
                self.callback, ["GET"]
            ),
            WebserverRoute(
                "/me", "me",
                self.me, ["GET"]
            ),
            WebserverRoute(
                "/streaming/split-time", "split_time",
                self.split_time, ["GET"]
            ),
            WebserverRoute(
                "/permission", "permission_check",
                self.permission, ["GET"]
            ),
            WebserverRoute(
                "/streaming/tag", "tag",
                self.tag, ["GET"]
            ),
            WebserverRoute(
                "/", "index",
                self.index, ["GET"]
            ),
            WebserverRoute(
                "/dashboard", "dashboard",
                self.index, ["GET"]
            ),
            WebserverRoute(
                "/times", "times",
                self.index, ["GET"]
            ),
            WebserverRoute(
                "/trails", "times",
                self.index, ["GET"]
            ),
            WebserverRoute(
                "/leaderboard", "leaderboard",
                self.leaderboard, ["GET"]
            ),
            WebserverRoute(
                "/get-leaderboard", "get_leaderboards",
                self.get_leaderboards, ["GET"]
            ),
            WebserverRoute(
                "/leaderboard", "get_leaderboard",
                self.get_leaderboard, ["GET"]
            ),
            WebserverRoute(
                "/leaderboard/<trail>", "get_leaderboard_trail",
                self.get_leaderboard_trail, ["GET"]
            ),
            WebserverRoute(
                "/get-all-times", "get_all_times",
                self.get_all_times, ["GET"]
            ),
            WebserverRoute(
                "/get", "get",
                self.get, ["GET"]
            ),
            WebserverRoute(
                "/api/get-spectated", "get_spectated",
                self.get_spectated, ["GET"]
            ),
            WebserverRoute(
                "/eval/<player_id>", "eval",
                self.eval, ["GET"]
            ),
            WebserverRoute(
                "/time/<time_id>", "time_details",
                self.time_details, ["GET"]
            ),
            WebserverRoute(
                "/verify_time/<time_id>", "verify_time",
                self.verify_time, ["GET"]
            ),
            WebserverRoute(
                "/login", "login",
                self.login, ["GET"]
            ),
            WebserverRoute(
                "/api/spectate", "spectate",
                self.spectate, ["GET"]
            ),
            WebserverRoute(
                "/api/spectating/get-time", "get_spectating_time",
                self.get_spectating_time, ["GET"]
            ),
            WebserverRoute(
                "/concurrency", "concurrency",
                self.concurrency, ["GET"]
            ),
            WebserverRoute(
                "/get-trails", "get_trails",
                self.get_trails, ["GET"]
            ),
            WebserverRoute(
                "/get-worlds", "get_worlds",
                self.get_worlds, ["GET"]
            ),
            WebserverRoute(
                "/upload-replay",
                "upload_replay",
                self.upload_replay,
                ["POST"]
            ),
            WebserverRoute(
                "/ignore-time/<time_id>/<value>",
                "ignore_time",
                self.ignore_time,
                ["GET"]
            ),
            WebserverRoute(
                "/get-output-log/<player_id>",
                "get_output_log",
                self.get_output_log,
                ["GET"]
            ),
            WebserverRoute(
                "/static/replays/<time_id>",
                "get_replay",
                self.get_replay,
                ["GET"]
            ),
        ]
        self.tokens_and_ids = {}
        self.add_routes()
        self.register_error_handlers()

    def add_routes(self):
        """ Adds the routes to the flask app """
        for route in self.routes:
            self.webserver_app.add_url_rule(
                route.route,
                    endpoint=route.endpoint,
                view_func=route.view_func,
                methods=route.methods
            )

    def register_error_handlers(self):
        """ Register error handlers for 404 and 500 errors """
        # Custom 404 error handler
        @self.webserver_app.errorhandler(404)
        def page_not_found(e):
            return render_template('404.html'), 404

        # Custom 500 error handler
        @self.webserver_app.errorhandler(500)
        def internal_server_error(e):
            return render_template('500.html'), 500

    async def spectate(self):
        """ Function to spectate a player """
        # get our player id
        try:
            our_id = await self.get_our_steam_id()
        except (InvalidTokenError, MissingTokenError):
            return ("ERROR - NOT LOGGED IN!", 500)
        # get us
        try:
            us = self.socket_server.get_player_by_id(str(our_id))
        except PlayerNotFound:
            return f"Failed to find you! your id : {our_id}"
        target_id = request.args.get("target_id")
        us.info.spectating = self.socket_server.get_player_by_id(
            target_id
        ).info.steam_name
        us.info.spectating_id = target_id
        # send the spectate command
        await us.send(f"SPECTATE|{target_id}")
        return "Success"

    async def eval(self, player_id):
        """ Function to evaluate commands sent to player with id player_id """
        if await self.permission() == "AUTHORISED":
            args = request.args.get("order")
            try:
                if args is None:
                    return "Failed - no args"
                await self.socket_server.get_player_by_id(player_id).send(args)
            except PlayerNotFound:
                return "Player not found"
            return ""
        return "FAILED - NOT VALID PERMISSIONS!", 401

    async def get_replay(self, time_id):
        """ Function to get the replay of a time with id time_id """
        time_id = time_id.split(".")[0]
        try:
            return send_file(
                "static/replays/" + time_id + ".replay",
                download_name=f"{await self.dbms.get_replay_name_from_id(time_id)}.replay"
            )
        except FileNotFoundError:
            return "No replay found!"

    async def get_spectated(self):
        """ Function to get the player we are spectating """
        our_id = request.args.get("my_id")
        try:
            us = self.socket_server.get_player_by_id(str(our_id))
        except PlayerNotFound:
            return f"Failed to find you! your id : {our_id}"
        return us.info.spectating

    async def get_spectating_time(self):
        """ Function to get the times of the player we are spectating """
        our_id = request.args.get("my_id")
        # get time
        trail_time = {}
        time_started = 0
        while not trail_time or str(trail_time) == str(session['previous_result']):
            try:
                us = self.socket_server.get_player_by_id(str(our_id))
            except PlayerNotFound:
                return f"Failed to find you! your id : {our_id}"
            try:
                spectating = self.socket_server.get_player_by_id(us.info.spectating_id)
            except PlayerNotFound:
                return "Failed to find player you are spectating"
            for trail_name in spectating.trails:
                trail = await spectating.get_trail(trail_name)
                if trail.timer_info.started:
                    trail_time = {"time": trail.timer_info.time_started, "started": True, "times": trail.timer_info.times}
                    break
                if trail.timer_info.time_started > time_started:
                    if len(trail.timer_info.times) != 0:
                        trail_time = {"time": trail.timer_info.times[-1], "started": False, "times": trail.timer_info.times}
                    time_started = trail.timer_info.time_started
            time.sleep(0.1)
        session['previous_result'] = str(trail_time)
        return jsonify(trail_time)

    async def time_details(self, time_id):
        """ Function to get the details of a time with id time_id """
        try:
            details = await self.dbms.get_time_details(time_id)
            # see if the time is faster than the player's current fastest verified time
            faster_than_current_fastest = False
            try:
                current_fastest = (await self.dbms.get_personal_fastest_split_times(details[7], details[0]))[-1]
                if current_fastest is not None and details[6] <= current_fastest:
                    faster_than_current_fastest = True
            except IndexError:
                faster_than_current_fastest = True
            return render_template(
                "Time.html",
                steam_id=details[0],
                steam_name=details[1],
                avatar_src=details[2],
                timestamp=details[3],
                time_id=details[4],
                total_checkpoints=details[5],
                total_time=details[6],
                trail_name=details[7],
                world_name=details[8],
                ignore=details[9],
                bike_type=details[10],
                starting_speed=details[11],
                version=details[12],
                verified=details[14],
                timestamp_to_time=datetime.fromtimestamp(details[3]),
                warning="WARNING - SLOWER THAN PLAYER'S FASTEST VERIFIED TIME" if not faster_than_current_fastest else ""
            )
        except IndexError:
            return "No time found!"

    async def verify_time(self, time_id):
        """ Function to verify a time with id time_id """
        if await self.permission() == "AUTHORISED":
            our_discord_id = self.get_discord_id()
            await self.dbms.verify_time(time_id)
            try:
                details = await self.dbms.get_time_details(time_id)
                steam_name = details[1]
                time_id=details[4]
                total_time=details[6]
                trail_name=details[7]
                verified=details[14]
                if self.discord_bot is not None and verified == 1:
                    self.discord_bot.loop.run_until_complete(
                        self.discord_bot.send_message_to_channel(
                                f"[Time](https://modkit.nohumanman.com/time/{time_id})"
                                f" by {steam_name} of {total_time} on {trail_name} has been verified by <@{our_discord_id}>."
                                " This time will now display in leaderboards where appropriate. 🎉",
                                1213907351896334426
                        )
                    )
            except RuntimeError as e:
                logging.warning("Failed to submit time to discord server %s", e)
                return "ERROR: Failed to submit time to discord server"
            return "Toggled verification on time"
        else:
            return "ERROR: NO PERMISSION"

    async def get_output_log(self, player_id):
        """ Function to get the output log of a player with id player_id """
        if await self.permission() == "AUTHORISED":
            lines = ""
            try:
                with open(
                    f"{os.getcwd()}/output_log/{player_id}.txt",
                    "rt",
                    encoding="utf-8"
                ) as my_file:
                    file_lines = my_file.read().splitlines()
                    file_lines = file_lines[-50:]
                    for line in file_lines:
                        lines += f"> {line}<br>"
            except FileNotFoundError:
                lines = (
                    "Failed to get output log."
                    " One likely does not exist, has the user just loaded in?"
                )
            return lines
        return "You are not authorised to fetch output log."

    async def get(self):
        """ Function to get the details of a player with id player_id """
        if True:
            player_json = [
                {
                    "steam_id": player.info.steam_id,
                    "steam_name": player.info.steam_name,
                    "steam_avatar_src": await player.get_avatar_src(),
                    "reputation": player.info.reputation,
                    "total_time": "",#player.get_total_time(),
                    "time_on_world": "",#player.get_total_time(onWorld=True),
                    "world_name": player.info.world_name,
                    "last_trick": player.info.last_trick,
                    "version": player.info.version,
                    "bike_type": player.info.bike_type,
                    "trail_info": str(player.trails),
                    "address": ""#(lambda: player.addr if self.permission() == "AUTHORISED" else "")()
                } for player in self.socket_server.players
            ]
            return jsonify({"players": player_json})
        else:
            # return json of every map and amount of players in it
            return jsonify({"state": {
                "players": len(self.socket_server.players)
            }})

    async def get_trails(self):
        """ Function to get the trails """ 
        return jsonify({"trails": await self.dbms.get_trails()})

    async def ignore_time(self, time_id : int, value: str):
        """ Function to ignore a time with id time_id"""
        if await self.permission() == "AUTHORISED":
            # value should be 'False' or 'True
            await self.dbms.set_ignore_time(time_id, value)
            if self.discord_bot is not None:
                self.discord_bot.loop.run_until_complete(
                    self.discord_bot.new_time(
                        f"[Time](https://modkit.nohumanman.com/time/{time_id}) has been deleted."
                    )
                )
            return "success"
        return "INVALID_PERMS"
            
    async def upload_replay(self):
        """ Function to upload a replay """
        replay_file = request.files.get("replay")  # Using .get() to handle missing keys
        time_id = request.form.get('time_id')       # Using .get() to handle missing keys

        # Validate time_id
        if time_id is None:
            return "Error: Invalid time_id"

        # Ensure replay_file is not None
        if replay_file is None:
            return "Error: No replay file provided"

        # Securely save the file using a secure filename
        filename = secure_filename(f"{time_id}.replay")
        replay_path = os.path.join(os.getcwd(), 'static', 'replays', filename)

        # Save the file
        replay_file.save(replay_path)
        return "Success"

    async def get_worlds(self):
        """ Function to get the worlds """
        return jsonify({"worlds": await self.dbms.get_worlds()})

    async def concurrency(self):
        """ Function to get the concurrency of a map """
        map_name = request.args.get("map_name")
        if map_name == "" or map_name is None:
            return jsonify({})
        return jsonify({
            "concurrency": await self.dbms.get_daily_plays(
                map_name,
                datetime(2022, 5, 1),
                datetime.now()
            )
        })

    async def permission(self):
        """ Function to get the permission of a user """
        oauth2_token = session.get('oauth2_token')
        if oauth2_token is None:
            return "UNKNOWN"
        discord = self.make_session(token=oauth2_token)
        user = discord.get(API_BASE_URL + '/users/@me').json()
        if user["id"] in [str(x[0]) for x in await self.dbms.get_valid_ids()]:
            return "AUTHORISED"
        return "UNAUTHORISED"

    async def logged_in(self):
        """ Function to check if a user is logged in """
        return (
            await self.permission() == "AUTHORISED"
            or await self.permission() == "UNAUTHORISED"
        )

    def make_session(self, token=None, state=None, scope=None):
        """ Function to make a session """
        return OAuth2Session(
            client_id=OAUTH2_CLIENT_ID,
            token=token,
            state=state,
            scope=scope,
            redirect_uri=OAUTH2_REDIRECT_URI,
            auto_refresh_kwargs={
                'client_id': OAUTH2_CLIENT_ID,
                'client_secret': OAUTH2_CLIENT_SECRET,
            },
            auto_refresh_url=TOKEN_URL,
            refresh_token=self.token_updater
        )

    def token_updater(self, token):
        """ Function to update the token """
        session['oauth2_token'] = token

    async def get_our_steam_id(self):
        """ Function to get the steam id of the user """
        discord = self.make_session(token=session.get('oauth2_token'))
        connections = discord.get(
            API_BASE_URL + '/users/@me/connections'
        ).json()
        for connection in connections:
            if not isinstance(connection, dict):
                return "None"
            if connection["type"] == "steam":
                return connection["id"]
        return "None"

    def get_discord_id(self):
        """ Function to get the discord name """
        discord = self.make_session(token=session.get('oauth2_token'))
        user = discord.get(API_BASE_URL + '/users/@me').json()
        return user["id"]

    # routes
    async def callback(self):
        """ Function to handle the callback of the website """
        try:
            if request.values.get('error'):
                return request.values['error']
            if session.get('oauth2_state') is None:
                return "Invalid oauth2_state"
            discord = self.make_session(
                state=session.get('oauth2_state')
            )
            token = discord.fetch_token(
                TOKEN_URL,
                client_secret=OAUTH2_CLIENT_SECRET,
                authorization_response=request.url
            )
            session['oauth2_token'] = token
            user = discord.get(
                API_BASE_URL + '/users/@me'
            ).json()
            connections = discord.get(
                API_BASE_URL + '/users/@me/connections'
            ).json()
            try:
                user_id = user['id']
            except IndexError:
                return "User id not found on discord user?"
            try:
                user_id = user['id']
                try:
                    email = user['email']
                except KeyError:
                    email = ""
                username = user['username']
                steam_id = "NONE"
                try:
                    for connection in connections:
                        if connection['type'] == "steam":
                            steam_id = connection['id']
                except KeyError:
                    logging.info("Steam ID Not Found")
                await self.dbms.discord_login(user_id, username, email, steam_id)
            except Exception as e:
                logging.info("User %s with error %s", user, str(e))
            return redirect("/")
        except (IndexError, KeyError) as e:
            return str(e)
        except Exception as e:
            return str(e)

    async def me(self):
        """ Function to get the details of a user """
        try:
            discord = self.make_session(token=session.get('oauth2_token'))
            user = discord.get(API_BASE_URL + '/users/@me').json()
            connections = discord.get(
                API_BASE_URL + '/users/@me/connections'
            ).json()
            guilds = discord.get(API_BASE_URL + '/users/@me/guilds').json()
            return jsonify(user=user, guilds=guilds, connections=connections)
        except MissingTokenError:
            return jsonify({})

    async def split_time(self):
        """ Function to get the split time """
        session['previous_result'] = "{}"
        return render_template("SplitTime.html")

    def tag(self):
        """ Function to get the player tag """
        return render_template("PlayerTag.html")

    def login(self):
        """ Function to login to the website """
        scope = request.args.get(
            'scope',
            'identify email connections guilds guilds.join'
        )
        scope = "identify connections"
        discord = self.make_session(scope=scope.split(' '))
        authorization_url, state = discord.create_authorization_url(
            AUTHORIZATION_BASE_URL
        )
        session['oauth2_state'] = state
        return redirect(authorization_url)

    async def index(self):
        """ Function to get the index of the website """
        logging.info("Webserver.py - index() called")
        return render_template("Dashboard.html")

    async def leaderboard(self):
        """ Function to get the leaderboard of the website"""
        return render_template("Leaderboard.html")

    async def get_leaderboards(self):
        """ Function to get the leaderboard of the website"""

        trail_name = request.args.get("trail_name")
        try:
            spectated_by = request.args.get("spectated_by")
            timestamp = request.args.get("timestamp")
        except KeyError:
            spectated_by = None
            timestamp = 0
        if trail_name is None:
            return jsonify({})
        return jsonify(
            await self.dbms.get_leaderboard(
                trail_name,
                num=10,
                spectated_by=spectated_by,
                timestamp=timestamp
            )
        )

    def get_leaderboard(self):
        """ Function to get the leaderboard of the website"""
        if self.logged_in():
            return render_template("Leaderboard.html")
        return redirect("/")

    async def get_leaderboard_trail(self, trail):
        """ Function to get the leaderboard of the website"""
        return jsonify(await self.dbms.get_leaderboard(trail))

    async def get_all_times(self):
        """ Function to get all the times of the website"""
        lim_str = request.args.get("lim")
        if lim_str is None:
            return jsonify({})
        lim = int(lim_str)
        return jsonify({"times": await self.dbms.get_all_times(lim)})
