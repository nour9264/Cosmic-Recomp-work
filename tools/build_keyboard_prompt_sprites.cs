// Build native-rex/src/keyboard_prompt_sprites.bin: one 128px prompt sprite per
// bindable keyboard/mouse token (see KeyToken in keyboard_mouse_controls.h).
// Uses only Windows' System.Drawing, so no extra tooling is needed:
//   csc /r:System.Drawing.dll /out:build\kps.exe tools\build_keyboard_prompt_sprites.cs
//   build\kps.exe native-rex\src\keyboard_prompt_sprites.bin native-rex\src\keyboard_prompt_icons.bin [preview.png]
// Sprites: "KMIC\1\0\0\0", u32 count, then per sprite a 16-byte ASCII token
// and a 16 KiB page in the same tiled BC3 form as default_prompt_sprites.bin.
// Icons: "KMIR\1\0\0\0", u32 count, then a 16-byte token and 64x64 RGBA each,
// for host (ImGui) pages that draw the same keycaps.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.IO;
using System.Text;

static class KeyboardPromptSprites {
    const int Size = 128, Page = 16384;

    static readonly Color Cap = Color.FromArgb(244, 245, 247), Edge = Color.FromArgb(19, 24, 32),
        Lip = Color.FromArgb(178, 184, 194), Ink = Color.FromArgb(16, 24, 32),
        Highlight = Color.FromArgb(151, 235, 40);

    static List<KeyValuePair<string, string>> Keys() {
        var keys = new List<KeyValuePair<string, string>>();
        Action<string, string> add = (token, label) => keys.Add(new KeyValuePair<string, string>(token, label));
        for (char c = 'A'; c <= 'Z'; ++c) add(c.ToString(), c.ToString());
        for (char c = '0'; c <= '9'; ++c) add(c.ToString(), c.ToString());
        for (int i = 1; i <= 12; ++i) add("F" + i, "F" + i);
        for (int i = 0; i <= 9; ++i) add("Numpad" + i, "NUM" + i);
        string[,] named = {
            {"Escape", "ESC"}, {"Space", "SPACE"}, {"Return", "ENTER"}, {"Tab", "TAB"},
            {"Backspace", "BKSP"}, {"Shift", "SHIFT"}, {"Control", "CTRL"}, {"Alt", "ALT"},
            {"Insert", "INS"}, {"Delete", "DEL"}, {"Home", "HOME"}, {"End", "END"},
            {"PageUp", "PG UP"}, {"PageDown", "PG DN"}, {"CapsLock", "CAPS"}, {"NumLock", "NUMLK"},
            {"ScrollLock", "SCRLK"}, {"PrintScreen", "PRTSC"}, {"Pause", "PAUSE"},
            {"Quote", "'"}, {"Comma", ","}, {"Minus", "-"}, {"Period", "."}, {"Slash", "/"},
            {"Semicolon", ";"}, {"Plus", "="}, {"LBracket", "["}, {"RBracket", "]"},
            {"Backslash", "\\"}, {"Backtick", "`"}, {"NumpadEnter", "NUM ENT"},
            {"NumpadPlus", "NUM +"}, {"NumpadMinus", "NUM -"}, {"NumpadStar", "NUM *"},
            {"NumpadSlash", "NUM /"},
            {"Up", "↑"}, {"Down", "↓"}, {"Left", "←"}, {"Right", "→"},
            {"LMB", "L"}, {"RMB", "R"}, {"MMB", "M"}, {"Mouse4", "4"}, {"Mouse5", "5"},
        };
        for (int i = 0; i < named.GetLength(0); ++i) add(named[i, 0], named[i, 1]);
        return keys;
    }

    static GraphicsPath Rounded(RectangleF r, float radius) {
        var path = new GraphicsPath();
        float d = radius * 2;
        path.AddArc(r.X, r.Y, d, d, 180, 90);
        path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
        path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
        path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
        path.CloseFigure();
        return path;
    }

