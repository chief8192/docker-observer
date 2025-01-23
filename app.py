#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# MIT License

# Copyright (c) 2025 Matt Doyle

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import datetime
import docker
import functools
import http.client
import itertools
import json
import os
import requests
import signal
import sys
import time
import urllib

from pushoverutil import Push
from threading import Thread, RLock


DOCKER_HEALTH_EVENTS = frozenset(["health_status"])
DOCKER_LIFECYCLE_EVENTS = frozenset(
    [
        "destroy",
        "die",
        "kill",
        "oom",
        "pause",
        "restart",
        "start",
        "stop",
        "unpause",
        "update",
    ]
)


@functools.cache
def LoadConfigJson():

    config_path = "/config.json"
    if not os.path.isfile(config_path):
        print("config.json not found")
        sys.exit(1)

    with open(config_path) as f:
        return json.load(f)


def NestedGet(indexable_obj, keys, default=None):
    result = indexable_obj
    for key in keys:
        result = result.get(key)
        if result is None:
            return default
    return result


class DockerEventThread(Thread):

    def __init__(self):
        super().__init__()

        self.running = False
        self.lock = RLock()

        config_json = LoadConfigJson()

        # Load Pushover credentials, if they're present.
        self.pushover_app_token = config_json.get("pushover_app_token")
        self.pushover_user_key = config_json.get("pushover_user_key")
        self.pushover_enabled = bool(self.pushover_app_token and self.pushover_user_key)

    def Start(self):
        with self.lock:
            self.running = True
            self.start()

    def Stop(self):
        with self.lock:
            self.running = False

    def IsRunning(self):
        with self.lock:
            return self.running

    def Pushover(self, title, message):
        print(f"{title}. {message}")
        if self.pushover_enabled:
            Push(self.pushover_user_key, self.pushover_app_token, message, title=title)

    def run(self):
        try:
            print("Starting Docker event thread")

            docker_client = docker.DockerClient(base_url="unix://var/run/docker.sock")
            filters = {
                "event": list(DOCKER_HEALTH_EVENTS) + list(DOCKER_LIFECYCLE_EVENTS)
            }

            while self.IsRunning():
                # See documentation:
                # https://docker-py.readthedocs.io/en/stable/client.html#docker.client.DockerClient.events
                for event in docker_client.events(filters=filters, decode=True):

                    event_type = event.get("Type", "????")
                    event_action = event.get("Action", "????")
                    print(f"New Docker event: {event_type} {event_action}")

                    # Grab the container name:
                    container_name = NestedGet(
                        event, ["Actor", "Attributes", "name"], "????"
                    )

                    # Skip non-status events.
                    if "status" not in event:
                        continue

                    # Figure out what the event status and (optional) substatus are.
                    event_pieces = event["status"].split(": ")
                    if len(event_pieces) == 1:
                        event_status, event_substatus = event_pieces[0], None
                    else:
                        event_status, event_substatus = event_pieces[0], event_pieces[1]

                    # Process the event depending on what type it is.
                    if event_status in DOCKER_HEALTH_EVENTS:
                        self.Pushover(
                            f"Container: {container_name}",
                            f"Health: {event_substatus.upper()}",
                        )

                    elif event_status in DOCKER_LIFECYCLE_EVENTS:
                        self.Pushover(
                            f"Container: {container_name}",
                            f"Status: {event_status.upper()}",
                        )

                    else:
                        self.Pushover(
                            f"Container: {container_name}",
                            f"Unsupported event: {event_status.upper()}",
                        )

        except Exception as e:
            self.Pushover("docker-observer", f"{e.__class__.__name__}: {str(e)}")


def ExitHandler(event_thread, unused_signo, unused_stack_frame):
    event_thread.Stop()


def main():
    docker_event_thread = DockerEventThread()

    # Set up exit handling for the thread. See documentation:
    # https://docs.python.org/3/library/signal.html#signal.signal
    exit_handler = functools.partial(ExitHandler, docker_event_thread)
    signal.signal(signal.SIGTERM, exit_handler)
    signal.signal(signal.SIGINT, exit_handler)

    # Start the thread.
    docker_event_thread.Start()
    docker_event_thread.join()


if __name__ == "__main__":
    main()
