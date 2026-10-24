# Storage Controller & SMBIOS Architecture Specification

## 1. Overview
This specification details low-level hardware identity extraction and communication mechanisms across Windows storage and firmware subsystems.

## 2. Firmware Identification via SMBIOS
The system firmware table provider retrieves SMBIOS tables using `GetSystemFirmwareTable` (`'RSMB'` provider).
The firmware table structure encompasses:
- Types 0 (BIOS Information), 1 (System Information), 2 (Baseboard Information), 3 (System Enclosure/Chassis), 4 (Processor Information), 11 (OEM Strings), and 17 (Memory Device).

Corresponding WMI queries map to:
- `Win32_BIOS` (SerialNumber, SMBIOSBIOSVersion, Manufacturer)
- `Win32_BaseBoard` (SerialNumber, Product, Manufacturer)
- `Win32_DiskDrive` (SerialNumber, Model, PNPDeviceID)

```powershell
Get-CimInstance -Namespace root\cimv2 -ClassName Win32_BIOS
```

## 3. Storage Driver IOCTL Dispatch
Storage telemetry and queries are handled via `\\Device\\Harddisk0\\DR0` through direct kernel control codes:

| Control Code | Hex Code | Dispatch Routine |
| :--- | :--- | :--- |
| `IOCTL_STORAGE_QUERY_PROPERTY` | `0x2D1400` | Storage device property descriptor |
| `IOCTL_DISK_GET_DRIVE_GEOMETRY_EX` | `0x700A0` | Extended geometry and partition layout |
| `IOCTL_SCSI_PASS_THROUGH_DIRECT` | `0x4D014` | SCSI miniport command bypass |

Kernel dispatch invokes `NtDeviceIoControlFile` and handles buffered completion through `DeviceIoControl`.
