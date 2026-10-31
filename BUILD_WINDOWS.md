# Build Sleep Sense for Windows

Run PowerShell from the project folder:

```powershell
.\build_windows.ps1
```

The script installs the build requirements, creates the application icon when
needed, builds the windowed PyInstaller distribution, and compiles the Inno
Setup installer.

Outputs:

- `dist\SleepSense\SleepSense.exe`
- `installer\SleepSense_Setup_3.0.0.exe`

To build only the unpacked application:

```powershell
.\build_windows.ps1 -SkipInstaller
```

Saved patient data is not stored under `Program Files`. It remains in the
current Windows user's persistent application-data folder:

```text
%LOCALAPPDATA%\SleepSense\data
```

Raw recordings selected through **Open Data Folder** are stored in:

```text
%LOCALAPPDATA%\SleepSense\data\raw_recordings
```
