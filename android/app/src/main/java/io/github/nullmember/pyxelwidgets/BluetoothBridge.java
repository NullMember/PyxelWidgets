package io.github.nullmember.pyxelwidgets;

import android.Manifest;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothManager;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanFilter;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.content.Context;
import android.content.pm.PackageManager;
import android.media.midi.MidiDevice;
import android.media.midi.MidiDeviceInfo;
import android.media.midi.MidiManager;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.ParcelUuid;
import android.util.Log;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * Bluetooth MIDI devices for Python (pyxelwidgets.devices.bluetooth): scanning for
 * the BLE MIDI service, and connecting through Android's MIDI service, which then
 * lists the device's ports like a USB device's (MidiBridge).
 *
 * Results are tab-separated strings ("address\tname\trssi"), simple to read from Python.
 */
public final class BluetoothBridge {
    private static final String TAG = "PyxelWidgetsBluetooth";
    /** The BLE MIDI service (Apple's specification, adopted by the MIDI Association) */
    public static final ParcelUuid MIDI_SERVICE = ParcelUuid.fromString("03B80E5A-EDE8-4B33-A751-6CE34EC4C700");
    private static final long CONNECT_TIMEOUT = 20;

    private static Context context;
    private static Handler handler;
    /** Open Bluetooth MIDI devices by address, and their names */
    private static final Map<String, MidiDevice> devices = Collections.synchronizedMap(new LinkedHashMap<>());
    private static final Map<String, String> names = Collections.synchronizedMap(new LinkedHashMap<>());

    private BluetoothBridge() {}

    public static synchronized void init(Context appContext) {
        if (context != null) {
            return;
        }
        context = appContext;
        HandlerThread thread = new HandlerThread("PyxelWidgetsBluetooth");
        thread.start();
        handler = new Handler(thread.getLooper());
        MidiManager manager = (MidiManager) context.getSystemService(Context.MIDI_SERVICE);
        if (manager != null) {
            // A device out of range or switched off: forget the connection (Python connects it again)
            manager.registerDeviceCallback(new MidiManager.DeviceCallback() {
                @Override
                public void onDeviceRemoved(MidiDeviceInfo info) {
                    if (info.getType() != MidiDeviceInfo.TYPE_BLUETOOTH) {
                        return;
                    }
                    BluetoothDevice device = info.getProperties().getParcelable(MidiDeviceInfo.PROPERTY_BLUETOOTH_DEVICE);
                    if (device != null) {
                        close(device.getAddress());
                    }
                }
            }, handler);
        }
    }

    private static BluetoothAdapter adapter() {
        BluetoothManager manager = (BluetoothManager) context.getSystemService(Context.BLUETOOTH_SERVICE);
        return manager == null ? null : manager.getAdapter();
    }

    static String[] permissions() {
        if (Build.VERSION.SDK_INT >= 31) {
            return new String[] {Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT};
        }
        return new String[] {Manifest.permission.ACCESS_FINE_LOCATION};
    }

    private static boolean granted() {
        for (String permission : permissions()) {
            if (context.checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) {
                return false;
            }
        }
        return true;
    }

