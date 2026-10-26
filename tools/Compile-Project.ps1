<#
    Compile-Project.ps1
    Compiles the hardware configuration and then the PLC software, printing
    every message. Saves only when the software compile reports no errors.

    Compiling the software on its own reports "aborted" until the hardware
    configuration has been compiled, so the order here matters.
#>
param(
    [string]$ProjectPath = ((Get-ChildItem (Join-Path $PSScriptRoot "..\tia") -Recurse -Filter "*.ap15_1" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName),
    [string]$ApiDir      = "C:\Program Files\Siemens\Automation\Portal V15_1\PublicAPI\V15.1",
    [switch]$DryRun
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
if (Get-Process -Name 'Siemens.Automation.Portal' -ErrorAction SilentlyContinue) {
    throw "TIA Portal is running. Close it first."
}
$engDll = Join-Path $ApiDir 'Siemens.Engineering.dll'
[System.Reflection.Assembly]::LoadFrom($engDll) | Out-Null

$src = @'
using System;
using System.IO;
using Siemens.Engineering;
using Siemens.Engineering.Compiler;
using Siemens.Engineering.HW;
using Siemens.Engineering.HW.Features;
using Siemens.Engineering.SW;
using Siemens.Engineering.SW.Blocks;

public class ProjectCompiler
{
    static DeviceItem CpuItem = null;
    public static int SwErrors = -1;

    public static void Run(string projectPath, bool dryRun)
    {
        TiaPortal portal = new TiaPortal(TiaPortalMode.WithoutUserInterface);
        Project prj = null;
        try
        {
            prj = portal.Projects.Open(new FileInfo(projectPath));
            PlcSoftware plc = FindPlc(prj);
            if (plc == null) throw new Exception("PLC software not found");

            Console.WriteLine("=== 1. HARDWARE ===");
            Run1(CpuItem.GetService<ICompilable>());

            Console.WriteLine("");
            Console.WriteLine("=== 2. SOFTWARE ===");
            CompilerResult r = Run1(plc.GetService<ICompilable>());
            SwErrors = r.ErrorCount;

            Console.WriteLine("");
            Console.WriteLine("=== 2b. PER-BLOCK COMPILE (diagnostic) ===");
            foreach (PlcBlock b in plc.BlockGroup.Blocks)
            {
                if (b.IsConsistent) continue;
                Console.WriteLine("--- " + b.Name + " ---");
                try
                {
                    ICompilable bc = b.GetService<ICompilable>();
                    if (bc == null) { Console.WriteLine("   no ICompilable"); continue; }
                    Run1(bc);
                }
                catch (Exception ex) { Console.WriteLine("   EX: " + ex.Message); }
            }

            Console.WriteLine("");
            Console.WriteLine("=== 3. BLOCK CONSISTENCY ===");
            foreach (PlcBlock b in plc.BlockGroup.Blocks)
                Console.WriteLine(string.Format("  {0,-24} consistent={1}",
                    b.Name, b.IsConsistent));

            if (dryRun) { Console.WriteLine("\nDRY RUN - not saved."); }
            else if (SwErrors == 0) { prj.Save(); Console.WriteLine("\nPROJECT SAVED."); }
            else { Console.WriteLine("\nERRORS - not saved."); }
        }
        finally
        {
            try { if (prj != null) prj.Close(); } catch { }
            try { portal.Dispose(); } catch { }
        }
    }

    static CompilerResult Run1(ICompilable c)
    {
        CompilerResult r = c.Compile();
        Console.WriteLine("state=" + r.State + "  errors=" + r.ErrorCount
                          + "  warnings=" + r.WarningCount);
        foreach (CompilerResultMessage m in r.Messages) Print(m, "  ");
        return r;
    }

    static void Print(CompilerResultMessage m, string pad)
    {
        string d = m.Description;
        if (string.IsNullOrEmpty(d)) d = "-";
        Console.WriteLine(pad + "[" + m.State + "] " + d
                          + (string.IsNullOrEmpty(m.Path) ? "" : "   @ " + m.Path));
        foreach (CompilerResultMessage s in m.Messages) Print(s, pad + "  ");
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
}
'@

Add-Type -TypeDefinition $src -ReferencedAssemblies $engDll, 'System.Core' -ErrorAction Stop
[ProjectCompiler]::Run($ProjectPath, [bool]$DryRun)
