<#
    Apply-Tags.ps1
    ------------------------------------------------------------------
    Imports one or more generated SimaticML PLC tag tables into the TIA
    project, compiles, prints compiler messages, and saves only after a clean
    compile. Files are resolved inside -BuildDir and imported in order.

    TIA Portal must be CLOSED. -DryRun imports and compiles but does not save.

    NOTE: do NOT add a PowerShell AssemblyResolve handler here. Openness raises
    AssemblyResolve re-entrantly while starting up, and a handler that calls
    Assembly.LoadFrom can recurse until the process dies with an uncatchable
    StackOverflowException.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Files,
    [string]$ProjectPath,
    [string]$BuildDir,
    [string]$ApiDir = "C:\Program Files\Siemens\Automation\Portal V15_1\PublicAPI\V15.1",
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
if (-not $ProjectPath) {
    $ProjectPath = (Get-ChildItem (Join-Path $PSScriptRoot "..\tia") -Recurse -Filter "*.ap15_1" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
}
if (-not $ProjectPath) { throw "No *.ap15_1 project found under tia\" }
if (-not $BuildDir) { $BuildDir = Join-Path $root "build" }

foreach ($v in 'ProjectPath','BuildDir','ApiDir') {
    $cur = (Get-Variable -Name $v -ValueOnly)
    if ($cur) { Set-Variable -Name $v -Value ([System.IO.Path]::GetFullPath($cur)) }
}
$buildPrefix = $BuildDir.TrimEnd('\') + '\'
$resolvedFiles = @()
foreach ($f in $Files) {
    $p = [System.IO.Path]::GetFullPath((Join-Path $BuildDir $f))
    if (-not $p.StartsWith($buildPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "tag table must be inside build\: $f"
    }
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "missing build file: $p" }
    $resolvedFiles += $p
}
if (-not (Test-Path -LiteralPath $ProjectPath -PathType Leaf)) { throw "project not found: $ProjectPath" }

Write-Host "project : $ProjectPath"
Write-Host "build   : $BuildDir"
if (Get-Process -Name 'Siemens.Automation.Portal' -ErrorAction SilentlyContinue) {
    throw "TIA Portal is running. Close it first."
}

$engDll = Join-Path $ApiDir 'Siemens.Engineering.dll'
[System.Reflection.Assembly]::LoadFrom($engDll) | Out-Null

$src = @'
using System;
using System.IO;
using System.Collections.Generic;
using Siemens.Engineering;
using Siemens.Engineering.Compiler;
using Siemens.Engineering.HW;
using Siemens.Engineering.HW.Features;
using Siemens.Engineering.SW;
using Siemens.Engineering.SW.Blocks;
using Siemens.Engineering.SW.Tags;

public class TagApplier
{
    static List<string> Failures = new List<string>();
    static DeviceItem CpuItem = null;

    public static bool Run(string projectPath, string[] files, bool dryRun)
    {
        TiaPortal portal = new TiaPortal(TiaPortalMode.WithoutUserInterface);
        Project prj = null;
        try
        {
            prj = portal.Projects.Open(new FileInfo(projectPath));
            Console.WriteLine("project opened: " + prj.Name);

            PlcSoftware plc = FindPlc(prj);
            if (plc == null) throw new Exception("PLC software not found");
            Console.WriteLine("PLC: " + plc.Name);

            Console.WriteLine("");
            Console.WriteLine("=== IMPORTING TAG TABLES (overwrite) ===");
            foreach (string file in files) ImportTagTable(plc, file);

            Console.WriteLine("");
            Console.WriteLine("=== COMPILING (hardware) ===");
            ICompilable hardwareCompiler = CpuItem == null ? null : CpuItem.GetService<ICompilable>();
            if (hardwareCompiler == null) throw new Exception("CPU compiler not found");
            Check("hardware", RunCompile(hardwareCompiler));

            Console.WriteLine("");
            Console.WriteLine("=== COMPILING (PLC software) ===");
            ICompilable softwareCompiler = plc.GetService<ICompilable>();
            if (softwareCompiler == null) throw new Exception("PLC software compiler not found");
            Check("PLC software", RunCompile(softwareCompiler));

            Console.WriteLine("");
            Console.WriteLine("=== COMPILING (inconsistent blocks) ===");
            foreach (PlcBlock block in AllBlocks(plc.BlockGroup))
            {
                if (block.IsConsistent) continue;
                ICompilable blockCompiler = block.GetService<ICompilable>();
                if (blockCompiler == null)
                {
                    Failures.Add("block " + block.Name + ": no compiler");
                    Console.WriteLine("  no compiler for " + block.Name);
                    continue;
                }
                Check("block " + block.Name, RunCompile(blockCompiler));
            }

            Console.WriteLine("");
            Console.WriteLine("=== CHECKING BLOCK CONSISTENCY ===");
            int total = 0, inconsistent = 0;
            foreach (PlcBlock block in AllBlocks(plc.BlockGroup))
            {
                total++;
                if (block.IsConsistent) continue;
                inconsistent++;
                Failures.Add("block " + block.Name + " inconsistent");
                Console.WriteLine("  INCONSISTENT: " + block.Name);
            }
            Console.WriteLine("  consistent " + (total - inconsistent) + "/" + total);

            Console.WriteLine("");
            if (Failures.Count > 0)
            {
                Console.WriteLine("NOT CLEAN - project NOT saved:");
                foreach (string failure in Failures) Console.WriteLine("  - " + failure);
                return false;
            }
            if (dryRun)
            {
                Console.WriteLine("CLEAN. DRY RUN - project NOT saved.");
                return true;
            }
            prj.Save();
            Console.WriteLine("CLEAN. PROJECT SAVED.");
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

    static void ImportTagTable(PlcSoftware plc, string file)
    {
        IList<PlcTagTable> imported = plc.TagTableGroup.TagTables.Import(
            new FileInfo(file), ImportOptions.Override);
        foreach (PlcTagTable table in imported)
            Console.WriteLine("  imported: " + table.Name + " (" + table.Tags.Count + " tags)");
    }

    static CompilerResult RunCompile(ICompilable compiler)
    {
        CompilerResult result = compiler.Compile();
        Console.WriteLine("state=" + result.State + "  errors=" + result.ErrorCount
                          + "  warnings=" + result.WarningCount);
        foreach (CompilerResultMessage message in result.Messages) Print(message, "  ");
        return result;
    }

    static void Check(string what, CompilerResult result)
    {
        string state = result.State.ToString();
        bool acceptedState = state == "Success" || state == "Information" || state == "Warning";
        if (!acceptedState || result.ErrorCount != 0)
            Failures.Add(what + ": state=" + state + " errors=" + result.ErrorCount);
    }

    static IEnumerable<PlcBlock> AllBlocks(PlcBlockGroup group)
    {
        foreach (PlcBlock block in group.Blocks) yield return block;
        foreach (PlcBlockGroup sub in group.Groups)
            foreach (PlcBlock block in AllBlocks(sub)) yield return block;
    }

    static void Print(CompilerResultMessage message, string pad)
    {
        string description = message.Description;
        if (string.IsNullOrEmpty(description)) description = "(no text)";
        Console.WriteLine(pad + "[" + message.State + "] " + description
                          + (string.IsNullOrEmpty(message.Path) ? "" : "   @ " + message.Path));
        foreach (CompilerResultMessage sub in message.Messages) Print(sub, pad + "    ");
    }

    static PlcSoftware FindPlc(Project project)
    {
        foreach (Device device in project.Devices)
            foreach (DeviceItem item in device.DeviceItems)
            {
                PlcSoftware plc = Walk(item, 0);
                if (plc != null) return plc;
            }
        return null;
    }

    static PlcSoftware Walk(DeviceItem item, int depth)
    {
        if (depth > 12) return null;
        try
        {
            SoftwareContainer container = item.GetService<SoftwareContainer>();
            if (container != null)
            {
                PlcSoftware plc = container.Software as PlcSoftware;
                if (plc != null) { CpuItem = item; return plc; }
            }
        }
        catch { }
        foreach (DeviceItem sub in item.DeviceItems)
        {
            PlcSoftware plc = Walk(sub, depth + 1);
            if (plc != null) return plc;
        }
        return null;
    }
}
'@

Add-Type -TypeDefinition $src -ReferencedAssemblies $engDll, 'System.Core' -ErrorAction Stop
if (-not [TagApplier]::Run($ProjectPath, $resolvedFiles, [bool]$DryRun)) { exit 1 }
