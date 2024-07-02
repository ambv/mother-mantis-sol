# redblue for Sol

This is the controller software installed on
[Mother Mantis](https://modulargrid.net/e/racks/view/2502933).
It provides a fat duophonic instrument with deep expression control.

It is roughly based on
[aiotone.redblue](https://github.com/ambv/aiotone/blob/master/aiotone/redblue.py).

## Usage
The mod wheel (CC1) set Resonance for both Mothers.

The foot pedal (CC4) sets Cutoff for both Mothers.

Send MIDI notes to Channel 1 for UNISON operation. In this mode both
Mothers and their subs sound at the same time. The stereo field and
detune makes this a very fat bass. In this mode legato playback doesn't
retrigger the envelopes.

Send MIDI notes to Channel 2 for DUOPHONIC operation. In this mode notes
alternate between the Red and the Blue Mother. If you hold a note, only
the other Mother will be used. If you hold two notes and press another,
the oldest note will be replaced. This allows you to play two-note chords
and stereo arps.

Velocity over 92 causes an "accent", which is a 25% cutoff bump.
Aftertouch also causes up to a 25% cutoff bump. While poly AT is read,
it's treated as channel AT.

## TODO

Maybe CV C and CV D should output  red cutoff and blue cutoff
respectively, to allow for polyphonic aftertouch?  In this case
resonance CV would have to be encoded with pulses and decoded by Crow.

## Winterbloom Sol software
This is based on Sol 2022.10.17 with the following changes:
- neopixel.mpy is replaced with
  [the latest release](https://github.com/adafruit/Adafruit_CircuitPython_NeoPixel/releases)
  for Circuit Python 9 (Mother Mantis runs on 9.0.5)
- SlewLimiter has a writable `last` property, which enables you to use
  it only selectively
- the LED pulses on quarter notes like Ableton Live's click track