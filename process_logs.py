import collections
import enum
import os
import re


_GrassAddress = collections.namedtuple("GrassAddress", [
    "scene_name",
    "grassName",
    "grass_x",
    "grass_y",
    "grass_z",
])


class GrassAddress(_GrassAddress):
    def __str__(self):
        return (
            f"{self.scene_name}/{self.grassName} "
            f"({self.grass_x}, {self.grass_y}, {self.grass_z})")


class GrassState(enum.Enum):
    UNCUT = 0
    SHOULD_BE_CUT = 1
    CUT = 2

    @classmethod
    def from_event_kind(cls, kind):
        if kind == "discovered":
            return cls.UNCUT
        elif kind == "pseudoCut":
            return cls.SHOULD_BE_CUT
        elif kind == "cut":
            return cls.CUT

        raise ValueError(f"Unrecognized kind {kind}")


class Event:
    EVENT_RE = re.compile(
        r"^.*!grassHuntEvent (?P<kind>[^ ]+) +"
        r"(?P<scene_name>.+?)\/(?P<grassName>.+) \("
        r"(?P<grass_x>-?[0-9]+(?:\.[0-9]*)?), "
        r"(?P<grass_y>-?[0-9]+(?:\.[0-9]*)?), "
        r"(?P<grass_z>-?[0-9]+(?:\.[0-9]*)?)\)\s*$")

    def __init__(self, kind, scene_name, grassName, grass_x, grass_y, grass_z):
        self.kind = kind
        self.address = GrassAddress(
            scene_name=scene_name,
            grassName=grassName,
            grass_x=grass_x,
            grass_y=grass_y,
            grass_z=grass_z)

    @classmethod
    def from_log_line(cls, log_line):
        match = cls.EVENT_RE.match(log_line)
        if match:
            return Event(**match.groupdict())
        else:
            return None


class GrassStateAccumulator:
    def __init__(self):
        self.grass_state_by_address = {}

        # It's possible for us to see grass cut without it ever being
        # discovered. This will mean that there's a log file missing from what
        # the player uploaded, so we'll want to flag this.
        self.discovered_grass_by_address = set()

    def has_data(self):
        return bool(self.grass_state_by_address)

    @staticmethod
    def get_new_state(old_state, event_kind):
        maybe_new_state = GrassState.from_event_kind(event_kind)
        if old_state is None or old_state.value < maybe_new_state.value:
            return maybe_new_state
        else:
            return old_state

    def take_event(self, event):
        if event.kind == "discovered":
            self.discovered_grass_by_address.add(event.address)

        old_state = self.grass_state_by_address.get(event.address)

        new_state = self.get_new_state(old_state, event.kind)
        self.grass_state_by_address[event.address] = new_state

    def sums_by(self, key_name, key_func):
        sums = {}
        for k, state in self.grass_state_by_address.items():
            sums_for_k = sums.setdefault(key_func(k), {
                key_name: key_func(k),
                "grassSeen": 0,
                "grassShouldBeCut": 0,
                "grassCut": 0,
                "missingDiscoveries": 0,
            })

            sums_for_k["grassSeen"] += 1

            if state == GrassState.SHOULD_BE_CUT:
                sums_for_k["grassShouldBeCut"] += 1
            elif state == GrassState.CUT:
                sums_for_k["grassCut"] += 1

            if k not in self.discovered_grass_by_address:
                sums_for_k["missingDiscoveries"] += 1

        return list(sums.values())


def process_logs(root):
    # This is how we'll compute all but the player-specific stats
    global_accumulator = GrassStateAccumulator()

    # And this is how we'll accumulate the player-specific stats
    player_accumulators = {}

    for player_name in os.listdir(root):
        player_accumulator = GrassStateAccumulator()
        player_accumulators[player_name] = player_accumulator

        for file_name in os.listdir(os.path.join(root, player_name)):
            with open(os.path.join(root, player_name, file_name), "r") as f:
                for log_line in f:
                    event = Event.from_log_line(log_line)
                    if event:
                        print("event kind", event.kind, event.address)
                        global_accumulator.take_event(event)
                        player_accumulator.take_event(event)

    return {
        "players": [
            {
                "name": player_name,
                **accumulator.sums_by(None, lambda _: None)[0]
            }
            for player_name, accumulator in player_accumulators.items()
            if accumulator.has_data()
        ],
        "scenes": global_accumulator.sums_by("name", lambda k: k.scene_name),
        "grass": [
            {
                "address": str(k),
                "state": state.name,
            }
            for k, state in global_accumulator.grass_state_by_address.items()
        ]
    }