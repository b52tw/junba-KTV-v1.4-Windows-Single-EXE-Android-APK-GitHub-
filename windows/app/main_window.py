from __future__ import annotations

import bisect
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .alignment import align_untimed_to_base, align_untimed_to_duration
from .formats import fmt_time, load_track, to_srt, to_vtt
from .html_export import export_html_package
from .models import TextTrack
from .project import load_project, save_project
from .review import compare_tracks

AUDIO_FILTER = "音訊 (*.m4a *.mp3 *.wav *.aac *.flac *.ogg *.wma *.mp4);;所有檔案 (*.*)"
TRACK_FILTER = "逐字稿/字幕 (*.srt *.vtt *.txt *.json *.csv *.docx *.html *.htm);;所有檔案 (*.*)"



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("峻爸 KTV 多文字軌核對器 v1.4｜精準閱讀版")
        self.resize(1400, 900)
        self.audio_path = ""
        self.tracks: list[TextTrack] = []
        self._ranges: list[tuple[int, int]] = []
        self._last_index = -1
        self._review = []
        self._top_follow = True
        self._timeline_follow = True
        self._timeline_current_row = -1

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(0.9)
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.playbackStateChanged.connect(self._state_changed)
        self.player.errorOccurred.connect(self._player_error)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)

        # 1) Audio selection stays compact.
        g_audio = QGroupBox("錄音檔")
        la = QHBoxLayout(g_audio)
        self.audio_label = QLabel("尚未選擇錄音檔")
        self.audio_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        b_audio = QPushButton("選擇錄音檔")
        b_audio.clicked.connect(self.choose_audio)
        la.addWidget(self.audio_label, 1)
        la.addWidget(b_audio)
        layout.addWidget(g_audio)

        # 2) Player controls are always visible.
        ctrl = QHBoxLayout()
        self.play_btn = QPushButton("▶ 播放")
        self.play_btn.clicked.connect(self.play_audio)
        self.pause_btn = QPushButton("⏸ 暫停")
        self.pause_btn.clicked.connect(self.player.pause)
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.clicked.connect(self.stop_audio)
        back = QPushButton("↶ 5秒")
        back.clicked.connect(lambda: self.seek_delta(-5000))
        fwd = QPushButton("5秒 ↷")
        fwd.clicked.connect(lambda: self.seek_delta(5000))
        self.pos_label = QLabel("00:00:00 / 00:00:00")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.player.setPosition)
        self.speed = QComboBox()
        self.speed.addItems(["0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
        self.speed.setCurrentText("1.0x")
        self.speed.currentTextChanged.connect(self._speed_changed)
        for w in (self.play_btn, self.pause_btn, self.stop_btn, back, fwd, self.pos_label):
            ctrl.addWidget(w)
        ctrl.addWidget(self.slider, 1)
        ctrl.addWidget(QLabel("速度"))
        ctrl.addWidget(self.speed)
        layout.addLayout(ctrl)

        # 3) Keep only KTV selection and playback-follow controls on the main line.
        # Comparison is optional and stays collapsed unless the user opens it.
        sel = QHBoxLayout()
        self.active_combo = QComboBox()
        self.active_combo.currentIndexChanged.connect(self.rebuild_views)
        self.compare_combo = QComboBox()
        self.compare_combo.currentIndexChanged.connect(self.rebuild_views)
        self.review_summary = QLabel("未啟用比較")
        self.track_toggle = QPushButton("☰ 文字軌管理 ▾")
        self.track_toggle.clicked.connect(self.toggle_track_panel)
        self.compare_toggle = QPushButton("🔎 比較文字軌 ▾")
        self.compare_toggle.clicked.connect(self.toggle_compare_panel)
        self.top_follow = QCheckBox("上方 KTV 跟隨")
        self.top_follow.setChecked(True)
        self.top_follow.toggled.connect(self._top_follow_changed)
        self.timeline_follow = QCheckBox("下方時間軸跟隨")
        self.timeline_follow.setChecked(True)
        self.timeline_follow.toggled.connect(self._timeline_follow_changed)
        sel.addWidget(QLabel("KTV 文字軌"))
        sel.addWidget(self.active_combo, 3)
        sel.addWidget(self.track_toggle)
        sel.addWidget(self.compare_toggle)
        sel.addWidget(self.top_follow)
        sel.addWidget(self.timeline_follow)
        layout.addLayout(sel)

        self.compare_panel = QGroupBox("文字軌比較（需要時才開啟）")
        lcp = QHBoxLayout(self.compare_panel)
        lcp.addWidget(QLabel("比較軌"))
        lcp.addWidget(self.compare_combo, 3)
        lcp.addWidget(self.review_summary, 2)
        self.compare_panel.setVisible(False)
        layout.addWidget(self.compare_panel)

        # Collapsible track manager: max 3 rows, no giant source-path column.
        self.track_panel = QGroupBox("文字軌管理")
        lt = QVBoxLayout(self.track_panel)
        top = QHBoxLayout()
        for text, cb in (
            ("＋ 加入文字／字幕", self.add_tracks),
            ("移除選取", self.remove_track),
            ("自動對齊未定時文字", self.align_tracks),
        ):
            b = QPushButton(text)
            b.clicked.connect(cb)
            top.addWidget(b)
        top.addStretch(1)
        lt.addLayout(top)
        self.track_table = QTableWidget(0, 3)
        self.track_table.setHorizontalHeaderLabels(["名稱", "時間軸", "狀態"])
        self.track_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.track_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.track_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.track_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.track_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.track_table.setMaximumHeight(155)
        self.track_table.itemChanged.connect(self._track_item_changed)
        lt.addWidget(self.track_table)
        self.track_panel.setVisible(False)
        layout.addWidget(self.track_panel)


        # 4) The KTV text and timeline are the main workspace and get most of the screen.
        splitter = QSplitter(Qt.Vertical)
        self.full_text = QTextEdit()
        self.full_text.setReadOnly(True)
        self.full_text.setPlaceholderText("完整全文會顯示在這裡；播放時目前句段會像 KTV 一樣同步反白。")
        self.full_text.setStyleSheet("QTextEdit { font-size: 19px; line-height: 1.75; padding: 8px; }")
        self.full_text.setMinimumHeight(180)
        splitter.addWidget(self.full_text)

        self.timeline = QTableWidget(0, 6)
        self.timeline.setHorizontalHeaderLabels(["開始", "結束", "講者", "目前文字軌", "比較文字軌", "核對結果"])
        hdr = self.timeline.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.Stretch)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.timeline.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.timeline.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.timeline.cellDoubleClicked.connect(self._timeline_seek)
        self.timeline.setMinimumHeight(220)
        splitter.addWidget(self.timeline)
        splitter.setSizes([360, 390])
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 6)
        layout.addWidget(splitter, 1)

        foot = QHBoxLayout()
        for text, cb in (
            ("開啟專案", self.open_project),
            ("儲存專案", self.save_project),
            ("匯出目前軌 SRT", lambda: self.export_track("srt")),
            ("匯出目前軌 VTT", lambda: self.export_track("vtt")),
            ("產生離線 KTV 網頁包", self.export_html),
        ):
            b = QPushButton(text)
            b.clicked.connect(cb)
            foot.addWidget(b)
        foot.addStretch(1)
        layout.addLayout(foot)

        self.statusBar().showMessage("v1.4：KTV 閱讀優先；比較區預設收合，上方 KTV 與下方時間軸可獨立跟隨。")

    # ---------- Collapsible panels ----------
    def toggle_track_panel(self):
        show = not self.track_panel.isVisible()
        self.track_panel.setVisible(show)
        self.track_toggle.setText("☰ 文字軌管理 ▴" if show else "☰ 文字軌管理 ▾")

    def toggle_compare_panel(self):
        show = not self.compare_panel.isVisible()
        self.compare_panel.setVisible(show)
        self.compare_toggle.setText("🔎 比較文字軌 ▴" if show else "🔎 比較文字軌 ▾")
        if not show:
            # Keep the selected comparison available, but reclaim screen space.
            self.statusBar().showMessage("比較面板已收合；KTV 與時間軸仍可正常使用。", 3500)

    def _top_follow_changed(self, checked):
        self._top_follow = bool(checked)
        if not checked:
            self.full_text.setExtraSelections([])
        else:
            self._position_changed(self.player.position())

    def _timeline_follow_changed(self, checked):
        self._timeline_follow = bool(checked)
        if not checked:
            self._clear_timeline_current()
        else:
            self._position_changed(self.player.position())

    # ---------- Audio / tracks ----------
    def choose_audio(self):
        p, _ = QFileDialog.getOpenFileName(self, "選擇錄音檔", "", AUDIO_FILTER)
        if not p:
            return
        self.audio_path = p
        self.audio_label.setText(p)
        self.player.setSource(QUrl.fromLocalFile(p))

    def add_tracks(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "加入文字/字幕", "", TRACK_FILTER)
        for p in paths:
            try:
                self.tracks.append(load_track(p))
            except Exception as exc:
                QMessageBox.warning(self, "讀取失敗", f"{Path(p).name}\n{exc}")
        self.refresh_tracks()
        self.align_tracks(auto_only=True)

    def remove_track(self):
        rows = sorted({x.row() for x in self.track_table.selectedItems()}, reverse=True)
        for r in rows:
            if 0 <= r < len(self.tracks):
                self.tracks.pop(r)
        self.refresh_tracks()

    def refresh_tracks(self):
        active = self.active_combo.currentIndex()
        comp = self.compare_combo.currentIndex() - 1

        self.track_table.blockSignals(True)
        self.track_table.setRowCount(len(self.tracks))
        for r, track in enumerate(self.tracks):
            vals = [
                track.name,
                "有" if track.timed else "無",
                "估算對齊" if track.estimated else "原始時間碼",
            ]
            for c, value in enumerate(vals):
                item = QTableWidgetItem(value)
                item.setToolTip(f"格式：{track.format_name}\n來源：{track.source_path or '程式產生'}")
                if c != 0:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.track_table.setItem(r, c, item)
        self.track_table.blockSignals(False)

        self.active_combo.blockSignals(True)
        self.compare_combo.blockSignals(True)
        self.active_combo.clear()
        self.compare_combo.clear()
        self.compare_combo.addItem("不比較")
        for idx, track in enumerate(self.tracks, 1):
            suffix = "（估算）" if track.estimated else ""
            label = f"[{idx}] {track.name}{suffix}"
            self.active_combo.addItem(label)
            self.compare_combo.addItem(label)
        if self.tracks:
            self.active_combo.setCurrentIndex(min(max(active, 0), len(self.tracks) - 1))
        if comp >= 0 and self.tracks:
            self.compare_combo.setCurrentIndex(min(comp + 1, len(self.tracks)))
        self.active_combo.blockSignals(False)
        self.compare_combo.blockSignals(False)
        self.rebuild_views()

    def _track_item_changed(self, item):
        if item.column() == 0 and 0 <= item.row() < len(self.tracks):
            self.tracks[item.row()].name = item.text().strip() or self.tracks[item.row()].name
            self.refresh_tracks()

    def _base_track(self):
        return next(
            (t for t in self.tracks if t.timed and not t.estimated and t.segments),
            next((t for t in self.tracks if t.timed and t.segments), None),
        )

    def align_tracks(self, auto_only=False):
        if not self.tracks:
            return
        base = self._base_track()
        duration = self.player.duration() / 1000.0 if self.player.duration() > 0 else 0.0
        changed = False
        for i, track in enumerate(list(self.tracks)):
            if track.timed:
                continue
            if base and base is not track:
                self.tracks[i] = align_untimed_to_base(track, base)
                changed = True
            elif duration > 0:
                self.tracks[i] = align_untimed_to_duration(track, duration)
                changed = True
        if changed:
            self.refresh_tracks()
        elif not auto_only:
            self.statusBar().showMessage("目前沒有需要對齊的未定時文字，或尚未載入可用時間軸／音訊長度。", 7000)

    # ---------- KTV / comparison ----------
    def rebuild_views(self):
        self._ranges = []
        self._last_index = -1
        self._timeline_current_row = -1
        self._review = []
        if not self.tracks or self.active_combo.currentIndex() < 0:
            self.full_text.clear()
            self.timeline.setRowCount(0)
            self.review_summary.setText("尚未選擇文字軌")
            return

        track = self.tracks[self.active_combo.currentIndex()]
        self.full_text.clear()
        cur = self.full_text.textCursor()
        for seg in track.segments:
            start = cur.position()
            cur.insertText(seg.text.strip() + " ")
            end = cur.position()
            self._ranges.append((start, end))
        self.full_text.setTextCursor(QTextCursor(self.full_text.document()))

        comp_idx = self.compare_combo.currentIndex() - 1
        comp = self.tracks[comp_idx] if 0 <= comp_idx < len(self.tracks) else None
        if comp:
            self._review = compare_tracks(track, comp)

        # Reclaim timeline width when comparison is not being used.
        self.timeline.setColumnHidden(4, comp is None)
        self.timeline.setColumnHidden(5, comp is None)
        hdr = self.timeline.horizontalHeader()
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        if comp:
            hdr.setSectionResizeMode(4, QHeaderView.Stretch)
            hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.timeline.setRowCount(len(track.segments))
        counts = {"green": 0, "yellow": 0, "red": 0}
        for r, seg in enumerate(track.segments):
            other = ""
            status = "—"
            level = ""
            if comp and r < len(self._review):
                rr = self._review[r]
                other = rr.other_text
                level = rr.level
                counts[level] += 1
                marker = "●"
                status = f"{marker} {rr.score * 100:.0f}%｜{rr.note}"
            vals = [fmt_time(seg.start)[:8], fmt_time(seg.end)[:8], seg.speaker, seg.text, other, status]
            for c, value in enumerate(vals):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, seg.start)
                if c == 5 and level:
                    colors = {"green": "#67d17a", "yellow": "#ffd54f", "red": "#ff6b6b"}
                    item.setForeground(QColor(colors[level]))
                    font = item.font(); font.setBold(True); item.setFont(font)
                self.timeline.setItem(r, c, item)
        if comp:
            self.review_summary.setText(f"核對：綠 {counts['green']}｜黃 {counts['yellow']}｜紅 {counts['red']}（紅＝差異）")
        else:
            self.review_summary.setText("未啟用比較")
        self._position_changed(self.player.position())

    def play_audio(self):
        if not self.audio_path:
            self.statusBar().showMessage("請先選擇錄音檔。", 5000)
            return
        self.player.play()

    def stop_audio(self):
        self.player.stop()
        self.player.setPosition(0)

    def seek_delta(self, ms):
        self.player.setPosition(max(0, min(self.player.duration(), self.player.position() + ms)))

    def _state_changed(self, state):
        self.play_btn.setEnabled(state != QMediaPlayer.PlayingState)
        self.pause_btn.setEnabled(state == QMediaPlayer.PlayingState)

    def _duration_changed(self, duration):
        self.slider.setRange(0, max(0, duration))
        self.align_tracks(auto_only=True)

    def _speed_changed(self, text):
        self.player.setPlaybackRate(float(text.rstrip("x")))

    def _player_error(self, *_):
        if self.player.error() != QMediaPlayer.NoError:
            self.statusBar().showMessage("播放器無法直接開啟此音訊格式；可先轉 WAV／MP3 再載入。", 10000)

    def _position_changed(self, ms):
        self.slider.blockSignals(True)
        self.slider.setValue(ms)
        self.slider.blockSignals(False)
        self.pos_label.setText(f"{fmt_time(ms / 1000)[:8]} / {fmt_time(self.player.duration() / 1000)[:8]}")
        if not self.tracks or self.active_combo.currentIndex() < 0:
            return
        track = self.tracks[self.active_combo.currentIndex()]
        now = ms / 1000.0
        starts = [seg.start for seg in track.segments]
        i = bisect.bisect_right(starts, now) - 1
        if i < 0 or i >= len(track.segments):
            return
        seg = track.segments[i]
        if seg.end > seg.start and now > seg.end and i + 1 < len(track.segments):
            return
        self._highlight(i, now)

    def _clear_timeline_current(self):
        row = self._timeline_current_row
        if 0 <= row < self.timeline.rowCount():
            for c in range(min(5, self.timeline.columnCount())):
                it = self.timeline.item(row, c)
                if it:
                    it.setBackground(QColor(Qt.transparent))
        self._timeline_current_row = -1

    def _mark_timeline_current(self, row: int):
        if self._timeline_current_row == row:
            return
        self._clear_timeline_current()
        if 0 <= row < self.timeline.rowCount():
            for c in range(min(5, self.timeline.columnCount())):
                it = self.timeline.item(row, c)
                if it:
                    it.setBackground(QColor("#1f5666"))
            self._timeline_current_row = row
            if self.timeline.item(row, 0):
                self.timeline.scrollToItem(self.timeline.item(row, 0), QAbstractItemView.PositionAtCenter)

    def _highlight(self, i, now):
        if i >= len(self._ranges):
            return
        start, end = self._ranges[i]
        seg = self.tracks[self.active_combo.currentIndex()].segments[i]
        if self._top_follow:
            progress = max(0.0, min(1.0, (now - seg.start) / max(0.08, seg.end - seg.start))) if seg.end > seg.start else 1.0
            mid = start + int((end - start) * progress)
            selections = []

            whole = QTextCursor(self.full_text.document())
            whole.setPosition(start)
            whole.setPosition(end, QTextCursor.KeepAnchor)
            s1 = self.full_text.ExtraSelection(); s1.cursor = whole
            f1 = QTextCharFormat(); f1.setBackground(QColor("#d7ebf8")); f1.setForeground(QColor("#202020")); s1.format = f1
            selections.append(s1)

            done = QTextCursor(self.full_text.document())
            done.setPosition(start); done.setPosition(mid, QTextCursor.KeepAnchor)
            s2 = self.full_text.ExtraSelection(); s2.cursor = done
            f2 = QTextCharFormat(); f2.setBackground(QColor("#ffd54f")); f2.setForeground(QColor("#111111")); s2.format = f2
            selections.append(s2)
            self.full_text.setExtraSelections(selections)
            if i != self._last_index:
                cursor = QTextCursor(self.full_text.document()); cursor.setPosition(start)
                self.full_text.setTextCursor(cursor); self.full_text.ensureCursorVisible()
        if self._timeline_follow:
            self._mark_timeline_current(i)
        if i != self._last_index:
            self._last_index = i

    def _timeline_seek(self, row, _col):
        item = self.timeline.item(row, 0)
        if item:
            self.player.setPosition(int(float(item.data(Qt.UserRole) or 0) * 1000))
            self.player.play()

    # ---------- Project / export ----------
    def save_project(self):
        p, _ = QFileDialog.getSaveFileName(self, "儲存 KTV 專案", "峻爸_KTV專案.jktv", "峻爸 KTV 專案 (*.jktv)")
        if p:
            save_project(p, self.audio_path, self.tracks, self.active_combo.currentIndex(), self.compare_combo.currentIndex() - 1)

    def open_project(self):
        p, _ = QFileDialog.getOpenFileName(self, "開啟 KTV 專案", "", "峻爸 KTV 專案 (*.jktv)")
        if not p:
            return
        try:
            audio, tracks, active, compare = load_project(p)
            self.audio_path = audio
            self.tracks = tracks
            self.audio_label.setText(audio or "尚未指定錄音檔")
            if audio and Path(audio).exists():
                self.player.setSource(QUrl.fromLocalFile(audio))
            self.refresh_tracks()
            if tracks:
                self.active_combo.setCurrentIndex(max(0, min(active, len(tracks) - 1)))
            self.compare_combo.setCurrentIndex(compare + 1 if 0 <= compare < len(tracks) else 0)
        except Exception as exc:
            QMessageBox.critical(self, "專案讀取失敗", str(exc))

    def export_track(self, kind):
        if not self.tracks or self.active_combo.currentIndex() < 0:
            return
        track = self.tracks[self.active_combo.currentIndex()]
        ext = kind.lower()
        p, _ = QFileDialog.getSaveFileName(self, "匯出文字軌", f"{track.name}.{ext}", f"{ext.upper()} (*.{ext})")
        if p:
            Path(p).write_text(to_srt(track) if ext == "srt" else to_vtt(track), encoding="utf-8")

    def export_html(self):
        if not self.audio_path or not self.tracks:
            self.statusBar().showMessage("請先選擇錄音檔並加入至少一個文字軌。", 6000)
            return
        out = QFileDialog.getExistingDirectory(self, "選擇 KTV 網頁包輸出資料夾")
        if not out:
            return
        try:
            p = export_html_package(out, self.audio_path, self.tracks)
            self.statusBar().showMessage(f"已建立離線核對網頁：{p}", 9000)
            if sys.platform.startswith("win"):
                os.startfile(str(p))
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except Exception as exc:
            QMessageBox.critical(self, "匯出失敗", str(exc))
