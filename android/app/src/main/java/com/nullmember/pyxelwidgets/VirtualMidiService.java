package com.nullmember.pyxelwidgets;

import android.media.midi.MidiDeviceService;
import android.media.midi.MidiReceiver;

/**
 * The app's own MIDI device ("PyxelWidgets", res/xml/midi_device.xml): other apps
 * on the phone (synths, DAWs) see it as a MIDI device, like a virtual port on a
 * computer. A layout's virtual MIDI port uses it (MidiBridge.openVirtual).
 */
public class VirtualMidiService extends MidiDeviceService {
    private static volatile VirtualMidiService current;
    /** Gets what other apps send to the device's input port */
    static volatile MidiBridge.Listener listener;

    static VirtualMidiService instance() {
        return current;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        current = this;
    }

    @Override
    public void onDestroy() {
        current = null;
        super.onDestroy();
    }

    @Override
    public MidiReceiver[] onGetInputPortReceivers() {
        return new MidiReceiver[] {
            new MidiReceiver() {
                @Override
                public void onSend(byte[] data, int offset, int count, long timestamp) {
                    MidiBridge.Listener now = listener;
                    if (now != null) {
                        byte[] run = new byte[count];
                        System.arraycopy(data, offset, run, 0, count);
                        now.onMidi(run);
                    }
                }
            }
        };
    }
}
