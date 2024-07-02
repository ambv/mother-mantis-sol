import gc
import time

import micropython
from winterbloom_smolmidi import NOTE_ON, NOTE_OFF, CC
from winterbloom_sol import helpers, SlewLimiter


RED = micropython.const(0)
BLUE = micropython.const(1)
VOICES = micropython.const((RED, BLUE))
RVOICES = micropython.const((BLUE, RED))
UNISON = micropython.const(0)
DUOPHONIC = micropython.const(1)
ACCENT_VOLUME = micropython.const(92)


counter = 0
last_out = 0

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
        self.is_accent = False

    @micropython.native
    def update(self, state, msg, outputs):
        global counter, last_out

        counter += 1
        self.triggers = [False, False]

        if msg:
            if msg.type == NOTE_ON:
                gc.disable()
                if msg.channel != self.mode:
                    self.reset(msg.channel)

                note = msg.data[0]
                velo = msg.data[1]

                self.is_accent = velo >= ACCENT_VOLUME
                if self.mode == UNISON:
                    notes = state.notes
                    if len(notes) > 1:
                        glide = state.cc(64) >= 0.5 or state.cc(65) >= 0.5
                        self.legato(notes[-2], note, RED, glide)
                        self.legato(notes[-2], note, BLUE, glide)
                    else:
                        self.note_on(note, RED)
                        self.note_on(note, BLUE)
                elif self.mode == DUOPHONIC:
                    assignment_index = self.select_voice()
                    self.note_on(note, assignment_index)
                    self.reverse = not self.reverse

            elif msg.type == NOTE_OFF:
                note = msg.data[0]
                if self.mode == UNISON:
                    notes = state.notes
                    if notes:
                        glide = state.cc(64) >= 0.5 or state.cc(65) >= 0.5
                        self.legato(note, notes[-1], RED, glide)
                        self.legato(note, notes[-1], BLUE, glide)
                    else:
                        self.note_off(note)
                elif self.mode == DUOPHONIC:
                    self.note_off(note)
            
            elif msg.type == CC:
                if msg.data[0] == 120 or msg.data[0] == 123:
                    self.reset(self.mode)
                # elif msg.data[0] == 126:
                #     self.reset(UNISON)
                # elif msg.data[0] == 127:
                #     self.reset(DUOPHONIC)

        if (note_red := self.assignments[RED][0]):
            if note_red.__class__ is SlewLimiter:
                note_red = note_red.output
            outputs.cv_a = helpers.voct(note_red, state.pitch_bend, range=12)
            if self.triggers[RED]:
                outputs.retrigger_gate_1()
        else:
            outputs.gate_1 = False
        if (note_blue := self.assignments[BLUE][0]):
            if note_blue.__class__ is SlewLimiter:
                note_blue = note_blue.output
            outputs.cv_b = helpers.voct(note_blue, state.pitch_bend, range=12)
            if self.triggers[BLUE]:
                outputs.retrigger_gate_2()
        else:
            outputs.gate_2 = False

        # rez
        outputs.cv_c = -5.0 + state.cc(1) * 10.0
        # cutoff
        bump = state.pressure/4 + (0.25 if self.is_accent else 0.0)
        outputs.cv_d = -5.0 + min(state.cc(4) + bump, 1.0) * 10.0
        gc.enable()
        if time.monotonic_ns() - last_out > 1000000000:
            last_out = time.monotonic_ns()
            print(f"{counter} callback calls")
            counter = 0

    @micropython.native
    def note_off(self, note):
        for n in VOICES:
            assign = self.assignments[n][0]
            if (
                assign == note
                or (assign.__class__ is SlewLimiter and assign.target == note)
            ):
                self.assignments[n][0] = None
                self.triggers[n] = False
                self.gates[n] = False

    @micropython.native
    def note_on(self, note, assignment_index):
        now = time.monotonic_ns()

        self.assignments[assignment_index][0] = note
        self.assignments[assignment_index][1] = now
        self.gates[assignment_index] = True
        self.triggers[assignment_index] = True

    @micropython.native
    def legato(self, from_note, to_note, assignment_index, glide=False):
        now = time.monotonic_ns()

        if glide:
            slew = self.slews[assignment_index]
            slew.last = from_note
            slew.target = to_note
            to_note = slew

        self.assignments[assignment_index][0] = to_note
        self.assignments[assignment_index][1] = now
        self.gates[assignment_index] = True

    @micropython.native
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
