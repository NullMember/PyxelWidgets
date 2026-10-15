package com.nullmember.pyxelwidgets;

import android.Manifest;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothGattServer;
import android.bluetooth.BluetoothGattServerCallback;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.bluetooth.le.AdvertiseCallback;
import android.bluetooth.le.AdvertiseData;
import android.bluetooth.le.AdvertiseSettings;
import android.bluetooth.le.BluetoothLeAdvertiser;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.ParcelUuid;
import android.util.Log;

import java.io.IOException;
import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * The phone as a Bluetooth MIDI device (pyxelwidgets.devices.ble_midi.BleMidi on
 * Android): a GATT server with the BLE MIDI service, advertised so Macs, iPads, PCs
 * and other phones connect to it. Python sends ready-made BLE MIDI packets and gets
 * the ones written to it.
 *
 * Android allows one notification in flight per connection, so packets queue per
 * device and go one by one (onNotificationSent). Android advertises the phone's own
 * Bluetooth name; apps can't choose another.
 *
 * The GATT server stays open for the app's life: stop() only stops advertising and
 * detaches Python. Android can't drop a link a computer opened, so a closed server
 * would leave that computer writing into nothing; kept, it carries on after start().
 */
@SuppressWarnings({"MissingPermission", "deprecation"})
public final class BlePeripheral {
    private static final String TAG = "PyxelWidgetsPeripheral";
    static final UUID SERVICE = UUID.fromString("03B80E5A-EDE8-4B33-A751-6CE34EC4C700");
    static final UUID CHARACTERISTIC = UUID.fromString("7772E5DB-3868-4112-A1A9-F2669D106BF3");
    static final UUID CLIENT_CONFIG = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");
    /** Packets kept per device while it's behind */
    private static final int QUEUE_LIMIT = 1000;

    /** Python's side: what was written to the characteristic, and how many devices listen. */
    public interface Listener {
        void onWrite(byte[] data);
        void onListening(int devices);
    }

    private static Context context;
    private static BluetoothGattServer server;
    private static BluetoothGattCharacteristic characteristic;
    private static BluetoothLeAdvertiser advertiser;
    private static AdvertiseCallback advertising;
    private static Listener listener;
    private static boolean secured;
    private static final Object lock = new Object();
    private static final Map<String, BluetoothDevice> listening = new HashMap<>();
    /** Every device connected to the server, listening or not: stopping drops them all */
    private static final Map<String, BluetoothDevice> connections = new HashMap<>();
    private static final Map<String, Integer> mtus = new HashMap<>();
    private static final Map<String, ArrayDeque<byte[]>> queues = new HashMap<>();
    private static final Set<String> sending = new HashSet<>();
    /** Packets given up because a device stopped taking them */
    public static volatile int dropped = 0;

    private BlePeripheral() {}

    public static void init(Context appContext) {
        context = appContext;
        // Bluetooth turned off takes the server and advertising with it: both come back with Bluetooth
        context.registerReceiver(new BroadcastReceiver() {
            @Override
            public void onReceive(Context receiving, Intent intent) {
                int state = intent.getIntExtra(BluetoothAdapter.EXTRA_STATE, BluetoothAdapter.ERROR);
                if (state == BluetoothAdapter.STATE_OFF) {
                    close();
                } else if (state == BluetoothAdapter.STATE_ON && listener != null) {
                    final Listener again = listener;
                    new Thread(() -> {
                        try {
                            start(again, secured);
                        } catch (IOException error) {
                            Log.w(TAG, "Advertising again after Bluetooth came back", error);
                        }
                    }, "PyxelWidgetsPeripheral").start();
                }
            }
        }, new IntentFilter(BluetoothAdapter.ACTION_STATE_CHANGED));
    }

    static String[] permissions() {
        if (Build.VERSION.SDK_INT >= 31) {
            return new String[] {Manifest.permission.BLUETOOTH_ADVERTISE, Manifest.permission.BLUETOOTH_CONNECT};
        }
        return new String[0];
    }

    private static boolean granted() {
        for (String permission : permissions()) {
            if (context.checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) {
                return false;
            }
        }
        return true;
    }

    private static BluetoothAdapter adapter() {
        BluetoothManager manager = (BluetoothManager) context.getSystemService(Context.BLUETOOTH_SERVICE);
        return manager == null ? null : manager.getAdapter();
    }

