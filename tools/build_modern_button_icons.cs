// Build the modern Xbox and PlayStation button icons used by the game's own
// menus, QTEs and text prompts. Everything is drawn here (no game assets), with
// Windows' System.Drawing only:
//   csc /r:System.Drawing.dll /out:build\mbi.exe tools\build_modern_button_icons.cs
//   build\mbi.exe native-rex\src [preview.png]
// Writes, in native-rex\src:
//   default_prompt_sprites.bin  PlayStation prompt sprites ("PSIC\3", 16 pages).
//   xbox_prompt_sprites.bin     Xbox prompt sprites, same layout.
//   modern_face_icons.bin       "MFIC\1", then Xbox and PlayStation face icons
//                               (A, B, X, Y) at 64 and 128 px: base + mip page each.
// Prompt sprite slots: 0-3 faces in prompt-code order (A, X, Y, B), 4/6/8/10 the
// left shoulder, left trigger, right trigger and right stick click. The keyboard
// slots (5, 7, 9, 11, 12-15) are kept from the existing default_prompt_sprites.bin.
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.IO;
using System.Text;

static class ModernButtonIcons {
    const int Size = 128, Page = 16384;
    static readonly Color Body = Color.FromArgb(22, 26, 33), Light = Color.FromArgb(230, 234, 240);

    // Faces in A, B, X, Y order.
    static readonly Color[] XboxColors = {
        Color.FromArgb(111, 220, 60), Color.FromArgb(255, 95, 107), Color.FromArgb(74, 155, 255), Color.FromArgb(255, 204, 51) };
    static readonly string[] XboxLetters = { "A", "B", "X", "Y" };
    static readonly Color[] PlayStationColors = {
        Color.FromArgb(143, 179, 255), Color.FromArgb(255, 111, 125), Color.FromArgb(240, 147, 208), Color.FromArgb(79, 216, 168) };

    static Bitmap Canvas(out Graphics g) {
        var image = new Bitmap(Size, Size, PixelFormat.Format32bppArgb);
        g = Graphics.FromImage(image);
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
        g.Clear(Color.Transparent);
        return image;
    }

    static void Text(Graphics g, string text, RectangleF area, Color color, float largest) {
        using (var format = new StringFormat(StringFormat.GenericTypographic) {
                   Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center })
        using (var brush = new SolidBrush(color)) {
            format.FormatFlags |= StringFormatFlags.NoWrap;
            for (float size = largest; size >= 12; size -= 1)
                using (var font = new Font("Segoe UI", size, FontStyle.Bold, GraphicsUnit.Pixel)) {
                    var extent = g.MeasureString(text, font, 1000, format);
                    if (extent.Width <= area.Width && extent.Height <= area.Height) {
                        g.DrawString(text, font, brush, area, format);
                        return;
                    }
                }
        }
    }

