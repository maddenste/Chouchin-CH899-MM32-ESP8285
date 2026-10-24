# How the project started

The aim was to give an existing Chouchin CH899 movement more flexible settings: different hand movements, overnight seconds parking and straightforward Wi-Fi setup.

The board was designed by someone else, with no supplied circuit diagram or MM32 application source. The work began by identifying the components, finding how they were connected and observing how the Wi-Fi module talked to the movement controller.

An earlier project replaced only the ESP Wi-Fi application. This v1.5 project goes further: it supplies replacement applications for both the MM32 movement controller and the ESP8285.

The [HC32/TXW813 project](https://github.com/maddenste/Chouchin-899-latest-revision), for a different board, provided the settings-page design and a useful comparison for movement behavior. Its firmware cannot be used on this board.

A major part of development was keeping the seconds hand consistent through pauses, time updates and setting changes. Some tests passed in software while movement on the real clock still varied. The seconds hand is now running consistently smoothly on the clock used for development. Testing continues; [the test record](development/TESTING.md) records the checks and their limits.

For source history, hardware findings and technical evidence, see [the developer documentation](development/README.md).

The board photographs are from the [original ESP-only project](https://github.com/maddenste/Chouchin-CH899-Firmware). Personal flash backups, credentials and private captures are not published.
