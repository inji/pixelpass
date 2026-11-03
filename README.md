
# pixelpass
This repository will be used to host the source code, documentation, and other related files for the PixelPass project which is used to generate and decode VC data to and from QR.

## Available Libraries

This library is available in Kotlin, Swift, and JavaScript, supporting Android, JVM, iOS, and Node platforms.

- **Kotlin**: [Android (AAR) & JVM (JAR)](./kotlin/Readme.md)
- **JavaScript**: [Node.js & Web](./js/Readme.md)
- **Swift**: [iOS](https://github.com/inji/pixelpass-ios-swift)
- **Python**: [CPython 3.9+](./python/Readme.md)

## Python

The [`python/`](./python/Readme.md) folder holds `pixelpass-python`, a port of the JavaScript library
that produces byte-identical QR data for well-formed input. Install it with `pip install ./python`
and see [python/Readme.md](./python/Readme.md) for the API, the deliberate deviations from JS and the
security limits.


