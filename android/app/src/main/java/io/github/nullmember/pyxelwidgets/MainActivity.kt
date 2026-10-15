package io.github.nullmember.pyxelwidgets

import android.annotation.SuppressLint
import android.content.pm.ApplicationInfo
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.WindowInsets
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlin.concurrent.thread

/**
 * The designer in a WebView. Python (Chaquopy) runs the designer's server in this
 * process (pyxelwidgets_android.start); the page talks to it on 127.0.0.1 as in a
 * browser, and to this activity through PyxelWidgetsHost (saving files).
 */
class MainActivity : ComponentActivity() {
    private lateinit var web: WebView
    private var chooser: ValueCallback<Array<Uri>>? = null
    private var pendingText: String? = null

    private val pickFile = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        chooser?.onReceiveValue(if (uri != null) arrayOf(uri) else null)
        chooser = null
    }

    private val createFile = registerForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
        val text = pendingText
        pendingText = null
        if (uri != null && text != null) {
            contentResolver.openOutputStream(uri)?.use { it.write(text.toByteArray()) }
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0) {
            // chrome://inspect on a computer reaches the page
            WebView.setWebContentsDebuggingEnabled(true)
        }
        web = WebView(this)
        // A WebView ignores its own padding: the frame around it keeps it clear of the system bars
        val frame = FrameLayout(this)
        frame.addView(web, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        setContentView(frame)
        if (Build.VERSION.SDK_INT >= 30) {
            // Android 15 draws apps under the status and navigation bars
            frame.setOnApplyWindowInsetsListener { view, insets ->
                // Bars hidden (immersive) give no insets; a camera cutout still does
                val bars = insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout() or WindowInsets.Type.ime())
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
                insets
            }
        }
        // Landscape, full screen: the bars come back with a swipe from the edge
        WindowCompat.getInsetsController(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        // The page asks for a 1280 px wide layout (index.html): scaled to fit the screen
        web.settings.useWideViewPort = true
        web.settings.loadWithOverviewMode = true
        web.settings.setSupportZoom(false)
        web.webViewClient = WebViewClient()
        web.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
                chooser?.onReceiveValue(null)
                chooser = callback
                pickFile.launch("*/*")
                return true
            }
        }
        web.addJavascriptInterface(Host(), "PyxelWidgetsHost")
        show("Starting PyxelWidgets…")
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            // Back leaves the app running (devices stay connected), like Home
            override fun handleOnBackPressed() {
                moveTaskToBack(true)
            }
        })
        MidiBridge.init(applicationContext)
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(applicationContext))
        }
        val folder = (getExternalFilesDir(null) ?: filesDir).absolutePath
        thread(name = "PyxelWidgetsStart") {
            try {
                val url = Python.getInstance().getModule("pyxelwidgets_android").callAttr("start", folder).toString()
                runOnUiThread { web.loadUrl(url) }
            } catch (error: Exception) {
                Log.e("PyxelWidgets", "Starting failed", error)
                runOnUiThread { show("PyxelWidgets couldn't start:\n\n${error.message}") }
            }
        }
    }

    private fun show(text: String) {
        val html = "<body style='background:#121418;color:#e6e8ec;font:16px sans-serif;padding:24px;white-space:pre-wrap'>" +
            android.text.Html.escapeHtml(text) + "</body>"
        web.loadDataWithBaseURL(null, html, "text/html", "utf-8", null)
    }

    /** window.PyxelWidgetsHost in the page (core.js appWindow) */
    inner class Host {
        @JavascriptInterface
        fun download(name: String, text: String): Boolean {
            pendingText = text
            runOnUiThread { createFile.launch(name) }
            return true
        }

        @JavascriptInterface
        fun changed(dirty: Boolean, file: String?) {
        }
    }
}
