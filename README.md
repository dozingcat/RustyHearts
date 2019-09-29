# RustyHearts
Hearts card game with AI in Rust and front end in Python.

To play a round from the command line:
```
cargo run --bin hearts_console --release
```

To build the Rust shared library used by the Python app:
```
cargo build --lib --release
```

To run the Python desktop app after building the shared library, go to the `py` directory and run:
```
python main.py
```

To build an Android app (currently only on Linux):
1. Make sure `javac` is using Java 8. Kivy fails with later versions: https://github.com/kivy/buildozer/issues/862. `sudo apt install openjdk-8-jdk` will install Java 8.
1. Install build dependencies: `sudo apt install autoconf libtool`.
1. Install Python dependencies by running `pip install -r requirements.txt` from the `py` directory.
1. Install Android targets for Rust:
`rustup target add aarch64-linux-android armv7-linux-androideabi x86_64-linux-android i686-linux-android`
1. Install the Android NDK (either standalone or through Android Studio) and add these entries to `~/.cargo/config` (creating the file if it doesn't exit):
```
[target.aarch64-linux-android]
ar = "Android/Sdk/ndk-bundle/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android-ar"
linker = "Android/Sdk/ndk-bundle/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android29-clang"

[target.armv7-linux-androideabi]
ar = "Android/Sdk/ndk-bundle/toolchains/llvm/prebuilt/linux-x86_64/bin/arm-linux-androideabi-ar"
linker = "Android/Sdk/ndk-bundle/toolchains/llvm/prebuilt/linux-x86_64/bin/armv7a-linux-androideabi29-clang"

[target.x86_64-linux-android]
ar = "Android/Sdk/ndk-bundle/toolchains/llvm/prebuilt/linux-x86_64/bin/x86_64-linux-android-ar"
linker = "Android/Sdk/ndk-bundle/toolchains/llvm/prebuilt/linux-x86_64/bin/x86_64-linux-android29-clang"

[target.i686-linux-android]
ar = "Android/Sdk/ndk-bundle/toolchains/llvm/prebuilt/linux-x86_64/bin/i686-linux-android-ar"
linker = "Android/Sdk/ndk-bundle/toolchains/llvm/prebuilt/linux-x86_64/bin/i686-linux-android29-clang"
```
Adjust the `Android/Sdk/ndk-bundle` prefix as needed to point to your NDK installation; the path is relative to your home directory.
1. Build an Android shared library. For 64-bit ARM run `cargo build --target aarch64-linux-android --release` from the `rust` directory.
1. Copy the resulting shared library at `rust/target/aarch64-linux-android/release/libhearts.so` to `py/lib/libhearts_arm64.so`.
1. From the `py` directory run `buildozer android debug`. This may take several minutes the first time. If it succeeds, it will create an APK in the `bin` directory, which you can install on a device or emulator with adb.

See https://github.com/kivy/kivy/wiki/Creating-a-Release-APK for creating a signed release build. After running `zipalign`, you may need to run [apksigner](https://developer.android.com/studio/command-line/apksigner) on the aligned APK.

If there are Android build problems, cleaning the build might help: `buildozer android clean`.

Card images from https://code.google.com/archive/p/vector-playing-cards/.
