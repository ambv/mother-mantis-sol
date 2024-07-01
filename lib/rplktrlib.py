import time

import winterbloom_smolmidi as smolmidi
from winterbloom_sol import helpers, SlewLimiter


RED = 0
BLUE = 1
VOICES = RED, BLUE
RVOICES = BLUE, RED
UNISON = 0
DUOPHONIC = 1


class RedBlue:
    def __init__(self):
        self.reset(UNISON)
    
    def reset(self, mode):
        self.assignments = [[None, 0], [None, 0]]
        self.gates = [False, False]
        self.triggers = [False, False]
        self.mode = mode
        self.reverse = False
        self.slews =[SlewLimiter(0.1), SlewLimiter(0.1)]

    def update(self, last, state, outputs):
        # clear all triggers from the last update,
        # so we can properly re-trigger them if
        # new notes have shown up.
        self.triggers = [False, False]

        msg = state.message
        if not msg:
            return
        
        if msg.type == smolmidi.NOTE_ON:
            if msg.channel != self.mode:
                self.reset(msg.channel)

            note = msg.data[0]                
            if self.mode == UNISON:
                latest_note = last.latest_note
                if latest_note is None:
                    self.note_on(note, RED)
                    self.note_on(note, BLUE)
                else:
                    self.legato(latest_note, note, RED)
                    self.legato(latest_note, note, BLUE)
            elif self.mode == DUOPHONIC:
                assignment_index = self.select_voice()
                self.note_on(note, assignment_index)
                self.reverse = not self.reverse

        elif msg.type == smolmidi.NOTE_OFF:
            note = msg.data[0]
            if self.mode == UNISON:
                latest_note = state.latest_note
                if latest_note is None:
                    self.note_off(note)
                else:
                    self.legato(note, latest_note, RED)
                    self.legato(note, latest_note, BLUE)

        if (note_red := self.assignments[RED][0]):
            outputs.cv_a = helpers.voct(note_red, state.pitch_bend, range=12)
            if self.triggers[RED]:
                outputs.retrigger_gate_1()
        else:
            outputs.gate_1 = False
        if (note_blue := self.assignments[BLUE][0]):
            outputs.cv_b = helpers.voct(note_blue, state.pitch_bend, range=12)
            if self.triggers[BLUE]:
                outputs.retrigger_gate_2()
        else:
            outputs.gate_2 = False

        outputs.cv_c = -5.0 + state.cc(1) * 10.0
        outputs.cv_d = -5.0 + state.cc(4) * 10.0

    def note_off(self, note):
        for n in VOICES:
            if self.assignments[n][0] == note:
                self.assignments[n][0] = None
                self.triggers[n] = False
                self.gates[n] = False

    def note_on(self, note, assignment_index):
        now = time.monotonic_ns()

        self.assignments[assignment_index][0] = note
        self.assignments[assignment_index][1] = now
        self.gates[assignment_index] = True
        self.triggers[assignment_index] = True

    def legato(self, from_note, to_note, assignment_index):
        now = time.monotonic_ns()

        self.assignments[assignment_index][0] = to_note
        self.assignments[assignment_index][1] = now
        self.gates[assignment_index] = True

    def select_voice(self):
        oldest_time = 0
        oldest_index = 0

        v = RVOICES if self.reverse else VOICES
        for n in v:
            if self.assignments[n][0] is None:
                assignment_index = n
                break
            if oldest_time == 0 or self.assignments[n][1] < oldest_time:
                oldest_time = self.assignments[n][1]
                oldest_index = n
        else:
                # No free voice, assign to the oldest one.
            assignment_index = oldest_index
        return assignment_index
