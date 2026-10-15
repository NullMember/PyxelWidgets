import java.util.Properties

// One version for everything: the Python package's
val packageVersion = Regex("__version__ = '([^']+)'")
    .find(file("../../src/pyxelwidgets/__init__.py").readText())!!.groupValues[1]
val (major, minor, patch) = packageVersion.split(".").map { it.takeWhile(Char::isDigit).toInt() }

// The release key: environment variables (CI) or android/keystore.properties (this computer); never committed
val keystore = Properties().apply {
    val local = rootProject.file("keystore.properties")
    if (local.exists()) local.inputStream().use { load(it) }
}
fun signing(name: String): String? = System.getenv("PYXELWIDGETS_${name.uppercase()}") ?: keystore.getProperty(name)

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.nullmember.pyxelwidgets"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.nullmember.pyxelwidgets"
        minSdk = 24
        targetSdk = 35
        versionCode = major * 10000 + minor * 100 + patch
        versionName = packageVersion
        ndk {
            // Python 3.12 and later are 64-bit only; x86_64 is for the emulator
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    signingConfigs {
        create("release") {
            val path = signing("store_file")
            if (path != null) {
                storeFile = file(path)
                storePassword = signing("store_password")
                keyAlias = signing("key_alias")
                keyPassword = signing("key_password")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // Without the release key (a build on another computer) it's signed with the debug key
            signingConfig = signingConfigs.getByName(if (signing("store_file") != null) "release" else "debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

chaquopy {
    defaultConfig {
        // numpy's Android wheels stop at 3.13
        version = "3.13"
        // The build needs a Python 3.13 too: python3.13 on the PATH, or -PbuildPython=/path/to/python3.13
        buildPython(providers.gradleProperty("buildPython").getOrElse("python3.13"))
        pip {
            install("numpy")
            install("python-osc")
        }
        // The designer reads its page and templates as files
        extractPackages("pyxelwidgets")
    }
    sourceSets {
        getByName("main") {
            // The package itself, straight from the repository
            srcDir("../../src")
        }
    }
}

dependencies {
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.core:core-ktx:1.13.1")
}
