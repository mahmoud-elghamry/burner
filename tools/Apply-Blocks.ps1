<#
    Apply-Blocks.ps1
    ------------------------------------------------------------------
    Imports one or more generated SimaticML block documents into the TIA
    project, compiles, reports consistency, and saves only on a clean
    compile. Generic replacement for the per-change Apply-*.ps1 scripts.

      .\Apply-Blocks.ps1 -Files HMI_Jog.xml,HMI_Jog_DB.xml,Main_jog.xml -DryRun

    Files are resolved inside -BuildDir and imported IN THE ORDER GIVEN.
    An FB must be imported before its instance DB, and before the OB that
    calls it.

    TIA Portal must be CLOSED. -DryRun does everything except Save.

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

public class BlockApplier
{
    static List<string> Failures = new List<string>();
    static DeviceItem CpuItem = null;

    public static bool Run(string projectPath, string buildDir, string[] files, bool dryRun)
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

            Console.WriteLine("=== IMPORTING ===");
            foreach (string f in files)
                ImportBlock(plc, Path.Combine(buildDir, f));

            Console.WriteLine("");
            Console.WriteLine("=== COMPILING (device) ===");
            Compile(plc);

            // On V15.1 the device compile refreshes the hardware only; blocks
            // stay inconsistent until each one is compiled on its own.
            Console.WriteLine("");
            Console.WriteLine("=== COMPILING (per block) ===");
            foreach (PlcBlock b in AllBlocks(plc.BlockGroup))
            {
                if (b.IsConsistent) continue;
                ICompilable bc = b.GetService<ICompilable>();
                if (bc == null)
                {
                    Console.WriteLine("  no compiler for " + b.Name);
                    Failures.Add("block " + b.Name + ": no compiler");
                    continue;
                }
                CompilerResult r = bc.Compile();
                Console.WriteLine("  " + b.Name + ": state=" + r.State
                                  + " errors=" + r.ErrorCount + " warnings=" + r.WarningCount);
                Check("block " + b.Name, r);
                foreach (CompilerResultMessage m in r.Messages) Print(m, "      ");
            }

            Console.WriteLine("");
            Console.WriteLine("=== CONSISTENCY ===");
            int bad = 0, total = 0;
            foreach (PlcBlock b in AllBlocks(plc.BlockGroup))
            {
                total++;
                if (!b.IsConsistent)
                {
                    bad++;
                    Console.WriteLine("  INCONSISTENT: " + b.Name);
                    Failures.Add("block " + b.Name + " inconsistent");
                }
            }
            Console.WriteLine("  consistent " + (total - bad) + "/" + total);

            Console.WriteLine("");
            if (Failures.Count > 0)
            {
                Console.WriteLine("NOT CLEAN - project NOT saved:");
                foreach (string f in Failures) Console.WriteLine("  - " + f);
                return false;
            }
            if (dryRun) { Console.WriteLine("CLEAN. DRY RUN - project NOT saved."); return true; }
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

    static void ImportBlock(PlcSoftware plc, string file)
    {
        if (!File.Exists(file)) throw new Exception("missing " + file);
        IList<PlcBlock> imported = plc.BlockGroup.Blocks.Import(
            new FileInfo(file), ImportOptions.Override);
        foreach (PlcBlock b in imported)
            Console.WriteLine("  imported: " + b.Name + " (" + b.GetType().Name + ")");
    }

    // Compiling PlcSoftware on its own returns state=Error with
    // "Compiling aborted (errors: 0; warnings: 0)" and no diagnostics on
    // V15.1. Compiling the CPU DeviceItem works and gives real messages.
    static void Compile(PlcSoftware plc)
    {
        ICompilable compiler = null;
        if (CpuItem != null) compiler = CpuItem.GetService<ICompilable>();
        if (compiler == null) compiler = plc.GetService<ICompilable>();

        CompilerResult result = compiler.Compile();
        Console.WriteLine("state=" + result.State
                          + "  errors=" + result.ErrorCount
                          + "  warnings=" + result.WarningCount);
        Check("device", result);
        foreach (CompilerResultMessage m in result.Messages) Print(m, "  ");
    }

    // Clean = one of these states AND zero errors. "aborted" with 0 errors, or
    // any state this list does not know, is a failure.
    static void Check(string what, CompilerResult r)
    {
        string st = r.State.ToString();
        bool okState = st == "Success" || st == "Information" || st == "Warning";
        if (!okState || r.ErrorCount != 0)
            Failures.Add(what + ": state=" + st + " errors=" + r.ErrorCount);
    }

    static IEnumerable<PlcBlock> AllBlocks(PlcBlockGroup g)
    {
        foreach (PlcBlock b in g.Blocks) yield return b;
        foreach (PlcBlockGroup sub in g.Groups)
            foreach (PlcBlock b in AllBlocks(sub)) yield return b;
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
if (-not [BlockApplier]::Run($ProjectPath, $BuildDir, $Files, [bool]$DryRun)) { exit 1 }
