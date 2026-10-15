package com.nullmember.pyxelwidgets;

import android.content.Context;
import android.media.midi.MidiDevice;
import android.media.midi.MidiDeviceInfo;
import android.media.midi.MidiInputPort;
import android.media.midi.MidiManager;
import android.media.midi.MidiOutputPort;
import android.media.midi.MidiReceiver;
import android.os.Bundle;
import android.os.Handler;
import android.os.HandlerThread;
import android.util.Log;

import java.io.Closeable;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * Android's MIDI service for Python (pyxelwidgets.devices.android_midi): port names,
 * opening ports by name, sending, and receiving through a Listener Python implements.
 *
 * A port is named after its device ("Launchpad Mini MK3") plus the port's own name
 * when Android has one, or its number when the device has several. Inputs are the
 * ports we receive from (the device's output ports), outputs the ones we send to.
 */
public final class MidiBridge {
    private static final String TAG = "PyxelWidgetsMIDI";
    private static final long OPEN_TIMEOUT = 5;

    /** Gets each run of bytes received (a whole message or several, or part of a sysex). */
    public interface Listener {
        void onMidi(byte[] data);
    }

    private static MidiManager manager;
    private static Handler handler;
    private static String ownPackage;
    /** Open devices by id, shared by their ports, with how many ports use them */
    private static final Map<Integer, MidiDevice> devices = new HashMap<>();
    private static final Map<Integer, Integer> users = new HashMap<>();

    private MidiBridge() {}

    public static synchronized void init(Context context) {
        if (manager != null) {
            return;
        }
        manager = (MidiManager) context.getSystemService(Context.MIDI_SERVICE);
        ownPackage = context.getPackageName();
        HandlerThread thread = new HandlerThread("PyxelWidgetsMIDI");
        thread.start();
        handler = new Handler(thread.getLooper());
    }

    public static boolean available() {
        return manager != null;
    }

    private static final class Entry {
        final String name;
        final MidiDeviceInfo info;
        final int port;

        Entry(String name, MidiDeviceInfo info, int port) {
            this.name = name;
            this.info = info;
            this.port = port;
        }
    }

    static String deviceName(MidiDeviceInfo info) {
        Bundle properties = info.getProperties();
        String name = properties.getString(MidiDeviceInfo.PROPERTY_NAME);
        if (name == null || name.isEmpty()) {
            name = properties.getString(MidiDeviceInfo.PROPERTY_PRODUCT);
        }
        if (name == null || name.isEmpty()) {
            name = "MIDI device " + info.getId();
        }
        return name.trim();
    }

    /** The app's own device (VirtualMidiService): not listed, it would loop back */
    @SuppressWarnings("deprecation")
    private static boolean own(MidiDeviceInfo info) {
        // MidiDeviceInfo.PROPERTY_SERVICE_INFO is hidden from the SDK; its key is "service_info"
        Object service = info.getProperties().get("service_info");
        if (service instanceof android.content.pm.ServiceInfo) {
            return ownPackage.equals(((android.content.pm.ServiceInfo) service).packageName);
        }
        return info.getType() == MidiDeviceInfo.TYPE_VIRTUAL
                && "PyxelWidgets".equals(info.getProperties().getString(MidiDeviceInfo.PROPERTY_PRODUCT));
    }

    @SuppressWarnings("deprecation")
    private static synchronized List<Entry> entries(int type) {
        List<Entry> found = new ArrayList<>();
        if (manager == null) {
            return found;
        }
        Map<String, Integer> seen = new HashMap<>();
        for (MidiDeviceInfo info : manager.getDevices()) {
            if (own(info)) {
                continue;
            }
            String device = deviceName(info);
            int count = type == MidiDeviceInfo.PortInfo.TYPE_OUTPUT ? info.getOutputPortCount() : info.getInputPortCount();
            for (MidiDeviceInfo.PortInfo port : info.getPorts()) {
                if (port.getType() != type) {
                    continue;
                }
                String portName = port.getName() == null ? "" : port.getName().trim();
                String name = device;
                if (!portName.isEmpty() && !device.contains(portName)) {
                    name = device + " " + portName;
                } else if (count > 1) {
                    name = device + " " + (port.getPortNumber() + 1);
                }
                // Two of the same device
                int times = seen.merge(name, 1, Integer::sum);
                if (times > 1) {
                    name = name + " #" + times;
                }
                found.add(new Entry(name, info, port.getPortNumber()));
            }
        }
        return found;
    }

    private static String[] names(List<Entry> entries) {
        String[] names = new String[entries.size()];
        for (int i = 0; i < names.length; i++) {
            names[i] = entries.get(i).name;
        }
        return names;
    }

    /** Ports we can receive from. */
    public static String[] inputs() {
        return names(entries(MidiDeviceInfo.PortInfo.TYPE_OUTPUT));
    }

    /** Ports we can send to. */
    public static String[] outputs() {
        return names(entries(MidiDeviceInfo.PortInfo.TYPE_INPUT));
    }

    /** Every device's name and its ports as Android names them, for the log and bug reports. */
    @SuppressWarnings("deprecation")
    public static String describe() {
        StringBuilder text = new StringBuilder();
        if (manager == null) {
            return "No MIDI service";
        }
        for (MidiDeviceInfo info : manager.getDevices()) {
            Bundle properties = info.getProperties();
            text.append(info.getId()).append(": ").append(deviceName(info))
                    .append(" (type ").append(info.getType())
                    .append(", manufacturer ").append(properties.getString(MidiDeviceInfo.PROPERTY_MANUFACTURER))
                    .append(", product ").append(properties.getString(MidiDeviceInfo.PROPERTY_PRODUCT))
                    .append(")\n");
            for (MidiDeviceInfo.PortInfo port : info.getPorts()) {
                text.append("  ").append(port.getType() == MidiDeviceInfo.PortInfo.TYPE_INPUT ? "in " : "out ")
                        .append(port.getPortNumber()).append(": '").append(port.getName()).append("'\n");
            }
        }
        return text.toString();
    }

    private static Entry find(int type, String name) throws IOException {
        for (Entry entry : entries(type)) {
            if (entry.name.equals(name)) {
                return entry;
            }
        }
        throw new IOException("No MIDI port " + name);
    }

    private static MidiDevice open(MidiDeviceInfo info) throws IOException {
        synchronized (devices) {
            MidiDevice device = devices.get(info.getId());
            if (device != null) {
                users.merge(info.getId(), 1, Integer::sum);
                return device;
            }
        }
        final MidiDevice[] opened = new MidiDevice[1];
        final CountDownLatch done = new CountDownLatch(1);
        manager.openDevice(info, device -> {
            opened[0] = device;
            done.countDown();
        }, handler);
        try {
            if (!done.await(OPEN_TIMEOUT, TimeUnit.SECONDS)) {
                throw new IOException("Opening " + deviceName(info) + " timed out");
            }
        } catch (InterruptedException error) {
            throw new IOException("Interrupted opening " + deviceName(info));
        }
        if (opened[0] == null) {
            throw new IOException("Android could not open " + deviceName(info));
        }
        synchronized (devices) {
            devices.put(info.getId(), opened[0]);
            users.put(info.getId(), 1);
        }
        return opened[0];
    }

    private static void release(MidiDevice device) {
        int id = device.getInfo().getId();
        synchronized (devices) {
            int left = users.merge(id, -1, Integer::sum);
            if (left > 0) {
                return;
            }
            devices.remove(id);
            users.remove(id);
        }
        try {
            device.close();
        } catch (IOException error) {
            Log.w(TAG, "Closing " + deviceName(device.getInfo()), error);
        }
    }

    /** An open port: send() for outputs; inputs deliver to their Listener until closed. */
    public static final class Port {
        private final MidiDevice device;
        private final Closeable port;
        private final MidiReceiver receiver;
        private final MidiReceiver connected;
        private boolean open = true;

        Port(MidiDevice device, Closeable port, MidiReceiver receiver, MidiReceiver connected) {
            this.device = device;
            this.port = port;
            this.receiver = receiver;
            this.connected = connected;
        }

        public void send(byte[] data) throws IOException {
            receiver.send(data, 0, data.length);
        }

        public synchronized void close() {
            if (!open) {
                return;
            }
            open = false;
            if (connected != null && port instanceof MidiOutputPort) {
                ((MidiOutputPort) port).disconnect(connected);
            }
            try {
                if (port != null) {
                    port.close();
                }
            } catch (IOException error) {
                Log.w(TAG, "Closing a port", error);
            }
            if (device != null) {
                release(device);
            }
        }
    }

    static MidiReceiver forward(final Listener listener) {
        return new MidiReceiver() {
            @Override
            public void onSend(byte[] data, int offset, int count, long timestamp) {
                byte[] run = new byte[count];
                System.arraycopy(data, offset, run, 0, count);
                try {
                    listener.onMidi(run);
                } catch (RuntimeException error) {
                    Log.w(TAG, "MIDI listener failed", error);
                }
            }
        };
    }

    public static Port openInput(String name, Listener listener) throws IOException {
        Entry entry = find(MidiDeviceInfo.PortInfo.TYPE_OUTPUT, name);
        MidiDevice device = open(entry.info);
        MidiOutputPort port = device.openOutputPort(entry.port);
        if (port == null) {
            release(device);
            throw new IOException(name + " is in use by another app");
        }
        MidiReceiver receiver = forward(listener);
        port.connect(receiver);
        return new Port(device, port, null, receiver);
    }

    public static Port openOutput(String name) throws IOException {
        Entry entry = find(MidiDeviceInfo.PortInfo.TYPE_INPUT, name);
        MidiDevice device = open(entry.info);
        MidiInputPort port = device.openInputPort(entry.port);
        if (port == null) {
            release(device);
            throw new IOException(name + " is in use by another app");
        }
        return new Port(device, port, port, null);
    }

    /** The app's own device (VirtualMidiService): [what other apps send us, what we send them]. */
    @SuppressWarnings("deprecation")
    public static Port[] openVirtual(Listener listener) throws IOException {
        // Android runs the service while someone has the device open: we do, so it stays
        MidiDevice own = null;
        if (VirtualMidiService.instance() == null) {
            for (MidiDeviceInfo info : manager.getDevices()) {
                if (own(info)) {
                    own = open(info);
                    break;
                }
            }
        }
        VirtualMidiService service = VirtualMidiService.instance();
        if (service == null) {
            if (own != null) {
                release(own);
            }
            throw new IOException("The PyxelWidgets MIDI device didn't start");
        }
        VirtualMidiService.listener = listener;
        MidiReceiver[] outputs = service.getOutputPortReceivers();
        Port receiving = new Port(own, () -> VirtualMidiService.listener = null, null, null);
        Port sending = new Port(null, null, outputs[0], null);
        return new Port[] {receiving, sending};
    }
}
