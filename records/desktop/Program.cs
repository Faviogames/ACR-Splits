using System.Diagnostics;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        using var mutex = new Mutex(true, @"Local\ACR_MOD_RECORDS_DESKTOP", out var first);
        if (!first)
        {
            var window = FindWindow(null, "ACR MOD RECORDS");
            if (window != IntPtr.Zero) { ShowWindow(window, 9); SetForegroundWindow(window); }
            return;
        }
        ApplicationConfiguration.Initialize();
        Application.Run(new RecordsWindow());
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern IntPtr FindWindow(string? className, string windowName);
    [DllImport("user32.dll")] private static extern bool ShowWindow(IntPtr window, int command);
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr window);
}

internal sealed class RecordsWindow : Form
{
    private readonly WebView2 browser = new() { Dock = DockStyle.Fill, DefaultBackgroundColor = Color.FromArgb(21, 21, 22) };
    private readonly HttpClient client = new() { Timeout = TimeSpan.FromSeconds(2) };
    private readonly string records = Directory.Exists(Path.Combine(AppContext.BaseDirectory, "records")) ? Path.Combine(AppContext.BaseDirectory, "records") : Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, ".."));
    private readonly string data = Environment.GetEnvironmentVariable("ACR_RECORDS_DATA") ?? Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "app-data"));
    private Process? worker;
    private string origin = "", token = "";
    private bool closing, allowClose;
    private Size regularSize = new(1300, 940);

    public RecordsWindow()
    {
        Text = "ACR MOD RECORDS";
        BackColor = Color.FromArgb(21, 21, 22);
        ClientSize = regularSize;
        MinimumSize = new Size(940, 720);
        StartPosition = FormStartPosition.CenterScreen;
        Controls.Add(browser);
        using var bitmap = new Bitmap(64, 64);
        using (var graphics = Graphics.FromImage(bitmap))
        {
            graphics.Clear(Color.FromArgb(26, 26, 28));
            using var brush = new SolidBrush(Color.FromArgb(255, 48, 59));
            graphics.FillPolygon(brush, [new(8, 48), new(29, 16), new(40, 16), new(19, 48)]);
            graphics.FillPolygon(brush, [new(28, 48), new(49, 16), new(60, 16), new(39, 48)]);
        }
        var iconHandle = bitmap.GetHicon();
        using (var temporary = System.Drawing.Icon.FromHandle(iconHandle)) Icon = (Icon)temporary.Clone();
        DestroyIcon(iconHandle);
        Shown += async (_, _) => await Initialize();
        FormClosing += OnClosing;
    }

    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        int dark = 1;
        DwmSetWindowAttribute(Handle, 20, ref dark, sizeof(int));
    }

    private async Task<bool> ReadRuntime()
    {
        var file = Path.Combine(data, "runtime.json");
        if (!File.Exists(file)) return false;
        try
        {
            using var runtime = JsonDocument.Parse(await File.ReadAllTextAsync(file));
            var value = runtime.RootElement;
            var address = value.GetProperty("origin").GetString()!;
            var secret = value.GetProperty("token").GetString()!;
            if (!Uri.TryCreate(address, UriKind.Absolute, out var uri) || uri.Scheme != "http" || uri.Host != "127.0.0.1") return false;
            using var request = new HttpRequestMessage(HttpMethod.Get, address + "/api/state");
            request.Headers.Add("X-App-Token", secret);
            using var response = await client.SendAsync(request);
            if (!response.IsSuccessStatusCode) return false;
            using var state = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
            if (state.RootElement.GetProperty("app").GetString() != "ACR MOD RECORDS") return false;
            origin = address; token = secret;
            return true;
        }
        catch (Exception error) when (error is IOException or HttpRequestException or TaskCanceledException or JsonException or KeyNotFoundException) { return false; }
    }

    private async Task Initialize()
    {
        try
        {
            if (!await ReadRuntime())
            {
                var root = Path.GetFullPath(Path.Combine(records, ".."));
                var embedded = Path.Combine(root, "python", "python.exe");
                var start = new ProcessStartInfo(File.Exists(embedded) ? embedded : Path.Combine(root, "_internal", "wrcg2acr-worker.exe"))
                {
                    WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true
                };
                start.ArgumentList.Add("-m"); start.ArgumentList.Add("records.app");
                start.Environment["PYTHONPATH"] = root;
                start.Environment["ACR_RECORDS_DATA"] = data;
                worker = Process.Start(start) ?? throw new IOException("No se pudo iniciar el motor local.");
                for (int attempt = 0; attempt < 40 && !await ReadRuntime(); attempt++)
                {
                    if (worker.HasExited) throw new IOException("El motor local terminó. Revisa records/app-data/app.log.");
                    await Task.Delay(250);
                }
                if (origin.Length == 0) throw new IOException("El motor local no respondió a tiempo.");
            }
            var environment = await CoreWebView2Environment.CreateAsync(null, Path.Combine(data, "webview"));
            await browser.EnsureCoreWebView2Async(environment);
            browser.CoreWebView2.Settings.AreDevToolsEnabled = false;
            browser.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;
            browser.CoreWebView2.Settings.IsStatusBarEnabled = false;
            browser.CoreWebView2.NavigationStarting += (_, args) => { if (!args.Uri.StartsWith(origin + "/", StringComparison.Ordinal)) args.Cancel = true; };
            browser.CoreWebView2.NewWindowRequested += (_, args) => args.Handled = true;
            browser.CoreWebView2.PermissionRequested += (_, args) => args.State = CoreWebView2PermissionState.Deny;
            browser.CoreWebView2.WebMessageReceived += OnMessage;
            browser.Source = new Uri(origin + "/#" + token);
        }
        catch (Exception error)
        {
            MessageBox.Show(this, "No se pudo abrir ACR MOD RECORDS.\n\n" + error.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Error);
            Close();
        }
    }

    private async void OnMessage(object? sender, CoreWebView2WebMessageReceivedEventArgs args)
    {
        if (!args.Source.StartsWith(origin + "/", StringComparison.Ordinal)) return;
        try
        {
            using var document = JsonDocument.Parse(args.WebMessageAsJson);
            var message = document.RootElement;
            switch (message.GetProperty("action").GetString())
            {
                case "close": Close(); break;
                case "login":
                    var loginUrl = message.GetProperty("url").GetString()!;
                    if (Uri.TryCreate(loginUrl, UriKind.Absolute, out var login) && login.Scheme == "https" && login.Host == "yhqsxrqzkzroesbxvzka.supabase.co" && login.AbsolutePath == "/auth/v1/authorize" && login.IsDefaultPort && login.UserInfo.Length == 0)
                        Process.Start(new ProcessStartInfo(loginUrl) { UseShellExecute = true });
                    break;
                case "website":
                    Process.Start(new ProcessStartInfo("https://acrsplits.online") { UseShellExecute = true });
                    break;
                case "compact":
                    bool compact = message.GetProperty("enabled").GetBoolean();
                    if (compact) { regularSize = ClientSize; MinimumSize = new Size(380, 470); ClientSize = new Size(430, 535); }
                    else { MinimumSize = new Size(940, 720); ClientSize = regularSize; }
                    TopMost = compact;
                    break;
                case "export":
                    using (var dialog = new SaveFileDialog { Title = "Exportar resultado", Filter = "Resultado JSON (*.json)|*.json", FileName = "ACR-MOD-RECORDS-resultado.json", AddExtension = true, OverwritePrompt = true })
                    {
                        if (dialog.ShowDialog(this) != DialogResult.OK) return;
                        var result = message.GetProperty("result");
                        await File.WriteAllTextAsync(dialog.FileName, JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);
                        browser.CoreWebView2.PostWebMessageAsJson("{\"action\":\"exported\"}");
                    }
                    break;
            }
        }
        catch (Exception error) when (error is JsonException or IOException or UnauthorizedAccessException or KeyNotFoundException or InvalidOperationException or System.ComponentModel.Win32Exception)
        { MessageBox.Show(this, error.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Warning); }
    }

    private async void OnClosing(object? sender, FormClosingEventArgs e)
    {
        if (allowClose) return;
        e.Cancel = true;
        if (closing) return;
        closing = true;
        try
        {
            if (origin.Length > 0)
            {
                using var request = new HttpRequestMessage(HttpMethod.Post, origin + "/api/shutdown");
                request.Headers.Add("X-App-Token", token); request.Headers.Add("Origin", origin);
                request.Content = new StringContent("{}", Encoding.UTF8, "application/json");
                using var response = await client.SendAsync(request);
                response.EnsureSuccessStatusCode();
            }
            if (worker is { HasExited: false })
            {
                using var wait = new CancellationTokenSource(TimeSpan.FromSeconds(8));
                await worker.WaitForExitAsync(wait.Token);
            }
        }
        catch (Exception error) when (error is HttpRequestException or TaskCanceledException or OperationCanceledException)
        { MessageBox.Show(this, "No se confirmó el cierre del motor. La traza ya escrita se conserva.\n" + error.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Warning); }
        finally { allowClose = true; browser.Dispose(); client.Dispose(); worker?.Dispose(); Close(); }
    }

    [DllImport("dwmapi.dll")] private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref int value, int size);
    [DllImport("user32.dll")] private static extern bool DestroyIcon(IntPtr icon);
}