    /** Start the GATT server and advertising; returns the name other devices see. */
    public static String start(Listener pythonListener, boolean secure) throws IOException {
        synchronized (lock) {
            stop();
            if (!context.getPackageManager().hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE)) {
                throw new IOException("This device has no Bluetooth LE");
            }
            if (!granted() && !Permissions.request(permissions())) {
                throw new IOException("Bluetooth permission refused (Android settings > Apps > PyxelWidgets > Permissions)");
            }
            BluetoothAdapter adapter = adapter();
            if (adapter == null || !adapter.isEnabled()) {
                throw new IOException("Bluetooth is off");
            }
            if (!adapter.isMultipleAdvertisementSupported() || adapter.getBluetoothLeAdvertiser() == null) {
                throw new IOException("This phone can't advertise as a Bluetooth LE device");
            }
            listener = pythonListener;
            if (server == null || secure != secured) {
                close();
                openServer(secure);
            }
            secured = secure;
            final int already = listening.size();

            advertiser = adapter.getBluetoothLeAdvertiser();
            final CountDownLatch started = new CountDownLatch(1);
            final int[] failure = {0};
            advertising = new AdvertiseCallback() {
                @Override
                public void onStartSuccess(AdvertiseSettings settings) {
                    started.countDown();
                }

                @Override
                public void onStartFailure(int code) {
                    failure[0] = code;
                    started.countDown();
                }
            };
            AdvertiseSettings settings = new AdvertiseSettings.Builder()
                    .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY)
                    .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_HIGH)
                    .setConnectable(true)
                    .setTimeout(0)
                    .build();
            // The 128-bit service UUID fills most of the advertisement: the name goes in the scan response
            AdvertiseData data = new AdvertiseData.Builder().addServiceUuid(new ParcelUuid(SERVICE)).setIncludeDeviceName(false).build();
            AdvertiseData response = new AdvertiseData.Builder().setIncludeDeviceName(true).build();
            advertiser.startAdvertising(settings, data, response, advertising);
            try {
                started.await(5, TimeUnit.SECONDS);
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
            }
            if (failure[0] != 0) {
                stop();
                throw new IOException(failure[0] == AdvertiseCallback.ADVERTISE_FAILED_DATA_TOO_LARGE
                        ? "The phone's Bluetooth name is too long to advertise (shorten it in Android's Bluetooth settings)"
                        : "Advertising failed (" + failure[0] + ")");
            }
            // Computers that stayed connected while it was stopped listen again
            if (already > 0) {
                listeners(already);
            }
            return adapter.getName();
        }
    }

    /** Open the GATT server with the MIDI service (holding lock); tries twice, Android can be slow after a close. */
    private static void openServer(boolean secure) throws IOException {
        BluetoothManager manager = (BluetoothManager) context.getSystemService(Context.BLUETOOTH_SERVICE);
        for (int attempt = 0; attempt < 2; attempt++) {
            final CountDownLatch added = new CountDownLatch(1);
            server = manager.openGattServer(context, new Callback(added));
            if (server == null) {
                throw new IOException("Android couldn't open a GATT server");
            }
            int permissions = secure
                    ? BluetoothGattCharacteristic.PERMISSION_READ_ENCRYPTED | BluetoothGattCharacteristic.PERMISSION_WRITE_ENCRYPTED
                    : BluetoothGattCharacteristic.PERMISSION_READ | BluetoothGattCharacteristic.PERMISSION_WRITE;
            characteristic = new BluetoothGattCharacteristic(CHARACTERISTIC,
                    BluetoothGattCharacteristic.PROPERTY_READ | BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE
                            | BluetoothGattCharacteristic.PROPERTY_NOTIFY, permissions);
            characteristic.addDescriptor(new BluetoothGattDescriptor(CLIENT_CONFIG,
                    BluetoothGattDescriptor.PERMISSION_READ | BluetoothGattDescriptor.PERMISSION_WRITE));
            BluetoothGattService service = new BluetoothGattService(SERVICE, BluetoothGattService.SERVICE_TYPE_PRIMARY);
            service.addCharacteristic(characteristic);
            server.addService(service);
            try {
                if (added.await(10, TimeUnit.SECONDS)) {
                    return;
                }
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
            }
            close();
            try {
                Thread.sleep(1000);
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
            }
        }
        throw new IOException("Android didn't add the MIDI service (turning Bluetooth off and on may help)");
    }

    /** Stop advertising and detach Python; the server and its connections stay (see the class). */
    public static void stop() {
        synchronized (lock) {
            if (advertiser != null && advertising != null) {
                try {
                    advertiser.stopAdvertising(advertising);
                } catch (RuntimeException error) {
                    Log.w(TAG, "Stopping advertising", error);
                }
            }
            advertiser = null;
            advertising = null;
            listener = null;
            queues.clear();
            sending.clear();
        }
    }

    /** Close the server too (another security setting, or a server Android lost). */
    private static void close() {
        boolean had;
        synchronized (lock) {
            had = !listening.isEmpty();
            if (server != null) {
                // Else a computer stays connected to a server that's gone, writing into nothing
                for (BluetoothDevice device : connections.values()) {
                    server.cancelConnection(device);
                }
                server.close();
            }
            server = null;
            characteristic = null;
            listening.clear();
            connections.clear();
            mtus.clear();
            queues.clear();
            sending.clear();
        }
        if (had) {
            listeners(0);
        }
    }

    /** The longest packet every listening device takes (its MTU less 3), at least 20. */
    public static int payload() {
        synchronized (lock) {
            int payload = Integer.MAX_VALUE;
            for (String address : listening.keySet()) {
                Integer mtu = mtus.get(address);
                payload = Math.min(payload, mtu == null ? 20 : mtu - 3);
            }
            return payload == Integer.MAX_VALUE ? 20 : Math.max(20, Math.min(payload, 512));
        }
    }

    /** Notify every listening device of ``packet`` (queued: Android takes one at a time per device). */
    public static void send(byte[] packet) {
        synchronized (lock) {
            for (BluetoothDevice device : listening.values()) {
                ArrayDeque<byte[]> queue = queues.computeIfAbsent(device.getAddress(), key -> new ArrayDeque<>());
                queue.add(packet);
                while (queue.size() > QUEUE_LIMIT) {
                    queue.poll();
                    dropped++;
                }
                if (!sending.contains(device.getAddress())) {
                    next(device);
                }
            }
        }
    }

    /** Send the device's next queued packet (holding lock). */
    private static void next(BluetoothDevice device) {
        ArrayDeque<byte[]> queue = queues.get(device.getAddress());
        if (server == null || characteristic == null || queue == null || queue.isEmpty()) {
            sending.remove(device.getAddress());
            return;
        }
        byte[] packet = queue.poll();
        boolean sent;
        if (Build.VERSION.SDK_INT >= 33) {
            sent = server.notifyCharacteristicChanged(device, characteristic, false, packet) == BluetoothGatt.GATT_SUCCESS;
        } else {
            characteristic.setValue(packet);
            sent = server.notifyCharacteristicChanged(device, characteristic, false);
        }
        if (sent) {
            sending.add(device.getAddress());
        } else {
            // Busy: try this one again when the last notification is through
            queue.addFirst(packet);
            sending.remove(device.getAddress());
        }
    }

    private static void listeners(int count) {
        Listener now = listener;
        if (now != null) {
            try {
                now.onListening(count);
            } catch (RuntimeException error) {
                Log.w(TAG, "Listener failed", error);
            }
        }
    }

    private static final class Callback extends BluetoothGattServerCallback {
        private final CountDownLatch added;

        Callback(CountDownLatch added) {
            this.added = added;
        }

        @Override
        public void onServiceAdded(int status, BluetoothGattService service) {
            added.countDown();
        }

        @Override
        public void onConnectionStateChange(BluetoothDevice device, int status, int state) {
            if (state == BluetoothProfile.STATE_CONNECTED) {
                synchronized (lock) {
                    connections.put(device.getAddress(), device);
                }
            } else if (state == BluetoothProfile.STATE_DISCONNECTED) {
                int count;
                synchronized (lock) {
                    connections.remove(device.getAddress());
                    listening.remove(device.getAddress());
                    mtus.remove(device.getAddress());
                    queues.remove(device.getAddress());
                    sending.remove(device.getAddress());
                    count = listening.size();
                }
                listeners(count);
            }
        }

        @Override
        public void onMtuChanged(BluetoothDevice device, int mtu) {
            synchronized (lock) {
                mtus.put(device.getAddress(), mtu);
            }
        }

        @Override
        public void onCharacteristicReadRequest(BluetoothDevice device, int id, int offset, BluetoothGattCharacteristic read) {
            // BLE MIDI: reading gives an empty packet
            BluetoothGattServer now = server;
            if (now != null) {
                now.sendResponse(device, id, BluetoothGatt.GATT_SUCCESS, 0, new byte[0]);
            }
        }

        @Override
        public void onCharacteristicWriteRequest(BluetoothDevice device, int id, BluetoothGattCharacteristic written,
                                                 boolean prepared, boolean responseNeeded, int offset, byte[] value) {
            BluetoothGattServer now = server;
            if (responseNeeded && now != null) {
                now.sendResponse(device, id, BluetoothGatt.GATT_SUCCESS, 0, null);
            }
            Listener python = listener;
            if (python != null && value != null) {
                try {
                    python.onWrite(value);
                } catch (RuntimeException error) {
                    Log.w(TAG, "Listener failed", error);
                }
            }
        }

        @Override
        public void onDescriptorReadRequest(BluetoothDevice device, int id, int offset, BluetoothGattDescriptor descriptor) {
            boolean on;
            synchronized (lock) {
                on = listening.containsKey(device.getAddress());
            }
            BluetoothGattServer now = server;
            if (now != null) {
                now.sendResponse(device, id, BluetoothGatt.GATT_SUCCESS, 0,
                        on ? BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE : BluetoothGattDescriptor.DISABLE_NOTIFICATION_VALUE);
            }
        }

        @Override
        public void onDescriptorWriteRequest(BluetoothDevice device, int id, BluetoothGattDescriptor descriptor,
                                             boolean prepared, boolean responseNeeded, int offset, byte[] value) {
            int count;
            synchronized (lock) {
                if (value != null && value.length > 0 && (value[0] & 1) != 0) {
                    listening.put(device.getAddress(), device);
                } else {
                    listening.remove(device.getAddress());
                    queues.remove(device.getAddress());
                    sending.remove(device.getAddress());
                }
                count = listening.size();
            }
            BluetoothGattServer now = server;
            if (responseNeeded && now != null) {
                now.sendResponse(device, id, BluetoothGatt.GATT_SUCCESS, 0, null);
            }
            listeners(count);
        }

        @Override
        public void onNotificationSent(BluetoothDevice device, int status) {
            synchronized (lock) {
                sending.remove(device.getAddress());
                next(device);
            }
        }
    }
}
