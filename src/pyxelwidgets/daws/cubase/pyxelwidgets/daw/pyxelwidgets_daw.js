// PyxelWidgets DAW protocol for Cubase and Nuendo 12+ (made by `pyxelwidgets daw install cubase`).
//
// PyxelWidgets' DAW output (a virtual MIDI port "PyxelWidgets DAW") talks to this
// MIDI Remote script: transport, track selection, the mixer of 8 tracks at a time
// and the focused quick controls as 8 macros, with names back. Start PyxelWidgets,
// then in Cubase: Studio > MIDI Remote Manager > Reload Scripts. It finds the port
// by its name. Clips and scenes don't exist in Cubase; those commands do nothing.

var midiremote_api = require('midiremote_api_v1')

var P = __PROTOCOL__

var deviceDriver = midiremote_api.makeDeviceDriver('PyxelWidgets', 'DAW', 'PyxelWidgets')
var midiInput = deviceDriver.mPorts.makeMidiInput()
var midiOutput = deviceDriver.mPorts.makeMidiOutput()
deviceDriver.makeDetectionUnit().detectPortPair(midiInput, midiOutput)
    .expectInputNameEquals('PyxelWidgets DAW')
    .expectOutputNameEquals('PyxelWidgets DAW')

var surface = deviceDriver.mSurface
var page = deviceDriver.mMapping.makePage('PyxelWidgets')
var host = page.mHostAccess

// Surface elements: one per command, in a grid (the layout only matters in Cubase's MIDI Remote view)
var placed = 0
function place() {
    var spot = { x: (placed % 16) * 2, y: Math.floor(placed / 16) * 2 }
    placed++
    return spot
}
function button(name) {
    var spot = place()
    var element = surface.makeButton(spot.x, spot.y, 2, 2)
    element.mSurfaceValue.mMidiBinding.setInputPort(midiInput).setOutputPort(midiOutput).bindToNote(P.channel, P.buttons[name])
    return element.mSurfaceValue
}
function fader(name) {
    var spot = place()
    var element = surface.makeKnob(spot.x, spot.y, 2, 2)
    element.mSurfaceValue.mMidiBinding.setInputPort(midiInput).setOutputPort(midiOutput).bindToControlChange(P.channel, P.faders[name])
    return element.mSurfaceValue
}

// Texts back to PyxelWidgets, kept so a refresh can send them again
var texts = {}
function sendText(activeDevice, name, value) {
    value = String(value || '')
    texts[name] = value
    var place = P.texts[name]
    var data = [0xF0].concat(P.sysex, [place[0], place[1]])
    for (var i = 0; i < value.length && i < 32; i++) {
        var c = value.charCodeAt(i)
        data.push(c >= 32 && c < 127 ? c : 63)
    }
    data.push(0xF7)
    midiOutput.sendMidi(activeDevice, data)
}
midiInput.mOnSysex = function (activeDevice, data) {
    if (data.length >= 5 && data[1] == P.sysex[0] && data[2] == P.sysex[1] && data[3] == P.sysex[2] && data[4] == P.refresh) {
        for (var name in texts) sendText(activeDevice, name, texts[name])
    }
}
deviceDriver.mOnActivate = function (activeDevice) {
    sendText(activeDevice, 'DAW', 'Cubase')
}

// Transport
var transport = host.mTransport.mValue
page.makeValueBinding(button('Play'), transport.mStart).setTypeToggle()
page.makeValueBinding(button('Stop'), transport.mStop)
page.makeValueBinding(button('Record'), transport.mRecord).setTypeToggle()
page.makeValueBinding(button('Loop'), transport.mCycleActive).setTypeToggle()
page.makeValueBinding(button('Metronome'), transport.mMetronomeActive).setTypeToggle()
page.makeValueBinding(button('Rewind'), transport.mRewind)
page.makeValueBinding(button('Forward'), transport.mForward)
page.makeCommandBinding(button('Undo'), 'Edit', 'Undo')
page.makeCommandBinding(button('Redo'), 'Edit', 'Redo')

// The selected track
var selected = host.mTrackSelection.mMixerChannel
page.makeActionBinding(button('Track Left'), host.mTrackSelection.mAction.mPrevTrack)
page.makeActionBinding(button('Track Right'), host.mTrackSelection.mAction.mNextTrack)
page.makeValueBinding(button('Selected Mute'), selected.mValue.mMute).setTypeToggle()
page.makeValueBinding(button('Selected Solo'), selected.mValue.mSolo).setTypeToggle()
page.makeValueBinding(button('Selected Arm'), selected.mValue.mRecordEnable).setTypeToggle()
page.makeValueBinding(button('Automation'), selected.mValue.mAutomationWrite).setTypeToggle()
page.makeValueBinding(fader('Selected Volume'), selected.mValue.mVolume)
page.makeValueBinding(fader('Selected Pan'), selected.mValue.mPan)
page.makeValueBinding(fader('Selected Send A'), selected.mSends.getByIndex(0).mLevel)
page.makeValueBinding(fader('Selected Send B'), selected.mSends.getByIndex(1).mLevel)
selected.mOnTitleChange = function (activeDevice, activeMapping, title) {
    sendText(activeDevice, 'Selected Name', title)
}

// 8 strips of the mixer
var zone = host.mMixConsole.makeMixerBankZone().excludeInputChannels().excludeOutputChannels()
page.makeActionBinding(button('Bank Left'), zone.mAction.mPrevBank)
page.makeActionBinding(button('Bank Right'), zone.mAction.mNextBank)
for (var n = 1; n <= 8; n++) {
    var channel = zone.makeMixerBankChannel()
    page.makeValueBinding(button('Select ' + n), channel.mValue.mSelected).setTypeToggle()
    page.makeValueBinding(button('Mute ' + n), channel.mValue.mMute).setTypeToggle()
    page.makeValueBinding(button('Solo ' + n), channel.mValue.mSolo).setTypeToggle()
    page.makeValueBinding(button('Arm ' + n), channel.mValue.mRecordEnable).setTypeToggle()
    page.makeValueBinding(fader('Volume ' + n), channel.mValue.mVolume)
    page.makeValueBinding(fader('Pan ' + n), channel.mValue.mPan)
    page.makeValueBinding(fader('Send A ' + n), channel.mSends.getByIndex(0).mLevel)
    page.makeValueBinding(fader('Send B ' + n), channel.mSends.getByIndex(1).mLevel)
    channel.mOnTitleChange = (function (name) {
        return function (activeDevice, activeMapping, title) { sendText(activeDevice, name, title) }
    })('Track Name ' + n)
}

// The master
var outputs = host.mMixConsole.makeMixerBankZone().includeOutputChannels()
page.makeValueBinding(fader('Master Volume'), outputs.makeMixerBankChannel().mValue.mVolume)

// The focused quick controls: the selected track's (or plug-in's) 8 macros, with names and values
for (var m = 1; m <= 8; m++) {
    var macro = fader('Macro ' + m)
    page.makeValueBinding(macro, host.mFocusedQuickControls.getByIndex(m - 1))
    macro.mOnTitleChange = (function (index) {
        return function (activeDevice, objectTitle, valueTitle) {
            sendText(activeDevice, 'Macro Name ' + index, valueTitle)
            if (index == 1) sendText(activeDevice, 'Device Name', objectTitle)
        }
    })(m)
    macro.mOnDisplayValueChange = (function (index) {
        return function (activeDevice, value, units) { sendText(activeDevice, 'Macro Value ' + index, units ? value + ' ' + units : value) }
    })(m)
}
