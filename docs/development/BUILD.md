# Build the supplied source

For developers. Prepared installation files will be listed on [the downloads page](../DOWNLOADS.md) when available; ordinary users should not need to compile.

Building, exporting and flashing are separate operations. Nothing in these build/test steps flashes a clock.

## MM32

Use **Arm Compiler 6.24** and PowerShell. Obtain the compiler under its own terms. A device pack is needed for the supplied µVision programming project, but the scripted C build does not bundle a vendor SDK/library.

From the repository root, specify your actual compiler location:

```powershell
& ./firmware/mm32/build.ps1 -CompilerPath 'C:/path/to/ARMCLANG/bin/armclang.exe'
```

The script compiles Cortex-M0 Thumb GNU C11 at `-Os -Wall -Wextra -Werror`, links the supplied startup, application, UART, RTC and motor code, enforces the stack reservation, then exports Intel HEX using `fromelf.exe` beside armclang. Artifacts are in `firmware/mm32/build/` and are ignored by Git. It does not invoke a programmer.

The default compiler path in this retained candidate script reflects the development PC; use the parameter elsewhere. The µVision project is provided for programming the matching built HEX, not as an independently maintained second application build recipe.

## ESP8285

Install Arduino CLI and **ESP8266 by ESP8266 Community 3.1.2** separately. Then:

```powershell
& ./firmware/esp/Build-ESP.ps1 -ArduinoCli 'C:/path/to/arduino-cli.exe'
```

The build regenerates `web_ui.h` from `web/index.html` and compiles FQBN `esp8266:esp8266:esp8285:eesz=autoflash`. It verifies core 3.1.2 is installed. The output is under `firmware/esp/build/`; the temporary Arduino build directory is outside the Git tree. No external webpage fonts/scripts are required at runtime.

Edit the HTML and regenerate `web_ui.h` rather than editing that header directly. Rebuild before distributing a changed BIN. Compare the emitted hash with [the build identity](RELEASE_IDENTITY.md); record and investigate differences before publication.

## Verify and test

`python tools/verify_repository.py` performs dependency-free documentation/source-manifest checks. Follow [TESTING.md](TESTING.md) for compiled ARM model and mocked-browser tests. Those tests are not a physical motor/radio emulator.

Windows PowerShell may restrict unsigned scripts on a network share. Review the scripts and apply your organization's approved execution policy; no permanent machine-wide policy change is required by the project.
