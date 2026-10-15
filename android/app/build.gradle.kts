plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "io.github.nullmember.pyxelwidgets"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.nullmember.pyxelwidgets"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
        ndk {
            // Python 3.12 and later are 64-bit only; x86_64 is for the emulator
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // Signed with the debug key until there's a release key
            signingConfig = signingConfigs.getByName("debug")
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
