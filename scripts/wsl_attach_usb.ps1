param(
    [Parameter(Mandatory = $true)]
    [string]$BusId
)

# Run in an elevated PowerShell prompt (Admin) on Windows.
# Example:
#   .\scripts\wsl_attach_usb.ps1 -BusId 4-4

usbipd bind --busid $BusId
usbipd attach --wsl --busid $BusId
