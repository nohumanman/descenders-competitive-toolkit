import socket
import time
import srcomapi
import srcomapi.datatypes as dt
from DBMS import DBMS
from TrailTimer import TrailTimer
import requests
from Tokens import webhook
from Tokens import steam_api_key
import logging

operations = {
    "STEAM_ID":
        lambda netPlayer, data: netPlayer.set_steam_id(data[1]),
    "STEAM_NAME":
        lambda netPlayer, data: netPlayer.set_steam_name(data[1]),
    "WORLD_NAME":
        lambda netPlayer, data: netPlayer.set_world_name(data[1]),
    "BOUNDRY_ENTER":
        lambda netPlayer, data: netPlayer.on_boundry_enter(data[1], data[2]),
    "BOUNDRY_EXIT":
        lambda netPlayer, data: netPlayer.on_boundry_exit(data[1], data[2]),
    "CHECKPOINT_ENTER":
        lambda netPlayer, data: netPlayer.on_checkpoint_enter(
            data[1],
            data[2],
            data[3]
        ),
    "RESPAWN":
        lambda netPlayer, data: netPlayer.on_respawn(),
    "MAP_ENTER":
        lambda netPlayer, data: netPlayer.on_map_enter(data[1], data[2]),
    "MAP_EXIT":
        lambda netPlayer, data: netPlayer.on_map_exit(),
    "BIKE_SWITCH":
        lambda netPlayer, data: netPlayer.on_bike_switch(data[1], data[2]),
    "REP":
        lambda netPlayer, data: netPlayer.set_reputation(data[1]),
    "SPEEDRUN_DOT_COM_LEADERBOARD":
        lambda netPlayer, data: (
            netPlayer.send(
                "SPEEDRUN_DOT_COM_LEADERBOARD|"
                + data[1] + "|"
                + str(netPlayer.convert_to_unity(
                    netPlayer.get_speedrun_dot_com_leaderboard(data[1])
                ))
            )
        ),
    "LEADERBOARD":
        lambda netPlayer, data: (
            netPlayer.send(
                "LEADERBOARD|"
                + data[1] + "|"
                + str(
                    netPlayer.get_leaderboard(data[1])
                )
            )
        ),
    "START_SPEED":
        lambda netPlayer, data: netPlayer.start_speed(float(data[1])),
    "TRICK":
        lambda netPlayer, data: netPlayer.set_last_trick(str(data[1])),
    "VERSION":
        lambda netPlayer, data: netPlayer.set_version(str(data[1])),
}


