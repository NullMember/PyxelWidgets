-- PyxelWidgets DAW protocol for REAPER (made by `pyxelwidgets daw install reaper`).
--
-- PyxelWidgets' DAW output (a virtual MIDI port called "PyxelWidgets DAW") talks
-- to this script: transport, track selection, the mixer of 8 tracks at a time,
-- the selected track's first plug-in's parameters as 8 macros, and names back.
-- In REAPER: Preferences > MIDI Devices, enable "PyxelWidgets DAW" as an input
-- (not for recording: right-click > Enable input for control messages only is
-- enough) and as an output, then run this script from the Actions list (or let
-- it start with REAPER: Actions > ... > "Set as startup action"). Start
-- PyxelWidgets first: REAPER only sees ports that exist when it looks (the
-- script asks it to look again every few seconds until it finds the port).

local P = __PROTOCOL__

local PORT = 'PyxelWidgets DAW'
local input, output                 -- REAPER's device indexes of the port
local last_seq = nil                -- the newest MIDI event already handled
local bank, fx, page = 0, 0, 0      -- the first strip's track, the macros' plug-in and page of 8
local sent = {}                     -- what the other side has: name -> value
local looked = 0

local function find(count, name_of)
  for i = 0, count - 1 do
    local ok, name = name_of(i, '')
    if ok and name:find(PORT, 1, true) then return i end
  end
end

local function connect()
  input = find(reaper.GetNumMIDIInputs(), reaper.GetMIDIInputName)
  output = find(reaper.GetNumMIDIOutputs(), reaper.GetMIDIOutputName)
  if input and output then
    sent = {}
    return true
  end
  -- Not there (yet): look again now and then (resets MIDI devices)
  if reaper.time_precise() - looked > 5 then
    looked = reaper.time_precise()
    reaper.Main_OnCommand(41175, 0)   -- Reset all MIDI devices
  end
  return false
end

local function send(bytes)
  reaper.SendMIDIMessageToHardware(output, string.char(table.unpack(bytes)))
end

-- Tracks, plug-ins and values

local function strip(n) return reaper.GetTrack(0, bank + n - 1) end
local function selected() return reaper.GetSelectedTrack(0, 0) end
local function fader_to_volume(v) return 10 ^ (reaper.SLIDER2DB(v * 1000) / 20) end
local function volume_to_fader(volume)
  if volume < 0.0000001 then return 0 end
  return math.max(0, math.min(1, reaper.DB2SLIDER(20 * math.log(volume, 10)) / 1000))
end
local function toggle(track, key, on)
  if track then reaper.SetMediaTrackInfo_Value(track, key, reaper.GetMediaTrackInfo_Value(track, key) ~= 0 and 0 or on) end
end
local function send_volume(track, index, v)
  if track and reaper.GetTrackNumSends(track, 0) > index then
    reaper.SetTrackSendInfo_Value(track, 0, index, 'D_VOL', fader_to_volume(v))
  end
end
local function plugin()
  local track = selected()
  if not track or reaper.TrackFX_GetCount(track) == 0 then return nil end
  fx = math.max(0, math.min(fx, reaper.TrackFX_GetCount(track) - 1))
  return track
end

-- Commands

local buttons = {
  ['Play'] = function() reaper.OnPlayButton() end,
  ['Stop'] = function() reaper.OnStopButton() end,
  ['Record'] = function() reaper.CSurf_OnRecord() end,
  ['Loop'] = function() reaper.GetSetRepeat(2) end,
  ['Metronome'] = function() reaper.Main_OnCommand(40364, 0) end,
  ['Rewind'] = function() reaper.CSurf_GoStart() end,
  ['Forward'] = function() reaper.CSurf_GoEnd() end,
  ['Undo'] = function() reaper.Undo_DoUndo2(0) end,
  ['Redo'] = function() reaper.Undo_DoRedo2(0) end,
  ['Tap Tempo'] = function() reaper.Main_OnCommand(1134, 0) end,
  ['Automation'] = function()
    local track = selected()
    if track then reaper.SetTrackAutomationMode(track, reaper.GetTrackAutomationMode(track) == 0 and 2 or 0) end
  end,
  ['Track Left'] = function() reaper.Main_OnCommand(40286, 0) end,
  ['Track Right'] = function() reaper.Main_OnCommand(40285, 0) end,
  ['Bank Left'] = function() bank = math.max(0, bank - 8) end,
  ['Bank Right'] = function() if bank + 8 < reaper.CountTracks(0) then bank = bank + 8 end end,
  ['Device Left'] = function() fx, page = math.max(0, fx - 1), 0 end,
  ['Device Right'] = function() fx, page = fx + 1, 0; plugin() end,
  ['Macro Page Left'] = function() page = math.max(0, page - 1) end,
  ['Macro Page Right'] = function()
    local track = plugin()
    if track and (page + 1) * 8 < reaper.TrackFX_GetNumParams(track, fx) then page = page + 1 end
  end,
  ['Device On'] = function()
    local track = plugin()
    if track then reaper.TrackFX_SetEnabled(track, fx, not reaper.TrackFX_GetEnabled(track, fx)) end
  end,
  ['Selected Mute'] = function() toggle(selected(), 'B_MUTE', 1) end,
  ['Selected Solo'] = function() toggle(selected(), 'I_SOLO', 2) end,
  ['Selected Arm'] = function() toggle(selected(), 'I_RECARM', 1) end,
}
for n = 1, 8 do
  buttons['Select ' .. n] = function() local track = strip(n) if track then reaper.SetOnlyTrackSelected(track) end end
  buttons['Mute ' .. n] = function() toggle(strip(n), 'B_MUTE', 1) end
  buttons['Solo ' .. n] = function() toggle(strip(n), 'I_SOLO', 2) end
  buttons['Arm ' .. n] = function() toggle(strip(n), 'I_RECARM', 1) end
