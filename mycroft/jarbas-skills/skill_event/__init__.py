import sys
from os.path import dirname, abspath, basename

from mycroft.skills.media import MediaSkill
from mycroft.skills.scheduled_skills import ScheduledSkill, Timer
from adapt.intent import IntentBuilder
from mycroft.messagebus.message import Message

import time
from time import mktime

from os.path import dirname
from mycroft.util.log import getLogger

sys.path.append(abspath(dirname(__file__)))

logger = getLogger(abspath(__file__).split('/')[-2])
__author__ = 'forslund'


class EventSkill(ScheduledSkill):
    def __init__(self):
        super(EventSkill, self).__init__('EventSkill')
        self.waiting = True

    def initialize(self):
        self.times = []
        self.emitter.on("intent_to_skill_response", self.receive_skill_id)
        self.config_events = self.config

        for e in self.config_events:
            self.register_vocabulary(e, 'EventKeyword')
            logger.debug(e)
            if 'time' in self.config_events[e]:
                self.add_event(e)

        intent = IntentBuilder('EventIntent')\
                 .require('EventKeyword')\
                 .build()
        self.register_intent(intent, self.handle_run_event)

        self.register_vocabulary('cancel events', 'CancelEventsKeyword')
        intent = IntentBuilder('CancelEventsIntent')\
                 .require('CancelEventsKeyword')\
                 .build()
        self.register_intent(intent, self.handle_cancel_events)


        self.emitter.on('recognizer_loop:audio_output_end',
                        self.ready_to_continue)
        self.schedule()
    
    def add_event(self, event):
        now = self.get_utc_time()
        conf_times = self.config_events[event]['time']
        if not isinstance(conf_times, list):
            conf_times = [conf_times]
        for t in conf_times:
            time = self.get_utc_time(t)
            if time <= now:
                time += self.SECONDS_PER_DAY
            self.times.append((time, event))
            self.times = sorted(self.times)
            self.times.reverse()

    def ready_to_continue(self, message):
        self.waiting = False

    def repeat(self, event):
        self.add_event(event)

    def execute_event(self, event):
        for a in self.config_events[event]['actions']:
            self.waiting = True
            for intent_name in a:
                skill_id = self.intent_to_skill_id(intent_name)
                if skill_id == 0:
                    self.log.error("Could not identify source skill for " + intent_name)
                    continue
                intent_message = str(skill_id) + ":" + intent_name
                self.emitter.emit(Message(intent_message, a[intent_name]))
            timeout = 0
            while self.waiting and timeout < 10:
                time.sleep(1)

    def notify(self, timestamp, event):

        self.execute_event(event)
        self.repeat(event)
        self.schedule()

    def get_times(self):
        if len(self.times) > 0:
            return [self.times.pop()]
        else:
            logger.debug('No further events')
            return []

    def schedule(self):
        times = sorted(self.get_times())

        if len(times) > 0:
            self.cancel()
            t, event = times[0]
            now = self.get_utc_time()
            delay = max(float(t) - now, 1)
            logger.debug('starting event in ' + str(delay))
            self.timer = Timer(delay, self.notify, [t, event])
            self.start()

    def handle_run_event(self, message):
        e = message.data.get('EventKeyword')
        self.execute_event(e)

    def handle_cancel_events(self, message):
        self.cancel()
        self.speak('Cancelling all events')

    def intent_to_skill_id(self, intent_name):
        self.waiting = True
        self.id = 0
        self.emitter.emit(Message("intent_to_skill_request", {"intent_name": intent_name}))
        start_time = time.time()
        t = 0
        while self.waiting and t < 20:
            t = time.time() - start_time
        self.waiting = False
        return self.id

    def receive_skill_id(self, message):
        self.id = message.data["skill_id"]
        self.waiting = False


def create_skill():
    return EventSkill()