package io.github.nullmember.pyxelwidgets;

import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Looper;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * Asks for runtime permissions from a background thread (Python's): the activity
 * shows Android's question and passes the answer back (MainActivity forwards
 * onRequestPermissionsResult).
 */
public final class Permissions {
    private static final int CODE = 4021;
    private static volatile Activity activity;
    private static CountDownLatch answered;
    private static boolean result;

    private Permissions() {}

    static void attach(Activity current) {
        activity = current;
    }

    static void detach(Activity current) {
        if (activity == current) {
            activity = null;
        }
    }

    /** Whether all of ``permissions`` are granted, asking for those that aren't (waits for the answer). */
    public static synchronized boolean request(String[] permissions) {
        Activity current = activity;
        if (current == null || Looper.myLooper() == Looper.getMainLooper()) {
            return false;
        }
        answered = new CountDownLatch(1);
        result = false;
        current.runOnUiThread(() -> current.requestPermissions(permissions, CODE));
        try {
            // Someone has to answer: a long wait, but not forever
            answered.await(120, TimeUnit.SECONDS);
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
        }
        return result;
    }

    static void answered(int code, int[] grants) {
        if (code != CODE || answered == null) {
            return;
        }
        boolean all = grants.length > 0;
        for (int grant : grants) {
            all &= grant == PackageManager.PERMISSION_GRANTED;
        }
        result = all;
        answered.countDown();
    }
}
