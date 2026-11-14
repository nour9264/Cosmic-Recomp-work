"""Generate native-rex/src/menu_text_table.inc: the native Options pages' text in every language.

Columns: English, Arabic, German, French, Spanish, Italian, Portuguese, Turkish, Russian, Japanese. The
table is written with octal escapes so the C++ sources stay plain ASCII."""
from pathlib import Path

NAMES = {'English': 'English', 'Arabic': 'العربية', 'German': 'Deutsch', 'French': 'Français', 'Spanish': 'Español',
         'Italian': 'Italiano', 'Portuguese': 'Português', 'Turkish': 'Türkçe', 'Russian': 'Русский', 'Japanese': '日本語'}

# English | ar | de | fr | es | it | pt | tr | ru | ja
ROWS = [
    ('OPTIONS', 'الخيارات', 'OPTIONEN', 'OPTIONS', 'OPCIONES', 'OPZIONI', 'OPÇÕES', 'SEÇENEKLER', 'НАСТРОЙКИ', 'オプション'),
    ('GAMEPLAY', 'اللعب', 'SPIELVERLAUF', 'JEU', 'JUGABILIDAD', 'GIOCO', 'JOGABILIDADE', 'OYNANIŞ', 'ИГРА', 'ゲームプレイ'),
    ('SOUND', 'الصوت', 'TON', 'SON', 'SONIDO', 'AUDIO', 'ÁUDIO', 'SES', 'ЗВУК', 'サウンド'),
    ('VIDEO', 'الفيديو', 'VIDEO', 'VIDÉO', 'VÍDEO', 'VIDEO', 'VÍDEO', 'GÖRÜNTÜ', 'ВИДЕО', '映像'),
    ('CREDITS', 'الشكر والتقدير', 'CREDITS', 'GÉNÉRIQUE', 'CRÉDITOS', 'CREDITI', 'CRÉDITOS', 'EMEĞİ GEÇENLER', 'ТИТРЫ', 'クレジット'),
    ('Output Resolution', 'دقة الإخراج', 'Ausgabeauflösung', 'Résolution de sortie', 'Resolución de salida', 'Risoluzione di uscita', 'Resolução de saída', 'Çıkış çözünürlüğü', 'Разрешение вывода', '出力解像度'),
    ('Frame Limit', 'حد الإطارات', 'Bildratenlimit', "Limite d'images", 'Límite de fotogramas', 'Limite di fotogrammi', 'Limite de quadros', 'Kare sınırı', 'Лимит кадров', 'フレーム制限'),
    ('Show FPS', 'إظهار FPS', 'FPS anzeigen', 'Afficher les FPS', 'Mostrar FPS', 'Mostra FPS', 'Mostrar FPS', 'FPS göster', 'Показывать FPS', 'FPS表示'),
    ('Display Mode', 'وضع العرض', 'Anzeigemodus', "Mode d'affichage", 'Modo de pantalla', 'Modalità schermo', 'Modo de exibição', 'Ekran modu', 'Режим экрана', '表示モード'),
    ('Button Icons', 'أيقونات الأزرار', 'Tastensymbole', 'Icônes des boutons', 'Iconos de botones', 'Icone dei pulsanti', 'Ícones dos botões', 'Düğme simgeleri', 'Значки кнопок', 'ボタンアイコン'),
    ('Internal Resolution', 'الدقة الداخلية', 'Interne Auflösung', 'Résolution interne', 'Resolución interna', 'Risoluzione interna', 'Resolução interna', 'İç çözünürlük', 'Внутреннее разрешение', '内部解像度'),
    ('Anti-Aliasing', 'تنعيم الحواف', 'Kantenglättung', 'Anticrénelage', 'Suavizado de bordes', 'Anti-aliasing', 'Suavização de bordas', 'Kenar yumuşatma', 'Сглаживание', 'アンチエイリアス'),
    ('Texture Filtering', 'تصفية الخامات', 'Texturfilterung', 'Filtrage des textures', 'Filtrado de texturas', 'Filtro texture', 'Filtragem de texturas', 'Doku filtreleme', 'Фильтрация текстур', 'テクスチャフィルタリング'),
    ('Sharpening', 'التحديد', 'Schärfung', 'Netteté', 'Nitidez', 'Nitidezza', 'Nitidez', 'Keskinleştirme', 'Резкость', 'シャープネス'),
    ('Screen Bloom', 'توهج الشاشة', 'Bildschirm-Bloom', "Bloom d'écran", 'Resplandor de pantalla', 'Bloom dello schermo', 'Bloom de tela', 'Ekran parlaması', 'Свечение экрана', '画面ブルーム'),
    ('Game Monitor', 'شاشة اللعبة', 'Spielmonitor', 'Écran du jeu', 'Monitor del juego', 'Monitor di gioco', 'Monitor do jogo', 'Oyun monitörü', 'Монитор игры', 'ゲームモニター'),
    ('Language', 'اللغة', 'Sprache', 'Langue', 'Idioma', 'Lingua', 'Idioma', 'Dil', 'Язык', '言語'),
    ('Unlimited', 'غير محدود', 'Unbegrenzt', 'Illimité', 'Sin límite', 'Illimitato', 'Ilimitado', 'Sınırsız', 'Без ограничений', '無制限'),
    ('On', 'تشغيل', 'An', 'Activé', 'Activado', 'Attivo', 'Ligado', 'Açık', 'Вкл.', 'オン'),
    ('Off', 'إيقاف', 'Aus', 'Désactivé', 'Desactivado', 'Disattivo', 'Desligado', 'Kapalı', 'Выкл.', 'オフ'),
    ('Windowed', 'نافذة', 'Fenster', 'Fenêtré', 'En ventana', 'Finestra', 'Em janela', 'Pencereli', 'В окне', 'ウィンドウ'),
    ('Borderless', 'بدون إطار', 'Rahmenlos', 'Sans bordure', 'Sin bordes', 'Senza bordi', 'Sem bordas', 'Çerçevesiz', 'Без рамки', 'ボーダーレス'),
    ('Exclusive', 'حصري', 'Exklusiv', 'Exclusif', 'Exclusivo', 'Esclusivo', 'Exclusivo', 'Ayrıcalıklı', 'Эксклюзивный', '排他'),
    ('Keyboard and Mouse', 'لوحة المفاتيح والفأرة', 'Tastatur und Maus', 'Clavier et souris', 'Teclado y ratón', 'Tastiera e mouse', 'Teclado e mouse', 'Klavye ve fare', 'Клавиатура и мышь', 'キーボードとマウス'),
    ('Auto', 'تلقائي', 'Automatisch', 'Auto', 'Automático', 'Automatico', 'Automático', 'Otomatik', 'Авто', '自動'),
    ('Original', 'الأصلي', 'Original', 'Original', 'Original', 'Originale', 'Original', 'Orijinal', 'Оригинал', 'オリジナル'),
    ('Native (1x)', 'أصلي (1x)', 'Nativ (1x)', 'Natif (1x)', 'Nativa (1x)', 'Nativa (1x)', 'Nativa (1x)', 'Yerel (1x)', 'Нативное (1x)', 'ネイティブ (1x)'),
    ('Low', 'منخفض', 'Niedrig', 'Faible', 'Bajo', 'Basso', 'Baixo', 'Düşük', 'Низкий', '低'),
    ('Medium', 'متوسط', 'Mittel', 'Moyen', 'Medio', 'Medio', 'Médio', 'Orta', 'Средний', '中'),
    ('High', 'مرتفع', 'Hoch', 'Élevé', 'Alto', 'Alto', 'Alto', 'Yüksek', 'Высокий', '高'),
    ('Invert Up / Down', 'عكس أعلى / أسفل', 'Oben / Unten umkehren', 'Inverser haut / bas', 'Invertir arriba / abajo', 'Inverti su / giù', 'Inverter cima / baixo', 'Yukarı / aşağıyı ters çevir', 'Инвертировать вверх / вниз', '上下を反転'),
    ('Invert Left / Right', 'عكس يسار / يمين', 'Links / Rechts umkehren', 'Inverser gauche / droite', 'Invertir izquierda / derecha', 'Inverti sinistra / destra', 'Inverter esquerda / direita', 'Sol / sağı ters çevir', 'Инвертировать влево / вправо', '左右を反転'),
    ('Vibration', 'الاهتزاز', 'Vibration', 'Vibration', 'Vibración', 'Vibrazione', 'Vibração', 'Titreşim', 'Вибрация', '振動'),
    ('Play as Albedo', 'اللعب كـ Albedo', 'Als Albedo spielen', "Jouer en tant qu'Albedo", 'Jugar como Albedo', 'Gioca come Albedo', 'Jogar como Albedo', 'Albedo olarak oyna', 'Играть за Albedo', 'Albedoとしてプレイ'),
    ('Background Controller Input', 'إدخال ذراع التحكم في الخلفية', 'Controller-Eingabe im Hintergrund', 'Entrée manette en arrière-plan', 'Entrada del mando en segundo plano', 'Input del controller in background', 'Entrada do controle em segundo plano', 'Arka planda kumanda girişi', 'Ввод с геймпада в фоне', 'バックグラウンドでのコントローラー入力'),
    ('Customize Keyboard and Mouse Controls', 'تخصيص أدوات التحكم بلوحة المفاتيح والفأرة', 'Tastatur- und Maussteuerung anpassen', 'Personnaliser clavier et souris', 'Personalizar teclado y ratón', 'Personalizza tastiera e mouse', 'Personalizar teclado e mouse', 'Klavye ve fare kontrollerini özelleştir', 'Настроить клавиатуру и мышь', 'キーボードとマウスの操作設定'),
    ('Wipe Data', 'مسح البيانات', 'Daten löschen', 'Effacer les données', 'Borrar datos', 'Cancella dati', 'Apagar dados', 'Verileri sil', 'Стереть данные', 'データ消去'),
    ('Field of View', 'زاوية الرؤية', 'Sichtfeld', 'Champ de vision', 'Campo de visión', 'Campo visivo', 'Campo de visão', 'Görüş alanı', 'Поле зрения', '視野角'),
    ('OPEN', 'فتح', 'ÖFFNEN', 'OUVRIR', 'ABRIR', 'APRI', 'ABRIR', 'AÇ', 'ОТКРЫТЬ', '開く'),
    ('RESET PROGRESS', 'إعادة ضبط التقدم', 'FORTSCHRITT ZURÜCKSETZEN', 'RÉINITIALISER LA PROGRESSION', 'REINICIAR PROGRESO', 'AZZERA PROGRESSI', 'REDEFINIR PROGRESSO', 'İLERLEMEYİ SIFIRLA', 'СБРОСИТЬ ПРОГРЕСС', '進行状況をリセット'),
    ('CONFIRM RESET', 'تأكيد إعادة الضبط', 'ZURÜCKSETZEN BESTÄTIGEN', 'CONFIRMER LA RÉINITIALISATION', 'CONFIRMAR REINICIO', 'CONFERMA AZZERAMENTO', 'CONFIRMAR REDEFINIÇÃO', 'SIFIRLAMAYI ONAYLA', 'ПОДТВЕРДИТЬ СБРОС', 'リセットを確認'),
    ('Music Volume', 'مستوى الموسيقى', 'Musiklautstärke', 'Volume de la musique', 'Volumen de la música', 'Volume musica', 'Volume da música', 'Müzik ses düzeyi', 'Громкость музыки', 'ミュージック音量'),
    ('SFX Volume', 'مستوى المؤثرات', 'Effektlautstärke', 'Volume des effets', 'Volumen de efectos', 'Volume effetti', 'Volume dos efeitos', 'Efekt ses düzeyi', 'Громкость эффектов', '効果音の音量'),
    ('Voice Volume', 'مستوى الأصوات', 'Sprachlautstärke', 'Volume des voix', 'Volumen de voces', 'Volume voci', 'Volume das vozes', 'Seslendirme düzeyi', 'Громкость голосов', 'ボイス音量'),
    ('Music Integration', 'تكامل الموسيقى', 'Musikintegration', 'Intégration musicale', 'Integración de música', 'Integrazione musicale', 'Integração de música', 'Müzik entegrasyonu', 'Интеграция музыки', 'ミュージック連携'),
    ('Music Overlay Shortcut', 'اختصار نافذة الموسيقى', 'Musik-Overlay-Kürzel', 'Raccourci superposition musicale', 'Atajo de superposición de música', 'Scorciatoia overlay musicale', 'Atalho da sobreposição de música', 'Müzik kaplaması kısayolu', 'Кнопка оверлея музыки', 'ミュージックオーバーレイのショートカット'),
    ('BACK', 'رجوع', 'ZURÜCK', 'RETOUR', 'ATRÁS', 'INDIETRO', 'VOLTAR', 'GERİ', 'НАЗАД', '戻る'),
    ('SELECT', 'اختيار', 'AUSWÄHLEN', 'SÉLECTIONNER', 'SELECCIONAR', 'SELEZIONA', 'SELECIONAR', 'SEÇ', 'ВЫБРАТЬ', '選択'),
    ('Select to save  |  Applies after restart', 'اختر للحفظ  |  يسري بعد إعادة التشغيل', 'Auswählen zum Speichern  |  Gilt nach Neustart', 'Sélectionner pour enregistrer  |  S\'applique après redémarrage', 'Seleccionar para guardar  |  Se aplica al reiniciar', 'Seleziona per salvare  |  Si applica dopo il riavvio', 'Selecionar para salvar  |  Aplicado após reiniciar', 'Kaydetmek için seç  |  Yeniden başlatınca uygulanır', 'Выбрать для сохранения  |  Применится после перезапуска', '選択で保存  |  再起動後に反映'),
    ('Left / Right to change  |  Select to apply', 'يمين / يسار للتغيير  |  اختر للتطبيق', 'Links / Rechts zum Ändern  |  Auswählen zum Anwenden', 'Gauche / Droite pour changer  |  Sélectionner pour appliquer', 'Izquierda / Derecha para cambiar  |  Seleccionar para aplicar', 'Sinistra / Destra per cambiare  |  Seleziona per applicare', 'Esquerda / Direita para alterar  |  Selecionar para aplicar', 'Değiştirmek için Sol / Sağ  |  Uygulamak için seç', 'Влево / вправо для смены  |  Выбрать для применения', '左 / 右で変更  |  選択で適用'),
    ('Reset saved progress? Backup kept.', 'إعادة ضبط التقدم المحفوظ؟ تبقى نسخة احتياطية.', 'Gespeicherten Fortschritt zurücksetzen? Sicherung bleibt erhalten.', 'Réinitialiser la progression ? Une sauvegarde est conservée.', '¿Reiniciar el progreso guardado? Se conserva una copia.', 'Azzerare i progressi salvati? Il backup viene conservato.', 'Redefinir o progresso salvo? Um backup é mantido.', 'Kayıtlı ilerleme sıfırlansın mı? Yedek saklanır.', 'Сбросить сохранённый прогресс? Резервная копия останется.', '保存した進行状況をリセットしますか？バックアップは残ります。'),
]
for english, native in NAMES.items():
    ROWS.append((english,) + (native,) * 9)


def escaped(text):
    return '"' + ''.join(chr(b) if 32 <= b < 127 and chr(b) not in '"\\?' else '\\%03o' % b for b in text.encode('utf8')) + '"'


def main():
    out = ['// Generated by tools/gen_menu_text.py. English, Arabic, German, French, Spanish, Italian, Portuguese, Turkish, Russian, Japanese.']
    for row in ROWS:
        assert len(row) == 10, row[0]
        out.append('{' + ', '.join(escaped(cell) for cell in row) + '},')
    Path(__file__).resolve().parents[1].joinpath('native-rex/src/menu_text_table.inc').write_text('\n'.join(out) + '\n', encoding='ascii')
    print(len(ROWS), 'rows')


if __name__ == '__main__':
    main()