class NetPlayer():
    def __init__(self, conn: socket, addr, parent):
        self.addr = addr
        self.conn = conn
        self.parent = parent
        self.trails = {}
        self.__avatar_src = None
        self.steam_id = None
        self.steam_name = None
        self.bike_type = "enduro"
        self.world_name = None
        self.last_trick = ""
        self.reputation = 6969
        self.version = "OUTDATED"
        self.time_started = time.time()
        self.send("SUCCESS")
        self.send("INVALIDATE_TIME|Server Restarted - Timer Reset.")

    def set_last_trick(self, trick: str):
        self.last_trick = trick

    def set_version(self, version: str):
        self.version = version

    def set_reputation(self, reputation):
        self.reputation = int(reputation)
        DBMS.log_rep(self.steam_id, self.reputation)

    def start_speed(self, starting_speed: float):
        if starting_speed > 50:
            self.send("INVALIDATE_TIME|You went through the start too fast!")

    def convert_to_unity(self, leaderboard):
        logging.info("Getting speedrun.com leaderboard")
        if len(leaderboard) == 0:
            return {}
        keys = [key for key in leaderboard[0]]
        unityLeaderboard = {}
        for key in keys:
            unityLeaderboard[key] = []
        for leaderboardTime in leaderboard:
            for key in leaderboardTime:
                unityLeaderboard[key].append(leaderboardTime[key])
        return unityLeaderboard

    def get_leaderboard(self, trail_name):
        logging.info("Getting speedrun.com leaderboard for " + trail_name)
        return self.convert_to_unity(
            DBMS.get_leaderboard(
                trail_name
                )
            )

    def get_speedrun_dot_com_leaderboard(self, trail_name):
        logging.info("Getting speedrun.com leaderboard for " + trail_name)
        api = srcomapi.SpeedrunCom()
        game = api.get_game("Descenders")
        for level in game.levels:
            if level.data["name"] == trail_name:
                leaderboard = dt.Leaderboard(
                    api,
                    data=api.get(
                        f"leaderboards/{game.id}/level/{level.id}"
                        f"/7dg4yg4d?embed=variables"
                    )
                )
                leaderboard_json = ([
                    {
                        "place": leaderboard["place"],
                        "time": leaderboard["run"].times["realtime_t"],
                        "name": leaderboard["run"].players[0].name
                    } for leaderboard in leaderboard.runs if (
                        leaderboard["place"] != 0
                    )
                    ])
                return leaderboard_json
        return {}

    def get_total_time(self, onWorld=False):
        if onWorld:
            return DBMS.get_time_on_world(self.steam_id, self.world_name)
        return DBMS.get_time_on_world(self.steam_id)

    def get_avatar_src(self):
        if self.__avatar_src is not None:
            return self.__avatar_src
        avatar_src_req = requests.get(
            "https://api.steampowered.com/"
            "ISteamUser/GetPlayerSummaries"
            f"/v0002/?key={steam_api_key}"
            f"&steamids={self.steam_id}"
        )
        try:
            self.__avatar_src = avatar_src_req.json()[
                "response"]["players"][0]["avatarfull"]
        except (KeyError, IndexError):
            self.__avatar_src = DBMS().get_avatar(self.steam_id)
        return self.__avatar_src

    def set_steam_name(self, steam_name):
        self.steam_name = steam_name

    def set_steam_id(self, steam_id):
        self.steam_id = steam_id
        for player in self.parent.players:
            if (
                player.steam_id == self.steam_id
                and not isinstance(self, player)
            ):
                logging.warning(
                    f"Duplicate steam id on {player.steam_id} "
                    f"named {player.steam_name}! Destroying old player now!"
                )
                self.parent.players.remove(player)
                del(player)
        if steam_id == "OFFLINE" or steam_id == "":
            self.send("TOGGLE_GOD")
        for steam_id, ban_type in DBMS().get_banned_users():
            if ban_type == "CLOSE":
                self.send("BANNED|CLOSE")
            elif ban_type == "CRASH":
                self.send("BANNED|CRASH")
            elif ban_type == "ILLEGAL":
                self.send("BANNED|TOGGLE_GOD")

    def set_world_name(self, world_name):
        self.world_name = world_name
        DBMS().update_player(
            self.steam_id,
            self.steam_name,
            self.get_avatar_src()
        )
        DBMS.submit_ip(self.steam_id, self.addr[0], self.addr[1])
        # data = {
        #    "content": f"{self.steam_name} has **joined** {self.world_name}!",
        #     "username": "Split Timer"
        # }
        # requests.post(webhook, json=data)

    def send(self, data: str):
        self.conn.sendall((data + "\n").encode())

    def handle_data(self, data: str):
        if data == "":
            return
        logging.info(f"From {self.steam_name} Handling data '{data}'")
        data_list = data.split("|")
        for operator in operations:
            if data.startswith(operator):
                try:
                    operations[operator](self, data_list)
                except Exception as e:
                    logging.error(e)

    def recieve(self):
        while True:
            try:
                data = self.conn.recv(1024)
            except ConnectionResetError:
                logging.info("User has disconnected, breaking loop")
                break
            if not data:
                logging.info("User has disconnected, breaking loop 2")
                break
            for piece in data.decode().split("\n"):
                self.handle_data(piece)
        del(self)

    def ban(self, reason, method):
        self.send("BAN|" + reason + "|" + method)

    def invalidate_all_trails(self, reason: str):
        for trail in self.trails:
            self.trails[trail].invalidate_timer(reason)

    def on_respawn(self):
        if str(self.steam_id) == "76561198314526424":
            self.invalidate_all_trails("THOU HAST EATEN SHIT")
            return
        self.invalidate_all_trails("You respawned!")

    def get_trail(self, trail_name) -> TrailTimer:
        if trail_name not in self.trails:
            self.trails[trail_name] = TrailTimer(trail_name, self)
        return self.trails[trail_name]

    def on_bike_switch(self, old_bike: str, new_bike: str):
        self.bike_type = new_bike
        self.invalidate_all_trails("You switched bikes!")

    def on_boundry_enter(self, trail_name: str, boundry_guid: str):
        trail = self.get_trail(trail_name)
        trail.add_boundary(boundry_guid)

    def on_boundry_exit(self, trail_name: str, boundry_guid: str):
        trail = self.get_trail(trail_name)
        trail.remove_boundary(boundry_guid)

    def on_checkpoint_enter(
        self,
        trail_name: str,
        type: str,
        total_checkpoints: str
    ):
        self.get_trail(trail_name).total_checkpoints = int(total_checkpoints)
        if type == "Start":
            self.get_trail(trail_name).start_timer(total_checkpoints)
        if type == "Intermediate":
            self.get_trail(trail_name).checkpoint()
        if type == "Finish":
            self.get_trail(trail_name).end_timer()

    def on_map_enter(self, map_id, map_name):
        self.time_started = time.time()

    def on_map_exit(self):
        data = {
            "content": f"{self.steam_name} has **exited** {self.world_name}!",
            "username": "Split Timer"
        }
        requests.post(webhook, json=data)
        self.trails = {}
        DBMS.end_session(
            self.steam_id,
            self.time_started,
            time.time(),
            self.world_name
        )
        self.conn.close()
