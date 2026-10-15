package com.nullmember.pyxelwidgets;

import android.content.Context;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import android.os.Build;
import android.provider.Settings;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * Announces a service on the network (Bonjour / DNS-SD) through Android's
 * NsdManager, e.g. the network MIDI session (_apple-midi._udp) so a Mac finds
 * the phone in Audio MIDI Setup's directory.
 */
public final class NsdAdvert {
    private static Context context;

    private final NsdManager manager;
    private final CountDownLatch answered = new CountDownLatch(1);
    private volatile String registered;
    private volatile String error;
    private boolean closed;

    private final NsdManager.RegistrationListener listener = new NsdManager.RegistrationListener() {
        @Override
        public void onServiceRegistered(NsdServiceInfo info) {
            registered = info.getServiceName();
            answered.countDown();
        }

        @Override
        public void onRegistrationFailed(NsdServiceInfo info, int code) {
            error = "Android refused to announce it (" + reason(code) + ")";
            answered.countDown();
        }

        @Override
        public void onServiceUnregistered(NsdServiceInfo info) {}

        @Override
        public void onUnregistrationFailed(NsdServiceInfo info, int code) {}
    };

    public static void init(Context appContext) {
        context = appContext;
    }

    /** The phone's name as its owner set it (Settings > About phone), else its model. */
    public static String deviceName() {
        String name = null;
        if (context != null) {
            name = Settings.Global.getString(context.getContentResolver(), Settings.Global.DEVICE_NAME);
        }
        return name == null || name.isEmpty() ? Build.MODEL : name;
    }

    private NsdAdvert(String name, String type, int port) {
        manager = (NsdManager) context.getSystemService(Context.NSD_SERVICE);
        NsdServiceInfo info = new NsdServiceInfo();
        info.setServiceName(name);
        info.setServiceType(type);
        info.setPort(port);
        manager.registerService(info, NsdManager.PROTOCOL_DNS_SD, listener);
    }

    /**
     * Announce ``name`` (a service of ``type``, e.g. _apple-midi._udp) on
     * ``port``, waiting up to ``timeoutMs`` for Android's answer: ``name()``
     * is the name announced (Android adds " (2)" when it's taken), ``error()``
     * why it isn't.
     */
    public static NsdAdvert register(String name, String type, int port, int timeoutMs) {
        if (context == null) {
            throw new IllegalStateException("NsdAdvert.init wasn't called");
        }
        NsdAdvert advert = new NsdAdvert(name, type, port);
        try {
            // Without an answer by then it is still going: name() stays null until it's registered
            advert.answered.await(timeoutMs, TimeUnit.MILLISECONDS);
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
        }
        return advert;
    }

    public String name() {
        return registered;
    }

    public String error() {
        return error;
    }

    public synchronized void close() {
        if (closed) {
            return;
        }
        closed = true;
        if (error == null) {
            try {
                manager.unregisterService(listener);
            } catch (IllegalArgumentException notRegistered) {
                // Failed or never registered
            }
        }
    }

    private static String reason(int code) {
        switch (code) {
            case NsdManager.FAILURE_ALREADY_ACTIVE:
                return "already announced";
            case NsdManager.FAILURE_MAX_LIMIT:
                return "too many announcements";
            case NsdManager.FAILURE_INTERNAL_ERROR:
            default:
                return "internal error " + code;
        }
    }
}