    /** null when Bluetooth MIDI can be used, else why not; with ``ask``, asks for the permissions if needed. */
    public static String problem(boolean ask) {
        if (context == null || !context.getPackageManager().hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE)) {
            return "This device has no Bluetooth LE";
        }
        if (!context.getPackageManager().hasSystemFeature(PackageManager.FEATURE_MIDI)) {
            return "This device has no MIDI service";
        }
        if (!granted() && !(ask && Permissions.request(permissions()))) {
            return ask ? "Bluetooth permission refused (Android settings > Apps > PyxelWidgets > Permissions)"
                       : "PyxelWidgets may not use Bluetooth yet";
        }
        BluetoothAdapter adapter = adapter();
        if (adapter == null) {
            return "This device has no Bluetooth";
        }
        if (!adapter.isEnabled()) {
            return "Bluetooth is off";
        }
        return null;
    }

    @SuppressWarnings("MissingPermission")
    private static String nameOf(BluetoothDevice device, ScanResult result) {
        String name = result != null && result.getScanRecord() != null ? result.getScanRecord().getDeviceName() : null;
        if (name == null || name.isEmpty()) {
            try {
                name = device.getName();
            } catch (SecurityException error) {
                name = null;
            }
        }
        return name == null || name.isEmpty() ? device.getAddress() : name;
    }

    /** Devices advertising the MIDI service, found within ``millis``. */
    @SuppressWarnings("MissingPermission")
    public static String[] scan(int millis) throws IOException {
        String problem = problem(true);
        if (problem != null) {
            throw new IOException(problem);
        }
        BluetoothLeScanner scanner = adapter().getBluetoothLeScanner();
        if (scanner == null) {
            throw new IOException("Bluetooth is off");
        }
        final Map<String, String> found = Collections.synchronizedMap(new LinkedHashMap<>());
        final int[] failed = {0};
        ScanCallback callback = new ScanCallback() {
            @Override
            public void onScanResult(int type, ScanResult result) {
                BluetoothDevice device = result.getDevice();
                found.put(device.getAddress(), device.getAddress() + "\t" + nameOf(device, result) + "\t" + result.getRssi());
            }

            @Override
            public void onScanFailed(int code) {
                failed[0] = code;
            }
        };
        List<ScanFilter> filters = new ArrayList<>();
        filters.add(new ScanFilter.Builder().setServiceUuid(MIDI_SERVICE).build());
        ScanSettings settings = new ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build();
        scanner.startScan(filters, settings, callback);
        try {
            Thread.sleep(millis);
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
        } finally {
            scanner.stopScan(callback);
        }
        if (failed[0] != 0) {
            throw new IOException("Bluetooth scan failed (" + failed[0] + ")");
        }
        synchronized (found) {
            return found.values().toArray(new String[0]);
        }
    }

    /** Connect to the device at ``address``; returns its name once Android lists its MIDI ports. */
    public static String connect(String address) throws IOException {
        String problem = problem(true);
        if (problem != null) {
            throw new IOException(problem);
        }
        MidiDevice open = devices.get(address);
        if (open != null) {
            return names.get(address);
        }
        BluetoothDevice device;
        try {
            device = adapter().getRemoteDevice(address);
        } catch (IllegalArgumentException error) {
            throw new IOException("No Bluetooth address " + address);
        }
        MidiManager manager = (MidiManager) context.getSystemService(Context.MIDI_SERVICE);
        final MidiDevice[] opened = new MidiDevice[1];
        final CountDownLatch done = new CountDownLatch(1);
        manager.openBluetoothDevice(device, midiDevice -> {
            opened[0] = midiDevice;
            done.countDown();
        }, handler);
        try {
            if (!done.await(CONNECT_TIMEOUT, TimeUnit.SECONDS)) {
                throw new IOException("Connecting to " + address + " timed out (is it on and in range?)");
            }
        } catch (InterruptedException error) {
            throw new IOException("Interrupted connecting to " + address);
        }
        if (opened[0] == null) {
            throw new IOException("Couldn't connect to " + address);
        }
        String name = MidiBridge.deviceName(opened[0].getInfo());
        devices.put(address, opened[0]);
        names.put(address, name);
        Log.i(TAG, "Connected " + name + " (" + address + ")");
        return name;
    }

    public static void disconnect(String address) {
        close(address);
    }

    private static void close(String address) {
        MidiDevice device = devices.remove(address);
        names.remove(address);
        if (device != null) {
            try {
                device.close();
            } catch (IOException error) {
                Log.w(TAG, "Closing " + address, error);
            }
        }
    }

    /** Connected devices: "address\tname". */
    public static String[] connected() {
        List<String> list = new ArrayList<>();
        synchronized (names) {
            for (Map.Entry<String, String> entry : names.entrySet()) {
                list.add(entry.getKey() + "\t" + entry.getValue());
            }
        }
        return list.toArray(new String[0]);
    }
}
