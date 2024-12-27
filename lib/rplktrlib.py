import micropython
import supervisor
from winterbloom_smolmidi import NOTE_ON, NOTE_OFF, CC
from winterbloom_sol.helpers import note_to_volts_per_octave, offset_for_pitch_bend
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
        self.voct = [None, None]
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
        
        micropython.heap_lock()
        # triggers will be turned on inside `note_on()`
        self.triggers[0] = False
        self.triggers[1] = False

        if msg:
            if msg.type == NOTE_ON:
                if msg.channel != self.mode:
                    micropython.heap_unlock()
                    self.reset(msg.channel)
                    state.notes.clear()
                    micropython.heap_lock()

                note = msg.data[0]
                velo = msg.data[1]

                self.is_accent = velo >= ACCENT_VOLUME
                if self.mode == UNISON:
                    notes = state.notes
                    if len(notes) > 1:
                        glide = state._cc[64] >= 64 or state._cc[65] >= 64
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
                        glide = state._cc[64] >= 64 or state._cc[65] >= 64
                        self.legato(note, notes[-1], RED, glide)
                        self.legato(note, notes[-1], BLUE, glide)
                    else:
                        self.note_off(note)
                elif self.mode == DUOPHONIC:
                    self.note_off(note)
            
            elif msg.type == CC:
                micropython.heap_unlock()
                if msg.data[0] == 120 or msg.data[0] == 123:
                    self.reset(self.mode)
                    state.notes.clear()
                # elif msg.data[0] == 126:
                #     self.reset(UNISON)
                # elif msg.data[0] == 127:
                #     self.reset(DUOPHONIC)
                micropython.heap_lock()

        if (note_red := self.voct[RED]):
            if note_red.__class__ is SlewLimiter:
                note_red = note_red.output
            outputs._cv_a.voltage = (
                note_to_volts_per_octave(note_red)
                + offset_for_pitch_bend(state.pitch_bend, range=12)
            )
            if self.triggers[RED]:
                outputs._gate_1_retrigger.retrigger()
        else:
            outputs.gate_1 = False

        if (note_blue := self.voct[BLUE]):
            if note_blue.__class__ is SlewLimiter:
                note_blue = note_blue.output
            outputs._cv_b.voltage = (
                note_to_volts_per_octave(note_blue)
                + offset_for_pitch_bend(state.pitch_bend, range=12)
            )
            if self.triggers[BLUE]:
                outputs._gate_2_retrigger.retrigger()
        else:
            outputs.gate_2 = False

        if any(self.triggers):
            outputs._gate_3_retrigger.retrigger()
            outputs._gate_4_retrigger.retrigger()
        elif note_red or note_blue:
            outputs.gate_3 = True
            outputs.gate_4 = True
        else:
            outputs.gate_3 = False
            outputs.gate_4 = False

        # rez
        outputs.cv_c = -5.0 + state.cc(1) * 10.0
        # cutoff
        bump = state.pressure/4 + (0.25 if self.is_accent else 0.0)
        outputs.cv_d = -5.0 + min(state.cc(4) + bump, 1.0) * 10.0
        micropython.heap_unlock()

        now = supervisor.ticks_ms()
        if now - last_out > 1000:
            last_out = now
            print(f"{counter} callback calls")
            counter = 0

    @micropython.native
    def note_off(self, note):
        micropython.heap_lock()
        for n in VOICES:
            assign = self.voct[n]
            if (
                assign == note
                or (assign.__class__ is SlewLimiter and assign.target == note)
            ):
                self.voct[n] = None
                self.triggers[n] = False
                self.gates[n] = False
        micropython.heap_unlock()

    @micropython.native
    def note_on(self, note, assignment_index):
        micropython.heap_lock()
        self.voct[assignment_index] = note
        self.gates[assignment_index] = True
        self.triggers[assignment_index] = True
        self.last_assignment_index = assignment_index
        micropython.heap_unlock()

    @micropython.native
    def legato(self, from_note, to_note, assignment_index, glide=False):
        micropython.heap_lock()
        if glide:
            slew = self.slews[assignment_index]
            slew.last = from_note
            slew.target = to_note
            to_note = slew

        self.voct[assignment_index] = to_note
        self.last_assignment_index = assignment_index
        self.gates[assignment_index] = True
        micropython.heap_unlock()

    @micropython.native
    def select_voice(self):
        micropython.heap_lock()
        v = RVOICES if self.reverse else VOICES
        try:
            for n in v:
                if self.voct[n] is None:
                    return n

            # No free voice, assign to the oldest one.
            if self.last_assignment_index == RED:
                return BLUE
            else:
                return RED
        finally:
            micropython.heap_unlock()
