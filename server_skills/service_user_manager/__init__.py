# Copyright 2016 Mycroft AI, Inc.
#
# This file is part of Mycroft Core.
#
# Mycroft Core is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mycroft Core is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mycroft Core.  If not, see <http://www.gnu.org/licenses/>.

from adapt.intent import IntentBuilder

from mycroft.skills.core import MycroftSkill
from mycroft.util.log import getLogger

__author__ = 'eward'

LOGGER = getLogger(__name__)

from mycroft.messagebus.message import Message
from mycroft.skills.settings import SkillSettings

from os.path import dirname
import time, os


class User():
    def __init__(self, id, name="user", emitter=None):
        self.user_id = id
        self.name = name
        self.emitter = emitter
        self.load_user()
        self.save_user()
        # session data
        self.session_key = None #encrypt everything with this shared key
        self.current_sock = None
        self.current_ip = None
        self.status = "offline"
        self.user_type = "client"
        self.default_forbidden_messages = [
            "incoming_file",
            "image.classification.request",
            "style.transfer.request",
            "deep.dream.request",
            "class.visualization.request",
            "face.recognition.request",
            "object.recognition.request"]
        self.default_forbidden_skills = ["control_center_skill"] #TODO get skills names, not ids
        self.default_forbidden_intents = ["StyleTransferIntent",
                                          "DreamIntent",
                                          "DeepDrawIntent",
                                          "ImageClassfyStatusIntent",
                                          "TestObjectRecogIntent",
                                          "FollowUserIntent",
                                          "UnFollowUserIntent",
                                          "PostTweetIntent",
                                          "FbLikeRandomPhotoIntent",
                                          "FbAddSuggestedFriendIntent",
                                          "FbAddFriendsofFriendsIntent",
                                          "FbBuildAboutMeIntent",
                                          "FbLastOnlineIntent",
                                          "FbChatPersonIntent",
                                          "FbLikePhotosofPersonIntent"
                                          ]

    def load_user(self, path=None):
        if path is None:
            path = dirname(__file__) + "/users"
        # check if folders exist
        if not os.path.exists(path):
            os.makedirs(path)
        path += "/"+str(self.user_id)+".json"
        self.settings = SkillSettings(path)
        if self.user_id not in self.settings.keys():
            self.settings[self.user_id] = {}
        self.name = self.settings[self.user_id].get("name", "user")
        self.nicknames = self.settings[self.user_id].get("nicknames", [])
        self.public_key = self.settings[self.user_id].get("public_key")
        self.security_level = self.settings[self.user_id].get("security_level", 0)
        self.forbidden_skills = self.settings[self.user_id].get("forbidden_skills", self.default_forbidden_skills)
        self.forbidden_messages = self.settings[self.user_id].get("forbidden_messages",  self.default_forbidden_messages)
        self.forbidden_intents = self.settings[self.user_id].get("forbidden_intents", self.default_forbidden_intents)
        self.last_seen = self.settings[self.user_id].get("last_seen", "never")
        self.last_timestamp = self.settings[self.user_id].get("last_ts", 0)
        self.known_ips = self.settings[self.user_id].get("known_ips", [])
        self.timestamp_history = self.settings[self.user_id].get("timestamp_history", [])
        self.photo = self.settings[self.user_id].get("photo")
        self.user_type = self.settings[self.user_id].get("user_type", "client")

    def save_user(self):
        self.settings[self.user_id]["name"] = self.name
        self.settings[self.user_id]["nicknames"] = self.nicknames
        self.settings[self.user_id]["public_key"] = self.public_key
        self.settings[self.user_id]["security_level"] = self.security_level
        self.settings[self.user_id]["forbidden_skills"] = self.forbidden_skills
        self.settings[self.user_id]["forbidden_intents"] = self.forbidden_intents
        self.settings[self.user_id]["last_seen"] = self.last_seen
        self.settings[self.user_id]["last_ts"] = self.last_timestamp
        self.settings[self.user_id]["known_ips"] = self.known_ips
        self.settings[self.user_id]["timestamp_history"] = self.timestamp_history
        self.settings[self.user_id]["photo"] = self.photo
        self.settings[self.user_id]["user_type"] = self.user_type
        self.settings[self.user_id]["forbidden_messages"] = self.forbidden_messages
        self.settings.store()

    def add_new_ip(self, ip, emit=True):
        if ip not in self.known_ips:
            self.known_ips.append(ip)
            if emit:
                self.emitter.emit(Message("user.new_ip", {"ts": time.time(), "name": self.name, "last_seen": self.last_seen}))

    def update_timestamp(self):
        self.last_timestamp = time.time()
        self.timestamp_history.append(self.last_timestamp)

    def update_last_seen(self, last_seen):
        self.last_seen = last_seen

    def set_key(self, key):
        self.public_key = key

    def authenticate(self):
        pass

    def add_nicknames(self, names):
        for name in names:
            if name not in self.nicknames:
                self.nicknames.append(name)

    def reset(self):
        self.name = "user"
        self.nicknames = []
        self.public_key = "todo"
        self.security_level = 0
        self.forbidden_messages = []
        self.forbidden_skills = []
        self.forbidden_intents = []
        self.last_seen = "never"
        self.last_timestamp = 0
        self.known_ips = []
        self.timestamp_history = []
        self.photo = None
        self.user_type = "client"
        self.save_user()


