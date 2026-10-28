<#
    Download-Plcsim.ps1
    ------------------------------------------------------------------
    بينزّل البرنامج من مشروع TIA على PLCSIM V15.1 عن طريق Openness، من غير
    ما حد يدوس Download في TIA. PLCSIM لازم يكون شغال (S7-1200، Power ON).

      .\Download-Plcsim.ps1 -List      # بيطبع أوضاع الاتصال والكروت بس
      .\Download-Plcsim.ps1            # بينزّل (Mode PN/IE، كارت PLCSIM)

    بيفتح المشروع للقراية بس، ومش بيحفظه. TIA لازم يكون مقفول.
#>
param(
    [string]$ProjectPath,
    [string]$ApiDir = "C:\Program Files\Siemens\Automation\Portal V15_1\PublicAPI\V15.1",
    [string]$Mode = "PN/IE",
    [string]$PcInterface = "PLCSIM",
    [switch]$List
)
$ErrorActionPreference = 'Stop'
if (-not $ProjectPath) { $ProjectPath = (Get-ChildItem (Join-Path $PSScriptRoot "..\tia") -Recurse -Filter "*.ap15_1" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName }
$ProjectPath = [System.IO.Path]::GetFullPath($ProjectPath)
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
using Siemens.Engineering.Connection;
using Siemens.Engineering.Download;
using Siemens.Engineering.Download.Configurations;

public class SimDownloader
{
    static DeviceItem Cpu;

    public static bool Run(string projectPath, string mode, string pcif, bool listOnly)
    {
        TiaPortal portal = new TiaPortal(TiaPortalMode.WithoutUserInterface);
        Project prj = null;
        try
        {
            prj = portal.Projects.Open(new FileInfo(projectPath));
            foreach (Device d in prj.Devices)
                foreach (DeviceItem it in d.DeviceItems) { if (Cpu == null) Walk(it, 0); }
            if (Cpu == null) throw new Exception("CPU not found");
            DownloadProvider dp = Cpu.GetService<DownloadProvider>();
            if (dp == null) throw new Exception("no DownloadProvider on " + Cpu.Name);
            ConnectionConfiguration cc = dp.Configuration;

            foreach (ConfigurationMode m in cc.Modes)
            {
                Console.WriteLine("mode: " + m.Name);
                foreach (ConfigurationPcInterface p in m.PcInterfaces)
                {
                    Console.WriteLine("    pc interface: " + p.Name + " #" + p.Number);
                    foreach (ConfigurationTargetInterface t in p.TargetInterfaces)
                        Console.WriteLine("        target: " + t.Name);
                }
            }
            if (listOnly) return true;

            ConfigurationMode cm = cc.Modes.Find(mode);
            if (cm == null) throw new Exception("mode not found: " + mode);
            ConfigurationPcInterface pi = cm.PcInterfaces.Find(pcif, 1);
            if (pi == null) throw new Exception("pc interface not found: " + pcif);
            ConfigurationTargetInterface ti = null;
            foreach (ConfigurationTargetInterface t in pi.TargetInterfaces) { ti = t; break; }
            if (ti == null) throw new Exception("no target interface on " + pcif);
            Console.WriteLine("downloading via " + mode + " / " + pi.Name + " / " + ti.Name);

            DownloadResult r = dp.Download(ti, Pre, Post, DownloadOptions.Hardware | DownloadOptions.Software);
            Console.WriteLine("download state=" + r.State + " errors=" + r.ErrorCount + " warnings=" + r.WarningCount);
            foreach (DownloadResultMessage msg in r.Messages) Print(msg, "  ");
            return r.ErrorCount == 0;
        }
        catch (Exception ex)
        {
            Console.WriteLine("EXCEPTION: " + ex.Message);
            return false;
        }
        finally
        {
            try { if (prj != null) prj.Close(); } catch { }
            try { portal.Dispose(); } catch { }
        }
    }

    // كل سؤال قبل التنزيل: الاختيار الآمن الافتراضي، وبنطبعه عشان يتشاف.
    static void Pre(DownloadConfiguration c)
    {
        Console.WriteLine("  pre: " + c.GetType().Name + " - " + c.Message);
        StopModules sm = c as StopModules;
        if (sm != null) { sm.CurrentSelection = StopModulesSelections.StopAll; return; }
        ConsistentBlocksDownload cb = c as ConsistentBlocksDownload;
        if (cb != null) { cb.CurrentSelection = ConsistentBlocksDownloadSelections.ConsistentDownload; return; }
        OverwriteSystemData os = c as OverwriteSystemData;
        if (os != null) { os.CurrentSelection = OverwriteSystemDataSelections.Overwrite; return; }
        AllBlocksDownload ab = c as AllBlocksDownload;
        if (ab != null) { ab.CurrentSelection = AllBlocksDownloadSelections.DownloadAllBlocks; return; }
        DifferentTargetConfiguration dt = c as DifferentTargetConfiguration;
        if (dt != null) { dt.CurrentSelection = DifferentTargetConfigurationSelections.AcceptAll; return; }
    }

    static void Post(DownloadConfiguration c)
    {
        Console.WriteLine("  post: " + c.GetType().Name + " - " + c.Message);
        StartModules st = c as StartModules;
        if (st != null) { st.CurrentSelection = StartModulesSelections.StartModule; }
    }

    static void Print(DownloadResultMessage m, string pad)
    {
        Console.WriteLine(pad + "[" + m.State + "] " + m.Message);
        foreach (DownloadResultMessage s in m.Messages) Print(s, pad + "    ");
    }

    static void Walk(DeviceItem item, int depth)
    {
        if (depth > 12 || Cpu != null) return;
        SoftwareContainer sc = item.GetService<SoftwareContainer>();
        if (sc != null && sc.Software is PlcSoftware) { Cpu = item; return; }
        foreach (DeviceItem sub in item.DeviceItems) Walk(sub, depth + 1);
    }
}
'@

Add-Type -TypeDefinition $src -ReferencedAssemblies $engDll -ErrorAction Stop
if (-not [SimDownloader]::Run($ProjectPath, $Mode, $PcInterface, [bool]$List)) { exit 1 }
