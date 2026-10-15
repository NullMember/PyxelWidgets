package io.github.nullmember.pyxelwidgets

import android.content.Context
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

/**
 * Python and the designer's server, once per process: the activity and the
 * player service both need them, whichever comes first.
 */
object Runtime {
    @Volatile
    private var url: String? = null

    /** Start everything (blocks while Python starts the designer: not on the main thread); returns the page's address. */
    @Synchronized
    fun start(context: Context): String {
        url?.let { return it }
        val app = context.applicationContext
        MidiBridge.init(app)
        BluetoothBridge.init(app)
        BlePeripheral.init(app)
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(app))
        }
        val folder = (app.getExternalFilesDir(null) ?: app.filesDir).absolutePath
        val started = Python.getInstance().getModule("pyxelwidgets_android").callAttr("start", folder).toString()
        url = started
        return started
    }

    /** Close the designer: devices get their goodbye messages, outputs close. */
    fun stop() {
        if (url == null) {
            return
        }
        try {
            Python.getInstance().getModule("pyxelwidgets_android").callAttr("stop")
        } catch (error: Exception) {
            android.util.Log.w("PyxelWidgets", "Stopping", error)
        }
    }
}