end

local faders = {
  ['Selected Volume'] = function(v) local track = selected() if track then reaper.SetMediaTrackInfo_Value(track, 'D_VOL', fader_to_volume(v)) end end,
  ['Selected Pan'] = function(v) local track = selected() if track then reaper.SetMediaTrackInfo_Value(track, 'D_PAN', v * 2 - 1) end end,
  ['Selected Send A'] = function(v) send_volume(selected(), 0, v) end,
  ['Selected Send B'] = function(v) send_volume(selected(), 1, v) end,
  ['Master Volume'] = function(v) reaper.SetMediaTrackInfo_Value(reaper.GetMasterTrack(0), 'D_VOL', fader_to_volume(v)) end,
}
for n = 1, 8 do
  faders['Volume ' .. n] = function(v) local track = strip(n) if track then reaper.SetMediaTrackInfo_Value(track, 'D_VOL', fader_to_volume(v)) end end
  faders['Pan ' .. n] = function(v) local track = strip(n) if track then reaper.SetMediaTrackInfo_Value(track, 'D_PAN', v * 2 - 1) end end
  faders['Send A ' .. n] = function(v) send_volume(strip(n), 0, v) end
  faders['Send B ' .. n] = function(v) send_volume(strip(n), 1, v) end
  faders['Macro ' .. n] = function(v)
    local track = plugin()
    if track and page * 8 + n - 1 < reaper.TrackFX_GetNumParams(track, fx) then
      reaper.TrackFX_SetParamNormalized(track, fx, page * 8 + n - 1, v)
    end
  end
end

local note_names, control_names = {}, {}
for name, note in pairs(P.buttons) do note_names[note] = name end
for name, number in pairs(P.faders) do control_names[number] = name end

local function received(buf)
  local status, first, second = buf:byte(1, 3)
  if status == 0xF0 then
    local bytes = { buf:byte(1, -1) }
    if bytes[2] == P.sysex[1] and bytes[3] == P.sysex[2] and bytes[4] == P.sysex[3] and bytes[5] == P.refresh then sent = {} end
    return
  end
  if status == (0x90 | P.channel) and second > 0 then
    local action = buttons[note_names[first] or '']
    if action then action() end
  elseif status == (0xB0 | P.channel) then
    local action = faders[control_names[first] or '']
    if action then action(second / 127) end
  end
end

