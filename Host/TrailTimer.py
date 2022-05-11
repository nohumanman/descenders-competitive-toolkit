import time
import math
from DBMS import DBMS
from Tokens import webhook
import requests
import logging


class TrailTimer():
    def __init__(self, trail_name, network_player):
        self.trail_name = trail_name
        self.network_player = network_player
        self.started = False
        self.times = []
        self.total_checkpoints = None
        self.__boundaries = []
        self.time_started = 0

    def send_message(self, content: str):
        for webhook[0] in DBMS.get_webhooks(self.trail_name):
            data = {
                "content": content,
                "username": "Split Timer"
            }
            requests.post(webhook, json=data)

    def add_boundary(self, boundary_guid):
        if len(self.__boundaries) == 0:
            self.invalidate_timer("No boundaries entered")
        if boundary_guid not in self.__boundaries:
            self.__boundaries.append(boundary_guid)

    def remove_boundary(self, boundary_guid):
        if boundary_guid in self.__boundaries:
            self.__boundaries.remove(boundary_guid)
        if len(self.__boundaries) == 0:
            self.invalidate_timer("Exited boundry without entering")

    def start_timer(self, total_checkpoints: int):
        self.started = True
        self.total_checkpoints = total_checkpoints
        self.time_started = time.time()
        self.times = []

    def checkpoint(self):
        if self.started:
            self.times.append(time.time() - self.time_started)

    def invalidate_timer(self, reason: str):
        logging.info(f"invalidating time of {self.network_player.steam_name}")
        self.network_player.send(f"INVALIDATE_TIME|{reason}")
        self.started = False
        self.times = []

    def end_timer(self):
        from DBMS import DBMS
        if self.total_checkpoints is None:
            self.invalidate_timer("Didn't go through all checkpoints.")
        self.times.append(time.time() - self.time_started)
        if (len(self.times) == self.total_checkpoints-1):
            logging.info(f"Times submitted: {self.times}")
            fastest = DBMS.get_fastest_split_times(self.trail_name)
            if self.times[len(self.times)-1] < fastest[len(fastest)]:
                our_time = TrailTimer.secs_to_str(
                    self.times[len(self.times)-1]
                )
                self.send_message(
                    f"{self.network_player.steam_name} has beaten the fastest"
                    f" time for {self.trail_name} with a"
                    f" {our_time}!"
                )
            DBMS().submit_time(
                self.network_player.steam_id,
                self.times,
                self.trail_name,
                False,
                self.network_player.world_name,
                self.network_player.bike_type
            )
        self.started = False
        self.times = []

    @staticmethod
    def secs_to_str(secs):
        secs = float(secs)
        d_mins = int(round(secs // 60))
        d_secs = int(round(secs - (d_mins * 60)))
        d_millis = int(round(secs-math.trunc(secs), 3) * 1000)
        if len(str(d_mins)) == 1:
            d_mins = "0" + str(d_mins)
        if len(str(d_secs)) == 1:
            d_secs = "0" + str(d_secs)
        while len(str(d_millis)) < 3:
            d_millis = str(d_millis) + "0"
        return f"{d_mins}:{d_secs}.{d_millis}"

    @staticmethod
    def ord(n):
        return (
            str(n)
            + ("th" if 4 <= (n % 100) <= 20 else {
                1: "st",
                2: "nd",
                3: "rd"
            }.get(n % 10, "th")
            )
        )