    static void Label(Graphics g, string text, RectangleF area, bool arrow) {
        // Measure and draw with the same single-line typographic layout.
        using (var format = new StringFormat(StringFormat.GenericTypographic) {
                   Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center })
        using (var brush = new SolidBrush(Ink)) {
            format.FormatFlags |= StringFormatFlags.NoWrap;
            string family = arrow ? "Segoe UI Symbol" : "Segoe UI";
            // Largest size that fits the keycap face.
            for (float size = arrow ? 64 : 58; size >= 12; size -= 1) {
                using (var font = new Font(family, size, FontStyle.Bold, GraphicsUnit.Pixel)) {
                    var extent = g.MeasureString(text, font, 1000, format);
                    if (extent.Width <= area.Width - 18 && extent.Height <= area.Height - 8) {
                        g.DrawString(text, font, brush, area, format);
                        return;
                    }
                }
            }
        }
    }

    static Bitmap Keycap(string label) {
        var image = new Bitmap(Size, Size, PixelFormat.Format32bppArgb);
        using (var g = Graphics.FromImage(image)) {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
            g.Clear(Color.Transparent);
            using (var lip = Rounded(new RectangleF(6, 12, 116, 110), 18)) {
                g.FillPath(new SolidBrush(Lip), lip);
                g.DrawPath(new Pen(Edge, 5), lip);
            }
            using (var face = Rounded(new RectangleF(10, 8, 108, 98), 15)) {
                g.FillPath(new SolidBrush(Cap), face);
                g.DrawPath(new Pen(Edge, 4), face);
            }
            bool arrow = label.Length == 1 && label[0] >= '←' && label[0] <= '↓';
            Label(g, label, new RectangleF(10, 8, 108, 98), arrow);
        }
        return image;
    }

    static Bitmap Mouse(string token) {
        var image = new Bitmap(Size, Size, PixelFormat.Format32bppArgb);
        using (var g = Graphics.FromImage(image)) {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
            g.Clear(Color.Transparent);
            var body = new RectangleF(28, 6, 72, 116);
            using (var shell = Rounded(body, 34)) {
                g.FillPath(new SolidBrush(Cap), shell);
                g.SetClip(shell);
                var hot = new SolidBrush(Highlight);
                if (token == "LMB") g.FillRectangle(hot, 28, 6, 36, 50);
                if (token == "RMB") g.FillRectangle(hot, 64, 6, 36, 50);
                g.ResetClip();
                var pen = new Pen(Edge, 5);
                g.DrawLine(pen, 28, 56, 100, 56);
                g.DrawLine(pen, 64, 6, 64, 56);
                using (var wheel = Rounded(new RectangleF(57, 20, 14, 26), 7)) {
                    g.FillPath(new SolidBrush(token == "MMB" ? Highlight : Lip), wheel);
                    g.DrawPath(new Pen(Edge, 3), wheel);
                }
                g.DrawPath(pen, shell);
            }
            if (token == "Mouse4" || token == "Mouse5") {
                // Side buttons on the left flank, with the button number.
                float y = token == "Mouse4" ? 74 : 60;
                using (var side = Rounded(new RectangleF(14, y, 20, 14), 5)) {
                    g.FillPath(new SolidBrush(Highlight), side);
                    g.DrawPath(new Pen(Edge, 3), side);
                }
                Label(g, token == "Mouse4" ? "4" : "5", new RectangleF(48, 62, 44, 50), false);
            }
        }
        return image;
    }

    // tiled_offset from tools/extract_discord_level_images.py (pitch 32 blocks, 16-byte blocks).
    static int TiledOffset(int x, int y) {
        const int pitch = 32, log2 = 4;
        int macro = ((x >> 5) + (y >> 5) * (pitch >> 5)) << (log2 + 7);
        int micro = ((x & 7) + ((y & 14) << 2)) << log2;
        int offset = macro + ((micro & ~15) << 1) + (micro & 15) + ((y & 1) << 4);
        return ((offset & ~511) << 3) + ((y & 16) << 7) + ((offset & 448) << 2) +
               (((((y & 8) >> 2) + (x >> 3)) & 3) << 6) + (offset & 63);
    }

