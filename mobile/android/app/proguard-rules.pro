# Flutter ProGuard rules for release builds.
# Keep Flutter runtime and engine classes.
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.** { *; }
-keep class io.flutter.util.** { *; }
-keep class io.flutter.view.** { *; }
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }

# Keep annotations and native methods.
-keepattributes *Annotation*
-keepclasseswithmembernames class * {
    native <methods>;
}

# Suppress warnings for missing optional classes that may not be on the classpath.
-dontwarn io.flutter.embedding.**