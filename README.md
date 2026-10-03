# 峻爸 KTV 多文字軌核對器 v1.4｜KTV 精準閱讀版

獨立的離線錄音＋文字軌核對工具。Windows 只產 Single EXE；Android 產 APK。此專案不含 Gemini / 雲端上傳。

## v1.4 重點
- Android 修正 DOCX/Word 讀取：支援 Word 表格時間範圍，也支援 `[00:00:30]` 這類單點時間碼。
- 單點時間碼 Word 會依下一個時間點，把段落切成較短句子並估算句內時間，避免整個 30–60 秒區塊一起反白。
- Android KTV 上方新增「目前句」提示列，播放到哪一段會固定顯示目前時間與文字。
- Android 上方 KTV 與下方時間軸仍可各自停止／恢復跟隨。
- Android 文字尺寸改為程式內固定閱讀尺寸，不再被手機「超大系統字型」整個放大破版；可用 A− / A+ 自行調整 KTV 字級。
- Android 15+ 加入狀態列／導覽列 Insets，避免標題與系統列重疊。
- KTV 顏色改為「淺藍＝目前句、黃色＝目前句已播放部分」，更容易看出播放位置。
- Windows 的「比較文字軌」改成預設收合；沒有啟用比較時，時間軸自動隱藏比較文字與核對結果欄，把寬度留給逐字稿。
- Windows/Android 的 TXT/DOCX 單點時間碼解析同步改善。

## Word 格式
支援 `.docx`。舊式 `.doc` 請先在 Word 另存為 `.docx`。

時間資料優先順序：
1. SRT/VTT/JSON 或 DOCX 表格中的完整開始～結束時間：精準使用原時間。
2. Word/TXT 的 `[HH:MM:SS]` 單點時間：以相鄰時間點做句子級估算。
3. 完全沒有時間碼的純文字：需要搭配另一條有時間的文字軌或音訊長度做估算對齊。

## GitHub Actions
Workflow：`.github/workflows/build-windows-android-v1.4.yml`

成功後產生：
- `Junba-KTV-MultiTrack-v1.4-Single-EXE-Windows-x64`
- `Junba-KTV-MultiTrack-v1.4-Android-APK`
