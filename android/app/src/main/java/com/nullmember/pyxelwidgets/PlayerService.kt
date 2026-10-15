package io.github.nullmember.pyxelwidgets

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import kotlin.concurrent.thread

/**
 * Keeps PyxelWidgets playing in the background: a foreground service (a
 * notification Android shows while it runs) so Android doesn't stop the app, a
 * wake lock so it keeps running with the screen off, and a Wi-Fi lock for network
 * MIDI and the shared designer. The notification's Quit closes everything.
 */
class PlayerService : Service() {
    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val notifications = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26) {
            notifications.createNotificationChannel(
                NotificationChannel(CHANNEL, "Running", NotificationManager.IMPORTANCE_LOW).apply {
                    description = "Shown while PyxelWidgets plays in the background"
                    setShowBadge(false)
                })
        }
        foreground()
        wakeLock = (getSystemService(Context.POWER_SERVICE) as PowerManager)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "PyxelWidgets:player").apply {
                setReferenceCounted(false)
                acquire()
            }
        val wifi = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        @Suppress("DEPRECATION")
        val mode = if (Build.VERSION.SDK_INT >= 29) WifiManager.WIFI_MODE_FULL_LOW_LATENCY else WifiManager.WIFI_MODE_FULL_HIGH_PERF
        wifiLock = wifi.createWifiLock(mode, "PyxelWidgets:player").apply {
            setReferenceCounted(false)
            acquire()
        }
        // The designer starts here too: after Android restarts the service, there may be no activity
        thread(name = "PyxelWidgetsStart") {
            try {
                Runtime.start(this)
            } catch (error: Exception) {
                android.util.Log.e("PyxelWidgets", "Starting failed", error)
            }
        }
    }

    /** Show the notification (again: one posted before notifications were allowed never shows). */
    private fun foreground() {
        val notification = notification()
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFICATION, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
        } else {
            startForeground(NOTIFICATION, notification)
        }
    }

    private fun notification(): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val quit = PendingIntent.getService(this, 1, Intent(this, PlayerService::class.java).setAction(QUIT),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val builder = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, CHANNEL) else @Suppress("DEPRECATION") Notification.Builder(this)
        return builder
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("PyxelWidgets is running")
            .setContentText("Devices and outputs stay connected. Tap to open.")
            .setContentIntent(open)
            .setOngoing(true)
            .addAction(Notification.Action.Builder(null, "Quit", quit).build())
            .build()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == QUIT) {
            quit()
            return START_NOT_STICKY
        }
        foreground()
        return START_STICKY
    }

    private fun quit() {
        thread(name = "PyxelWidgetsQuit") {
            Runtime.stop()
            MainActivity.finishAll()
            stopSelf()
            // A fresh start next time: Python, the designer and its connections
            android.os.Process.killProcess(android.os.Process.myPid())
        }
    }

    override fun onDestroy() {
        wakeLock?.release()
        wifiLock?.release()
        super.onDestroy()
    }

    companion object {
        private const val CHANNEL = "running"
        private const val NOTIFICATION = 1
        const val QUIT = "io.github.nullmember.pyxelwidgets.QUIT"

        fun start(context: Context) {
            val intent = Intent(context, PlayerService::class.java)
            if (Build.VERSION.SDK_INT >= 26) context.startForegroundService(intent) else context.startService(intent)
        }
    }
}
