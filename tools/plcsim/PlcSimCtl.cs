// PlcSimCtl — بيتحكم في S7-PLCSIM V15.1 (Compact) من سكريبت.
//
// الواجهة دي مش موثّقة من Siemens: PlcSim.Interproc.ICompact على named pipe
// عنوانه عشوائي، فبنلاقيه في ذاكرة Siemens.Simatic.PlcSim.Compact.exe.
// اتلقت بالبحث في 2026-10-28 (docs/evidence/2026-10-28-plcsim-automation.md).
//
// بيقرا أوامر من stdin، سطر سطر، ويرد بسطر واحد يبدأ بـ OK أو ERR:
//   power on|off          run          stop          mode
//   set I0.0 1            setw IW96 700              readq 0 2
//   sleep 500             quit
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.ServiceModel;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using PlcSim.Interproc;
using Siemens.Simatic.PlcSim.VplcApi.Types;
using Siemens.Simatic.PlcSim.VplcApi.Sequence;

[CallbackBehavior(UseSynchronizationContext = false, ConcurrencyMode = ConcurrencyMode.Multiple)]
public class FullStub : IFull
{
    public volatile string Mode = "?";
    public void OpenProject(string p) { }
    public void CloseProjectInFullView() { }
    public void DisconnectAndTerminate() { }
    public void SetNetworkAddress(List<string> l) { }
    public void ShowProjectView(bool b) { }
    public void UpdateCpuOperatingMode(CpuOperatingMode m) { Mode = m.ToString(); }
    public void GoOffline() { }
    public void CompactViewFamilyChanged(PlcSim.Interproc.Family f) { }
    public void UpdateBusyStatus(bool b) { }
    public void PowerStateChanged(bool b) { }
    public void ConfiguredStateChanged(bool b) { }
    public void NameChanged(string n) { }
    public void UpdateSequenceState(SequenceState s) { }
}

class PlcSimCtl
{
    [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(int a, bool b, int pid);
    [DllImport("kernel32.dll")] static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int n, out int read);
    [DllImport("kernel32.dll")] static extern int VirtualQueryEx(IntPtr h, IntPtr addr, out MBI m, int len);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [StructLayout(LayoutKind.Sequential)]
    struct MBI { public IntPtr Base, AllocBase; public uint AllocProt; public IntPtr Size; public uint State, Prot, Type; }

    static string FindUri()
    {
        Regex rx = new Regex(@"net\.pipe://localhost/PlcSim14/[0-9a-fA-F\-]{36}/Compact");
        foreach (Process p in Process.GetProcessesByName("Siemens.Simatic.PlcSim.Compact"))
        {
            IntPtr h = OpenProcess(0x0410, false, p.Id);
            if (h == IntPtr.Zero) continue;
            try
            {
                long addr = 0; MBI m;
                while (VirtualQueryEx(h, (IntPtr)addr, out m, Marshal.SizeOf(typeof(MBI))) != 0)
                {
                    long sz = (long)m.Size;
                    if (sz <= 0) break;
                    if (m.State == 0x1000 && (m.Prot & 0x101) == 0 && sz < 256L * 1024 * 1024)
                    {
                        byte[] buf = new byte[sz]; int rd;
                        if (ReadProcessMemory(h, m.Base, buf, (int)sz, out rd) && rd > 0)
                        {
                            Match x = rx.Match(Encoding.Unicode.GetString(buf, 0, rd));
                            if (x.Success) return x.Value;
                        }
                    }
                    addr = (long)m.Base + sz;
                }
            }
            finally { CloseHandle(h); }
        }
        return null;
    }