local function poll()
  local events, idx = {}, 0
  while true do
    local seq, buf, _, device = reaper.MIDI_GetRecentInputEvent(idx)
    if seq == 0 or (last_seq and seq <= last_seq) then break end
    if device == input then events[#events + 1] = buf end
    if idx == 0 then events.newest = seq end
    idx = idx + 1
  end
  if last_seq == nil then
    -- What came before the script started isn't for it
    last_seq = events.newest or 0
    return
  end
  if events.newest then last_seq = events.newest end
  for i = #events, 1, -1 do received(events[i]) end
end

-- What the other side shows: lights, values and names

local function state()
  local now = {}
  local play = reaper.GetPlayState()
  now['Play'] = play & 1 ~= 0 and 1 or 0
  now['Record'] = play & 4 ~= 0 and 1 or 0
  now['Loop'] = reaper.GetSetRepeat(-1)
  now['Metronome'] = reaper.GetToggleCommandState(40364) == 1 and 1 or 0
  for n = 1, 8 do
    local track = strip(n)
    local name = ''
    if track then
      _, name = reaper.GetTrackName(track)
      now['Select ' .. n] = reaper.IsTrackSelected(track) and 1 or 0
      now['Mute ' .. n] = reaper.GetMediaTrackInfo_Value(track, 'B_MUTE') ~= 0 and 1 or 0
      now['Solo ' .. n] = reaper.GetMediaTrackInfo_Value(track, 'I_SOLO') ~= 0 and 1 or 0
      now['Arm ' .. n] = reaper.GetMediaTrackInfo_Value(track, 'I_RECARM') ~= 0 and 1 or 0
      now['Volume ' .. n] = volume_to_fader(reaper.GetMediaTrackInfo_Value(track, 'D_VOL'))
      now['Pan ' .. n] = (reaper.GetMediaTrackInfo_Value(track, 'D_PAN') + 1) / 2
    else
      for _, key in ipairs({ 'Select ', 'Mute ', 'Solo ', 'Arm ', 'Volume ', 'Pan ' }) do now[key .. n] = 0 end
    end
    now['Track Name ' .. n] = name
  end
  local track = selected()
  now['Selected Name'] = ''
  if track then
    now['Selected Name'] = select(2, reaper.GetTrackName(track))
    now['Selected Mute'] = reaper.GetMediaTrackInfo_Value(track, 'B_MUTE') ~= 0 and 1 or 0
    now['Selected Solo'] = reaper.GetMediaTrackInfo_Value(track, 'I_SOLO') ~= 0 and 1 or 0
    now['Selected Arm'] = reaper.GetMediaTrackInfo_Value(track, 'I_RECARM') ~= 0 and 1 or 0
    now['Selected Volume'] = volume_to_fader(reaper.GetMediaTrackInfo_Value(track, 'D_VOL'))
    now['Selected Pan'] = (reaper.GetMediaTrackInfo_Value(track, 'D_PAN') + 1) / 2
    now['Automation'] = reaper.GetTrackAutomationMode(track) ~= 0 and 1 or 0
  end
  now['Master Volume'] = volume_to_fader(reaper.GetMediaTrackInfo_Value(reaper.GetMasterTrack(0), 'D_VOL'))
  local device = plugin()
  now['Device Name'] = ''
  for n = 1, 8 do now['Macro Name ' .. n], now['Macro Value ' .. n], now['Macro ' .. n] = '', '', 0 end
  if device then
    now['Device Name'] = select(2, reaper.TrackFX_GetFXName(device, fx, ''))
    now['Device On'] = reaper.TrackFX_GetEnabled(device, fx) and 1 or 0
    for n = 1, 8 do
      local parameter = page * 8 + n - 1
      if parameter < reaper.TrackFX_GetNumParams(device, fx) then
        now['Macro Name ' .. n] = select(2, reaper.TrackFX_GetParamName(device, fx, parameter, ''))
        now['Macro Value ' .. n] = select(2, reaper.TrackFX_GetFormattedParamValue(device, fx, parameter, ''))
        now['Macro ' .. n] = reaper.TrackFX_GetParamNormalized(device, fx, parameter)
      end
    end
  end
  now['DAW'] = 'REAPER'
  return now
end

local function text(name, value)
  local place = P.texts[name]
  local bytes = { 0xF0, P.sysex[1], P.sysex[2], P.sysex[3], place[1], place[2] }
  for i = 1, math.min(#value, 32) do
    local c = value:byte(i)
    bytes[#bytes + 1] = (c >= 32 and c < 127) and c or 63
  end
  bytes[#bytes + 1] = 0xF7
  send(bytes)
end

local function feedback()
  for name, value in pairs(state()) do
    if P.texts[name] then
      if sent[name] ~= value then text(name, value); sent[name] = value end
    elseif P.buttons[name] then
      local velocity = value ~= 0 and 127 or 0
      if sent[name] ~= velocity then send({ 0x90 | P.channel, P.buttons[name], velocity }); sent[name] = velocity end
    elseif P.faders[name] then
      local cc = math.floor(value * 127 + 0.5)
      if sent[name] ~= cc then send({ 0xB0 | P.channel, P.faders[name], cc }); sent[name] = cc end
    end
  end
end

local function loop()
  if input and output and reaper.GetMIDIInputName(input, '') then
    poll()
    feedback()
  else
    input, output = nil, nil
    connect()
  end
  reaper.defer(loop)
end

connect()
loop()
