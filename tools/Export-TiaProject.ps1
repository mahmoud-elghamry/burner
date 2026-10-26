<#
    Export-TiaProject.ps1
    -------------------------------------------------------------
    Exports a TIA Portal V15.1 project to XML using the Openness API.

      - PLC program blocks (OB/FB/FC/DB)  -> ProgramBlocks\**\*.xml
      - PLC data types (UDT)              -> PlcDataTypes\*.xml
      - PLC tag tables                    -> PlcTags\*.xml
      - HMI screens / templates / tags    -> HMI_<name>\**\*.xml

    REQUIREMENTS
      1. TIA Portal V15.1 installed (it is).
      2. The current Windows user must be a member of the local group
         "Siemens TIA Openness", then sign out and sign back in.
      3. TIA Portal must be CLOSED (project must not be locked).

    USAGE
      powershell -ExecutionPolicy Bypass -File .\Export-TiaProject.ps1
#>

[CmdletBinding()]
param(
    [string]$ProjectPath = ((Get-ChildItem (Join-Path $PSScriptRoot "..\tia") -Recurse -Filter "*.ap15_1" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName),
    [string]$OutDir      = (Join-Path $PSScriptRoot "..\export\xml"),
    [string]$ApiDir      = "C:\Program Files\Siemens\Automation\Portal V15_1\PublicAPI\V15.1"
)

$ErrorActionPreference = 'Stop'

# Openness rejects paths that still contain relative segments, so collapse
# the '..' introduced by the $PSScriptRoot defaults before using them.
foreach ($v in 'ProjectPath','OutDir','BuildDir','ApiDir') {
    if (Get-Variable -Name $v -Scope Local -ErrorAction SilentlyContinue) {
        $cur = (Get-Variable -Name $v -ValueOnly)
        if ($cur) { Set-Variable -Name $v -Value ([System.IO.Path]::GetFullPath($cur)) }
    }
}

# ---------------------------------------------------------------- pre-flight
if (-not (Test-Path $ProjectPath)) { throw "Project not found: $ProjectPath" }
if (-not (Test-Path $ApiDir))      { throw "Openness API folder not found: $ApiDir" }

$inGroup = $false
try {
    $me = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $sid = (Get-LocalGroup -Name 'Siemens TIA Openness').SID
    $inGroup = $me.Groups -contains $sid
} catch { }
if (-not $inGroup) {
    Write-Warning @"
The current user ($env:USERNAME) does not appear to be in the local group
"Siemens TIA Openness". Openness will refuse to start.

Fix (run ONE TIME in an *Administrator* PowerShell / CMD, then sign out & back in):

    net localgroup "Siemens TIA Openness" $env:USERNAME /add

Continuing anyway...
"@
}

if (Get-Process -Name 'Siemens.Automation.Portal' -ErrorAction SilentlyContinue) {
    Write-Warning "TIA Portal seems to be running. Close it first or the project will be locked."
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# ------------------------------------------------------- assembly resolution
# NOTE: do NOT install a PowerShell AssemblyResolve handler here. Openness raises
# AssemblyResolve re-entrantly while starting up and a scriptblock handler that
# calls Assembly.LoadFrom recurses until the process dies with an uncatchable
# StackOverflowException. Loading the two public API DLLs up front is enough -
# Openness resolves its own internal assemblies by itself.
$script:ApiDirResolved = (Resolve-Path $ApiDir).Path

$engDll = Join-Path $ApiDirResolved 'Siemens.Engineering.dll'
$hmiDll = Join-Path $ApiDirResolved 'Siemens.Engineering.Hmi.dll'
[System.Reflection.Assembly]::LoadFrom($engDll) | Out-Null
[System.Reflection.Assembly]::LoadFrom($hmiDll) | Out-Null
Write-Host "Loaded Openness assemblies from $ApiDirResolved" -ForegroundColor Cyan

# --------------------------------------------------------------- PLC exporter
$plcSource = @'
using System;
using System.IO;
using System.Text;
using Siemens.Engineering;
using Siemens.Engineering.HW;
using Siemens.Engineering.HW.Features;
using Siemens.Engineering.SW;
using Siemens.Engineering.SW.Blocks;
using Siemens.Engineering.SW.Tags;
using Siemens.Engineering.SW.Types;

public class TiaPlcExporter
{
    public static StringBuilder Log = new StringBuilder();
    public static int Ok, Failed, Protected;

    static void L(string s)
    {
        Console.WriteLine(s);
        Log.AppendLine(s);
    }

    static string Safe(string n)
    {
        foreach (char c in Path.GetInvalidFileNameChars()) n = n.Replace(c, '_');
        return n.Trim();
    }

    public static TiaPortal Portal;
    public static Project Prj;

    public static void Open(string projectPath)
    {
        Portal = new TiaPortal(TiaPortalMode.WithoutUserInterface);
        L("Opening " + projectPath);
        Prj = Portal.Projects.Open(new FileInfo(projectPath));
        L("Project opened: " + Prj.Name);
    }

    public static void Close()
    {
        try { if (Prj != null) Prj.Close(); } catch { }
        try { if (Portal != null) Portal.Dispose(); } catch { }
    }

    public static void ExportAll(string outDir)
    {
        foreach (Device d in Prj.Devices) Walk(d, outDir);
        foreach (DeviceUserGroup g in Prj.DeviceGroups) WalkGroup(g, outDir);
        L("");
        L("PLC summary -> exported: " + Ok + ", protected(skipped): " + Protected + ", failed: " + Failed);
    }

    static void WalkGroup(DeviceUserGroup g, string outDir)
    {
        foreach (Device d in g.Devices) Walk(d, outDir);
        foreach (DeviceUserGroup sub in g.Groups) WalkGroup(sub, outDir);
    }

    static void Walk(Device device, string outDir)
    {
        foreach (DeviceItem it in device.DeviceItems) WalkItem(it, outDir, 0);
    }

    // depth is capped so a deep/cyclic DeviceItems graph cannot blow the stack
    static void WalkItem(DeviceItem item, string outDir, int depth)
    {
        if (depth > 12) return;
        try
        {
            SoftwareContainer sc = item.GetService<SoftwareContainer>();
            if (sc != null)
            {
                PlcSoftware plc = sc.Software as PlcSoftware;
                if (plc != null) ExportPlc(plc, outDir);
            }
        }
        catch (Exception ex) { L("WARN device item " + item.Name + ": " + ex.Message); }

        foreach (DeviceItem sub in item.DeviceItems) WalkItem(sub, outDir, depth + 1);
    }

    static void ExportPlc(PlcSoftware plc, string root)
    {
        string b = Path.Combine(root, "PLC_" + Safe(plc.Name));
        L("");
        L("=== PLC: " + plc.Name + " ===");
        ExportBlockGroup(plc.BlockGroup, Path.Combine(b, "ProgramBlocks"));
        ExportTypeGroup(plc.TypeGroup, Path.Combine(b, "PlcDataTypes"));
        ExportTagGroup(plc.TagTableGroup, Path.Combine(b, "PlcTags"));
    }

    static void ExportBlockGroup(PlcBlockGroup group, string dir)
    {
        Directory.CreateDirectory(dir);
        foreach (PlcBlock blk in group.Blocks)
        {
            try
            {
                if (blk.IsKnowHowProtected)
                {
                    Protected++;
                    L("PROTECTED  " + blk.Name + "  (know-how protected, skipped)");
                    continue;
                }
                string f = Path.Combine(dir, Safe(blk.Name) + ".xml");
                if (File.Exists(f)) File.Delete(f);
                blk.Export(new FileInfo(f), ExportOptions.WithDefaults);
                Ok++;
                L("OK   " + blk.Name + "   [" + blk.ProgrammingLanguage + "]");
            }
            catch (Exception ex)
            {
                Failed++;
                L("FAIL " + blk.Name + " : " + ex.Message);
            }
        }
        foreach (PlcBlockUserGroup sub in group.Groups)
            ExportBlockGroup(sub, Path.Combine(dir, Safe(sub.Name)));
    }

    static void ExportTypeGroup(PlcTypeGroup group, string dir)
    {
        Directory.CreateDirectory(dir);
        foreach (PlcType t in group.Types)
        {
            try
            {
                string f = Path.Combine(dir, Safe(t.Name) + ".xml");
                if (File.Exists(f)) File.Delete(f);
                t.Export(new FileInfo(f), ExportOptions.WithDefaults);
                Ok++;
                L("OK   UDT " + t.Name);
            }
            catch (Exception ex) { Failed++; L("FAIL UDT " + t.Name + " : " + ex.Message); }
        }
        foreach (PlcTypeUserGroup sub in group.Groups)
            ExportTypeGroup(sub, Path.Combine(dir, Safe(sub.Name)));
    }

    static void ExportTagGroup(PlcTagTableGroup group, string dir)
    {
        Directory.CreateDirectory(dir);
        foreach (PlcTagTable t in group.TagTables)
        {
            try
            {
                string f = Path.Combine(dir, Safe(t.Name) + ".xml");
                if (File.Exists(f)) File.Delete(f);
                t.Export(new FileInfo(f), ExportOptions.WithDefaults);
                Ok++;
                L("OK   TagTable " + t.Name);
            }
            catch (Exception ex) { Failed++; L("FAIL TagTable " + t.Name + " : " + ex.Message); }
        }
        foreach (PlcTagTableUserGroup sub in group.Groups)
            ExportTagGroup(sub, Path.Combine(dir, Safe(sub.Name)));
    }
}
'@

Add-Type -TypeDefinition $plcSource -ReferencedAssemblies $engDll, 'System.Core' -ErrorAction Stop
Write-Host "PLC exporter compiled." -ForegroundColor Cyan

# --------------------------------------------------------------- HMI exporter
$hmiCompiled = $false
$hmiSource = @'
using System;
using System.IO;
using System.Text;
using Siemens.Engineering;
using Siemens.Engineering.HW;
using Siemens.Engineering.HW.Features;
using Siemens.Engineering.Hmi;
using Siemens.Engineering.Hmi.Screen;
using Siemens.Engineering.Hmi.Tag;

public class TiaHmiExporter
{
    public static StringBuilder Log = new StringBuilder();
    public static int Ok, Failed;

    static void L(string s) { Console.WriteLine(s); Log.AppendLine(s); }

    static string Safe(string n)
    {
        foreach (char c in Path.GetInvalidFileNameChars()) n = n.Replace(c, '_');
        return n.Trim();
    }

    public static void ExportAll(Project prj, string outDir)
    {
        foreach (Device d in prj.Devices)
            foreach (DeviceItem it in d.DeviceItems) WalkItem(it, outDir, 0);
        foreach (DeviceUserGroup g in prj.DeviceGroups) WalkGroup(g, outDir);
        L("");
        L("HMI summary -> exported: " + Ok + ", failed: " + Failed);
    }

    static void WalkGroup(DeviceUserGroup g, string outDir)
    {
        foreach (Device d in g.Devices)
            foreach (DeviceItem it in d.DeviceItems) WalkItem(it, outDir, 0);
        foreach (DeviceUserGroup sub in g.Groups) WalkGroup(sub, outDir);
    }

    static void WalkItem(DeviceItem item, string outDir, int depth)
    {
        if (depth > 12) return;
        try
        {
            SoftwareContainer sc = item.GetService<SoftwareContainer>();
            if (sc != null)
            {
                HmiTarget hmi = sc.Software as HmiTarget;
                if (hmi != null) ExportHmi(hmi, outDir);
            }
        }
        catch (Exception ex) { L("WARN hmi item " + item.Name + ": " + ex.Message); }

        foreach (DeviceItem sub in item.DeviceItems) WalkItem(sub, outDir, depth + 1);
    }

    static void ExportHmi(HmiTarget hmi, string root)
    {
        string b = Path.Combine(root, "HMI_" + Safe(hmi.Name));
        L("");
        L("=== HMI: " + hmi.Name + " ===");
        ExportScreenFolder(hmi.ScreenFolder, Path.Combine(b, "Screens"));
        ExportTagFolder(hmi.TagFolder, Path.Combine(b, "HmiTags"));
    }

    static void ExportScreenFolder(ScreenFolder folder, string dir)
    {
        Directory.CreateDirectory(dir);
        foreach (Screen s in folder.Screens)
        {
            try
            {
                string f = Path.Combine(dir, Safe(s.Name) + ".xml");
                if (File.Exists(f)) File.Delete(f);
                s.Export(new FileInfo(f), ExportOptions.WithDefaults);
                Ok++;
                L("OK   Screen " + s.Name);
            }
            catch (Exception ex) { Failed++; L("FAIL Screen " + s.Name + " : " + ex.Message); }
        }
        foreach (ScreenUserFolder sub in folder.Folders)
            ExportScreenFolder(sub, Path.Combine(dir, Safe(sub.Name)));
    }

    static void ExportTagFolder(TagFolder folder, string dir)
    {
        Directory.CreateDirectory(dir);
        foreach (TagTable t in folder.TagTables)
        {
            try
            {
                string f = Path.Combine(dir, Safe(t.Name) + ".xml");
                if (File.Exists(f)) File.Delete(f);
                t.Export(new FileInfo(f), ExportOptions.WithDefaults);
                Ok++;
                L("OK   HmiTagTable " + t.Name);
            }
            catch (Exception ex) { Failed++; L("FAIL HmiTagTable " + t.Name + " : " + ex.Message); }
        }
        foreach (TagUserFolder sub in folder.Folders)
            ExportTagFolder(sub, Path.Combine(dir, Safe(sub.Name)));
    }
}
'@

try {
    Add-Type -TypeDefinition $hmiSource -ReferencedAssemblies $engDll, $hmiDll, 'System.Core' -ErrorAction Stop
    $hmiCompiled = $true
    Write-Host "HMI exporter compiled." -ForegroundColor Cyan
} catch {
    Write-Warning "HMI exporter did not compile (API name mismatch) - PLC export will still run.`n$($_.Exception.Message)"
}

# ------------------------------------------------------------------- run
$logPath = Join-Path (Split-Path $OutDir -Parent) 'export-log.txt'
try {
    [TiaPlcExporter]::Open($ProjectPath)
    [TiaPlcExporter]::ExportAll($OutDir)

    if ($hmiCompiled) {
        try { [TiaHmiExporter]::ExportAll([TiaPlcExporter]::Prj, $OutDir) }
        catch { Write-Warning "HMI export failed: $($_.Exception.Message)" }
    }
}
finally {
    $log = [TiaPlcExporter]::Log.ToString()
    if ($hmiCompiled) { $log += "`r`n" + [TiaHmiExporter]::Log.ToString() }
    $log | Out-File -FilePath $logPath -Encoding utf8
    [TiaPlcExporter]::Close()
    Write-Host ""
    Write-Host "Done. XML -> $OutDir" -ForegroundColor Green
    Write-Host "Log  -> $logPath" -ForegroundColor Green
}