    // %I0.0 / %IW96 / I12.3 → عنوان PLCSIM
    static ProcessValueAddress Addr(string a, out bool word)
    {
        a = a.TrimStart('%').ToUpperInvariant();
        Match b = Regex.Match(a, @"^I(\d+)\.([0-7])$");
        Match w = Regex.Match(a, @"^IW(\d+)$");
        ProcessValueAddress pa = new ProcessValueAddress();
        pa.Area = RuntimeArea.Input;
        // لازم true: في VplcHost، IsPeripheral=false بيروح SetTagValue (محتاج اسم تاج في
        // TagNameUtf8) وبيرمي exception، وCompactService بيحوّل أي exception لـ
        // ServiceNotConnected. true بيروح SetInputBit / SetInput على منطقة الـ I.
        pa.IsPeripheral = true;
        if (b.Success)
        {
            word = false;
            pa.ByteOffset = ulong.Parse(b.Groups[1].Value);
            pa.IsBool = true;
            pa.BitNumber = byte.Parse(b.Groups[2].Value);
            return pa;
        }
        if (w.Success)
        {
            word = true;
            pa.ByteOffset = ulong.Parse(w.Groups[1].Value);
            pa.IsBool = false;
            return pa;
        }
        throw new Exception("bad address " + a);
    }

    static int Main(string[] args)
    {
        string uri = args.Length > 0 ? args[0] : FindUri();
        if (uri == null) { Console.WriteLine("ERR no running PLCSIM Compact found"); return 1; }
        FullStub cb = new FullStub();
        var conn = new PlcSim.Interproc.Util.ServiceConnector<ICompact>();
        ICompact svc;
        try
        {
            svc = conn.Connect(cb, uri, s => { });
            // ممنوع RegisterFullView: بيربط عمر PLCSIM بالأداة دي، فلما تقفل بيقفل معاها
            // (اتشاف 2026-10-28، ضاع تنزيلين كده).
            Console.WriteLine("OK connected " + svc.GetCurrentFamily());
        }
        catch (Exception e) { Console.WriteLine("ERR connect: " + e.Message); return 1; }

        string line;
        while ((line = Console.ReadLine()) != null)
        {
            string[] t = line.Trim().Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            if (t.Length == 0) continue;
            try
            {
                switch (t[0])
                {
                    case "power":
                        if (t[1] == "on") Console.WriteLine("OK " + svc.PowerOn("Burner"));
                        else { svc.PowerOff(); Console.WriteLine("OK off"); }
                        break;
                    case "run": svc.RequestCpuRunMode(); Console.WriteLine("OK"); break;
                    case "stop": svc.RequestCpuStopMode(); Console.WriteLine("OK"); break;
                    case "mode": Console.WriteLine("OK " + cb.Mode); break;
                    case "set":
                    case "setw":
                    {
                        bool word;
                        ProcessValue pv = new ProcessValue();
                        pv.Address = Addr(t[1], out word);
                        if (word)
                        {
                            short v = short.Parse(t[2]);
                            pv.Value = new byte[] { (byte)((v >> 8) & 0xFF), (byte)(v & 0xFF) };   // S7 = big-endian
                        }
                        else pv.Value = new byte[] { (byte)(t[2] == "1" ? 1 : 0) };
                        // بعد RUN/STOP الخدمة بتاخد لحظة ترجع: نعيد لحد 2 ث، وبعدها ERR (غالبًا VplcHost مات)
                        string s = "";
                        for (int i = 0; i < 8; i++)
                        {
                            s = string.Join(",", svc.SetValues(new[] { pv }));
                            if (s != "ServiceNotConnected") break;
                            Thread.Sleep(250);
                        }
                        Console.WriteLine((s == "Success" ? "OK " : "ERR ") + s);
                        break;
                    }
                    case "readq":
                    {
                        byte[] q = svc.ReadOutput(ulong.Parse(t[1]), ulong.Parse(t[2]));
                        Console.WriteLine("OK " + (q == null ? "null" : BitConverter.ToString(q)));
                        break;
                    }
                    case "call":    // تجربة: أي method من ICompact من غير معاملات
                    {
                        object r = typeof(ICompact).GetMethod(t[1]).Invoke(svc, null);
                        Console.WriteLine("OK " + (r == null ? "void" : r.ToString()));
                        break;
                    }
                    case "sleep": Thread.Sleep(int.Parse(t[1])); Console.WriteLine("OK"); break;
                    case "quit": Console.WriteLine("OK bye"); return 0;
                    default: Console.WriteLine("ERR unknown command " + t[0]); break;
                }
            }
            catch (Exception e) { Console.WriteLine("ERR " + e.GetType().Name + ": " + e.Message); }
        }
        return 0;
    }
}
