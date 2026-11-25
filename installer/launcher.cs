// Single user-facing entry point. Qt IFW still owns the complete installer UI.
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Collections.Generic;
using System.Threading.Tasks;

internal static class Launcher
{
    private const string WindowMarker = "NewHorizon.Setup.Window";
    private delegate bool WindowCallback(IntPtr window, IntPtr parameter);
    [DllImport("user32.dll")] private static extern bool EnumWindows(WindowCallback callback, IntPtr parameter);
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern bool SetProp(IntPtr window, string name, IntPtr value);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern IntPtr GetProp(IntPtr window, string name);
    [DllImport("user32.dll")] private static extern bool ShowWindowAsync(IntPtr window, int command);
    [DllImport("user32.dll")] private static extern bool IsIconic(IntPtr window);
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int MessageBox(IntPtr owner, string text, string title, uint flags);

    private static bool FocusExistingWindow(int attempts)
    {
        // A second double-click may arrive before the first window is painted.
        for (int attempt = 0; attempt < attempts; attempt++)
        {
            bool found = false;
            EnumWindows(delegate(IntPtr window, IntPtr unused) {
                if (!IsWindowVisible(window) || GetProp(window, WindowMarker) == IntPtr.Zero) return true;
                if (IsIconic(window)) ShowWindowAsync(window, 9);
                SetForegroundWindow(window);
                found = true;
                return false;
            }, IntPtr.Zero);
            if (found) return true;
            Thread.Sleep(100);
        }
        return false;
    }

    private static string Digest(Stream stream)
    {
        using (SHA256 hash = SHA256.Create())
            return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }

    private static string ExtractEngine()
    {
        using (Stream resource = Assembly.GetExecutingAssembly().GetManifestResourceStream("NewHorizon.QtInstaller"))
        {
            string digest = Digest(resource);
            string directory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                                            "NewHorizon", "installer", digest);
            Directory.CreateDirectory(directory);
            string executable = Path.Combine(directory, "NewHorizonEngine.exe");
            bool valid = false;
            if (File.Exists(executable))
                using (FileStream cached = File.OpenRead(executable)) valid = Digest(cached) == digest;
            if (!valid)
            {
                resource.Position = 0;
                using (FileStream target = new FileStream(executable, FileMode.Create, FileAccess.Write, FileShare.None))
                    resource.CopyTo(target);
            }
            return executable;
        }
    }

    private static string Quote(string value)
    {
        // Windows CommandLineToArgvW quoting, including quotes and trailing '\'.
        StringBuilder result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char ch in value)
        {
            if (ch == '\\') { slashes++; continue; }
            result.Append('\\', ch == '"' ? slashes * 2 + 1 : slashes);
            slashes = 0;
            result.Append(ch);
        }
        result.Append('\\', slashes * 2);
        return result.Append('"').ToString();
    }

    [STAThread]
    private static int Main(string[] args)
    {
        HashSet<string> commands = new HashSet<string>(new string[] {
            "install", "in", "update", "up", "check-updates", "ch", "purge", "pr", "remove", "rm",
            "search", "se", "list", "li", "create-offline", "co", "clear-cache", "cc", "--help", "-h", "-?", "--version", "-v"
        });
        bool commandLine = Array.Exists(args, delegate(string arg) { return commands.Contains(arg); });
        bool owned = false;
        string identity = WindowsIdentity.GetCurrent().User.Value;
        using (Mutex mutex = new Mutex(false, "Local\\NewHorizon.Setup." + identity))
        {
            try
            {
                try { owned = mutex.WaitOne(0); }
                catch (AbandonedMutexException) { owned = true; }
                if (!owned) { if (!commandLine) FocusExistingWindow(40); return commandLine ? 1 : 0; }
                // Recover an existing Qt window if its launcher was terminated.
                if (!commandLine && FocusExistingWindow(1)) return 0;

                string engine = ExtractEngine();
                string[] quoted = Array.ConvertAll(args, Quote);
                ProcessStartInfo start = new ProcessStartInfo(engine, String.Join(" ", quoted));
                start.UseShellExecute = false;
                start.CreateNoWindow = true;
                start.WorkingDirectory = Environment.CurrentDirectory;
                if (commandLine)
                {
                    start.RedirectStandardOutput = true;
                    start.RedirectStandardError = true;
                    using (Process command = Process.Start(start))
                    {
                        Task output = command.StandardOutput.BaseStream.CopyToAsync(Console.OpenStandardOutput());
                        Task error = command.StandardError.BaseStream.CopyToAsync(Console.OpenStandardError());
                        command.WaitForExit();
                        Task.WaitAll(output, error);
                        return command.ExitCode;
                    }
                }
                Dictionary<int, Process> active = new Dictionary<int, Process>();
                Process first = Process.Start(start);
                active[first.Id] = first;
                int session = Process.GetCurrentProcess().SessionId;
                int exitCode = 0;
                DateTime quietSince = DateTime.MaxValue;
                while (true)
                {
                    // Qt can restart itself. Keep the mutex until the last Qt
                    // process from THIS payload has actually exited.
                    foreach (Process candidate in Process.GetProcessesByName("NewHorizonEngine"))
                    {
                        try
                        {
                            if (candidate.SessionId == session &&
                                String.Equals(candidate.MainModule.FileName, engine, StringComparison.OrdinalIgnoreCase) &&
                                !active.ContainsKey(candidate.Id))
                            { active[candidate.Id] = candidate; continue; }
                        }
                        catch (InvalidOperationException) { }
                        catch (System.ComponentModel.Win32Exception) { }
                        candidate.Dispose();
                    }
                    foreach (int pid in new List<int>(active.Keys))
                    {
                        Process process = active[pid];
                        if (process.HasExited)
                        {
                            exitCode = process.ExitCode;
                            process.Dispose();
                            active.Remove(pid);
                        }
                    }
                    EnumWindows(delegate(IntPtr window, IntPtr unused) {
                        uint pid;
                        GetWindowThreadProcessId(window, out pid);
                        if (active.ContainsKey((int)pid) && IsWindowVisible(window)) SetProp(window, WindowMarker, new IntPtr(1));
                        return true;
                    }, IntPtr.Zero);
                    if (active.Count == 0)
                    {
                        if (quietSince == DateTime.MaxValue) quietSince = DateTime.UtcNow;
                        if ((DateTime.UtcNow - quietSince).TotalMilliseconds >= 750) return exitCode;
                    }
                    else quietSince = DateTime.MaxValue;
                    Thread.Sleep(100);
                }
            }
            catch (Exception error)
            {
                MessageBox(IntPtr.Zero, "Não foi possível abrir o instalador.\n\n" + error.Message, "New Horizon", 0x10);
                return 1;
            }
            finally { if (owned) mutex.ReleaseMutex(); }
        }
    }
}