class UserSkill(MycroftSkill):
    def __init__(self):
        super(UserSkill, self).__init__(name="UserSkill")
        self.default_key = "xxxxxxxx"
        self.reload_skill = False
        self.user_list = {} # id, sock
        self.users = {}    # id, user object
        for user_id in self.user_list.keys():
            user = User(id=user_id, emitter=self.emitter)
            #user.reset()
            self.users[user_id] = user
        self.facebook_users = {} #fb_id, user object

    def initialize(self):
        self.emitter.on("user.connect", self.handle_user_connect)
        self.emitter.on("user.names", self.handle_user_names)
        self.emitter.on("user.request", self.handle_user_request)
        self.emitter.on("user.disconnect", self.handle_user_disconnect)
        self.emitter.on("fb.chat.message", self.handle_fb_message_received)
        self.emitter.on("fb.chat.message.seen", self.handle_fb_message_seen)
        self.emitter.on("fb.last.seen.timestamps", self.handle_fb_timestamp)
        self.emitter.on("user.from_sock.request", self.handle_user_from_sock_request)
        self.emitter.on("user.from_id.request", self.handle_user_from_id_request)
        self.emitter.on("user.from_facebook.request", self.handle_user_from_facebook_request)

    # internal messages
    def handle_user_from_id_request(self, message):
        user_id = message.data.get("id")
        found = False
        for id in self.user_list.keys():
            # search socks
            if id == user_id:
                user_id = str(id)
                self.log.info("sock user found: " + user_id)
                found = True

        if not found:
            # search fb
            for id in self.facebook_users.keys():
                # search socks
                if id == user_id:
                    user_id = str(id)
                    self.log.info("facebook user found: " + user_id)
                    found = True
        else:
            data = {"id": user_id,
                    "forbidden_skills": self.users[user_id].forbidden_skills,
                    "forbidden_messages": self.users[user_id].forbidden_messages,
                    "forbidden_intents": self.users[user_id].forbidden_intents,
                    "security_level": self.users[user_id].security_level,
                    "pub_key": self.users[user_id].public_key,
                    "nicknames": self.users[user_id].nicknames}
            self.emitter.emit(Message("user.from_id.result", data, message.context))
            return

        if found:
            data = {"id": user_id,
                    "forbidden_skills": self.facebook_users[user_id].forbidden_skills,
                    "forbidden_messages": self.facebook_users[user_id].forbidden_messages,
                    "forbidden_intents": self.facebook_users[user_id].forbidden_intents,
                    "security_level": self.facebook_users[user_id].security_level,
                    "pub_key": self.facebook_users[user_id].public_key,
                    "nicknames": self.facebook_users[user_id].nicknames}
            self.emitter.emit(Message("user.from_id.result", data, message.context))
        else:
            data = {"id": user_id, "error": "no such user"}
            self.emitter.emit(Message("user.from_id.result", data, message.context))

    def handle_user_from_facebook_request(self, message):
        user_id = message.data.get("id")
        if user_id not in self.facebook_users.keys():
            self.log.warning("Unknown facebook id provided, creating new user profile")
            # new user
            new_user = User(id=user_id, emitter=self.emitter)
            self.facebook_users[user_id] = new_user

        data = {"id": user_id,
            "forbidden_skills": self.facebook_users[user_id].forbidden_skills,
            "forbidden_messages": self.facebook_users[user_id].forbidden_messages,
            "forbidden_intents": self.facebook_users[user_id].forbidden_intents,
            "security_level": self.facebook_users[user_id].security_level,
            "pub_key": self.facebook_users[user_id].public_key,
            "nicknames": self.facebook_users[user_id].nicknames}
        self.emitter.emit(Message("user.from_facebook.result", data, message.context))

    def handle_user_from_sock_request(self, message):
        sock = message.data.get("sock")
        ip = message.data.get("ip")
        user_id = None
        if ip is None:
            for user_id in self.users:
                user = self.users[user_id]
                if user.current_sock == sock:
                    self.user_list[user_id] = sock
                    break
        else:
            user_id = self.user_from_ip_sock(sock, ip)

        if user_id is None:
            self.log.error("Something went wrong")
            # TODO send close request?
            self.emitter.emit(Message("user.from_sock.result", {"id": None, "error": "that sock is not supposed to be open?"}))
            return

        data = {"id": user_id,
                "forbidden_skills": self.users[user_id].forbidden_skills,
                "forbidden_messages": self.users[user_id].forbidden_messages,
                "forbidden_intents": self.users[user_id].forbidden_intents,
                "security_level": self.users[user_id].security_level,
                "pub_key": self.users[user_id].public_key,
                "nicknames": self.users[user_id].nicknames}
        self.emitter.emit(Message("user.from_sock.result", data, message.context))

    # facebook messages
    def handle_fb_timestamp(self, message):
        timestamps = message.data.get("timestamps", {})
        for id in timestamps:
            name = timestamps[id]["name"]
            ts = timestamps[id]["timestamp"]
            if id in self.facebook_users.keys():
                current_user = self.facebook_users[id]
            else:
                current_user = User(id=id, name=name, emitter=self.emitter)
                self.facebook_users[id] = current_user
            current_user.name = name
            current_user.add_nicknames([name])
            current_user.user_type = "facebook chat"
            current_user.status = "online"
            current_user.last_timestamp = ts
            current_user.last_seen = time.asctime()
            if ts not in current_user.timestamp_history:
                current_user.timestamp_history.append(ts)
            current_user.save_user()

    def handle_fb_message_seen(self, message):
        name = message.data.get("friend_name")
        id = message.data.get("friend_id")
        ts = message.data.get("timestamp")
        if id in self.facebook_users.keys():
            current_user = self.facebook_users[id]
        else:
            current_user = User(id=id, name=name, emitter=self.emitter)
            self.facebook_users[id] = current_user

        current_user.name = name
        current_user.add_nicknames([name])
        current_user.user_type = "facebook chat"
        current_user.status = "online"
        current_user.last_timestamp = ts
        current_user.last_seen = time.asctime()
        if ts not in current_user.timestamp_history:
            current_user.timestamp_history.append(ts)
        current_user.save_user()

    def handle_fb_message_received(self, message):
        name = message.data.get("author_name")
        id = message.data.get("author_id")
        photo = message.data.get("photo")
        if id in self.facebook_users.keys():
            current_user = self.facebook_users[id]
        else:
            current_user = User(id=id, name=name, emitter=self.emitter)
            self.facebook_users[id] = current_user
        current_user.name = name
        current_user.add_nicknames([name])
        current_user.user_type = "facebook chat"
        current_user.status = "online"
        current_user.last_seen = time.asctime()
        current_user.photo = photo
        current_user.save_user()


    # server messages
    def handle_user_connect(self, message):
        ip = message.data.get("ip")
        sock = message.data.get("sock")
        pub_key = message.data.get("pub_key")
        user_name = message.context.get("user", "user")

        type = "sock_client"
        current_user = None
        if pub_key is None:
            pub_key = "yy"

        self.log.info("Comparing user key to default key")
        if pub_key == self.default_key:
            # default shared user
            current_user = self.users["0"]
        else:
            self.log.info("Comparing user key to keys in db")
            # id user by pub_key
            for user in self.users:
                user = self.users[user]
                if user.public_key == pub_key:
                    self.log.info("User found")
                    current_user = user.user_id

        if current_user is None:
            self.log.info("Registering new user")
            # new user
            # get new_id
            new_id = len(self.users.keys()) + 1
            self.log.info("Assigning new id: " + str(new_id))
            while str(new_id) in self.users.keys():
                self.log.info("assigned id already exists, increasing count")
                new_id += 1
            # save new user
            new_id = str(new_id)
            self.log.info("Creating user")
            new_user = User(id=new_id, emitter=self.emitter, name=user_name)
            new_user.public_key = pub_key
            self.users[new_id] = new_user
            current_user = new_id

        self.log.info("Setting user sock")
        self.user_list[current_user] = sock # set active sock
        # update user info
        self.log.info("Updating user info")
        current_user = self.users[current_user]
        current_user.current_sock = sock
        current_user.current_ip = ip
        current_user.add_new_ip(ip)
        current_user.last_timestamp = time.time()
        current_user.last_seen = time.asctime()
        current_user.timestamp_history.append(time.time())
        current_user.user_type = type
        current_user.status = "online"
        current_user.save_user()
        self.log.info("User updated: " + current_user.name + " " + current_user.current_ip + " " + str(current_user.last_timestamp))
        self.emitter.emit(Message("user.connected", {} ,message.context))

    def user_from_ip_sock(self, sock, ip):
        user_id = None
        for uid in self.user_list.keys():
            if self.user_list[uid] == sock:
                user_id = uid
                break
        if user_id is None:
            for user_id in self.users:
                if self.users[user_id].current_ip == ip:
                    self.user_list[user_id] = sock
                    break
        return user_id

    def handle_user_names(self, message):
        names = message.data.get("names")
        sock = message.data.get("sock")
        ip = message.data.get("ip")
        user_id = self.user_from_ip_sock(sock, ip)
        current_user = self.users[user_id]
        current_user.add_nicknames(names)
        current_user.current_sock = sock
        current_user.last_timestamp = time.time()
        current_user.last_seen = time.asctime()
        current_user.timestamp_history.append(time.time())
        current_user.save_user()

    def handle_user_request(self, message):
        sock = message.data.get("sock")
        ip = message.data.get("ip")
        user_id = self.user_from_ip_sock(sock, ip)

        current_user = self.users[user_id]
        current_user.last_timestamp = time.time()
        current_user.last_seen = time.asctime()
        current_user.timestamp_history.append(time.time())
        current_user.save_user()

    def handle_user_disconnect(self, message):
        sock = message.data.get("sock")
        ip = message.data.get("ip")
        user_id = self.user_from_ip_sock(sock, ip)
        current_user = self.users[user_id]
        current_user.last_timestamp = time.time()
        current_user.current_sock = None
        current_user.last_seen = time.asctime()
        current_user.timestamp_history.append(time.time())
        current_user.status = "offline"
        current_user.save_user()
        self.emitter.emit(Message("user.disconnected",{},message.context))

    def stop(self):
        # save all users
        for user in self.facebook_users:
            self.facebook_users[user].save_user()
        for user in self.users:
            self.users[user].save_user()


def create_skill():
    return UserSkill()
