<#
    Remove-Blocks.ps1
    Removes obsolete blocks from PLC_1, then saves the project.
    Modelled on Apply-Blocks.ps1; TIA Portal must be CLOSED.

      .\Remove-Blocks.ps1 -Names Sys,Common

    -DryRun resolves and reports the blocks without deleting or saving.
    Run after importing the Rev B replacements so Main no longer
    calls the obsolete FCs. This script does not import or compile blocks.
#>
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Names,
    [string]$ProjectPath,
    [string]$ApiDir = "C:\Program Files\Siemens\Automation\Portal V15_1\PublicAPI\V15.1",
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
if (-not $ProjectPath) { $ProjectPath = (Get-ChildItem (Join-Path $PSScriptRoot "..\tia") -Recurse -Filter "*.ap15_1" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName }
foreach ($v in 'ProjectPath','ApiDir') {
    $cur = Get-Variable -Name $v -ValueOnly
    if ($cur) { Set-Variable -Name $v -Value ([System.IO.Path]::GetFullPath($cur)) }
}
$Names = @($Names | ForEach-Object { $_.Split(',') } | ForEach-Object { $_.Trim() } | Select-Object -Unique)
foreach ($name in $Names) {
    if ($name -notin @('Sys','Common')) { throw "not an obsolete Rev B block: $name" }
}
Write-Host "project : $ProjectPath"
Write-Host "remove  : $($Names -join ',')"
if (Get-Process -Name 'Siemens.Automation.Portal' -ErrorAction SilentlyContinue) {
    throw "TIA Portal is running. Close it first."
}
if (-not $ProjectPath -or -not (Test-Path -LiteralPath $ProjectPath -PathType Leaf)) { throw "project not found: $ProjectPath" }
$engDll = Join-Path $ApiDir 'Siemens.Engineering.dll'
[System.Reflection.Assembly]::LoadFrom($engDll) | Out-Null

$src = @'
using System;
using System.IO;
using System.Collections.Generic;
using Siemens.Engineering;
using Siemens.Engineering.HW;
using Siemens.Engineering.HW.Features;
using Siemens.Engineering.SW;
using Siemens.Engineering.SW.Blocks;

public class BlockRemover
{
    public static bool Run(string projectPath, string[] names, bool dryRun)
    {
        TiaPortal portal = new TiaPortal(TiaPortalMode.WithoutUserInterface);
        Project prj = null;
        try
        {
            prj = portal.Projects.Open(new FileInfo(projectPath));
            Console.WriteLine("project opened: " + prj.Name);
            List<PlcSoftware> plcs = new List<PlcSoftware>();
            FindDevices(prj.Devices, plcs);
            foreach (DeviceUserGroup group in prj.DeviceGroups) FindGroup(group, plcs);
            if (plcs.Count != 1) throw new Exception("expected exactly one PLC_1; found " + plcs.Count);
            PlcSoftware plc = plcs[0];
            Console.WriteLine("PLC: " + plc.Name);
            List<PlcBlock> blocks = new List<PlcBlock>(AllBlocks(plc.BlockGroup));
            List<PlcBlock> targets = new List<PlcBlock>();
            // Resolve every name before performing any deletion.
            foreach (string name in names)
            {
                List<PlcBlock> matches = blocks.FindAll(b => b.Name == name);
                if (matches.Count > 1) throw new Exception("duplicate block name: " + name);
                if (matches.Count == 0) Console.WriteLine("  already absent: " + name);
                else targets.Add(matches[0]);
            }
            Console.WriteLine("=== REMOVING ===");
            foreach (PlcBlock block in targets)
            {
                string name = block.Name;
                if (dryRun) Console.WriteLine("  would remove: " + name);
                else { block.Delete(); Console.WriteLine("  removed: " + name); }
            }
            if (dryRun) { Console.WriteLine("DRY RUN - project NOT saved."); return true; }
            prj.Save();
            Console.WriteLine("PROJECT SAVED.");
            return true;
        }
        catch (Exception ex)
        {
            Console.WriteLine("EXCEPTION - project NOT saved: " + ex.Message);
            return false;
        }
        finally
        {
            try { if (prj != null) prj.Close(); } catch { }
            try { portal.Dispose(); } catch { }
        }
    }

    static void FindDevices(DeviceComposition devices, List<PlcSoftware> found)
    {
        foreach (Device device in devices)
            foreach (DeviceItem item in device.DeviceItems) Walk(item, 0, found);
    }
    static void FindGroup(DeviceUserGroup group, List<PlcSoftware> found)
    {
        FindDevices(group.Devices, found);
        foreach (DeviceUserGroup sub in group.Groups) FindGroup(sub, found);
    }
    static void Walk(DeviceItem item, int depth, List<PlcSoftware> found)
    {
        if (depth > 12) return;
        SoftwareContainer sc = item.GetService<SoftwareContainer>();
        PlcSoftware plc = sc == null ? null : sc.Software as PlcSoftware;
        if (plc != null && plc.Name == "PLC_1" && !found.Contains(plc)) found.Add(plc);
        foreach (DeviceItem sub in item.DeviceItems) Walk(sub, depth + 1, found);
    }
    static IEnumerable<PlcBlock> AllBlocks(PlcBlockGroup group)
    {
        foreach (PlcBlock block in group.Blocks) yield return block;
        foreach (PlcBlockGroup sub in group.Groups)
            foreach (PlcBlock block in AllBlocks(sub)) yield return block;
    }
}
'@
Add-Type -TypeDefinition $src -ReferencedAssemblies $engDll, 'System.Core' -ErrorAction Stop
if (-not [BlockRemover]::Run($ProjectPath, $Names, [bool]$DryRun)) { exit 1 }
