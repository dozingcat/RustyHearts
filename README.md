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

To build the Rust shared library for 64-bit ARM Android:
```
cargo build --target aarch64-linux-android --release
```

To build an Anddroid app (currently 64-bit ARM only), build the above shared library, copy it to `py/lib/libhearts_arm64.so`, and from the `py` directory run:
```
buildozer android debug
```
I've only been able to get this to build successfully on Linux.

If there are Android build problems, cleaning the build might help: `buildozer android clean`.

Card images from https://github.com/hayeah/playing-cards-assets.
