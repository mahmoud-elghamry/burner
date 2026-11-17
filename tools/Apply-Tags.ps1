<#
    Apply-Tags.ps1
    ------------------------------------------------------------------
    Imports one or more generated PLC tag table documents (SimaticML, made by
    tools/build_tags.py) into the TIA project with ImportOverwrite, compiles
    the CPU (hardware + software) and then every block, reports consistency,
    and saves only when there are no errors.

      .\Apply-Tags.ps1 -Files tags\IO.xml -DryRun

    Files are resolved inside -BuildDir (build\) and imported IN THE ORDER GIVEN.

    TIA Portal must be CLOSED. -DryRun does everything except Save.

    Compile sequence: device (CPU) compile, then each block, then IsConsistent,
    as in Apply-Blocks.ps1. PlcSoftware is not compiled on its own: on this
    setup it reports "aborted" (see the crane project's Apply-Watchdog.ps1).

    NOTE: do NOT add a PowerShell AssemblyResolve handler here. Openness
    raises AssemblyResolve re-entrantly while starting up, and a scriptblock
    handler that calls Assembly.LoadFrom recurses until the process dies with
    an uncatchable StackOverflowException - no stack trace, no log.
#>
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Files,
    [string]$ProjectPath,
    [string]$BuildDir,
    [string]$ApiDir = "C:\Program Files\Siemens\Automation\Portal V15_1\PublicAPI\V15.1",
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'

# $PSScriptRoot is empty while param defaults are evaluated on an advanced
# script, so the repo-relative paths are built here in the body instead.
$root = Split-Path -Parent $PSScriptRoot
if (-not $ProjectPath) { $ProjectPath = (Get-ChildItem (Join-Path $PSScriptRoot "..\tia") -Recurse -Filter "*.ap15_1" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName }
if (-not $BuildDir)    { $BuildDir    = Join-Path $root "build" }

# Openness rejects paths that still contain relative segments.
foreach ($v in 'ProjectPath','BuildDir','ApiDir') {
    $cur = (Get-Variable -Name $v -ValueOnly)
    if ($cur) { Set-Variable -Name $v -Value ([System.IO.Path]::GetFullPath($cur)) }
}
if (-not $ProjectPath -or -not (Test-Path $ProjectPath)) { throw "no *.ap15_1 project found under tia\" }
Write-Host "project : $ProjectPath"
Write-Host "build   : $BuildDir"

if (Get-Process -Name 'Siemens.Automation.Portal' -ErrorAction SilentlyContinue) {
    throw "TIA Portal is running. Close it first."
}

foreach ($f in $Files) {
    $p = Join-Path $BuildDir $f
    if (-not (Test-Path $p)) { throw "missing build file: $p" }
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
    public static int ErrorCount = 0;
    static DeviceItem CpuItem = null;

    public static void Run(string projectPath, string buildDir, string[] files, bool dryRun)
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

            Console.WriteLine("=== IMPORTING TAG TABLES ===");
            foreach (string f in files)
                ImportTags(plc, Path.Combine(buildDir, f));

            Console.WriteLine("");
            Console.WriteLine("=== COMPILING (device: hardware + software) ===");
            CompileDevice(plc);

            Console.WriteLine("");
            Console.WriteLine("=== COMPILING (every block) ===");
            foreach (PlcBlock b in plc.BlockGroup.Blocks)
            {
                ICompilable bc = b.GetService<ICompilable>();
                if (bc == null) { Console.WriteLine("  no compiler for " + b.Name); continue; }
                CompilerResult r = bc.Compile();
                Console.WriteLine("  " + b.Name + ": state=" + r.State
                                  + " errors=" + r.ErrorCount + " warnings=" + r.WarningCount);
                ErrorCount += Problems(r);
                foreach (CompilerResultMessage m in r.Messages) Print(m, "      ");
            }

            Console.WriteLine("");
            Console.WriteLine("=== CONSISTENCY ===");
            int bad = 0, total = 0;
            foreach (PlcBlock b in plc.BlockGroup.Blocks)
            {
                total++;
                if (!b.IsConsistent) { bad++; Console.WriteLine("  INCONSISTENT: " + b.Name); }
            }
            Console.WriteLine("  consistent " + (total - bad) + "/" + total);
            ErrorCount += bad;

            Console.WriteLine("");
            Console.WriteLine("=== TAG TABLES IN PROJECT ===");
            foreach (PlcTagTable t in plc.TagTableGroup.TagTables)
                Console.WriteLine("  " + t.Name + ": " + t.Tags.Count + " tags");

            Console.WriteLine("");
            if (dryRun)      Console.WriteLine("DRY RUN - project NOT saved.");
            else if (ErrorCount == 0) { prj.Save(); Console.WriteLine("PROJECT SAVED."); }
            else Console.WriteLine("ERRORS (" + ErrorCount + ") - project NOT saved.");
        }
        finally
        {
            try { if (prj != null) prj.Close(); } catch { }
            try { portal.Dispose(); } catch { }
        }
    }

    static PlcSoftware FindPlc(Project prj)
    {
        foreach (Device d in prj.Devices)
            foreach (DeviceItem it in d.DeviceItems)
            {
                PlcSoftware p = Walk(it, 0);
                if (p != null) return p;
            }
        return null;
    }

    // PlcSoftware hangs off a SoftwareContainer on a NESTED DeviceItem,
    // not on the Device. Cap the depth so a deep graph cannot blow the stack.
    static PlcSoftware Walk(DeviceItem item, int depth)
    {
        if (depth > 12) return null;
        try
        {
            SoftwareContainer sc = item.GetService<SoftwareContainer>();
            if (sc != null)
            {
                PlcSoftware p = sc.Software as PlcSoftware;
                if (p != null) { CpuItem = item; return p; }
            }
        }
        catch { }
        foreach (DeviceItem sub in item.DeviceItems)
        {
            PlcSoftware p = Walk(sub, depth + 1);
            if (p != null) return p;
        }
        return null;
    }

    static void ImportTags(PlcSoftware plc, string file)
    {
        if (!File.Exists(file)) throw new Exception("missing " + file);
        IList<PlcTagTable> imported = plc.TagTableGroup.TagTables.Import(
            new FileInfo(file), ImportOptions.Override);
        foreach (PlcTagTable t in imported)
            Console.WriteLine("  imported table: " + t.Name + " (" + t.Tags.Count + " tags)");
    }

    // A compile that reports State=Error without any error count was aborted;
    // count it as one error so the project is never saved on an aborted compile.
    static int Problems(CompilerResult r)
    {
        if (r.ErrorCount > 0) return r.ErrorCount;
        if (r.State == CompilerResultState.Error) return 1;
        return 0;
    }

    static void CompileDevice(PlcSoftware plc)
    {
        ICompilable compiler = null;
        if (CpuItem != null) compiler = CpuItem.GetService<ICompilable>();
        if (compiler == null) compiler = plc.GetService<ICompilable>();
        if (compiler == null) { Console.WriteLine("  no compiler found"); ErrorCount += 1; return; }

        CompilerResult result = compiler.Compile();
        Console.WriteLine("state=" + result.State
                          + "  errors=" + result.ErrorCount
                          + "  warnings=" + result.WarningCount);
        foreach (CompilerResultMessage m in result.Messages) Print(m, "  ");
        ErrorCount += Problems(result);
    }

    static void Print(CompilerResultMessage m, string pad)
    {
        string desc = m.Description;
        if (string.IsNullOrEmpty(desc)) desc = "(no text)";
        Console.WriteLine(pad + "[" + m.State + "] " + desc
                          + (string.IsNullOrEmpty(m.Path) ? "" : "   @ " + m.Path));
        foreach (CompilerResultMessage sub in m.Messages) Print(sub, pad + "    ");
    }
}
'@

Add-Type -TypeDefinition $src -ReferencedAssemblies $engDll, 'System.Core' -ErrorAction Stop
[TagApplier]::Run($ProjectPath, $BuildDir, $Files, [bool]$DryRun)
