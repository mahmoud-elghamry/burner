# Lists every block in the PLC with its type, number and instance-of info,
# so new blocks/DBs can be created without colliding. Read-only.
param(
    [string]$ProjectPath = ((Get-ChildItem (Join-Path $PSScriptRoot "..\tia") -Recurse -Filter "*.ap15_1" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName),
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
if (Get-Process -Name 'Siemens.Automation.Portal' -ErrorAction SilentlyContinue) {
    throw "TIA Portal is running. Close it first."
}
$engDll = Join-Path $ApiDir 'Siemens.Engineering.dll'
[System.Reflection.Assembly]::LoadFrom($engDll) | Out-Null

$src = @'
using System;
using System.IO;
using Siemens.Engineering;
using Siemens.Engineering.HW;
using Siemens.Engineering.HW.Features;
using Siemens.Engineering.SW;
using Siemens.Engineering.SW.Blocks;
using Siemens.Engineering.SW.Tags;

public class BlockLister
{
    public static void Run(string projectPath)
    {
        TiaPortal portal = new TiaPortal(TiaPortalMode.WithoutUserInterface);
        Project prj = null;
        try
        {
            prj = portal.Projects.Open(new FileInfo(projectPath));
            foreach (Device d in prj.Devices)
                foreach (DeviceItem it in d.DeviceItems) Walk(it, 0);
        }
        finally
        {
            try { if (prj != null) prj.Close(); } catch { }
            try { portal.Dispose(); } catch { }
        }
    }

    static void Walk(DeviceItem item, int depth)
    {
        if (depth > 12) return;
        try
        {
            SoftwareContainer sc = item.GetService<SoftwareContainer>();
            if (sc != null)
            {
                PlcSoftware plc = sc.Software as PlcSoftware;
                if (plc != null) Dump(plc);
            }
        }
        catch { }
        foreach (DeviceItem sub in item.DeviceItems) Walk(sub, depth + 1);
    }

    static void Dump(PlcSoftware plc)
    {
        Console.WriteLine("=== PLC: " + plc.Name + " ===");
        Console.WriteLine("--- BLOCKS ---");
        DumpGroup(plc.BlockGroup, "");
        Console.WriteLine("--- TAG TABLES ---");
        DumpTags(plc.TagTableGroup, "");
    }

    static void DumpGroup(PlcBlockGroup g, string path)
    {
        foreach (PlcBlock b in g.Blocks)
        {
            string extra = "";
            InstanceDB idb = b as InstanceDB;
            if (idb != null) extra = "  instanceOf=" + idb.InstanceOfName;
            GlobalDB gdb = b as GlobalDB;
            if (gdb != null) extra = "  (global DB)";
            Console.WriteLine(string.Format("  {0,-28} {1,-6} No.{2,-5} {3}{4}",
                b.Name, b.GetType().Name, b.Number, b.ProgrammingLanguage, extra));
        }
        foreach (PlcBlockUserGroup sub in g.Groups) DumpGroup(sub, path + sub.Name + "/");
    }

    static void DumpTags(PlcTagTableGroup g, string path)
    {
        foreach (PlcTagTable t in g.TagTables)
            Console.WriteLine("  " + path + t.Name + "   (" + t.Tags.Count + " tags)");
        foreach (PlcTagTableUserGroup sub in g.Groups) DumpTags(sub, path + sub.Name + "/");
    }
}
'@

Add-Type -TypeDefinition $src -ReferencedAssemblies $engDll, 'System.Core' -ErrorAction Stop
[BlockLister]::Run($ProjectPath)