    static ushort Rgb565(int r, int g, int b) { return (ushort)(((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)); }
    static int[] Expand(ushort c) {
        int r = c >> 11, g = (c >> 5) & 63, b = c & 31;
        return new[] { (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2) };
    }

    // Straightforward BC3: interpolated alpha block plus a bounding-box colour block.
    static byte[] EncodeBlock(int[] px) {
        var block = new byte[16];
        int a0 = 0, a1 = 255;
        for (int i = 0; i < 16; ++i) { a0 = Math.Max(a0, px[i * 4 + 3]); a1 = Math.Min(a1, px[i * 4 + 3]); }
        block[0] = (byte)a0; block[1] = (byte)a1;
        var alphas = new int[8];
        alphas[0] = a0; alphas[1] = a1;
        for (int i = 1; i < 7; ++i) alphas[i + 1] = ((7 - i) * a0 + i * a1) / 7;
        ulong alphaBits = 0;
        for (int i = 0; i < 16; ++i) {
            int best = 0, error = int.MaxValue;
            for (int j = 0; j < 8; ++j) {
                int e = Math.Abs(alphas[j] - px[i * 4 + 3]);
                if (e < error) { error = e; best = j; }
            }
            alphaBits |= (ulong)best << (3 * i);
        }
        for (int i = 0; i < 6; ++i) block[2 + i] = (byte)(alphaBits >> (8 * i));

        int[] low = { 255, 255, 255 }, high = { 0, 0, 0 };
        bool any = false;
        for (int i = 0; i < 16; ++i) {
            if (px[i * 4 + 3] < 8) continue;
            any = true;
            for (int c = 0; c < 3; ++c) { low[c] = Math.Min(low[c], px[i * 4 + c]); high[c] = Math.Max(high[c], px[i * 4 + c]); }
        }
        if (!any) { low = new[] { 0, 0, 0 }; high = new[] { 0, 0, 0 }; }
        ushort c0 = Rgb565(high[0], high[1], high[2]), c1 = Rgb565(low[0], low[1], low[2]);
        if (c0 < c1) { var t = c0; c0 = c1; c1 = t; }
        var e0 = Expand(c0); var e1 = Expand(c1);
        var palette = new int[4][];
        palette[0] = e0; palette[1] = e1;
        palette[2] = new int[3]; palette[3] = new int[3];
        for (int c = 0; c < 3; ++c) {
            palette[2][c] = (2 * e0[c] + e1[c]) / 3;
            palette[3][c] = (e0[c] + 2 * e1[c]) / 3;
        }
        uint colorBits = 0;
        for (int i = 0; i < 16; ++i) {
            int best = 0, error = int.MaxValue;
            for (int j = 0; j < 4; ++j) {
                int dr = palette[j][0] - px[i * 4], dg = palette[j][1] - px[i * 4 + 1], db = palette[j][2] - px[i * 4 + 2];
                int e = dr * dr + dg * dg + db * db;
                if (e < error) { error = e; best = j; }
            }
            colorBits |= (uint)best << (2 * i);
        }
        block[8] = (byte)c0; block[9] = (byte)(c0 >> 8);
        block[10] = (byte)c1; block[11] = (byte)(c1 >> 8);
        for (int i = 0; i < 4; ++i) block[12 + i] = (byte)(colorBits >> (8 * i));
        return block;
    }

    static byte[] Encode(Bitmap image) {
        var page = new byte[Page];
        var data = image.LockBits(new Rectangle(0, 0, Size, Size), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
        var bgra = new byte[Size * Size * 4];
        System.Runtime.InteropServices.Marshal.Copy(data.Scan0, bgra, 0, bgra.Length);
        image.UnlockBits(data);
        for (int by = 0; by < Size / 4; ++by)
            for (int bx = 0; bx < Size / 4; ++bx) {
                var px = new int[64];
                for (int i = 0; i < 16; ++i) {
                    int x = bx * 4 + i % 4, y = by * 4 + i / 4, s = (y * Size + x) * 4;
                    px[i * 4] = bgra[s + 2]; px[i * 4 + 1] = bgra[s + 1]; px[i * 4 + 2] = bgra[s]; px[i * 4 + 3] = bgra[s + 3];
                }
                var block = EncodeBlock(px);
                // Xenos stores 16-bit words big-endian (see retile in prepare_playstation_button_icons.py).
                int target = TiledOffset(bx, by);
                for (int i = 0; i < 16; i += 2) { page[target + i] = block[i + 1]; page[target + i + 1] = block[i]; }
            }
        return page;
    }

    static byte[] Rgba(Bitmap image, int side) {
        using (var small = new Bitmap(side, side, PixelFormat.Format32bppArgb)) {
            using (var g = Graphics.FromImage(small)) {
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                g.Clear(Color.Transparent);
                g.DrawImage(image, 0, 0, side, side);
            }
            var data = small.LockBits(new Rectangle(0, 0, side, side), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
            var bgra = new byte[side * side * 4];
            System.Runtime.InteropServices.Marshal.Copy(data.Scan0, bgra, 0, bgra.Length);
            small.UnlockBits(data);
            for (int i = 0; i < bgra.Length; i += 4) { var b = bgra[i]; bgra[i] = bgra[i + 2]; bgra[i + 2] = b; }
            return bgra;
        }
    }

    static int Main(string[] args) {
        if (args.Length < 2) { Console.Error.WriteLine("usage: kps <sprites.bin> <icons.bin> [preview.png]"); return 2; }
        var keys = Keys();
        using (var output = new MemoryStream())
        using (var icons = new MemoryStream()) {
            output.Write(Encoding.ASCII.GetBytes("KMIC\u0001\0\0\0"), 0, 8);
            output.Write(BitConverter.GetBytes((uint)keys.Count), 0, 4);
            icons.Write(Encoding.ASCII.GetBytes("KMIR\u0001\0\0\0"), 0, 8);
            icons.Write(BitConverter.GetBytes((uint)keys.Count), 0, 4);
            int columns = 12, rows = (keys.Count + columns - 1) / columns;
            using (var sheet = new Bitmap(columns * Size, rows * Size, PixelFormat.Format32bppArgb))
            using (var g = Graphics.FromImage(sheet)) {
                g.Clear(Color.FromArgb(40, 44, 52));
                for (int i = 0; i < keys.Count; ++i) {
                    string token = keys[i].Key;
                    if (token.Length > 15) throw new InvalidDataException("Token too long: " + token);
                    bool mouse = token == "LMB" || token == "RMB" || token == "MMB" || token == "Mouse4" || token == "Mouse5";
                    using (var image = mouse ? Mouse(token) : Keycap(keys[i].Value)) {
                        var name = new byte[16];
                        Encoding.ASCII.GetBytes(token, 0, token.Length, name, 0);
                        output.Write(name, 0, 16);
                        output.Write(Encode(image), 0, Page);
                        icons.Write(name, 0, 16);
                        icons.Write(Rgba(image, 64), 0, 64 * 64 * 4);
                        g.DrawImage(image, (i % columns) * Size, (i / columns) * Size);
                    }
                }
                if (args.Length > 2) sheet.Save(args[2], ImageFormat.Png);
            }
            File.WriteAllBytes(args[0], output.ToArray());
            File.WriteAllBytes(args[1], icons.ToArray());
        }
        Console.WriteLine("Wrote " + keys.Count + " keyboard/mouse prompt sprites.");
        return 0;
    }
}