    static Bitmap Face(bool xbox, int face) {
        Graphics g;
        var image = Canvas(out g);
        using (g) {
            var color = xbox ? XboxColors[face] : PlayStationColors[face];
            g.FillEllipse(new SolidBrush(Body), 6, 6, 116, 116);
            g.DrawEllipse(new Pen(color, 7), 9.5f, 9.5f, 109, 109);
            if (xbox) {
                Text(g, XboxLetters[face], new RectangleF(20, 18, 88, 90), color, 76);
            } else {
                var pen = new Pen(color, 9) { LineJoin = LineJoin.Round, StartCap = LineCap.Round, EndCap = LineCap.Round };
                if (face == 0) { g.DrawLine(pen, 44, 44, 84, 84); g.DrawLine(pen, 84, 44, 44, 84); }
                if (face == 1) g.DrawEllipse(pen, 40, 40, 48, 48);
                if (face == 2) g.DrawRectangle(pen, 43, 43, 42, 42);
                if (face == 3) g.DrawPolygon(pen, new[] { new PointF(64, 36), new PointF(90, 82), new PointF(38, 82) });
            }
        }
        return image;
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

    // Shoulders and triggers: a dark plate; triggers get a taller, rounded top.
    static Bitmap Plate(string label, bool trigger) {
        Graphics g;
        var image = Canvas(out g);
        using (g) {
            var area = trigger ? new RectangleF(12, 20, 104, 88) : new RectangleF(8, 32, 112, 64);
            using (var path = Rounded(area, trigger ? 30 : 20)) {
                g.FillPath(new SolidBrush(Body), path);
                g.DrawPath(new Pen(Light, 6), path);
            }
            Text(g, label, new RectangleF(area.X + 10, area.Y + 6, area.Width - 20, area.Height - 12), Light, 54);
        }
        return image;
    }

    static Bitmap Stick(string label) {
        Graphics g;
        var image = Canvas(out g);
        using (g) {
            g.FillEllipse(new SolidBrush(Body), 6, 6, 116, 116);
            g.DrawEllipse(new Pen(Light, 7), 9.5f, 9.5f, 109, 109);
            g.DrawEllipse(new Pen(Color.FromArgb(120, Light), 3), 26, 26, 76, 76);
            Text(g, label, new RectangleF(24, 26, 80, 76), Light, 48);
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

    // BC3 with an exhaustive endpoint search: icons mix a dark fill, a light rim
    // and transparency inside one 4x4 block, which a bounding box encodes badly.
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
        var candidates = new System.Collections.Generic.List<ushort>();
        int[] low = { 255, 255, 255 }, high = { 0, 0, 0 };
        for (int i = 0; i < 16; ++i) {
            if (px[i * 4 + 3] < 8) continue;
            for (int c = 0; c < 3; ++c) { low[c] = Math.Min(low[c], px[i * 4 + c]); high[c] = Math.Max(high[c], px[i * 4 + c]); }
            var color = Rgb565(px[i * 4], px[i * 4 + 1], px[i * 4 + 2]);
            if (!candidates.Contains(color)) candidates.Add(color);
        }
        if (candidates.Count == 0) candidates.Add(0);
        foreach (var color in new[] { Rgb565(high[0], high[1], high[2]), Rgb565(low[0], low[1], low[2]) })
            if (!candidates.Contains(color)) candidates.Add(color);
        ushort c0 = candidates[0], c1 = candidates[0];
        uint colorBits = 0;
        long bestError = long.MaxValue;
        for (int a = 0; a < candidates.Count; ++a)
            for (int b = a; b < candidates.Count; ++b) {
                ushort first = candidates[a], second = candidates[b];
                if (first < second) { var t = first; first = second; second = t; }
                var e0 = Expand(first); var e1 = Expand(second);
                var palette = new int[4][] { e0, e1, new int[3], new int[3] };
                for (int c = 0; c < 3; ++c) {
                    palette[2][c] = (2 * e0[c] + e1[c]) / 3;
                    palette[3][c] = (e0[c] + 2 * e1[c]) / 3;
                }
                // Four-colour mode needs first > second; equal endpoints decode as one colour.
                long total = 0;
                uint bits = 0;
                for (int i = 0; i < 16; ++i) {
                    int bestIndex = 0, error = int.MaxValue;
                    for (int j = 0; j < (first == second ? 1 : 4); ++j) {
                        int dr = palette[j][0] - px[i * 4], dg = palette[j][1] - px[i * 4 + 1], db = palette[j][2] - px[i * 4 + 2];
                        int e = dr * dr + dg * dg + db * db;
                        if (e < error) { error = e; bestIndex = j; }
                    }
                    total += (long)error * (px[i * 4 + 3] + 1);
                    bits |= (uint)bestIndex << (2 * i);
                }
                if (total < bestError) { bestError = total; c0 = first; c1 = second; colorBits = bits; }
            }
        block[8] = (byte)c0; block[9] = (byte)(c0 >> 8);
        block[10] = (byte)c1; block[11] = (byte)(c1 >> 8);
        for (int i = 0; i < 4; ++i) block[12 + i] = (byte)(colorBits >> (8 * i));
        return block;
    }

    // One tiled BC3 page holding the image scaled to side x side.
    static byte[] Encode(Bitmap image, int side) {
        var page = new byte[Page];
        using (var scaled = new Bitmap(side, side, PixelFormat.Format32bppArgb)) {
            using (var g = Graphics.FromImage(scaled)) {
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                g.Clear(Color.Transparent);
                g.DrawImage(image, 0, 0, side, side);
            }
            var data = scaled.LockBits(new Rectangle(0, 0, side, side), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
            var bgra = new byte[side * side * 4];
            System.Runtime.InteropServices.Marshal.Copy(data.Scan0, bgra, 0, bgra.Length);
            scaled.UnlockBits(data);
            for (int by = 0; by < side / 4; ++by)
                for (int bx = 0; bx < side / 4; ++bx) {
                    var px = new int[64];
                    for (int i = 0; i < 16; ++i) {
                        int x = bx * 4 + i % 4, y = by * 4 + i / 4, s = (y * side + x) * 4;
                        px[i * 4] = bgra[s + 2]; px[i * 4 + 1] = bgra[s + 1]; px[i * 4 + 2] = bgra[s]; px[i * 4 + 3] = bgra[s + 3];
                    }
                    var block = EncodeBlock(px);
                    // Xenos stores 16-bit words big-endian.
                    int target = TiledOffset(bx, by);
                    for (int i = 0; i < 16; i += 2) { page[target + i] = block[i + 1]; page[target + i + 1] = block[i]; }
                }
        }
        return page;
    }

    // Prompt sprites are bound without mip levels and drawn at about 48 px, so
    // pre-filter to that size: shrinking then needs no detail the GPU would skip.
    static Bitmap Smoothed(Bitmap image, int side) {
        var result = new Bitmap(Size, Size, PixelFormat.Format32bppPArgb);
        using (var small = new Bitmap(side, side, PixelFormat.Format32bppPArgb)) {
            foreach (var pass in new[] { new { from = image, to = small, n = side }, new { from = small, to = result, n = Size } })
                using (var g = Graphics.FromImage(pass.to)) {
                    g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                    g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                    g.Clear(Color.Transparent);
                    using (var wrap = new ImageAttributes()) {
                        wrap.SetWrapMode(WrapMode.TileFlipXY);
                        g.DrawImage(pass.from, new Rectangle(0, 0, pass.n, pass.n), 0, 0, pass.from.Width, pass.from.Height,
                                    GraphicsUnit.Pixel, wrap);
                    }
                }
        }
        return result;
    }

    static byte[] PromptSprites(bool xbox, byte[] existing, Graphics sheet, int row) {
        const string magic = "PSIC\u0003\0\0\0";
        if (existing.Length != 8 + 16 * Page || Encoding.ASCII.GetString(existing, 0, 8) != magic)
            throw new InvalidDataException("Unexpected default_prompt_sprites.bin");
        var output = (byte[])existing.Clone();
        int[] faceOrder = { 0, 2, 3, 1 };  // Prompt codes are A, X, Y, B.
        for (int slot = 0; slot < 11; ++slot) {
            Bitmap image = null;
            if (slot < 4) image = Face(xbox, faceOrder[slot]);
            else if (slot == 4) image = Plate(xbox ? "LB" : "L1", false);
            else if (slot == 6) image = Plate(xbox ? "LT" : "L2", true);
            else if (slot == 8) image = Plate(xbox ? "RT" : "R2", true);
            else if (slot == 10) image = Stick(xbox ? "RS" : "R3");
            if (image == null) continue;
            using (image)
            using (var smooth = Smoothed(image, 56)) {
                Buffer.BlockCopy(Encode(smooth, Size), 0, output, 8 + slot * Page, Page);
                sheet.DrawImage(image, slot * Size, row * Size);
            }
        }
        return output;
    }

    static int Main(string[] args) {
        if (args.Length < 1) { Console.Error.WriteLine("usage: mbi <native-rex\\src> [preview.png]"); return 2; }
        string folder = args[0];
        var existing = File.ReadAllBytes(Path.Combine(folder, "default_prompt_sprites.bin"));
        using (var preview = new Bitmap(11 * Size, 4 * Size, PixelFormat.Format32bppArgb))
        using (var sheet = Graphics.FromImage(preview)) {
            sheet.Clear(Color.FromArgb(40, 44, 52));
            var playstation = PromptSprites(false, existing, sheet, 0);
            var xbox = PromptSprites(true, existing, sheet, 1);
            using (var faces = new MemoryStream()) {
                faces.Write(Encoding.ASCII.GetBytes("MFIC\u0001\0\0\0"), 0, 8);
                for (int style = 0; style < 2; ++style)
                    for (int face = 0; face < 4; ++face)
                        using (var image = Face(style == 0, face)) {
                            sheet.DrawImage(image, face * Size, (2 + style) * Size);
                            foreach (int side in new[] { 64, 128 }) {
                                faces.Write(Encode(image, side), 0, Page);
                                faces.Write(Encode(image, side / 2), 0, Page);
                            }
                        }
                File.WriteAllBytes(Path.Combine(folder, "modern_face_icons.bin"), faces.ToArray());
            }
            File.WriteAllBytes(Path.Combine(folder, "default_prompt_sprites.bin"), playstation);
            File.WriteAllBytes(Path.Combine(folder, "xbox_prompt_sprites.bin"), xbox);
            if (args.Length > 1) preview.Save(args[1], ImageFormat.Png);
        }
        Console.WriteLine("Wrote modern Xbox and PlayStation button icons.");
        return 0;
    }
}
