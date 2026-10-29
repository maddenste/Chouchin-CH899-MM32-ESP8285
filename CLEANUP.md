# RC6BG — clean daily wake

RC6BG removes the temporary RC6BF reset recorder, reset-reason cookies, special SRAM retention and scheduled-wake timestamp stores. It also removes the extra memory barrier that surrounded the deleted cookie store. The ordinary reset path is restored.

Compared with public RC6BE, the complete MM32 application source now differs only in the three-second scheduled-wake admission check and the build identity (0x4D5052A4). Manual M.SET wake remains immediate. Existing operational health counters and fault protection are retained.

Motor, RTC and UART implementation files and ESP R13 source are unchanged. SRAM layout is unchanged. This cleanup has not been flashed or published; the live clock still uses RC6BF.

Local installer: output/MM32-RC6BG-Clean-Wake/Install-MM32-RC6BG.uvprojx.

Validation and exact image checksums are supplied with the installer. RC6BF remains available separately for rollback and investigation.
