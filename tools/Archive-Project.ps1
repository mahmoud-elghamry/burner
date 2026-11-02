# Archives the TIA project into one compressed file (.zap15_1) that opens in
# TIA Portal V15.1 on another PC. Read-only on the project. TIA must be closed.
param(
    [string]$ProjectPath = ((Get-ChildItem (Join-Path $PSScriptRoot "..\tia") -Recurse -Filter "*.ap15_1" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName),
    [string]$OutDir      = (Join-Path $PSScriptRoot "..\build\for-manager"),
    [string]$Name        = ("LCP-01_" + (Get-Date -Format 'yyyy-MM-dd')),
    [string]$ApiDir      = "C:\Program Files\Siemens\Automation\Portal V15_1\PublicAPI\V15.1"
)
$ErrorActionPreference = 'Stop'
$ProjectPath = [System.IO.Path]::GetFullPath($ProjectPath)
$OutDir = [System.IO.Path]::GetFullPath($OutDir)
if (Get-Process -Name 'Siemens.Automation.Portal' -ErrorAction SilentlyContinue) { throw "TIA Portal is open. Close it first." }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$engDll = Join-Path $ApiDir 'Siemens.Engineering.dll'
[System.Reflection.Assembly]::LoadFrom($engDll) | Out-Null
Add-Type -ReferencedAssemblies $engDll -TypeDefinition @'
using System.IO; using Siemens.Engineering;
public static class Arch { public static void Run(string prj, string outDir, string name) {
  var portal = new TiaPortal(TiaPortalMode.WithoutUserInterface);
  Project p = null;
  try { p = portal.Projects.Open(new FileInfo(prj));
        p.Archive(new DirectoryInfo(outDir), name + ".zap15_1", ProjectArchivationMode.Compressed);
        System.Console.WriteLine("OK " + Path.Combine(outDir, name + ".zap15_1")); }
  finally { try { if (p != null) p.Close(); } catch { } portal.Dispose(); }
}}
'@
[Arch]::Run($ProjectPath, $OutDir, $Name)
