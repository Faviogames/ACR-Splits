using System.Diagnostics;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;

internal static class Program
{
    const string ReleaseVersion = "0.7.0", Repo = "Faviogames/ACR-Splits";
    static readonly string Home = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ACRSplits");
    static readonly JsonSerializerOptions Json = new() { WriteIndented = true };
    [STAThread]
    static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
        try
        {
            if (args.Length == 2 && args[0] == "--self-test") { SelfTest(Path.GetFullPath(args[1])); return; }
            if (args.Length == 2 && args[0] == "--replace")
            {
                if (!int.TryParse(args[1], out var pid)) throw new IOException("Invalid update process");
                try { using var previous = Process.GetProcessById(pid); if (!previous.WaitForExit(30000)) throw new IOException("Close the running app before updating."); } catch (ArgumentException) { }
            }
            using var mutex = new Mutex(true, @"Local\ACR_SPLITS_LAUNCHER", out var first);
            if (!first) return;
            Directory.CreateDirectory(Home);
            var versionFile = Path.Combine(Home, "current.txt");
            var version = File.Exists(versionFile) ? File.ReadAllText(versionFile).Trim() : "0.0.0";
            if (!Version.TryParse(version, out var installed)) throw new IOException("Invalid installed version");
            if (installed < Version.Parse(ReleaseVersion))
            {
                Install(Home);
                version = ReleaseVersion;
                File.WriteAllText(versionFile + ".tmp", version);
                File.Move(versionFile + ".tmp", versionFile, true);
            }
            var launcher = Path.Combine(Home, "ACR Splits.exe");
            if (!string.Equals(Environment.ProcessPath, launcher, StringComparison.OrdinalIgnoreCase) && installed <= Version.Parse(ReleaseVersion))
                File.Copy(Environment.ProcessPath!, launcher, true);
            Shortcut(launcher);
            if (CheckUpdate(version).GetAwaiter().GetResult()) return;
            var folder = Path.Combine(Home, "versions", version);
            var start = new ProcessStartInfo(Path.Combine(folder, "ACR MOD RECORDS.exe")) { WorkingDirectory = folder, UseShellExecute = false };
            start.Environment["ACR_RECORDS_DATA"] = Path.Combine(Home, "data");
            using var app = Process.Start(start) ?? throw new IOException("Could not start ACR Splits.");
            app.WaitForExit();
        }
        catch (Exception error) { MessageBox.Show(error.Message, "ACR Splits", MessageBoxButtons.OK, MessageBoxIcon.Error); }
    }
    static void Install(string root)
    {
        var target = Path.Combine(root, "versions", ReleaseVersion);
        if (Directory.Exists(target)) return;
        var staging = Path.Combine(root, "versions", ".staging-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(staging);
        try
        {
            using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip") ?? throw new IOException("Missing application payload");
            using var zip = new ZipArchive(stream);
            foreach (var entry in zip.Entries)
            {
                var name = entry.FullName.Replace('\\', '/');
                var destination = SafeDestination(staging, name);
                if (name.EndsWith('/')) { Directory.CreateDirectory(destination); continue; }
                Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
                entry.ExtractToFile(destination, false);
            }
            foreach (var file in new[] { "ACR MOD RECORDS.exe", "python/python.exe", "records/app.py", "records/stages.json", "records/ui/index.html" })
                if (!File.Exists(Path.Combine(staging, file))) throw new IOException("Incomplete application payload: " + file);
            Directory.Move(staging, target);
        }
        finally { if (Directory.Exists(staging)) Directory.Delete(staging, true); }
    }
    static string SafeDestination(string staging, string name)
    {
        name = name.Replace('\\', '/');
        if (name.StartsWith('/') || name.Split('/').Any(part => part is ".." or ".") || name.Contains(':')) throw new IOException("Unsafe archive path");
        var destination = Path.GetFullPath(Path.Combine(staging, name));
        if (!destination.StartsWith(staging + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) throw new IOException("Unsafe archive path");
        return destination;
    }
    static async Task<bool> CheckUpdate(string current)
    {
        // shortcut: trust the fixed GitHub repository and GitHub's SHA-256 asset digest; add publisher signing before wider distribution.
        try
        {
            using var client = new HttpClient();
            client.DefaultRequestHeaders.UserAgent.ParseAdd("ACR-Splits/" + ReleaseVersion);
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(6));
            using var response = await client.GetAsync("https://api.github.com/repos/" + Repo + "/releases/latest", timeout.Token);
            response.EnsureSuccessStatusCode();
            using var release = JsonDocument.Parse(await response.Content.ReadAsStringAsync(timeout.Token));
            var root = release.RootElement;
            if (!Version.TryParse(root.GetProperty("tag_name").GetString()?.TrimStart('v'), out var next) || next <= Version.Parse(current)) return false;
            var asset = root.GetProperty("assets").EnumerateArray().Single(a => a.GetProperty("name").GetString() == "ACR-Splits-Setup.exe");
            var digest = asset.GetProperty("digest").GetString();
            if (digest is null || !digest.StartsWith("sha256:") || digest.Length != 71) throw new IOException("Update has no SHA-256 digest");
            var uri = new Uri(asset.GetProperty("browser_download_url").GetString()!);
            if (uri.Scheme != "https" || uri.Host != "github.com" || !uri.AbsolutePath.StartsWith("/" + Repo + "/releases/download/", StringComparison.Ordinal)) throw new IOException("Unexpected update source");
            var size = asset.GetProperty("size").GetInt64();
            if (size <= 0 || size > 300 * 1024 * 1024) throw new IOException("Invalid update size");
            var folder = Path.Combine(Home, "updates"); Directory.CreateDirectory(folder);
            var download = Path.Combine(folder, "setup-" + next + ".exe");
            using var downloadTimeout = new CancellationTokenSource(TimeSpan.FromMinutes(5));
            using var content = await client.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead, downloadTimeout.Token);
            content.EnsureSuccessStatusCode();
            await using (var output = new FileStream(download + ".part", FileMode.Create, FileAccess.Write))
            {
                await using var input = await content.Content.ReadAsStreamAsync(downloadTimeout.Token);
                var buffer = new byte[65536]; long total = 0; int read;
                while ((read = await input.ReadAsync(buffer, downloadTimeout.Token)) > 0) { total += read; if (total > size) throw new IOException("Update exceeds expected size"); await output.WriteAsync(buffer.AsMemory(0, read), downloadTimeout.Token); }
                if (total != size) throw new IOException("Incomplete update");
            }
            await using (var input = File.OpenRead(download + ".part"))
                if (!Convert.ToHexString(await SHA256.HashDataAsync(input)).Equals(digest[7..], StringComparison.OrdinalIgnoreCase)) throw new IOException("Update checksum mismatch");
            File.Move(download + ".part", download, true);
            var start = new ProcessStartInfo(download) { UseShellExecute = false, CreateNoWindow = true };
            start.ArgumentList.Add("--replace"); start.ArgumentList.Add(Environment.ProcessId.ToString());
            Process.Start(start); return true;
        }
        catch (Exception error)
        {
            File.WriteAllText(Path.Combine(Home, "update.log"), DateTime.UtcNow.ToString("O") + " " + error.Message);
            return false;
        }
    }
    static void Shortcut(string launcher)
    {
        var link = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "ACR Splits.lnk");
        if (File.Exists(link)) return;
        var shellType = Type.GetTypeFromProgID("WScript.Shell");
        if (shellType is null) return;
        dynamic shell = Activator.CreateInstance(shellType)!;
        dynamic shortcut = shell.CreateShortcut(link);
        shortcut.TargetPath = launcher; shortcut.WorkingDirectory = Home; shortcut.Description = "ACR Splits — community stage records"; shortcut.Save();
    }
    static void SelfTest(string report)
    {
        var root = Path.Combine(Path.GetTempPath(), "acr-splits-install-test-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(Path.Combine(root, "data"));
            foreach (var bad in new[] { "../escape", "a/../../escape", "C:/escape", "/escape", "a\\..\\escape" })
            {
                try { SafeDestination(root, bad); throw new Exception("Unsafe archive accepted"); } catch (IOException) { }
            }
            var saved = Path.Combine(root, "data", "session-test.txt"); File.WriteAllText(saved, "preserved");
            Install(root); Install(root);
            if (File.ReadAllText(saved) != "preserved") throw new IOException("Data lost");
            var folder = Path.Combine(root, "versions", ReleaseVersion);
            var start = new ProcessStartInfo(Path.Combine(folder, "python", "python.exe")) { WorkingDirectory = folder, UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
            start.ArgumentList.Add("-c"); start.ArgumentList.Add("import ssl,ctypes; from records.app import stage_catalog; c=stage_catalog(); assert len(c)==25; assert 'wrcgkess2full' in c; print('PASS standalone Python, TLS, Windows bindings and 25-stage catalogue')");
            using var python = Process.Start(start)!; var output = python.StandardOutput.ReadToEnd(); var errors = python.StandardError.ReadToEnd(); python.WaitForExit();
            if (python.ExitCode != 0) throw new IOException(errors);
            File.WriteAllText(report, JsonSerializer.Serialize(new { result = "PASS", version = ReleaseVersion, checks = new[] { "isolated extraction", "idempotent installation", "existing session preserved", output.Trim() } }, Json));
        }
        catch (Exception error) { File.WriteAllText(report, JsonSerializer.Serialize(new { result = "FAIL", error = error.ToString() }, Json)); }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
    }
}
