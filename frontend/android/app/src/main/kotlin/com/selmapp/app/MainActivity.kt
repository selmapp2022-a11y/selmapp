package com.selmapp.app

import android.os.Bundle
import androidx.core.view.WindowCompat
import io.flutter.embedding.android.FlutterActivity

@Suppress("unused") // Referenced by AndroidManifest.xml via android:name=".MainActivity"
class MainActivity : FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // Enable edge-to-edge across Android versions.
        // Android 15 (SDK 35) enables edge-to-edge by default for apps targeting 35+.
        // Setting this makes behavior consistent on older Android versions too.
        WindowCompat.setDecorFitsSystemWindows(window, false)
        super.onCreate(savedInstanceState)
    }
}




