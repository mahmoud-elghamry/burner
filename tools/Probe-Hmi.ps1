# P1 probe for decisions/0007: what Openness V15.1 can do with the HMI.
# Works ONLY on a copy of the project (refuses anything under tia\):
# adds a KTP400 Comfort, connects it to the PLC subnet, compiles it and
# exports whatever HMI objects Openness allows. Each step reports OK/FAIL
# instead of stopping, because the point is to learn what works.
param(
    [string]$ProbeDir = (Join-Path $PSScriptRoot "..\build\probe"),
    [string]$Source   = (Join-Path $PSScriptRoot "..\tia\Burner"),
    [string]$OrderNo  = "6AV2 124-2DC01-0AX0",
    [string]$HmiIp    = "192.168.0.2",
    [string]$ApiDir   = "C:\Program Files\Siemens\Automation\Portal V15_1\PublicAPI\V15.1"
)
$ErrorActionPreference = 'Stop'
$ProbeDir = [System.IO.Path]::GetFullPath($ProbeDir)
$Source   = [System.IO.Path]::GetFullPath($Source)
if (Get-Process -Name 'Siemens.Automation.Portal' -ErrorAction SilentlyContinue) {
    throw "TIA Portal is open. Close it first (single writer, AGENTS rule 6)."
}
if ($ProbeDir -like "*\tia\*" -or $ProbeDir -like "*\tia") { throw "refusing to probe inside tia\" }

# Fresh copy every run: the probe must never touch the real project.
if (Test-Path $ProbeDir) { Remove-Item $ProbeDir -Recurse -Force }
New-Item -ItemType Directory -Force $ProbeDir | Out-Null
Copy-Item $Source (Join-Path $ProbeDir "Burner") -Recurse
Get-ChildItem (Join-Path $ProbeDir "Burner") -Recurse -Include *.lock,~* -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse
$prjFile = (Get-ChildItem (Join-Path $ProbeDir "Burner") -Filter *.ap15_1 | Select-Object -First 1).FullName
$outDir  = Join-Path $ProbeDir "export"
New-Item -ItemType Directory -Force $outDir | Out-Null

$engDll = Join-Path $ApiDir 'Siemens.Engineering.dll'
$hmiDll = Join-Path $ApiDir 'Siemens.Engineering.Hmi.dll'
[System.Reflection.Assembly]::LoadFrom($engDll) | Out-Null
[System.Reflection.Assembly]::LoadFrom($hmiDll) | Out-Null

$src = @'
using System;
using System.IO;
using System.Collections.Generic;
using Siemens.Engineering;
using Siemens.Engineering.HW;
using Siemens.Engineering.HW.Features;
using Siemens.Engineering.Compiler;
using Siemens.Engineering.Hmi;
using Siemens.Engineering.Hmi.Screen;
using Siemens.Engineering.Hmi.Tag;
using Siemens.Engineering.Hmi.TextGraphicList;
using Siemens.Engineering.Hmi.Communication;

public class HmiProbe
{
    static void Step(string name, Action a)
    {
        try { a(); Console.WriteLine("OK    " + name); }
        catch (Exception e) { Console.WriteLine("FAIL  " + name + " :: " + e.GetType().Name + ": " + e.Message); }
    }

    static void Walk(DeviceItem it, int depth, List<DeviceItem> all)
    {
        if (depth > 12) return;
        all.Add(it);
        foreach (DeviceItem s in it.DeviceItems) Walk(s, depth + 1, all);
    }

    static List<Node> Nodes(Device d)
    {
        var res = new List<Node>();
        var all = new List<DeviceItem>();
        foreach (DeviceItem it in d.DeviceItems) Walk(it, 0, all);
        foreach (DeviceItem it in all)
        {
            NetworkInterface ni = null;
            try { ni = it.GetService<NetworkInterface>(); } catch { }
            if (ni != null) foreach (Node n in ni.Nodes) res.Add(n);
        }
        return res;
    }

    static HmiTarget FindHmi(Device d)
    {
        var all = new List<DeviceItem>();
        foreach (DeviceItem it in d.DeviceItems) Walk(it, 0, all);
        foreach (DeviceItem it in all)
        {
            SoftwareContainer sc = null;
            try { sc = it.GetService<SoftwareContainer>(); } catch { }
            if (sc != null && sc.Software is HmiTarget) return (HmiTarget)sc.Software;
        }
        return null;
    }

    public static void Run(string prjFile, string outDir, string orderNo, string hmiIp)
    {
        TiaPortal portal = new TiaPortal(TiaPortalMode.WithoutUserInterface);
        Project prj = null;
        try
        {
            prj = portal.Projects.Open(new FileInfo(prjFile));
            Device plcDev = null;
            foreach (Device d in prj.Devices)
            {
                Console.WriteLine("device: " + d.Name + "  type=" + d.TypeIdentifier);
                if (plcDev == null) plcDev = d;
            }

            // 1. add the panel - try the image versions V15.1 may offer
            Device hmiDev = null;
            foreach (string ver in new[] { "15.1.0.0", "15.0.0.0", "14.0.1.0", "14.0.0.0", "13.0.1.0" })
            {
                string id = "OrderNumber:" + orderNo + "/" + ver;
                try
                {
                    // HMI devices refuse a device name ("read-only attribute"): item name only.
                    hmiDev = prj.Devices.CreateWithItem(id, "HMI_1", null);
                    Console.WriteLine("OK    CreateWithItem " + id);
                    break;
                }
                catch (Exception e) { Console.WriteLine("FAIL  CreateWithItem " + id + " :: " + e.Message); }
            }
            if (hmiDev == null) return;
            Console.WriteLine("hmi type=" + hmiDev.TypeIdentifier);

            // 2. network: put the HMI port on the PLC's subnet
            Step("subnet + HMI IP", () =>
            {
                List<Node> pn = Nodes(plcDev), hn = Nodes(hmiDev);
                Console.WriteLine("  plc nodes=" + pn.Count + " hmi nodes=" + hn.Count);
                Node p = pn[0], h = hn[0];
                Console.WriteLine("  plc ip=" + p.GetAttribute("Address"));
                Subnet sn = p.ConnectedSubnet;
                if (sn == null) { sn = p.CreateAndConnectToSubnet("PN/IE_1"); Console.WriteLine("  created subnet PN/IE_1"); }
                else Console.WriteLine("  plc subnet=" + sn.Name);
                h.ConnectToSubnet(sn);
                h.SetAttribute("Address", hmiIp);
                Console.WriteLine("  hmi ip=" + h.GetAttribute("Address"));
            });

            HmiTarget hmi = FindHmi(hmiDev);
            Console.WriteLine(hmi == null ? "FAIL  no HmiTarget" : "OK    HmiTarget " + hmi.Name);
            if (hmi == null) return;

            // 3. what the target exposes
            Step("list objects", () =>
            {
                Console.WriteLine("  screens: " + hmi.ScreenFolder.Screens.Count);
                foreach (Screen s in hmi.ScreenFolder.Screens) Console.WriteLine("    " + s.Name);
                Console.WriteLine("  tag tables: " + hmi.TagFolder.TagTables.Count);
                foreach (TagTable t in hmi.TagFolder.TagTables) Console.WriteLine("    " + t.Name + " (" + t.Tags.Count + ")");
                Console.WriteLine("  connections: " + hmi.Connections.Count);
                foreach (Connection c in hmi.Connections) Console.WriteLine("    " + c.Name);
                Console.WriteLine("  text lists: " + hmi.TextLists.Count);
            });

            // 4. exports - one per object kind, to learn the XML shape
            Step("export screens", () =>
            {
                foreach (Screen s in hmi.ScreenFolder.Screens)
                    s.Export(new FileInfo(Path.Combine(outDir, "Screen_" + s.Name + ".xml")), ExportOptions.WithDefaults);
            });
            Step("export tag tables", () =>
            {
                foreach (TagTable t in hmi.TagFolder.TagTables)
                    t.Export(new FileInfo(Path.Combine(outDir, "Tags_" + t.Name + ".xml")), ExportOptions.WithDefaults);
            });
            Step("export connections", () =>
            {
                foreach (Connection c in hmi.Connections)
                    c.Export(new FileInfo(Path.Combine(outDir, "Conn_" + c.Name + ".xml")), ExportOptions.WithDefaults);
            });
            Step("export text lists", () =>
            {
                foreach (TextList t in hmi.TextLists)
                    t.Export(new FileInfo(Path.Combine(outDir, "TextList_" + t.Name + ".xml")), ExportOptions.WithDefaults);
            });

            // 5. compile the panel
            Step("compile HMI", () =>
            {
                ICompilable comp = hmi.GetService<ICompilable>();
                CompilerResult r = comp.Compile();
                Console.WriteLine("  state=" + r.State + " errors=" + r.ErrorCount + " warnings=" + r.WarningCount);
                Print(r.Messages, "    ", 0);
            });

            prj.Save();
            Console.WriteLine("saved probe copy");
        }
        finally
        {
            try { if (prj != null) prj.Close(); } catch { }
            try { portal.Dispose(); } catch { }
        }
    }

    static void Print(CompilerResultMessageComposition ms, string ind, int depth)
    {
        if (depth > 6) return;
        foreach (CompilerResultMessage m in ms)
        {
            if (m.State != CompilerResultState.Success || depth < 1)
                Console.WriteLine(ind + m.State + ": " + m.Path + " " + m.Description);
            Print(m.Messages, ind + "  ", depth + 1);
        }
    }
}
'@

Add-Type -TypeDefinition $src -ReferencedAssemblies $engDll, $hmiDll, 'System.Core' -ErrorAction Stop
[HmiProbe]::Run($prjFile, $outDir, $OrderNo, $HmiIp)
